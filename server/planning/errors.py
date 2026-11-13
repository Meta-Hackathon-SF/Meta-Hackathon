"""Planning errors that map onto the shared ApiError envelope (contracts/protocol.ts)."""
from __future__ import annotations


class PlanningError(Exception):
    """Safe to surface: messages never contain player text or model output."""

    def __init__(self, code: str, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.code = code  # ErrorCode literal, e.g. INVALID_INPUT, NOT_FOUND, PROVIDER_UNAVAILABLE
        self.message = message
        self.retryable = retryable


class BankError(ValueError):
    """The question bank or venue file failed validation. Names the row, never player data."""
