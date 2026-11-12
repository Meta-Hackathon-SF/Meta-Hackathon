"""Offline worker boundary checks; no provider or database is contacted."""

import asyncio
from unittest.mock import Mock

import pytest

from server.app.errors import ServiceError
from server.orchestration.worker import finalize_once


def test_no_pending_job_does_not_call_provider():
    repository = Mock()
    repository.claim_job.return_value = None

    async def unexpected(job):
        pytest.fail("Provider called without a durable job")

    assert asyncio.run(finalize_once(repository, worker_id="worker", finalizer=unexpected)) is None
    repository.complete_job.assert_not_called()


def test_provider_result_is_published_only_through_repository():
    repository = Mock()
    repository.claim_job.return_value = {"jobId": "job-1"}
    repository.complete_job.return_value = {"status": "scheduled"}

    async def provider(job):
        assert job == {"jobId": "job-1"}
        repository.complete_job.assert_not_called()
        return {"fixture": "validated-plan"}

    result = asyncio.run(finalize_once(repository, worker_id="worker", finalizer=provider))
    assert result == {"status": "scheduled"}
    repository.complete_job.assert_called_once_with(
        "job-1", worker_id="worker", plan={"fixture": "validated-plan"}
    )
    repository.fail_job.assert_not_called()


@pytest.mark.parametrize("failure", [ServiceError("STALE_REVISION"), RuntimeError("secret")])
def test_provider_failure_records_safe_code_and_never_publishes(failure):
    repository = Mock()
    repository.claim_job.return_value = {"jobId": "job-1"}

    async def provider(job):
        raise failure

    with pytest.raises(ServiceError) as caught:
        asyncio.run(finalize_once(repository, worker_id="worker", finalizer=provider))
    expected = "STALE_REVISION" if isinstance(failure, ServiceError) else "PROVIDER_UNAVAILABLE"
    assert caught.value.code == expected
    repository.fail_job.assert_called_once_with("job-1", worker_id="worker", code=expected)
    repository.complete_job.assert_not_called()
