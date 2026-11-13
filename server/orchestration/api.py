"""Kai's formation/Sky/operator/job routes and authorized SSE delivery."""

import asyncio
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from starlette.responses import StreamingResponse

from server.app.errors import ServiceError
from server.orchestration.stream import encode_sse, parse_last_event_id
from server.orchestration.wire import Wire
from server.privacy import session_token


def require_configured(value):
    if value is None:
        raise ServiceError("PROVIDER_UNAVAILABLE")
    return value


class EmptyCommand(Wire):
    pass


async def event_stream(runtime, chat, privacy, token, request, after):
    while not await request.is_disconnected():
        try:
            actor = privacy.require_session(token)
            privacy.require_consent(actor)
            runtime.drain_notices()
            public = runtime.public_events(actor, after)
            private = chat.events(actor, after, token=token)
            events = {e["seq"]: e for e in [*public, *private]}
            for seq in sorted(events):
                # Recheck immediately before each queued delivery, including replay.
                actor = privacy.require_session(token)
                privacy.require_consent(actor)
                runtime.drain_notices()
                candidates = runtime.public_events(actor, seq - 1) + chat.events(
                    actor, seq - 1, token=token
                )
                current = next((e for e in candidates if e["seq"] == seq), None)
                after = seq
                if current is not None:
                    yield encode_sse(current)
            if not events:
                yield ": keepalive\n\n"
            await asyncio.sleep(0.5)
        except asyncio.CancelledError:
            raise
        except Exception:
            # Session revocation/outage closes the stream; never echo private errors
            # or send a second HTTP envelope after response headers have started.
            return


def build_router(runtime, chat, privacy, session_dependency):
    router = APIRouter()
    Session = Annotated[object, Depends(session_dependency)]

    @router.post("/operator/cycles/{cycleId}/form", status_code=202)
    async def form(cycleId: str, request: Request, tasks: BackgroundTasks, actor: Session):
        raw = await request.body()
        if len(raw) > 4096:
            raise ServiceError("INVALID_INPUT")
        if raw.strip():
            try:
                EmptyCommand.model_validate_json(raw)
            except Exception:
                raise ServiceError("INVALID_INPUT") from None
        keys = request.headers.getlist("Idempotency-Key")
        if len(keys) != 1:
            raise ServiceError("INVALID_INPUT")
        result = runtime.enqueue(actor, cycleId, keys[0])
        tasks.add_task(runtime.run_job, result["jobId"])
        return result

    @router.get("/jobs/{jobId}")
    def job(jobId: str, request: Request, actor: Session):
        return runtime.job(actor, jobId, request.state.request_id)

    @router.get("/cycles/{cycleId}/sky")
    def sky(cycleId: str, actor: Session):
        return runtime.sky(actor, cycleId)

    @router.get("/stream")
    def stream(request: Request, actor: Session):
        privacy.require_consent(actor)
        headers = request.headers.getlist("Last-Event-ID")
        if len(headers) > 1:
            raise ServiceError("INVALID_INPUT")
        after = parse_last_event_id(headers[0] if headers else None)
        return StreamingResponse(
            event_stream(runtime, chat, privacy, session_token(request), request, after),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
        )

    return router
