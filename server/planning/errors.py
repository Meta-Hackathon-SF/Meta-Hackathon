"""Planning errors carrying shared ErrorCode values (contracts/protocol.ts)."""
from __future__ import annotations

from server.providers.errors import ProviderError


class PlanningError(Exception):
    def __init__(self, code: str, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable

    @classmethod
    def from_provider(cls, exc: ProviderError) -> "PlanningError":
        return cls(exc.api_code, exc.message, retryable=exc.retryable)

    def to_api_error(self, request_id: str) -> dict:
        return {"error": {"code": self.code, "message": self.message, "requestId": request_id, "retryable": self.retryable}}
