"""Demo stage view: what the presenter's big screen may show.

Two players may opt in to a stage slot ("A" or "B") from their own session.
Only then, and only to an operator, does ``GET /operator/stage`` return those
two players' own answer text. Everyone else appears as counts.

Rules kept here:
- A slot is set only by the player it shows (``POST /me/stage``); an operator
  cannot put someone else on stage.
- Answer text comes from ``AnswerStore.eligible_answers`` only, so a flagged
  answer, or any answer of a player with a flagged answer, is never returned.
- Constellation ``sharedMeaning`` and member ids are never returned. Names and
  theme labels are returned only if they pass the output guard again here, and
  a theme needs ``THEME_THRESHOLD`` members to be named.
"""

from copy import deepcopy
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict

from server.cycle import CycleError

SLOTS = ("A", "B")
THEME_THRESHOLD = 3
MAX_CALLS = 120


def _stamp() -> str:
    # Same shape as MuseCallEvidence.generatedAt, so the two compare as text.
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class StageChoice(BaseModel):
    model_config = ConfigDict(extra="forbid")
    slot: Literal["A", "B"] | None


def build_stage_router(*, repository, privacy, answers, cycles, guard, calls):
    """Returns ``(router, note_cycle)``. ``note_cycle(cycle)`` records when a week
    was first seen, so the stage lists only this week's model calls."""
    router = APIRouter()
    allowed = guard.text_guard()

    def note_cycle(cycle) -> None:
        cycle_id = cycle["cycleId"] if isinstance(cycle, dict) else cycle.cycleId
        with repository.transaction() as state:
            started = state.records.setdefault("stageStarted", {})
            started.setdefault(cycle_id, _stamp())
            while len(started) > 50:
                started.pop(next(iter(started)))

    def slot_of(state, actor):
        slots = state.records.get("stageSlots", {}).get(actor.community_id, {})
        return next((slot for slot in SLOTS if slots.get(slot) == actor.player_id), None)

    @router.get("/me/stage")
    def my_slot(request: Request):
        actor = request.state.cst_actor
        with repository.transaction() as state:
            return {"slot": slot_of(state, actor)}

    @router.post("/me/stage")
    def choose_slot(body: StageChoice, request: Request):
        actor = request.state.cst_actor
        privacy.require_consent(actor)
        with repository.transaction() as state:
            slots = state.records.setdefault("stageSlots", {}).setdefault(actor.community_id, {})
            for slot in SLOTS:
                if slots.get(slot) == actor.player_id:
                    slots.pop(slot)
            if body.slot is not None:
                slots[body.slot] = actor.player_id  # the newest opt-in takes the slot
        return {"slot": body.slot}

    @router.get("/operator/stage")
    def stage(request: Request):
        actor = request.state.cst_actor
        privacy.require_operator(actor)
        community = actor.community_id
        try:
            cycle = cycles.current(community)
        except CycleError:
            cycle = None
        with repository.transaction() as state:
            slots = dict(state.records.get("stageSlots", {}).get(community, {}))
            entry = None
            job_status = None
            started = ""
            if cycle is not None:
                started = state.records.get("stageStarted", {}).get(cycle.cycleId, "")
                entry = deepcopy(state.records.get("formations", {}).get(cycle.cycleId))
                job_id = state.records.get("activeJobs", {}).get(cycle.cycleId)
                job = state.records.get("jobs", {}).get(job_id)
                job_status = job["status"] if job else None
        rows = answers.eligible_answers(cycle.cycleId, community) if cycle is not None else []
        by_day = {day: 0 for day in range(1, 6)}
        for row in rows:
            by_day[row["day"]] = by_day.get(row["day"], 0) + 1
        player_of = {player: slot for slot, player in slots.items()}

        private = entry["privateFormation"] if entry else None
        constellations = []
        mine = {}
        for item in (private or {}).get("wire", {}).get("constellations", []):
            on_stage = sorted(player_of[m] for m in item["memberIds"] if m in player_of)
            name = item["name"] if allowed(item["name"]) else None
            summary = {
                "name": name,
                "size": len(item["memberIds"]),
                "isLooseMatch": bool(item.get("isLooseMatch")),
                "slots": on_stage,
            }
            constellations.append(summary)
            for slot in on_stage:
                mine[slot] = {k: summary[k] for k in ("name", "size", "isLooseMatch")}
        themes, suppressed = [], 0
        for theme in (private or {}).get("themes", []):
            count = len(theme["memberIds"])
            if count < THEME_THRESHOLD or not allowed(theme["label"]):
                suppressed += 1
                continue
            themes.append(
                {
                    "label": theme["label"],
                    "count": count,
                    "slots": sorted(player_of[m] for m in theme["memberIds"] if m in player_of),
                }
            )

        panels = []
        for slot in SLOTS:
            player = slots.get(slot)
            panels.append(
                {
                    "slot": slot,
                    "joined": player is not None,
                    "answers": [
                        {"day": row["day"], "text": row["text"]}
                        for row in rows
                        if player is not None and row["player_id"] == player
                    ],
                    "constellation": mine.get(slot),
                }
            )
        recent = sorted(
            (
                call
                for call in calls(actor)
                if cycle is not None and call.get("generatedAt", "") >= started
            ),
            key=lambda call: call.get("generatedAt", ""),
        )[-MAX_CALLS:]
        return {
            "cycle": cycle.model_dump() if cycle is not None else None,
            "formation": {
                "jobStatus": job_status,
                "formed": private is not None,
                "eligiblePlayers": len(entry["eligibleIds"]) if entry else None,
            },
            "population": {
                "players": len({row["player_id"] for row in rows}),
                "syntheticPlayers": len({row["player_id"] for row in rows if row["is_synthetic"]}),
                "answersByDay": [by_day[day] for day in range(1, 6)],
            },
            "panels": panels,
            "themes": themes,
            "suppressedThemes": suppressed,
            "constellations": constellations,
            "calls": recent,
        }

    return router, note_cycle
