"""One bounded workflow-worker iteration; the planner/validator must be injected."""

import asyncio
from collections.abc import Awaitable, Callable

from server.app.errors import ServiceError

from .repository import WorkflowRepository

Finalizer = Callable[[dict], Awaitable[dict]]


async def finalize_once(
    repository: WorkflowRepository,
    *,
    worker_id: str,
    finalizer: Finalizer,
    lease_seconds: int = 30,
) -> dict | None:
    """Model/validation runs outside the repository's database transaction.

    Tests may inject a labeled fixture finalizer. Production must supply the
    real planner + current authorized candidates/catalog; there is no fallback.
    """
    job = await asyncio.to_thread(
        repository.claim_job, worker_id=worker_id, lease_seconds=lease_seconds
    )
    if job is None:
        return None
    job_id = job["jobId"]
    try:
        final_plan = await asyncio.wait_for(finalizer(job), timeout=lease_seconds * 0.8)
        return await asyncio.to_thread(
            repository.complete_job, job_id, worker_id=worker_id, plan=final_plan
        )
    except ServiceError as error:
        await asyncio.to_thread(repository.fail_job, job_id, worker_id=worker_id, code=error.code)
        raise
    except Exception:
        await asyncio.to_thread(
            repository.fail_job, job_id, worker_id=worker_id, code="PROVIDER_UNAVAILABLE"
        )
        raise ServiceError("PROVIDER_UNAVAILABLE") from None
