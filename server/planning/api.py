"""FastAPI router for planning's operator routes (contracts/API.md, "Questions and nudges").

    GET  /operator/questions                    -> Question[]
    POST /operator/cycles/{cycleId}/select-week -> DailyQuestion[] (Mon-Fri)
    POST /operator/rooms/{roomId}/nudge         -> EventNudge (posted as muse_nudge)

Kai mounts it through the registry (owner "planning") under /api/v1 with
Patrik's verified-session dependency. Every route here is operator-only and
rechecks the role itself.

With a ``QuestionGenerator`` in the runtime (step 7) it also registers:
    POST /operator/questions/generate           -> 202 {status: "pending", questions, rejected, evidence}
and three routes that are NOT in contracts/API.md yet (proposed, additive;
they need ACK before they count as contract):
    GET  /operator/questions/pending            -> [{question, evidence}]
    POST /operator/questions/{id}/approve       -> Question (now active, in the bank)
    POST /operator/questions/{id}/reject        -> 204

This module is the only part of planning that needs FastAPI.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Literal

from fastapi import APIRouter, Body, Depends, FastAPI, Query, Request, Response
from fastapi.responses import JSONResponse

from datetime import datetime, timezone

from .custom_events import CustomEventService
from .errors import PlanningError
from .events import EventsService
from .generation import QuestionGenerator
from .nudge_copy import EventNudgeService
from .nudges import NudgeService
from .selection import QuestionService
from .venues import VenueCatalog

# code -> (HTTP status, public message, retryable). Messages are fixed text.
_ERRORS: dict[str, tuple[int, str, bool]] = {
    "INVALID_INPUT": (400, "Request does not match the API requirements.", False),
    "FORBIDDEN": (403, "This action is not permitted.", False),
    "NOT_FOUND": (404, "Resource not found.", False),
    "PROVIDER_UNAVAILABLE": (503, "The requested service is not available. Try again later.", True),
}

Category = Literal["routine", "belonging", "interests", "values", "hopes", "small_joys", "challenges"]


@dataclass
class PlanningRuntime:
    """What the router needs. Kai builds it at startup from real dependencies."""

    questions: QuestionService
    nudges: NudgeService | None = None
    # roomId -> constellationId, or None for an unknown room (Kai's chat data).
    room_constellation: Callable[[str], Awaitable[str | None]] | None = None
    venues: VenueCatalog | None = None
    muse_configured: bool = False
    generator: QuestionGenerator | None = None
    # The adapter's ReasoningTrace (``adapter.reasoning_trace``): every Muse call
    # plus the code verdicts on it. PROPOSED route, see build_router.
    trace: Any = None
    # v3 (3.0.0, PRD S13/S14): events list, event nudges, custom events. Each route
    # group mounts only when its service is supplied.
    events: EventsService | None = None
    event_nudges: EventNudgeService | None = None
    custom_events: CustomEventService | None = None
    # Server clock (Kai's demo-aware effective now); never the client's.
    now: Callable[[], datetime] = lambda: datetime.now(timezone.utc)

    async def ready(self) -> bool:
        """Readiness for the registry. Local state only; never probes the paid model."""
        try:
            active = [q for q in self.questions.bank.questions if q["active"]]
            if len(active) < 5 or not self.muse_configured:
                return False
            if self.nudges is not None and (self.venues is None or not self.venues.venues
                                            or self.room_constellation is None):
                return False
            return True
        except Exception:
            return False


def _player_id(session: Any) -> str | None:
    """The verified player id from Patrik's Actor or a wire-shaped session."""
    for name in ("player_id", "playerId"):
        value = session.get(name) if isinstance(session, dict) else getattr(session, name, None)
        if isinstance(value, str) and value:
            return value
    return None


def _session_fields(session: Any) -> tuple[str | None, bool]:
    """(communityId, isOperator) from Patrik's Actor or a wire-shaped session."""
    def pick(*names: str) -> Any:
        for name in names:
            value = session.get(name) if isinstance(session, dict) else getattr(session, name, None)
            if value is not None:
                return value
        return None

    community = pick("community_id", "communityId")
    return (community if isinstance(community, str) else None), pick("is_operator", "isOperator") is True


def _request_id(request: Request) -> str:
    rid = getattr(request.state, "request_id", None)
    if not isinstance(rid, str):
        rid = "req_" + uuid.uuid4().hex
        request.state.request_id = rid
    return rid


def planning_error_response(request: Request, exc: PlanningError) -> JSONResponse:
    code = exc.code if exc.code in _ERRORS else "PROVIDER_UNAVAILABLE"
    status, message, retryable = _ERRORS[code]
    rid = _request_id(request)
    body = {"error": {"code": code, "message": message, "requestId": rid, "retryable": retryable}}
    return JSONResponse(body, status_code=status, headers={"X-Request-Id": rid, "Cache-Control": "no-store"})


def install_planning_error_handler(app: FastAPI) -> None:
    """PlanningError -> ApiError envelope. Call once on the composed app."""

    @app.exception_handler(PlanningError)
    async def _planning(request: Request, exc: PlanningError) -> JSONResponse:
        return planning_error_response(request, exc)


def build_router(runtime: PlanningRuntime, session_dependency: Callable[..., Any]) -> APIRouter:
    """``session_dependency`` is Patrik's verified-session dependency (never client input)."""
    router = APIRouter()

    def operator(session: Any = Depends(session_dependency)) -> str:
        community, is_operator = _session_fields(session)
        if not is_operator or community is None:
            raise PlanningError("FORBIDDEN", "operator role required")
        return community

    @router.get("/operator/questions")
    async def list_questions(
        _community: str = Depends(operator),
        active: bool | None = Query(default=None),
        category: Category | None = Query(default=None),
        source: Literal["curated", "generated"] | None = Query(default=None),
    ) -> list[dict[str, Any]]:
        return runtime.questions.bank.list(active=active, category=category, source=source)

    @router.post("/operator/cycles/{cycle_id}/select-week")
    async def select_week(cycle_id: str, community: str = Depends(operator)) -> list[dict[str, Any]]:
        if not (1 <= len(cycle_id) <= 80):
            raise PlanningError("INVALID_INPUT", "bad cycle id")
        # The community comes from the session, so an operator cannot select for another one.
        return await runtime.questions.select_week(cycle_id, community)

    if runtime.nudges is not None and runtime.room_constellation is not None:
        nudges, room_constellation = runtime.nudges, runtime.room_constellation

        @router.post("/operator/rooms/{room_id}/nudge")
        async def post_nudge(room_id: str, request: Request, _community: str = Depends(operator)) -> dict[str, Any]:
            constellation_id = await room_constellation(room_id) if 1 <= len(room_id) <= 80 else None
            if constellation_id is None:
                raise PlanningError("NOT_FOUND", "room not found")
            result = await nudges.propose_and_post(constellation_id, request_id=_request_id(request))
            return result["nudge"]

    if runtime.trace is not None:
        trace = runtime.trace

        # PROPOSED (not yet in contracts/API.md): operator view of the reasoning.
        # Codes and counts only; never payloads, prompts, outputs or player data.
        @router.get("/operator/reasoning")
        async def reasoning(task: str | None = None, limit: int = 100,
                            _community: str = Depends(operator)) -> list[dict[str, Any]]:
            from server.providers.port import TASKS

            if task is not None and task not in TASKS:
                raise PlanningError("INVALID_INPUT", "unknown task")
            if not (1 <= limit <= 300):
                raise PlanningError("INVALID_INPUT", "limit must be 1-300")
            return trace.list(task=task, limit=limit)

    if runtime.generator is not None:
        generator = runtime.generator

        @router.post("/operator/questions/generate", status_code=202)
        async def generate(request: Request, body: dict[str, Any] = Body(...),
                           _community: str = Depends(operator)) -> dict[str, Any]:
            if set(body) - {"count", "categoryMix", "aggregateSignals"}:
                raise PlanningError("INVALID_INPUT", "unexpected fields")
            recent = [q["questionId"] for q in runtime.questions.bank.questions]
            result = await generator.generate(
                count=body.get("count"), request_id=_request_id(request), category_mix=body.get("categoryMix"),
                aggregate_signals=body.get("aggregateSignals"), recent_question_ids=recent,
            )
            return {"status": "pending", "questions": result.pending, "rejected": result.rejected,
                    "rejections": result.rejections, "basis": result.basis, "evidence": result.evidence}

        @router.get("/operator/questions/pending")
        async def pending(_community: str = Depends(operator)) -> list[dict[str, Any]]:
            return generator.pending()

        @router.post("/operator/questions/{question_id}/approve")
        async def approve(question_id: str, _community: str = Depends(operator)) -> dict[str, Any]:
            return generator.approve(question_id)

        @router.post("/operator/questions/{question_id}/reject", status_code=204)
        async def reject(question_id: str, _community: str = Depends(operator)) -> Response:
            generator.reject(question_id)
            return Response(status_code=204)

    def player(session: Any = Depends(session_dependency)) -> tuple[str, Any]:
        player_id = _player_id(session)
        if player_id is None:
            raise PlanningError("FORBIDDEN", "verified session required")
        return player_id, session

    if runtime.events is not None:
        events = runtime.events

        @router.get("/events")
        async def list_events(window: Literal["week"] = Query(default="week"),
                              who: tuple[str, Any] = Depends(player)) -> list[dict[str, Any]]:
            return await events.list(who[1], now=runtime.now())

        @router.get("/events/{event_id}")
        async def get_event(event_id: str, who: tuple[str, Any] = Depends(player)) -> dict[str, Any]:
            if not (1 <= len(event_id) <= 80):
                raise PlanningError("INVALID_INPUT", "bad event id")
            return await events.get(who[1], event_id)

    if runtime.event_nudges is not None:
        nudges_v3 = runtime.event_nudges

        @router.get("/me/nudges")
        async def my_nudges(who: tuple[str, Any] = Depends(player)) -> list[dict[str, Any]]:
            return nudges_v3.active(who[0], now=runtime.now())

        @router.post("/nudges/{nudge_id}/dismiss", status_code=204)
        async def dismiss_nudge(nudge_id: str, who: tuple[str, Any] = Depends(player)) -> Response:
            if not nudges_v3.dismiss(who[0], nudge_id):
                raise PlanningError("NOT_FOUND", "no such nudge")
            return Response(status_code=204)

        @router.get("/operator/events/nudges")
        async def nudge_counts(_community: str = Depends(operator)) -> dict[str, Any]:
            return {"activeByBucket": nudges_v3.bucket_counts(now=runtime.now())}

        @router.post("/operator/events/{event_id}/nudge-preview")
        async def nudge_preview(event_id: str, body: dict[str, Any] = Body(...),
                                _community: str = Depends(operator)) -> dict[str, Any]:
            if set(body) != {"interestBucket"} or body["interestBucket"] not in ("3-5", "6-9", "10+"):
                raise PlanningError("INVALID_INPUT", "body must be {interestBucket}")
            try:
                return await nudges_v3.preview(event_id, body["interestBucket"], now=runtime.now())
            except ValueError:
                raise PlanningError("NOT_FOUND", "no approved event with that id") from None

    if runtime.custom_events is not None:
        custom = runtime.custom_events

        @router.get("/operator/custom-events")
        async def pending_custom_events(_community: str = Depends(operator)) -> list[dict[str, Any]]:
            return custom.pending()

        @router.post("/operator/custom-events/{proposal_id}/decision")
        async def decide_custom_event(proposal_id: str, body: dict[str, Any] = Body(...),
                                      _community: str = Depends(operator)) -> dict[str, Any]:
            if set(body) - {"decision", "note"} or "decision" not in body:
                raise PlanningError("INVALID_INPUT", "body must be {decision, note?}")
            note = body.get("note")
            if note is not None and (not isinstance(note, str) or len(note) > 280):
                raise PlanningError("INVALID_INPUT", "note must be at most 280 characters")
            return custom.decide(proposal_id, body["decision"])

    return router
