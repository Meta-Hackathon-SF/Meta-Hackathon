"""Chat HTTP surface. The composition root supplies a verified session dependency."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Request, Response
from pydantic import Field

from server.app.errors import ServiceError
from server.orchestration.stream import parse_last_event_id
from server.orchestration.wire import Text, Wire
from server.privacy import session_token


class SendRequest(Wire):
    text: Annotated[str, Field(min_length=1, max_length=500)]


class ReportRequest(Wire):
    messageId: Text | None = None
    handle: Text
    reason: Literal["harassment", "self_harm", "spam", "personal_info", "other"]


class RevealRequest(Wire):
    toHandle: Text


def _key(request: Request):
    keys = request.headers.getlist("Idempotency-Key")
    if len(keys) != 1:
        raise ServiceError("INVALID_INPUT")
    return keys[0]


def build_router(service, session_dependency):
    """Paths omit /api/v1; Kai's registry mounts and guards this router."""
    router = APIRouter()
    Session = Annotated[object, Depends(session_dependency)]

    @router.get("/cycles/{cycleId}/room")
    def room(cycleId: str, request: Request, actor: Session):
        return service.room(actor, cycleId, token=session_token(request))

    @router.get("/rooms/{roomId}/messages")
    def messages(roomId: str, request: Request, actor: Session, after: str | None = None):
        return service.messages(
            actor, roomId, parse_last_event_id(after), token=session_token(request)
        )

    @router.post("/rooms/{roomId}/messages")
    async def send(roomId: str, body: SendRequest, request: Request, actor: Session):
        return await service.send(
            actor, roomId, body.text, _key(request), token=session_token(request)
        )

    @router.post("/rooms/{roomId}/reports", status_code=204, response_class=Response)
    def report(roomId: str, body: ReportRequest, request: Request, actor: Session):
        service.report(
            actor,
            roomId,
            body.handle,
            body.messageId,
            body.reason,
            _key(request),
            token=session_token(request),
        )
        return Response(status_code=204)

    @router.post("/rooms/{roomId}/reveal")
    def reveal(roomId: str, body: RevealRequest, request: Request, actor: Session):
        return service.reveal(
            actor, roomId, body.toHandle, _key(request), token=session_token(request)
        )

    return router
