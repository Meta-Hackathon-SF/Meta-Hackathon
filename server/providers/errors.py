"""Sanitized provider errors.

Messages never include prompts, payloads, provider response bodies or keys.
Callers map ``api_code`` onto the shared ApiError envelope (contracts/protocol.ts).
"""
from __future__ import annotations

from typing import Literal

ProviderErrorKind = Literal[
    "not_configured",   # no key/model configured on this server
    "unknown_task",     # task/promptVersion not in the allowlisted registry
    "invalid_request",  # payload too large / not serializable / provider 400/404/413
    "auth",             # provider 401/402/403 (credentials, billing, permission)
    "rate_limited",     # provider 429
    "unavailable",      # provider 5xx / network failure
    "timeout",          # attempt or overall deadline exceeded
    "malformed_output", # non-JSON or schema-invalid model output after retries
]

_RETRYABLE: dict[str, bool] = {
    "not_configured": False,
    "unknown_task": False,
    "invalid_request": False,
    "auth": False,
    "rate_limited": True,
    "unavailable": True,
    "timeout": True,
    "malformed_output": True,
}


class ProviderError(Exception):
    """A provider failure that is safe to surface to logs and API errors."""

    def __init__(
        self,
        kind: ProviderErrorKind,
        message: str,
        *,
        status: int | None = None,
        retry_after_s: float | None = None,
        attempts: int = 1,
    ) -> None:
        super().__init__(message)
        self.kind: ProviderErrorKind = kind
        self.message = message
        self.status = status
        self.retry_after_s = retry_after_s
        self.attempts = attempts

    @property
    def retryable(self) -> bool:
        return _RETRYABLE[self.kind]

    @property
    def api_code(self) -> str:
        """Shared ErrorCode for the HTTP layer."""
        if self.kind == "rate_limited":
            return "RATE_LIMITED"
        if self.kind == "unknown_task":
            return "INVALID_INPUT"
        return "PROVIDER_UNAVAILABLE"

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"ProviderError(kind={self.kind!r}, status={self.status!r}, attempts={self.attempts})"
