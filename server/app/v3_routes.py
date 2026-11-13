"""Live v3 routes: daily constellations, sky, week, main. Mounted on the matching router.

The player always comes from the verified session (request.state.cst_actor), never from the
request body. Placement reads the cycle's eligible answers (consented, unflagged) and calls
FormationV3, which uses Muse (M3/M4) when configured and labeled keyword fallbacks otherwise.
Views return star and room indices only; no player ids, no answer text."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Request

from server.matching.models import MatchingError
from server.matching.v3 import FormationV3, InMemoryDayStore, QuietSignals

CHAT_HOURS = 24
DAY_COLORS = ("ember", "tide", "moss", "dusk", "gold")


class AnswersDaySource:
    """DaySnapshotSource over AnswerStore.eligible_answers: refs are random per call."""

    def __init__(self, answers, community_id: str) -> None:
        self._answers, self._community = answers, community_id

    async def day_snapshot(self, cycle_id: str, day: int) -> dict[str, Any]:
        rows = [
            r for r in self._answers.eligible_answers(cycle_id, self._community) if r["day"] <= day
        ]
        todays = {r["player_id"] for r in rows if r["day"] == day}
        players = sorted(todays)
        refs = {p: "r-" + secrets.token_hex(4) for p in players}
        return {
            "answers": [
                {"id": refs[r["player_id"]], "text": r["text"], "weight": float(r["weight"])}
                for r in rows
                if r["player_id"] in refs and r["day"] == day
            ],
            "idMap": {refs[p]: p for p in players},
            "blockedPairs": [],
        }


def build_v3_router(
    *, answers, cycles, privacy_actor, muse, guard, store: InMemoryDayStore | None = None
) -> APIRouter:
    router = APIRouter()
    store = store or InMemoryDayStore()
    ports: dict[str, FormationV3] = {}
    signals = QuietSignals()

    def port(request: Request, cycle_id: str) -> tuple[FormationV3, Any]:
        actor = request.state.cst_actor
        gate = cycles.gate(cycle_id)
        if gate.cycle.communityId != actor.community_id:
            raise MatchingError("NOT_FOUND", "Unknown cycle", retryable=False)
        key = f"{actor.community_id}:{cycle_id}"
        if key not in ports:
            ports[key] = FormationV3(
                muse, AnswersDaySource(answers, actor.community_id), store, guard=guard
            )
        return ports[key], actor

    def deny(exc: MatchingError) -> dict:
        return {
            "status": "failed",
            "error": {"code": exc.code, "message": str(exc), "retryable": exc.retryable},
        }

    @router.get("/cycles/{cycleId}/days/{day}/constellations")
    async def daily(cycleId: str, day: int, request: Request):
        try:
            v3, actor = port(request, cycleId)
            await v3.dailyPlace(cycleId, day, actor.player_id)
            count = len((await v3._snap(cycleId, day)).refs)
            return v3.daily_view(cycleId, day, actor.player_id, DAY_COLORS[(day - 1) % 5], count)
        except MatchingError as exc:
            return deny(exc)

    @router.post("/cycles/{cycleId}/constellations/{constellationId}/quiet-signal")
    async def quiet_signal(cycleId: str, constellationId: str, request: Request):
        try:
            v3, actor = port(request, cycleId)
            mine = {
                g.group_id
                for rec in v3.store.load_days(cycleId).values()
                for g in rec.groups
                if actor.player_id in g.members
            }
            if constellationId not in mine:  # only members may signal; never reveals who is in it
                raise MatchingError("NOT_FOUND", "Unknown constellation", retryable=False)
            return signals.send(constellationId, actor.player_id)
        except MatchingError as exc:
            return deny(exc)

    @router.get("/cycles/{cycleId}/sky/stars")
    async def sky_stars(cycleId: str, request: Request):
        try:
            v3, _ = port(request, cycleId)
            return await v3.skyLayout(cycleId)
        except MatchingError as exc:
            return deny(exc)

    @router.get("/cycles/{cycleId}/sky/mine")
    async def sky_mine(cycleId: str, request: Request):
        try:
            v3, actor = port(request, cycleId)
            return v3.my_sky(
                cycleId, actor.player_id, {d: DAY_COLORS[(d - 1) % 5] for d in range(1, 6)}
            )
        except MatchingError as exc:
            return deny(exc)

    @router.get("/cycles/{cycleId}/week")
    async def week(cycleId: str, request: Request):
        try:
            v3, _ = port(request, cycleId)
            return await v3.weekGraph(cycleId)
        except MatchingError as exc:
            return deny(exc)

    @router.get("/cycles/{cycleId}/main")
    async def main(cycleId: str, request: Request):
        try:
            v3, actor = port(request, cycleId)
            now = datetime.now(UTC)
            return v3.main_view(
                cycleId,
                actor.player_id,
                f"room-{cycleId}",
                now.isoformat(),
                (now + timedelta(hours=CHAT_HOURS)).isoformat(),
            )
        except MatchingError as exc:
            return deny(exc)

    @router.post("/operator/cycles/{cycleId}/close-day")
    async def close_day(cycleId: str, request: Request, body: dict | None = None):
        day = int((body or {}).get("day", 1))
        privacy_actor.require_operator(request.state.cst_actor)
        v3, actor = port(request, cycleId)
        result = await v3.closeDay(cycleId, day)
        return {**result, "jobId": f"close-{cycleId}-{day}"}

    @router.post("/operator/cycles/{cycleId}/main/form")
    async def form_main(cycleId: str, request: Request):
        privacy_actor.require_operator(request.state.cst_actor)
        v3, actor = port(request, cycleId)
        return await v3.mainConstellation(cycleId)

    return router


class V3Scheduler:
    """Closes finished days and forms Sunday's main when the cycle locks. Driven by cycle
    changes (day advance, lock); every step is idempotent and failure never blocks the cycle."""

    def __init__(self, answers, muse, guard, store: InMemoryDayStore) -> None:
        self._answers, self._muse, self._guard, self._store = answers, muse, guard, store
        self._closed: set[tuple[str, int]] = set()
        self._main_done: set[str] = set()

    def _port(self, community_id: str) -> FormationV3:
        return FormationV3(
            self._muse,
            AnswersDaySource(self._answers, community_id),
            self._store,
            guard=self._guard,
        )

    async def on_cycle(self, cycle) -> None:
        # The publish hook hands over the wire dict; direct callers may pass the model.
        read = cycle.get if isinstance(cycle, dict) else lambda key: getattr(cycle, key)
        cycle_id, status, current_day = read("cycleId"), read("status"), read("currentDay")
        v3 = self._port(read("communityId"))
        last_finished = current_day if status != "open" else current_day - 1
        for day in range(1, max(0, last_finished) + 1):
            if (cycle_id, day) not in self._closed:
                self._closed.add((cycle_id, day))
                await v3.closeDay(cycle_id, day)
        if status != "open" and cycle_id not in self._main_done:
            self._main_done.add(cycle_id)
            await v3.mainConstellation(cycle_id)
