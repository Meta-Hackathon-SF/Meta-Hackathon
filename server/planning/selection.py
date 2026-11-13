"""Weekly selection: QuestionPort.selectWeek (contracts/protocol.ts 2.0.0).

Picks five active questions for Monday-Friday. Code decides; no model call.
Rules, in order of precedence:
  1. never a question used in this community's previous four cycles
  2. Monday is low sensitivity
  3. at most ``MAX_MEDIUM`` medium-sensitivity questions, never on adjacent days
  4. five different categories when the bank allows it
Deterministic: the same (bank, history, cycleId, communityId, seed) always gives
the same week. A cycle that already has a selection gets that selection back.

Future days: ``QuestionService.released`` is the only projection a player route
may use, and it returns nothing beyond ``currentDay``.
"""
from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, Protocol

from .errors import PlanningError
from .ports import WeekStartLookup
from .questions import QuestionBank

DAYS = (1, 2, 3, 4, 5)
NO_REPEAT_CYCLES = 4
MAX_MEDIUM = 2


def default_seed(cycle_id: str, community_id: str) -> int:
    digest = hashlib.sha256(f"{community_id}\x1f{cycle_id}".encode()).digest()
    return int.from_bytes(digest[:8], "big")


def _acceptable(week: list[dict[str, Any]], distinct_categories: bool) -> bool:
    if week[0]["sensitivity"] != "low":
        return False
    medium = [q["sensitivity"] == "medium" for q in week]
    if sum(medium) > MAX_MEDIUM or any(a and b for a, b in zip(medium, medium[1:])):
        return False
    return not distinct_categories or len({q["category"] for q in week}) == len(week)


def pick_week(bank: QuestionBank, recent_question_ids: set[str], seed: int) -> list[dict[str, Any]]:
    """Five questions in Monday-Friday order, or INVALID_INPUT when the bank cannot satisfy rules 1-3."""
    pool = sorted(
        (q for q in bank.questions if q["active"] and q["questionId"] not in recent_question_ids),
        key=lambda q: q["questionId"],
    )
    rng = random.Random(seed)
    rng.shuffle(pool)
    for distinct in (True, False):
        week = _search(pool, [], distinct)
        if week is not None:
            return week
    raise PlanningError(
        "INVALID_INPUT",
        "question bank cannot fill a week: need five unused active questions with a low-sensitivity Monday",
    )


def _search(pool: list[dict[str, Any]], week: list[dict[str, Any]], distinct: bool) -> list[dict[str, Any]] | None:
    if len(week) == len(DAYS):
        return week if _acceptable(week, distinct) else None
    for q in pool:
        if q in week:
            continue
        if not week and q["sensitivity"] != "low":
            continue
        if distinct and any(q["category"] == w["category"] for w in week):
            continue
        if week and q["sensitivity"] == "medium" and week[-1]["sensitivity"] == "medium":
            continue
        found = _search(pool, [*week, q], distinct)
        if found is not None:
            return found
    return None


class SelectionStore(Protocol):
    """Persistence for weekly selections. Kai's orchestration supplies the durable one."""

    def get(self, cycle_id: str) -> dict[str, Any] | None: ...
    def put(self, cycle_id: str, record: dict[str, Any]) -> None: ...
    def recent(self, community_id: str, limit: int, exclude_cycle_id: str) -> list[dict[str, Any]]: ...


@dataclass
class InMemorySelectionStore:
    """Process-local store for tests and a single-process demo. Not durable."""

    _by_cycle: dict[str, dict[str, Any]] = field(default_factory=dict)
    _order: list[str] = field(default_factory=list)

    def get(self, cycle_id: str) -> dict[str, Any] | None:
        return self._by_cycle.get(cycle_id)

    def put(self, cycle_id: str, record: dict[str, Any]) -> None:
        if cycle_id not in self._by_cycle:
            self._order.append(cycle_id)
        self._by_cycle[cycle_id] = record

    def recent(self, community_id: str, limit: int, exclude_cycle_id: str) -> list[dict[str, Any]]:
        rows = [self._by_cycle[c] for c in self._order
                if c != exclude_cycle_id and self._by_cycle[c]["communityId"] == community_id]
        rows.sort(key=lambda r: r["weekStart"])
        return rows[-limit:]


class QuestionService:
    """Python form of QuestionPort plus the released-days projection."""

    def __init__(self, bank: QuestionBank, store: SelectionStore, week_start: WeekStartLookup) -> None:
        self._bank = bank
        self._store = store
        self._week_start = week_start

    @property
    def bank(self) -> QuestionBank:
        return self._bank

    def replace_bank(self, bank: QuestionBank) -> None:
        self._bank = bank

    async def select_week(self, cycle_id: str, community_id: str, *, seed: int | None = None) -> list[dict[str, Any]]:
        """``DailyQuestion[]`` for Mon-Fri. Operator-only: it contains future days."""
        existing = self._store.get(cycle_id)
        if existing is not None:
            if existing["communityId"] != community_id:
                raise PlanningError("NOT_FOUND", "cycle not found")
            return self._daily(existing)
        week_start = await self._week_start(cycle_id)
        try:
            monday = date.fromisoformat(week_start)
        except (TypeError, ValueError):
            raise PlanningError("INVALID_INPUT", "cycle weekStart is not a date") from None
        if monday.weekday() != 0:
            raise PlanningError("INVALID_INPUT", "cycle weekStart must be a Monday")
        recent = {
            qid
            for row in self._store.recent(community_id, NO_REPEAT_CYCLES, cycle_id)
            for qid in row["questionIds"]
        }
        week = pick_week(self._bank, recent, default_seed(cycle_id, community_id) if seed is None else seed)
        record = {
            "cycleId": cycle_id, "communityId": community_id, "weekStart": monday.isoformat(),
            "questionIds": [q["questionId"] for q in week],
            # Snapshot so a later bank edit cannot change a week already announced.
            "questions": [dict(q) for q in week],
        }
        self._store.put(cycle_id, record)
        return self._daily(record)

    def released(self, cycle_id: str, current_day: int, *, cycle_open: bool = True) -> list[dict[str, Any]]:
        """Player-safe projection: days 1..currentDay only. Never a future day.

        ``current_day`` comes from Will's WeeklyCycle (server state), never from
        the client. After the cycle leaves ``open`` all five days are past.
        """
        record = self._store.get(cycle_id)
        if record is None:
            raise PlanningError("NOT_FOUND", "cycle has no selected questions")
        if isinstance(current_day, bool) or not isinstance(current_day, int) or current_day not in DAYS:
            raise PlanningError("INVALID_INPUT", "currentDay must be 1-5")
        last = current_day if cycle_open else DAYS[-1]
        return [d for d in self._daily(record) if d["day"] <= last]

    def question_for_day(self, cycle_id: str, day: int, current_day: int) -> dict[str, Any]:
        """One released ``DailyQuestion``; a future day is NOT_FOUND, same as a missing one."""
        for d in self.released(cycle_id, current_day):
            if d["day"] == day:
                return d
        raise PlanningError("NOT_FOUND", "question not available")

    @staticmethod
    def _daily(record: dict[str, Any]) -> list[dict[str, Any]]:
        monday = date.fromisoformat(record["weekStart"])
        return [
            {"cycleId": record["cycleId"], "day": day,
             "date": (monday + timedelta(days=day - 1)).isoformat(), "question": dict(q)}
            for day, q in zip(DAYS, record["questions"])
        ]
