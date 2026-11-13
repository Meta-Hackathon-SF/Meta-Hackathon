"""FastAPI router for planning's operator routes (contracts/API.md, "Questions and nudges").

    GET  /operator/questions                    -> Question[]
    POST /operator/cycles/{cycleId}/select-week -> DailyQuestion[] (Mon-Fri)
    POST /operator/rooms/{roomId}/nudge         -> EventNudge (posted as muse_nudge)

Kai mounts it through the registry (owner "planning") under /api/v1 with
Patrik's verified-session dependency. Every route here is operator-only and
rechecks the role itself. ``POST /operator/questions/generate`` is not
registered: question generation (M6) is not implemented.

This module is the only part of planning that needs FastAPI.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Literal

from fastapi import APIRouter, Depends, FastAPI, Query, Request
from fastapi.responses import JSONResponse

from .errors import PlanningError
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

    return router
