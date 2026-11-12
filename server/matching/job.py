"""HTTP-agnostic job entrypoint for Group Quests matching.

``run_match_job`` parses raw input, runs ``MatchingService.match`` and maps the outcome to
an HTTP status plus a public JSON body. Bodies are built from allowlists only: error
messages come from fixed per-code templates, never from exception text, so no input value,
private intent field or traceback can reach a client. Retryable is explicit everywhere.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional, Protocol, Union

from server.matching.models import (
    MatchInput, MatchingError, Matched, NoMatch, ValidationError,
)
from server.matching.service import public_projection

HTTP_STATUS: Mapping[str, int] = {
    "INVALID_INPUT": 400,
    "UNAUTHENTICATED": 401,
    "FORBIDDEN": 403,
    "CONSENT_REQUIRED": 403,
    "NOT_FOUND": 404,
    "STALE_REVISION": 409,
    "CAPACITY_REACHED": 409,
    "IDEMPOTENCY_CONFLICT": 409,
    "RATE_LIMITED": 429,
    "PROVIDER_UNAVAILABLE": 503,
}

_ERROR_MESSAGES: Mapping[str, str] = {
    "INVALID_INPUT": "Invalid match input.",
    "UNAUTHENTICATED": "Authentication required.",
    "FORBIDDEN": "Not authorized for this match.",
    "CONSENT_REQUIRED": "Consent is required before matching.",
    "NOT_FOUND": "Not found.",
    "STALE_REVISION": "The match is out of date. Refresh and try again.",
    "CAPACITY_REACHED": "This community has reached its capacity.",
    "IDEMPOTENCY_CONFLICT": "Idempotency key was reused with a different request.",
    "RATE_LIMITED": "Too many requests. Try again later.",
    "PROVIDER_UNAVAILABLE": "Matching is temporarily unavailable. Please retry.",
}
_UNEXPECTED_CODE = "PROVIDER_UNAVAILABLE"


class MatchService(Protocol):
    async def match(self, raw_or_input: Union[MatchInput, Mapping[str, Any]]
                    ) -> Union[Matched, NoMatch]: ...


@dataclass(frozen=True)
class JobOutcome:
    """``result`` is internal (for persistence only); ``body`` is the public response."""
    http_status: int
    body: dict
    result: Optional[Union[Matched, NoMatch]]


def _error_body(code: str, retryable: bool, request_id: str) -> dict:
    return {"error": {"code": code, "message": _ERROR_MESSAGES[code],
                      "requestId": request_id, "retryable": retryable}}


def _error_outcome(code: str, retryable: bool, request_id: str) -> JobOutcome:
    return JobOutcome(HTTP_STATUS[code], _error_body(code, retryable, request_id), None)


def _unexpected_outcome(request_id: str) -> JobOutcome:
    return _error_outcome(_UNEXPECTED_CODE, True, request_id)


def _matching_error_outcome(exc: MatchingError, request_id: str) -> JobOutcome:
    if exc.code not in HTTP_STATUS:
        return _unexpected_outcome(request_id)
    return _error_outcome(exc.code, bool(exc.retryable), request_id)


async def run_match_job(service: MatchService, raw_input: Mapping[str, Any], *,
                        request_id: str) -> JobOutcome:
    """Run one matching job and return its HTTP status, public body and internal result."""
    try:
        inp = MatchInput.from_dict(raw_input)
    except ValidationError:
        return _error_outcome("INVALID_INPUT", False, request_id)
    except Exception:  # noqa: BLE001 - nothing from the parser may leak to the client
        return _unexpected_outcome(request_id)

    try:
        result = await service.match(inp)
        profiles = {c.participant_id: c.public_profile for c in inp.candidates}
        body = public_projection(result, profiles)
    except MatchingError as exc:
        return _matching_error_outcome(exc, request_id)
    except Exception:  # noqa: BLE001 - unexpected failures become a generic retryable 503
        return _unexpected_outcome(request_id)

    return JobOutcome(200, body, result)
