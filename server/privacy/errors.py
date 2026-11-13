"""ApiError mapping for privacy failures (contracts/API.md, 2.0.0)."""

from __future__ import annotations

from .wire import ErrorCode

STATUS: dict[str, int] = {
    "INVALID_INPUT": 400,
    "UNAUTHENTICATED": 401,
    "FORBIDDEN": 403,
    "CONSENT_REQUIRED": 403,
    "NOT_FOUND": 404,
    "STALE_REVISION": 409,
    "IDEMPOTENCY_CONFLICT": 409,
    "CYCLE_LOCKED": 409,
    "ROOM_EXPIRED": 410,
    "MESSAGE_REJECTED": 422,
    "RATE_LIMITED": 429,
    "PROVIDER_UNAVAILABLE": 503,
}

_RETRYABLE = {"RATE_LIMITED", "PROVIDER_UNAVAILABLE"}


class PrivacyError(Exception):
    """Raised by the privacy service. Messages are generic and never echo
    private values or reveal whether another player exists."""

    def __init__(self, code: ErrorCode, message: str, *, retryable: bool | None = None):
        super().__init__(message)
        self.code: ErrorCode = code
        self.message = message
        self.status = STATUS[code]
        self.retryable = code in _RETRYABLE if retryable is None else retryable


def unauthenticated() -> PrivacyError:
    return PrivacyError("UNAUTHENTICATED", "Join Facebook Space to continue.")


def consent_required() -> PrivacyError:
    return PrivacyError("CONSENT_REQUIRED", "All three consents (match me, anonymous chat, 18+) are required to play.")


def forbidden() -> PrivacyError:
    return PrivacyError("FORBIDDEN", "Not allowed.")


def not_found() -> PrivacyError:
    return PrivacyError("NOT_FOUND", "Not found.")


def stale() -> PrivacyError:
    return PrivacyError("STALE_REVISION", "This was changed elsewhere. Reload and try again.")


def cycle_locked() -> PrivacyError:
    return PrivacyError("CYCLE_LOCKED", "This week is locked. Answers can't change after Saturday's lock.")


def invalid_input(reason: str = "Invalid input.") -> PrivacyError:
    # ``reason`` must be a fixed server string, never user-supplied text.
    return PrivacyError("INVALID_INPUT", reason)


def provider_unavailable() -> PrivacyError:
    return PrivacyError("PROVIDER_UNAVAILABLE", "Safety check is unavailable right now. Try again in a moment.")
