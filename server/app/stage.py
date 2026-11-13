"""Demo stage: the presenter's big screen and its controls (D017, D019).

The stage is always on. The two most recent real (non-synthetic) players who
joined, other than the account viewing the stage, appear as Phone A and Phone B
with their display name. A player can pin themselves to a slot or take
themselves off the stage from their phone (``POST /me/stage``), and the stage
can re-detect phones. Any signed-in member of the community may open and drive
the stage (demo: every account can present).

The stage drives the whole demo week, so the player-facing site needs no demo
buttons:
- ``POST /operator/stage/start``: a fresh demo week on Monday with the synthetic
  cast's answers, and the phones' Monday answer filled from the script.
- ``POST /operator/stage/next``: next day (cast answers and the phones' scripted
  answer for that day filled in); on Friday it locks and starts matching; once
  Muse has formed the constellations it reveals. Presenters type only Friday.

Rules kept here:
- Answer text comes from ``AnswerStore.eligible_answers`` only, so a flagged
  answer, or any answer of a player with a flagged answer, is never returned,
  and only for the two phones on stage. Everyone else appears as counts.
- Constellation ``sharedMeaning`` and member ids are never returned. Names and
  theme labels are returned only if they pass the output guard again here, and
  a theme needs ``THEME_THRESHOLD`` members to be named.
- Scripted answers are written only for players on stage, only on demo-timing
  weeks, never over an answer the player already gave.
"""

import hashlib
from copy import deepcopy
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict

from server.app.stage_script import SCRIPTS
from server.cycle import CycleError
from server.cycle.wire import NewCycleRequest

SLOTS = ("A", "B")
THEME_THRESHOLD = 3
MAX_CALLS = 120
LIVE_DAY = 5  # the presenters answer Friday themselves


def _stamp() -> str:
    # Same shape as MuseCallEvidence.generatedAt, so the two compare as text.
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _seed(value: str) -> str:
    """Opaque, stable value the screen uses to draw a constellation's map."""
    return hashlib.sha256(value.encode()).hexdigest()[:8]


class StageChoice(BaseModel):
    model_config = ConfigDict(extra="forbid")
    slot: Literal["A", "B", "off"] | None  # None: let the stage pick automatically


def build_stage_router(*, repository, privacy, privacy_store, answers, cycles, guard, calls):
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

    # ------------------------------------------------------------ phones
    def recent_players(community: str) -> list[tuple[str, str]]:
        """Real members who joined most recently and allow matching: (id, name)."""
        with privacy_store.tx() as conn:
            rows = conn.execute(
                """
                SELECT p.player_id, p.display_name FROM memberships m
                JOIN players p ON p.player_id = m.player_id
                JOIN current_consents c
                  ON c.player_id = m.player_id AND c.community_id = m.community_id
                WHERE m.community_id = ? AND m.left_at IS NULL AND p.is_synthetic = 0
                  AND c.match_answers = 1
                ORDER BY m.joined_at DESC, m.rowid DESC LIMIT 12
                """,
                (community,),
            ).fetchall()
        return [(r["player_id"], r["display_name"]) for r in rows]

    def resolve(state, community: str, viewer: str | None) -> dict[str, str]:
        """slot -> playerId. Pinned slots first, then the newest joiners fill the rest
        (the older of the two becomes A). The viewing account is never a phone."""
        pinned = dict(state.records.get("stageSlots", {}).get(community, {}))
        off = set(state.records.get("stageOff", {}).get(community, []))
        taken = set(pinned.values())
        candidates = [
            pid
            for pid, _ in recent_players(community)
            if pid != viewer and pid not in off and pid not in taken
        ]
        free = [slot for slot in SLOTS if slot not in pinned]
        picks = list(reversed(candidates[: len(free)]))  # older first
        out = {slot: pid for slot, pid in pinned.items() if pid != viewer}
        out.update(zip(free, picks, strict=False))  # fewer joiners than free slots is fine
        return out

    def names(player_ids) -> dict[str, str]:
        ids = list(player_ids)
        if not ids:
            return {}
        with privacy_store.tx() as conn:
            marks = ",".join("?" * len(ids))
            rows = conn.execute(
                f"SELECT player_id, display_name FROM players WHERE player_id IN ({marks})", ids
            ).fetchall()
        return {r["player_id"]: r["display_name"] for r in rows}

    def pin(community: str, viewer: str) -> dict[str, str]:
        with repository.transaction() as state:
            slots = resolve(state, community, viewer)
            state.records.setdefault("stageSlots", {})[community] = dict(slots)
        return slots

    @router.get("/me/stage")
    def my_slot(request: Request):
        actor = request.state.cst_actor
        with repository.transaction() as state:
            community = actor.community_id
            pinned = state.records.get("stageSlots", {}).get(community, {})
            if actor.player_id in state.records.get("stageOff", {}).get(community, []):
                return {"slot": "off"}
            return {"slot": next((s for s in SLOTS if pinned.get(s) == actor.player_id), None)}

    @router.post("/me/stage")
    def choose_slot(body: StageChoice, request: Request):
        actor = request.state.cst_actor
        privacy.require_consent(actor)
        with repository.transaction() as state:
            community = actor.community_id
            slots = state.records.setdefault("stageSlots", {}).setdefault(community, {})
            off = state.records.setdefault("stageOff", {}).setdefault(community, [])
            for slot in SLOTS:
                if slots.get(slot) == actor.player_id:
                    slots.pop(slot)
            if actor.player_id in off:
                off.remove(actor.player_id)
            if body.slot == "off":
                off.append(actor.player_id)
            elif body.slot is not None:
                slots[body.slot] = actor.player_id  # the newest choice takes the slot
        return {"slot": body.slot}

    # ------------------------------------------------------------ the view
    def current(community: str):
        try:
            return cycles.current(community)
        except CycleError:
            return None

    def view(actor) -> dict:
        community = actor.community_id
        cycle = current(community)
        with repository.transaction() as state:
            slots = resolve(state, community, actor.player_id)
            entry = None
            job_status = None
            started = ""
            if cycle is not None:
                started = state.records.get("stageStarted", {}).get(cycle.cycleId, "")
                entry = deepcopy(state.records.get("formations", {}).get(cycle.cycleId))
                job_id = state.records.get("activeJobs", {}).get(cycle.cycleId)
                job = state.records.get("jobs", {}).get(job_id)
                job_status = job["status"] if job else None
        display = names(slots.values())
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
                "mapSeed": _seed(item["constellationId"]),
                "slots": on_stage,
            }
            constellations.append(summary)
            for slot in on_stage:
                mine[slot] = {k: summary[k] for k in ("name", "size", "isLooseMatch", "mapSeed")}
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

        today = None
        if cycle is not None and cycle.status == "open":
            question = cycles.day_question(cycle.cycleId, community, cycle.currentDay).question
            today = {
                "day": cycle.currentDay,
                "questionId": question.questionId,
                "text": question.text,
            }

        panels = []
        for slot in SLOTS:
            player = slots.get(slot)
            mine_rows = [r for r in rows if player is not None and r["player_id"] == player]
            answered_today = today is not None and any(r["day"] == today["day"] for r in mine_rows)
            script = SCRIPTS[slot].get(today["questionId"]) if today else None
            panels.append(
                {
                    "slot": slot,
                    "joined": player is not None,
                    "displayName": display.get(player) if player else None,
                    "answers": [
                        {
                            "day": r["day"],
                            "text": r["text"],
                            "scripted": r["text"] in SCRIPTS[slot].values(),
                        }
                        for r in mine_rows
                    ],
                    # What to type on the phone today (only Friday is typed live).
                    "toType": script if (player and today and not answered_today) else None,
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
            "today": today,
            "liveDay": LIVE_DAY,
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

    @router.get("/operator/stage")
    def stage(request: Request):
        return view(request.state.cst_actor)  # signed-in member, scoped to their community

    # ------------------------------------------------------------ controls
    def fill_day(cycle, community: str, slots: dict[str, str]) -> None:
        """Cast answers for the days reached, and the phones' script up to Thursday."""
        cycles.synthetic_topup(cycle.cycleId)
        rows = []
        for slot, player in slots.items():
            for day in range(1, min(cycle.currentDay, LIVE_DAY - 1) + 1):
                qid = cycles.day_question(cycle.cycleId, community, day).question.questionId
                text = SCRIPTS[slot].get(qid)
                if text:
                    rows.append({"playerId": player, "day": day, "text": text})
        if rows:
            cycles.stage_answers(cycle.cycleId, community, rows)

    @router.post("/operator/stage/start")
    def start(request: Request):
        actor = request.state.cst_actor
        community = actor.community_id
        cycle = current(community)
        if cycle is not None and cycles.is_demo_cycle(cycle.cycleId):
            cycle = cycles.reset(cycle.cycleId)
        else:
            cycle = cycles.create_cycle(NewCycleRequest(communityId=community, demoTiming=True))
        fill_day(cycle, community, pin(community, actor.player_id))
        return view(actor)

    @router.post("/operator/stage/next")
    def next_step(request: Request):
        actor = request.state.cst_actor
        community = actor.community_id
        cycle = current(community)
        if cycle is None or not cycles.is_demo_cycle(cycle.cycleId):
            raise CycleError("NOT_FOUND")
        slots = pin(community, actor.player_id)
        if cycle.status == "open" and cycle.currentDay < LIVE_DAY:
            cycle = cycles.advance(cycle.cycleId)
            fill_day(cycle, community, slots)
        elif cycle.status == "open":
            fill_day(cycle, community, slots)  # anyone who joined late gets Mon-Thu
            cycles.advance(cycle.cycleId)  # Saturday lock: matching starts
            cycles.advance(cycle.cycleId)  # forming
        elif cycle.status == "locked":
            cycles.advance(cycle.cycleId)
        elif cycle.status == "forming":
            with repository.transaction() as state:
                formed = cycle.cycleId in state.records.get("formations", {})
            if formed:
                cycles.advance(cycle.cycleId)  # Sunday reveal
        return view(actor)

    @router.post("/operator/stage/phones/reset")
    def redetect(request: Request):
        actor = request.state.cst_actor
        with repository.transaction() as state:
            state.records.setdefault("stageSlots", {})[actor.community_id] = {}
        return view(actor)

    return router, note_cycle
