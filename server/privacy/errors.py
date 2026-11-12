"""ApiError mapping for privacy failures (contracts/API.md)."""

from __future__ import annotations

from .wire import ErrorCode

_STATUS: dict[str, int] = {
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

_RETRYABLE = {"RATE_LIMITED", "PROVIDER_UNAVAILABLE"}


class PrivacyError(Exception):
    """Raised by the privacy service. Messages are generic and never echo
    private values or reveal whether another participant exists."""

    def __init__(self, code: ErrorCode, message: str, *, retryable: bool | None = None):
        super().__init__(message)
        self.code: ErrorCode = code
        self.message = message
        self.status = _STATUS[code]
        self.retryable = code in _RETRYABLE if retryable is None else retryable


def unauthenticated() -> PrivacyError:
    return PrivacyError("UNAUTHENTICATED", "Sign in to continue.")


def consent_required() -> PrivacyError:
    return PrivacyError("CONSENT_REQUIRED", "Matching and model-processing consent are required.")


def not_found() -> PrivacyError:
    return PrivacyError("NOT_FOUND", "Not found.")


def stale() -> PrivacyError:
    return PrivacyError("STALE_REVISION", "This was changed elsewhere. Reload and try again.")
