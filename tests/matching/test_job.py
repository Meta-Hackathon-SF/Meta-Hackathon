"""Tests for the HTTP-agnostic matching job entrypoint, using synthetic fixtures only."""
import asyncio
import json

import pytest

from server.matching.job import HTTP_STATUS, JobOutcome, run_match_job
from server.matching.models import Matched, MatchingError, NoMatch
from server.matching.service import MatchingService
from tests.matching.fixtures import DEMO_POOL, FakeMusePort, make_match_input

REQ = "p_ava"
REQUEST_ID = "req_job_test"
ALL_ERROR_CODES = (
    "INVALID_INPUT", "UNAUTHENTICATED", "FORBIDDEN", "NOT_FOUND",
    "CONSENT_REQUIRED", "STALE_REVISION", "CAPACITY_REACHED",
    "PROVIDER_UNAVAILABLE", "RATE_LIMITED", "IDEMPOTENCY_CONFLICT",
)
PRIVATE_KEYS = ("memberVersions", "feasibleWindows", "maxBudgetMinor")


def run(coro):
    return asyncio.run(coro)


def service(responses=None):
    return MatchingService(FakeMusePort(responses), id_factory=lambda: "prop_fixed")


class AlwaysRaisingPort:
    """Muse port double whose every call fails with a provider error."""

    def __init__(self, exc: BaseException) -> None:
        self._exc = exc
        self.calls = 0

    async def generate(self, *, task, requestId, promptVersion, payload, signal=None):
        self.calls += 1
        raise self._exc


class RaisingService:
    """Service double that raises a fixed exception from ``match``."""

    def __init__(self, exc: BaseException) -> None:
        self._exc = exc

    async def match(self, raw_or_input):
        raise self._exc


def demo_input(requester=REQ, request_id=REQUEST_ID):
    return make_match_input(DEMO_POOL, requester, request_id=request_id)


def _all_keys(node):
    """Yield every dict key in a nested JSON-like structure."""
    if isinstance(node, dict):
        for key, value in node.items():
            yield key
            yield from _all_keys(value)
    elif isinstance(node, list):
        for item in node:
            yield from _all_keys(item)


def test_http_status_covers_every_error_code():
    assert set(HTTP_STATUS) == set(ALL_ERROR_CODES)


@pytest.mark.parametrize("code, status", [
    ("INVALID_INPUT", 400), ("UNAUTHENTICATED", 401), ("FORBIDDEN", 403),
    ("CONSENT_REQUIRED", 403), ("NOT_FOUND", 404), ("STALE_REVISION", 409),
    ("CAPACITY_REACHED", 409), ("IDEMPOTENCY_CONFLICT", 409), ("RATE_LIMITED", 429),
    ("PROVIDER_UNAVAILABLE", 503),
])
def test_http_status_matches_api_contract(code, status):
    assert HTTP_STATUS[code] == status


def test_job_outcome_is_frozen():
    outcome = JobOutcome(200, {}, None)
    with pytest.raises(Exception):
        outcome.http_status = 500  # type: ignore[misc]


def test_success_returns_200_with_public_body_and_internal_result():
    outcome = run(run_match_job(service(), demo_input(), request_id=REQUEST_ID))
    assert outcome.http_status == 200
    assert isinstance(outcome.result, Matched)
    assert outcome.body["status"] == "matched"
    assert outcome.body["proposal"]["proposalId"] == "prop_fixed"


def test_success_body_excludes_private_fields():
    outcome = run(run_match_job(service(), demo_input(), request_id=REQUEST_ID))
    keys = set(_all_keys(outcome.body))
    for private in PRIVATE_KEYS:
        assert private not in keys
    serialized = json.dumps(outcome.body)
    for private in PRIVATE_KEYS:
        assert private not in serialized


def test_success_body_keeps_synthetic_flag_on_members():
    outcome = run(run_match_job(service(), demo_input(), request_id=REQUEST_ID))
    members = outcome.body["proposal"]["members"]
    assert members
    assert all(member["isSynthetic"] is True for member in members)


def test_no_match_returns_200_with_no_match_body():
    too_small = make_match_input(DEMO_POOL[:2], REQ, request_id=REQUEST_ID)
    outcome = run(run_match_job(service(), too_small, request_id=REQUEST_ID))
    assert outcome.http_status == 200
    assert isinstance(outcome.result, NoMatch)
    assert outcome.body["status"] == "no_match"


@pytest.mark.parametrize("raw", [
    {},
    {"context": "not-an-object"},
    "not a mapping at all",
    None,
])
def test_malformed_input_returns_400_not_retryable(raw):
    outcome = run(run_match_job(service(), raw, request_id=REQUEST_ID))
    assert outcome.http_status == 400
    assert outcome.result is None
    assert outcome.body["error"]["code"] == "INVALID_INPUT"
    assert outcome.body["error"]["retryable"] is False


def test_malformed_input_with_secret_value_does_not_echo_value():
    raw = demo_input()
    raw["communityId"] = {"secret": "sk-do-not-echo"}
    outcome = run(run_match_job(service(), raw, request_id=REQUEST_ID))
    assert outcome.http_status == 400
    assert "sk-do-not-echo" not in json.dumps(outcome.body)


def test_missing_requester_returns_403_not_retryable():
    outcome = run(run_match_job(service(), demo_input(requester="p_nobody"),
                                request_id=REQUEST_ID))
    assert outcome.http_status == 403
    assert outcome.result is None
    assert outcome.body["error"]["code"] == "FORBIDDEN"
    assert outcome.body["error"]["retryable"] is False


def test_provider_always_failing_returns_503_retryable():
    port = AlwaysRaisingPort(RuntimeError("upstream timeout"))
    svc = MatchingService(port, id_factory=lambda: "prop_fixed")
    outcome = run(run_match_job(svc, demo_input(), request_id=REQUEST_ID))
    assert port.calls >= 1
    assert outcome.http_status == 503
    assert outcome.result is None
    assert outcome.body["error"]["code"] == "PROVIDER_UNAVAILABLE"
    assert outcome.body["error"]["retryable"] is True


def test_provider_failure_body_has_no_provider_detail():
    port = AlwaysRaisingPort(RuntimeError("upstream timeout sk-leak"))
    svc = MatchingService(port, id_factory=lambda: "prop_fixed")
    outcome = run(run_match_job(svc, demo_input(), request_id=REQUEST_ID))
    serialized = json.dumps(outcome.body)
    assert "sk-leak" not in serialized
    assert "upstream timeout" not in serialized


def test_request_id_is_echoed_on_success_path_errors():
    outcome = run(run_match_job(service(), demo_input(requester="p_nobody"),
                                request_id="req_echo_403"))
    assert outcome.body["error"]["requestId"] == "req_echo_403"


def test_request_id_is_echoed_on_provider_failure():
    svc = MatchingService(AlwaysRaisingPort(RuntimeError("x")),
                          id_factory=lambda: "prop_fixed")
    outcome = run(run_match_job(svc, demo_input(), request_id="req_echo_503"))
    assert outcome.body["error"]["requestId"] == "req_echo_503"


def test_request_id_is_echoed_on_malformed_input():
    outcome = run(run_match_job(service(), {}, request_id="req_echo_400"))
    assert outcome.body["error"]["requestId"] == "req_echo_400"


def test_unexpected_runtime_error_returns_generic_503_without_detail():
    svc = RaisingService(RuntimeError("secret detail"))
    outcome = run(run_match_job(svc, demo_input(), request_id=REQUEST_ID))
    assert outcome.http_status == 503
    assert outcome.result is None
    assert outcome.body["error"]["code"] == "PROVIDER_UNAVAILABLE"
    assert outcome.body["error"]["retryable"] is True
    assert outcome.body["error"]["requestId"] == REQUEST_ID
    assert "secret detail" not in json.dumps(outcome.body)
    assert "Traceback" not in json.dumps(outcome.body)


def test_unknown_matching_error_code_maps_to_generic_503():
    svc = RaisingService(MatchingError("BOGUS_CODE", "internal detail", retryable=False))
    outcome = run(run_match_job(svc, demo_input(), request_id=REQUEST_ID))
    assert outcome.http_status == 503
    assert outcome.body["error"]["code"] == "PROVIDER_UNAVAILABLE"
    assert outcome.body["error"]["retryable"] is True
    assert "internal detail" not in json.dumps(outcome.body)


@pytest.mark.parametrize("code", ["RATE_LIMITED", "CONSENT_REQUIRED"])
def test_matching_error_code_is_passed_through_with_its_status(code):
    svc = RaisingService(MatchingError(code, "detail that must not leak", retryable=True))
    outcome = run(run_match_job(svc, demo_input(), request_id=REQUEST_ID))
    assert outcome.http_status == HTTP_STATUS[code]
    assert outcome.body["error"]["code"] == code
    assert outcome.body["error"]["retryable"] is True
    assert "detail that must not leak" not in json.dumps(outcome.body)


def test_job_does_not_mutate_raw_input():
    raw = demo_input()
    snapshot = json.dumps(raw, sort_keys=True)
    run(run_match_job(service(), raw, request_id=REQUEST_ID))
    assert json.dumps(raw, sort_keys=True) == snapshot
