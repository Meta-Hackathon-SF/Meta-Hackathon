"""HTTP routes for "Weekly cycle and daily answers" and the cycle operator
controls in contracts/API.md (owner: Will). Kai mounts this router under
/api/v1 through the app registry.

    router = build_router(service, session_dependency, transcriber=...)

``session_dependency`` is a FastAPI dependency backed by Patrik's verified
session. It may return this package's ``Session`` or Patrik's ``Actor``
(``player_id``, ``community_id``, ``is_operator``); both are accepted without
importing his module. ``require_consent(actor)`` (Patrik's
``PrivacyService.require_consent``) runs before every answer or guess write.
Identity is never read from the request body, path or query. Bodies are
validated here (400 INVALID_INPUT, ApiError envelope).

Routes not yet in contracts/API.md (proposed, additive; see handoff):
GET /cycles/{id}/answers (own answers only) and POST /voice/transcribe.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from typing import Any, TypeVar

from fastapi import APIRouter, Depends, FastAPI, Request, WebSocket
from pydantic import BaseModel, ValidationError
from starlette.concurrency import run_in_threadpool
from starlette.responses import JSONResponse, Response

from server.voice import MAX_AUDIO_BYTES, Transcriber, UnconfiguredTranscriber, VoiceError, transcribe_audio
from server.voice.live import default_connect, origin_allowed
from server.voice.live import relay as live_relay
from server.voice.muse_stt import MuseSttConfig

from .muse_chat import MuseChat, MuseChatError
from .ports import Session
from .service import ERRORS, CycleError, CycleService
from .wire import (
    AdvanceRequest,
    EditAnswerRequest,
    GuessRequest,
    NewCycleRequest,
    SubmitAnswerRequest,
)

T = TypeVar("T", bound=BaseModel)
MAX_BODY_BYTES = 16 * 1024


def _request_id(request: Request) -> str:
    supplied = request.headers.get("X-Request-Id", "")
    if supplied and len(supplied) <= 128 and supplied.isprintable() and " " not in supplied:
        return supplied
    return f"req-{uuid.uuid4().hex}"


def _error(request: Request, code: str) -> JSONResponse:
    request_id = _request_id(request)
    return JSONResponse(
        CycleError(code).to_api_error(request_id),
        status_code=ERRORS[code][0],
        headers={"X-Request-Id": request_id},
    )


def install_cycle_error_handler(app: FastAPI) -> None:
    @app.exception_handler(CycleError)
    async def _handle(request: Request, exc: CycleError) -> JSONResponse:  # noqa: RUF029
        return _error(request, exc.code)


async def _body(request: Request, model: type[T], *, optional: bool = False) -> T:
    raw = await request.body()
    if len(raw) > MAX_BODY_BYTES:
        raise CycleError("INVALID_INPUT")
    if not raw.strip() and optional:
        raw = b"{}"
    try:
        return model.model_validate_json(raw)
    except ValidationError:
        raise CycleError("INVALID_INPUT") from None  # never echo the input


def _day(day: str) -> int:
    if day not in {"1", "2", "3", "4", "5"}:
        raise CycleError("INVALID_INPUT")
    return int(day)


def _json(model: BaseModel | list[Any] | dict, status: int = 200) -> JSONResponse:
    if isinstance(model, BaseModel):
        content: Any = model.model_dump(mode="json")
    elif isinstance(model, list):
        content = [m.model_dump(mode="json") for m in model]
    else:
        content = model
    return JSONResponse(content, status_code=status)


def _as_session(actor: Any) -> Session:
    """Accept this package's Session or Patrik's Actor. Anything else is no session."""
    if isinstance(actor, Session):
        return actor
    player = getattr(actor, "player_id", None)
    community = getattr(actor, "community_id", None)
    operator = getattr(actor, "is_operator", None)
    if not (isinstance(player, str) and player and isinstance(community, str) and community):
        raise CycleError("UNAUTHENTICATED")
    return Session(playerId=player, communityId=community, isOperator=operator is True)


def build_router(
    service: CycleService,
    session_dependency: Callable[..., Any],
    *,
    transcriber: Transcriber | None = None,
    require_consent: Callable[[Any], Any] | None = None,
    live_stt: MuseSttConfig | None = None,
    live_origins: tuple[str, ...] = (),
    live_connect: Callable[[str], Any] | None = None,
    muse_chat: MuseChat | None = None,
) -> APIRouter:
    router = APIRouter()
    # Configures itself from MUSE_API_KEY on the API host when not injected (503 without a key).
    group_muse = muse_chat or MuseChat.from_env()
    stt: Transcriber = transcriber or UnconfiguredTranscriber()
    actor_dependency = session_dependency

    def session_dependency(actor: Any = Depends(actor_dependency)) -> Session:  # noqa: F811
        return _as_session(actor)

    def consenting(actor: Any = Depends(actor_dependency)) -> Session:
        """Writes need current consent; Patrik's check raises CONSENT_REQUIRED."""
        if require_consent is not None:
            require_consent(actor)
        return _as_session(actor)

    # Demo controls (Will's call for the hackathon demo): any signed-in member may
    # start a demo-timing week and run it (advance, synthetic top-up, reset), so
    # every account can walk through the game. Real-calendar weeks stay operator-only.
    def demo_runner(session: Session = Depends(session_dependency)) -> Session:
        return session

    def require_demo_or_operator(session: Session, cycle_id: str) -> None:
        if session.isOperator is not True and not service.is_demo_cycle(cycle_id):
            raise CycleError("FORBIDDEN")

    call = run_in_threadpool

    # ---- players -----------------------------------------------------------
    @router.get("/cycles/current")
    async def current(session: Session = Depends(session_dependency)):
        return _json(await call(service.current_view, session))

    @router.get("/cycles/{cycle_id}/questions")
    async def questions(cycle_id: str, session: Session = Depends(session_dependency)):
        return _json(await call(service.released_questions, session, cycle_id))

    @router.get("/cycles/{cycle_id}/answers")
    async def my_answers(cycle_id: str, session: Session = Depends(session_dependency)):
        return _json(await call(service.my_answers, session, cycle_id))

    @router.post("/cycles/{cycle_id}/answers")
    async def submit(cycle_id: str, request: Request, session: Session = Depends(consenting)):
        body = await _body(request, SubmitAnswerRequest)
        return _json(await call(service.submit_answer, session, cycle_id, body), 202)

    @router.patch("/cycles/{cycle_id}/answers/{day}")
    async def edit(cycle_id: str, day: str, request: Request, session: Session = Depends(consenting)):
        body = await _body(request, EditAnswerRequest)
        return _json(await call(service.edit_answer, session, cycle_id, _day(day), body))

    @router.delete("/cycles/{cycle_id}/answers/{day}")
    async def delete(cycle_id: str, day: str, session: Session = Depends(session_dependency)):
        await call(service.delete_answer, session, cycle_id, _day(day))
        return Response(status_code=204)

    @router.get("/cycles/{cycle_id}/answers/{day}/followup")
    async def followup(cycle_id: str, day: str, session: Session = Depends(consenting)):
        return _json(await call(service.followup, session, cycle_id, _day(day)))

    @router.put("/cycles/{cycle_id}/guess")
    async def guess(cycle_id: str, request: Request, session: Session = Depends(consenting)):
        body = await _body(request, GuessRequest)
        return _json(await call(service.put_guess, session, cycle_id, body))

    @router.post("/muse-chat")
    async def muse_chat_line(request: Request, session: Session = Depends(session_dependency)):
        """Sunday Messenger group: one checked Muse suggestion (server/cycle/muse_chat.py)."""
        raw = await request.body()
        if len(raw) > MAX_BODY_BYTES:
            raise CycleError("INVALID_INPUT")
        try:
            body = json.loads(raw or b"{}")
        except ValueError:
            raise CycleError("INVALID_INPUT") from None  # never echo the input
        try:
            return _json(await call(group_muse.reply, body, session.playerId))
        except MuseChatError as error:
            raise CycleError(error.code) from None

    @router.post("/voice/transcribe")
    async def transcribe(request: Request, session: Session = Depends(session_dependency)):
        """Raw audio body with its Content-Type. Audio is never stored or logged."""
        request_id = _request_id(request)
        try:
            declared = int(request.headers.get("content-length", "0") or 0)
        except ValueError:
            declared = 0
        if declared > MAX_AUDIO_BYTES:
            data: bytes | None = b"\x00" * (MAX_AUDIO_BYTES + 1)  # rejected by validation, body unread
        else:
            data = await request.body()
        try:
            result = await call(
                lambda: transcribe_audio(
                    request.headers.get("content-type"), data, stt, request_id=request_id
                )
            )
        except VoiceError as exc:
            status = {"INVALID_INPUT": 400, "PROVIDER_UNAVAILABLE": 503, "RATE_LIMITED": 429}[exc.code]
            return JSONResponse(
                exc.to_api_error(request_id), status_code=status, headers={"X-Request-Id": request_id}
            )
        # mode "fixture" -> the UI must label the transcript as a fixture
        return _json({**result, "mode": stt.mode})

    # Mounted only when configured: without a key there is no live route, and the
    # browser falls back to POST /voice/transcribe. Composition must also accept
    # WebSocket routes (Kai's registry is HTTP-only today; see D013).
    if live_stt is not None:
        @router.websocket("/voice/live")
        async def live(websocket: WebSocket):
            """PROPOSED (D013): live speech-to-text while the player talks. One
            push-to-talk turn per connection; see server/voice/live.py."""
            if not origin_allowed(websocket.headers, live_origins):
                await websocket.close(code=1008)  # cookie-authenticated: same host only
                return
            await websocket.accept()
            try:
                actor = actor_dependency(websocket)  # session from the cookie, never a client id
                if require_consent is not None:
                    require_consent(actor)
            except Exception as exc:  # noqa: BLE001 - map to a contract code, no details
                code = getattr(exc, "code", "UNAUTHENTICATED")
                code = code if code in {"UNAUTHENTICATED", "CONSENT_REQUIRED", "FORBIDDEN"} else "UNAUTHENTICATED"
                await websocket.send_json({"type": "error", "code": code, "message": "Join and turn on consent to answer.", "retryable": False})
                await websocket.close(code=1008)
                return
            await live_relay(websocket.receive, websocket.send_json, live_stt, connect=live_connect or default_connect)
            try:
                await websocket.close()
            except RuntimeError:
                pass  # already closed by the client

    # ---- operator ("Demo timing") -------------------------------------------
    @router.post("/operator/cycles")
    async def new_cycle(request: Request, session: Session = Depends(demo_runner)):
        body = await _body(request, NewCycleRequest)
        if body.communityId != session.communityId:
            raise CycleError("FORBIDDEN")
        if session.isOperator is not True and body.demoTiming is not True:
            raise CycleError("FORBIDDEN")  # only operators start real-calendar weeks
        return _json(await call(service.create_cycle, body), 201)

    @router.post("/operator/cycles/{cycle_id}/advance")
    async def advance(cycle_id: str, request: Request, session: Session = Depends(demo_runner)):
        body = await _body(request, AdvanceRequest, optional=True)
        await call(service.released_questions, session, cycle_id)  # community check
        await call(require_demo_or_operator, session, cycle_id)
        return _json(await call(service.advance, cycle_id, body.to))

    @router.post("/operator/cycles/{cycle_id}/synthetic-topup")
    async def topup(cycle_id: str, session: Session = Depends(demo_runner)):
        await call(service.released_questions, session, cycle_id)
        await call(require_demo_or_operator, session, cycle_id)
        return _json(await call(service.synthetic_topup, cycle_id))

    @router.post("/operator/cycles/{cycle_id}/reset")
    async def reset(cycle_id: str, session: Session = Depends(demo_runner)):
        await call(service.released_questions, session, cycle_id)
        await call(require_demo_or_operator, session, cycle_id)
        return _json(await call(service.reset, cycle_id))

    return router
