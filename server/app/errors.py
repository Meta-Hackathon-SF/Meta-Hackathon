"""Runtime implementation of contracts/protocol.ts ApiError; never echo private input."""

from typing import Literal

from fastapi import Request
from pydantic import BaseModel, ConfigDict
from starlette.responses import JSONResponse

ErrorCode = Literal[
    "INVALID_INPUT",
    "UNAUTHENTICATED",
    "FORBIDDEN",
    "NOT_FOUND",
    "CONSENT_REQUIRED",
    "STALE_REVISION",
    "CYCLE_LOCKED",
    "ROOM_EXPIRED",
    "MESSAGE_REJECTED",
    "PROVIDER_UNAVAILABLE",
    "RATE_LIMITED",
    "IDEMPOTENCY_CONFLICT",
]

ERRORS: dict[ErrorCode, tuple[int, str, bool]] = {
    "INVALID_INPUT": (400, "Request does not match the API requirements.", False),
    "UNAUTHENTICATED": (401, "A verified session is required.", False),
    "FORBIDDEN": (403, "This action is not permitted.", False),
    "NOT_FOUND": (404, "Resource not found.", False),
    "CONSENT_REQUIRED": (403, "Current consent is required.", False),
    "STALE_REVISION": (409, "This revision is out of date. Refresh before retrying.", False),
    "CYCLE_LOCKED": (409, "This weekly cycle is locked.", False),
    "ROOM_EXPIRED": (410, "This room has expired.", False),
    "MESSAGE_REJECTED": (422, "This message cannot be shared.", False),
    "PROVIDER_UNAVAILABLE": (503, "The requested service is not available. Try again later.", True),
    "RATE_LIMITED": (429, "Too many requests. Try again later.", True),
    "IDEMPOTENCY_CONFLICT": (409, "This idempotency key was used for a different request.", False),
}


SUPPORT_CARD_MESSAGE = "This message was held. A private support card is available."
MessageKey = Literal["support_card"]


def _message(code: ErrorCode, message_key: MessageKey | None) -> str:
    if message_key is not None:
        if message_key != "support_card" or code != "MESSAGE_REJECTED":
            raise ValueError("Unknown safe API message key")
        return SUPPORT_CARD_MESSAGE
    return ERRORS[code][1]


class ErrorDetails(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    code: ErrorCode
    message: str
    requestId: str
    retryable: bool


class ApiError(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    error: ErrorDetails


class ServiceError(Exception):
    """Owners raise a stable error code, never a public free-form private message."""

    def __init__(self, code: ErrorCode, *, message_key: MessageKey | None = None):
        if code not in ERRORS:
            raise ValueError("Unknown API error code")
        _message(code, message_key)
        self.code = code
        self.message_key = message_key
        super().__init__(code)


def error_response(
    request: Request, code: ErrorCode, *, message_key: MessageKey | None = None
) -> JSONResponse:
    status, _default_message, retryable = ERRORS[code]
    message = _message(code, message_key)
    body = ApiError(
        error=ErrorDetails(
            code=code,
            message=message,
            requestId=request.state.request_id,
            retryable=retryable,
        )
    )
    return JSONResponse(body.model_dump(), status_code=status)
