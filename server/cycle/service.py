"""Weekly cycle, daily answers, catch-up, weights, streaks (owner: Will).

Code enforces every rule here; Muse only proposes the optional follow-up.
- State machine: open -> locked -> forming -> revealed -> closed, forward only.
- Answers: own answers only; future days rejected; writes re-check the cycle
  status at commit time (CYCLE_LOCKED); weight is computed here, never read
  from the client.
- Cycle state lives in an in-memory repository in this build (not durable).
  Answers and guesses live behind Patrik's AnswerStore port.
"""

from __future__ import annotations

import json
import threading
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from pydantic import ValidationError

from . import calendar as cal
from .ports import (
    AnswerStore,
    Clarify,
    CycleHooks,
    NoHooks,
    QuestionPort,
    SafetyScreen,
    Session,
    SyntheticSeeder,
    TextGuard,
)
from .streaks import DayState, compute_streak
from .wire import (
    STATUS_ORDER,
    WEIGHTS,
    AnswerResponse,
    CatchUpState,
    CurrentCycleResponse,
    CycleStatus,
    DailyAnswer,
    DailyQuestion,
    DayTarget,
    EditAnswerRequest,
    GuessRequest,
    M2Out,
    NewCycleRequest,
    PrevalenceGuess,
    Streak,
    SubmitAnswerRequest,
    WeeklyCycle,
)

DEFAULT_TIME_ZONE = "America/Los_Angeles"
FIXTURE_WEEK = Path(__file__).resolve().parents[2] / "contracts" / "fixtures" / "week-sample.json"

# code -> (HTTP status, public message, retryable). Messages never echo input.
ERRORS: dict[str, tuple[int, str, bool]] = {
    "INVALID_INPUT": (400, "Request does not match the API requirements.", False),
    "UNAUTHENTICATED": (401, "A verified session is required.", False),
    "FORBIDDEN": (403, "This action is not permitted.", False),
    "NOT_FOUND": (404, "Resource not found.", False),
    "STALE_REVISION": (409, "This was already answered. Refresh, then edit instead.", False),
    "CYCLE_LOCKED": (409, "This week is locked. Answers can no longer change.", False),
    "CONSENT_REQUIRED": (403, "Current consent is required.", False),
    "PROVIDER_UNAVAILABLE": (503, "The requested service is not available. Try again later.", True),
}


class CycleError(Exception):
    def __init__(self, code: str) -> None:
        if code not in ERRORS:
            raise ValueError("Unknown API error code")
        super().__init__(code)
        self.code = code
        self.status, self.message, self.retryable = ERRORS[code]

    def to_api_error(self, request_id: str) -> dict:
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                "requestId": request_id,
                "retryable": self.retryable,
            }
        }


def compute_weight(is_catch_up: bool, follow_up_used: bool) -> float:
    base = WEIGHTS["catchUp"] if is_catch_up else WEIGHTS["onDay"]
    bonus = WEIGHTS["followUpBonus"] if follow_up_used else 0.0
    return round(min(WEIGHTS["max"], base + bonus), 2)


@dataclass
class CycleRecord:
    cycle: WeeklyCycle
    time_zone: str
    fixture: bool  # created with demo timing by an operator; only these can be reset
    questions: list[DailyQuestion]
    # answerId -> the single follow-up issued for that answer
    followups: dict[str, M2Out] = field(default_factory=dict)
    # answerIds whose text M1 flagged; never sent to another Muse call
    flagged: set[str] = field(default_factory=set)
    # transitions committed inside a write path whose hooks have not fired yet
    pending: list[str] = field(default_factory=list)
    # bumps on every committed change to the cycle; see CycleService.gate
    revision: int = 1


@dataclass(frozen=True)
class CycleGate:
    """A cycle and the revision it was read at. Other owners (formation job,
    reveal, chat expiry) read a gate, do their work, then call ``check_gate``
    inside their commit so stale work is dropped instead of published."""

    cycle: WeeklyCycle
    revision: int


class InMemoryCycleRepository:
    """Process-local cycle state. Not durable: a restart loses cycles."""

    def __init__(self) -> None:
        self.lock = threading.RLock()
        self._records: dict[str, CycleRecord] = {}
        self._order: list[str] = []

    def add(self, record: CycleRecord) -> None:
        with self.lock:
            self._records[record.cycle.cycleId] = record
            self._order.append(record.cycle.cycleId)

    def get(self, cycle_id: str) -> CycleRecord | None:
        return self._records.get(cycle_id)

    def for_community(self, community_id: str) -> list[CycleRecord]:
        """Oldest first, by creation order."""
        return [
            self._records[i] for i in self._order if self._records[i].cycle.communityId == community_id
        ]


def _now() -> datetime:
    return datetime.now(UTC)


class CycleService:
    def __init__(
        self,
        *,
        answers: AnswerStore,
        questions: QuestionPort,
        screen: SafetyScreen,
        clarify: Clarify | None = None,
        guard: TextGuard | None = None,
        hooks: CycleHooks | None = None,
        seed_synthetic: SyntheticSeeder | None = None,
        repository: InMemoryCycleRepository | None = None,
        time_zones: dict[str, str] | None = None,
        clock: Callable[[], datetime] = _now,
    ) -> None:
        self._answers = answers
        self._questions = questions
        self._screen = screen
        self._clarify = clarify
        self._guard = guard
        self._hooks = hooks or NoHooks()
        self._seed = seed_synthetic
        self._repo = repository or InMemoryCycleRepository()
        self._time_zones = time_zones or {}
        self._clock = clock

    # ---- helpers -----------------------------------------------------------
    def _tz(self, record: CycleRecord) -> ZoneInfo:
        return ZoneInfo(record.time_zone)

    def _set(self, record: CycleRecord, **changes: object) -> WeeklyCycle:
        record.cycle = WeeklyCycle.model_validate({**record.cycle.model_dump(), **changes})
        record.revision += 1
        if changes.get("status") == "locked":
            # Patrik's store refuses writes for a locked cycle and starts the
            # 14-day retention clock from this moment.
            mark_locked = getattr(self._answers, "mark_locked", None)
            if callable(mark_locked):
                mark_locked(record.cycle.cycleId, cal.iso(self._clock()))
        return record.cycle

    def _sync(self, record: CycleRecord) -> list[str]:
        """Real-time cycles follow the clock. Demo-timing cycles only move when
        an operator advances them. Returns the transitions made (for hooks)."""
        cycle = record.cycle
        if cycle.demoTiming:
            return []
        now = self._clock()
        events: list[str] = []
        if cycle.status == "open":
            day = cal.clock_day(date.fromisoformat(cycle.weekStart), now, self._tz(record))
            if day != cycle.currentDay:
                self._set(record, currentDay=day)
                events.append("changed")
            if now >= cal.parse_iso(cycle.locksAt):
                self._set(record, status="locked")
                events.append("locked")
        elif cycle.status == "forming" and now >= cal.parse_iso(cycle.revealsAt):
            self._set(record, status="revealed")
            events.append("revealed")
        return events

    def _fire(self, record: CycleRecord, events: list[str]) -> None:
        """Hooks run after the state is committed and outside the lock."""
        if not events:
            return
        try:
            self._hooks.on_changed(record.cycle)
            if "locked" in events:
                self._hooks.on_locked(record.cycle)
            if "revealed" in events:
                self._hooks.on_revealed(record.cycle)
        except CycleError:
            raise
        except Exception:  # noqa: BLE001 - downstream detail must not leak
            raise CycleError("PROVIDER_UNAVAILABLE") from None

    def _load(self, cycle_id: str, session: Session | None = None) -> CycleRecord:
        with self._repo.lock:
            record = self._repo.get(cycle_id)
            # A cycle in another community is indistinguishable from a missing one.
            if record is None or (session and record.cycle.communityId != session.communityId):
                raise CycleError("NOT_FOUND")
            events = record.pending + self._sync(record)
            record.pending = []
        self._fire(record, events)
        return record

    def _phase(self, record: CycleRecord, day: int) -> str:
        """'future' | 'today' | 'past' for a question day."""
        cycle = record.cycle
        if cycle.demoTiming:
            if cycle.status != "open":
                return "past"
            today = cycle.currentDay
        else:
            local = self._clock().astimezone(self._tz(record)).date()
            today = (local - date.fromisoformat(cycle.weekStart)).days + 1
        return "future" if day > today else "today" if day == today else "past"

    def _question(self, record: CycleRecord, day: int) -> DailyQuestion:
        return next(q for q in record.questions if q.day == day)

    def _screen_text(self, text: str) -> str:
        try:
            flag = self._screen(text, "answer")
        except Exception:  # noqa: BLE001 - fail closed; never store unscreened text
            raise CycleError("PROVIDER_UNAVAILABLE") from None
        if flag not in ("none", "distress", "harm"):
            raise CycleError("PROVIDER_UNAVAILABLE")
        return flag

    # ---- CyclePort ---------------------------------------------------------
    def current(self, community_id: str) -> WeeklyCycle:
        """CyclePort.current: the community's most recently created cycle."""
        records = self._repo.for_community(community_id)
        if not records:
            raise CycleError("NOT_FOUND")
        return self._load(records[-1].cycle.cycleId).cycle

    def advance(self, cycle_id: str, to: CycleStatus | DayTarget | dict | None = None) -> WeeklyCycle:
        """CyclePort.advance (operator only; the route enforces the role).

        Forward only, one step at a time: day n -> n+1 while open, then
        locked -> forming -> revealed -> closed. ``to=None`` takes the next step.
        """
        if isinstance(to, dict):
            try:
                to = DayTarget.model_validate(to)
            except ValidationError:
                raise CycleError("INVALID_INPUT") from None
        with self._repo.lock:
            record = self._repo.get(cycle_id)
            if record is None:
                raise CycleError("NOT_FOUND")
            events = self._sync(record)
            cycle = record.cycle
            if to is None:
                if cycle.status == "open" and cycle.currentDay < 5:
                    to = DayTarget(day=cycle.currentDay + 1)
                elif cycle.status == "closed":
                    raise CycleError("INVALID_INPUT")
                else:
                    to = STATUS_ORDER[STATUS_ORDER.index(cycle.status) + 1]
            if isinstance(to, DayTarget):
                if cycle.status != "open":
                    raise CycleError("CYCLE_LOCKED")
                if not cycle.demoTiming or to.day != cycle.currentDay + 1:
                    raise CycleError("INVALID_INPUT")  # real time follows the clock; no skipping
                self._set(record, currentDay=to.day)
                events.append("changed")
            else:
                if to not in STATUS_ORDER:
                    raise CycleError("INVALID_INPUT")
                if STATUS_ORDER.index(to) != STATUS_ORDER.index(cycle.status) + 1:
                    raise CycleError("INVALID_INPUT")  # no backward moves, no skipped states
                self._set(record, status=to)
                events.append(to if to in ("locked", "revealed") else "changed")
        self._fire(record, events)
        return record.cycle

    # ---- gates for other owners --------------------------------------------
    def gate(self, cycle_id: str) -> CycleGate:
        record = self._load(cycle_id)
        with self._repo.lock:
            return CycleGate(cycle=record.cycle, revision=record.revision)

    def check_gate(self, cycle_id: str, revision: int, status: CycleStatus | None = None) -> WeeklyCycle:
        """STALE_REVISION unless the cycle is still at ``revision`` (and, when
        given, in ``status``). The clock is the server's, never the client's."""
        with self._repo.lock:
            record = self._repo.get(cycle_id)
            if record is None:
                raise CycleError("NOT_FOUND")
            record.pending += self._sync(record)
            if record.revision != revision or (status is not None and record.cycle.status != status):
                raise CycleError("STALE_REVISION")
            return record.cycle

    # ---- operator ----------------------------------------------------------
    def create_cycle(self, request: NewCycleRequest) -> WeeklyCycle:
        tz_name = self._time_zones.get(request.communityId, DEFAULT_TIME_ZONE)
        tz = ZoneInfo(tz_name)
        week_start = (
            date.fromisoformat(request.weekStart)
            if request.weekStart
            else cal.week_start_for(self._clock(), tz)
        )
        try:
            locks, reveals, expires = cal.cycle_times(week_start, tz)
        except ValueError:
            raise CycleError("INVALID_INPUT") from None
        cycle_id = f"cycle-{uuid.uuid4().hex}"
        try:
            selected = self._questions.select_week(cycle_id, request.communityId)
            questions = sorted(
                (DailyQuestion.model_validate(q if isinstance(q, dict) else q.model_dump()) for q in selected),
                key=lambda q: q.day,
            )
        except CycleError:
            raise
        except Exception:  # noqa: BLE001
            raise CycleError("PROVIDER_UNAVAILABLE") from None
        if [q.day for q in questions] != [1, 2, 3, 4, 5]:
            raise CycleError("PROVIDER_UNAVAILABLE")
        # The cycle, not the question provider, decides ids and dates.
        questions = [
            q.model_copy(update={"cycleId": cycle_id, "date": cal.day_date(week_start, q.day).isoformat()})
            for q in questions
        ]
        cycle = WeeklyCycle(
            cycleId=cycle_id,
            communityId=request.communityId,
            weekStart=week_start.isoformat(),
            status="open",
            currentDay=1,
            locksAt=cal.iso(locks),
            revealsAt=cal.iso(reveals),
            chatExpiresAt=cal.iso(expires),
            demoTiming=request.demoTiming,
        )
        record = CycleRecord(cycle=cycle, time_zone=tz_name, fixture=request.demoTiming, questions=questions)
        self._repo.add(record)
        events = ["changed"]
        with self._repo.lock:
            events += self._sync(record)
        self._fire(record, events)
        return record.cycle

    def reset(self, cycle_id: str) -> WeeklyCycle:
        """Fixture (demo-timing) cycles only. Never touches sessions or players."""
        with self._repo.lock:
            record = self._repo.get(cycle_id)
            if record is None:
                raise CycleError("NOT_FOUND")
            if not record.fixture:
                raise CycleError("FORBIDDEN")
            self._answers.purge_cycle(cycle_id)
            record.followups.clear()
            record.flagged.clear()
            self._set(record, status="open", currentDay=1)
        self._fire(record, ["changed"])
        return record.cycle

    def synthetic_topup(self, cycle_id: str) -> dict:
        """Add the labeled synthetic week from contracts/fixtures/week-sample.json
        to a fixture cycle. Fixture safety labels are applied directly (the
        distress case is stored flagged), so no model call is made."""
        if self._seed is None:
            raise CycleError("PROVIDER_UNAVAILABLE")
        fixture = json.loads(FIXTURE_WEEK.read_text(encoding="utf-8"))
        with self._repo.lock:
            record = self._repo.get(cycle_id)
            if record is None:
                raise CycleError("NOT_FOUND")
            if not record.fixture:
                raise CycleError("FORBIDDEN")
            cycle = record.cycle
            if cycle.status != "open":
                raise CycleError("CYCLE_LOCKED")
            players = fixture["players"]
            if not all(p.get("isSynthetic") is True for p in players):
                raise CycleError("INVALID_INPUT")
            try:
                self._seed(cycle.communityId, players)
            except Exception:  # noqa: BLE001
                raise CycleError("PROVIDER_UNAVAILABLE") from None
            rows = [(a, "none") for a in fixture["answers"]]
            rows.append((fixture["distressFixture"], fixture["distressFixture"]["expectedFlag"]))
            rows.append((fixture["injectionFixture"], "none"))
            added = 0
            now = cal.iso(self._clock())
            for row, flag in rows:
                day = row["day"]
                if day > cycle.currentDay or self._answers.get(cycle_id, row["playerId"], day):
                    continue
                is_catch_up = bool(row.get("isCatchUp", False)) or day < cycle.currentDay
                answer = DailyAnswer(
                    answerId=f"answer-{uuid.uuid4().hex}",
                    cycleId=cycle_id,
                    day=day,
                    questionId=self._question(record, day).question.questionId,
                    playerId=row["playerId"],
                    text=row["text"],
                    source="text",
                    isCatchUp=is_catch_up,
                    weight=compute_weight(is_catch_up, False),
                    followUpUsed=False,
                    createdAt=now,
                    editedAt=None,
                    deletedAt=None,
                )
                self._answers.save(answer, flag)
                if flag != "none":
                    record.flagged.add(answer.answerId)
                added += 1
            for guess in fixture["guesses"]:
                self._answers.save_guess(
                    PrevalenceGuess(cycleId=cycle_id, playerId=guess["playerId"], percent=guess["percent"])
                )
        return {"label": "Synthetic player", "syntheticPlayers": len(players), "answersAdded": added}

    # ---- player reads ------------------------------------------------------
    def _released_days(self, record: CycleRecord) -> list[int]:
        return [d for d in (1, 2, 3, 4, 5) if self._phase(record, d) != "future"]

    def released_questions(self, session: Session, cycle_id: str) -> list[DailyQuestion]:
        record = self._load(cycle_id, session)
        return [self._question(record, d) for d in self._released_days(record)]

    def my_answers(self, session: Session, cycle_id: str) -> list[DailyAnswer]:
        self._load(cycle_id, session)
        return sorted(self._answers.list_for_player(cycle_id, session.playerId), key=lambda a: a.day)

    def catch_up(self, session: Session, record: CycleRecord) -> CatchUpState:
        cycle = record.cycle
        missed: list[int] = []
        if cycle.status == "open":
            answered = {a.day for a in self._answers.list_for_player(cycle.cycleId, session.playerId)}
            missed = [d for d in (1, 2, 3, 4, 5) if self._phase(record, d) == "past" and d not in answered]
        return CatchUpState(cycleId=cycle.cycleId, missedDays=missed, closesAt=cycle.locksAt)

    def streak(self, session: Session) -> Streak:
        days: list[tuple[str, DayState]] = []
        for record in self._repo.for_community(session.communityId):
            by_day = {a.day: a for a in self._answers.list_for_player(record.cycle.cycleId, session.playerId)}
            for day in self._released_days(record):
                answer = by_day.get(day)
                if answer is not None:
                    state: DayState = "catch_up" if answer.isCatchUp else "on_day"
                elif self._phase(record, day) == "today" and record.cycle.status == "open":
                    state = "pending"
                else:
                    state = "missed"
                days.append((self._question(record, day).date, state))
        days.sort(key=lambda item: item[0])
        current, longest, last = compute_streak(days)
        return Streak(
            playerId=session.playerId,
            communityId=session.communityId,
            current=current,
            longest=longest,
            lastOnDayDate=last,
        )

    def current_view(self, session: Session) -> CurrentCycleResponse:
        cycle = self.current(session.communityId)
        record = self._load(cycle.cycleId, session)
        question = self._question(record, record.cycle.currentDay) if record.cycle.status == "open" else None
        return CurrentCycleResponse(
            cycle=record.cycle,
            question=question,
            streak=self.streak(session),
            catchUp=self.catch_up(session, record),
        )

    # ---- player writes -----------------------------------------------------
    def _writable(self, cycle_id: str, session: Session) -> CycleRecord:
        record = self._load(cycle_id, session)
        if record.cycle.status != "open":
            raise CycleError("CYCLE_LOCKED")
        return record

    def _commit(self, cycle_id: str, session: Session) -> CycleRecord:
        """Call while holding the repository lock, immediately before a write:
        the cycle may have locked while a provider call was in flight."""
        record = self._repo.get(cycle_id)
        if record is None:
            raise CycleError("NOT_FOUND")
        record.pending += self._sync(record)  # hooks fire on the next read
        if record.cycle.status != "open":
            raise CycleError("CYCLE_LOCKED")
        return record

    def submit_answer(self, session: Session, cycle_id: str, request: SubmitAnswerRequest) -> AnswerResponse:
        record = self._writable(cycle_id, session)
        if self._phase(record, request.day) == "future":
            raise CycleError("INVALID_INPUT")
        if self._answers.get(cycle_id, session.playerId, request.day) is not None:
            raise CycleError("STALE_REVISION")
        flag = self._screen_text(request.text)  # provider call: outside the lock
        with self._repo.lock:
            record = self._commit(cycle_id, session)
            phase = self._phase(record, request.day)
            if phase == "future":
                raise CycleError("INVALID_INPUT")
            if self._answers.get(cycle_id, session.playerId, request.day) is not None:
                raise CycleError("STALE_REVISION")
            is_catch_up = phase == "past"
            answer = DailyAnswer(
                answerId=f"answer-{uuid.uuid4().hex}",
                cycleId=cycle_id,
                day=request.day,
                questionId=self._question(record, request.day).question.questionId,
                playerId=session.playerId,  # from the verified session only
                text=request.text,
                source=request.source,
                isCatchUp=is_catch_up,
                weight=compute_weight(is_catch_up, False),
                followUpUsed=False,
                createdAt=cal.iso(self._clock()),
                editedAt=None,
                deletedAt=None,
            )
            self._answers.save(answer, flag)
            if flag != "none":
                record.flagged.add(answer.answerId)
        return AnswerResponse(answer=answer, supportCard=flag != "none")

    def edit_answer(
        self, session: Session, cycle_id: str, day: int, request: EditAnswerRequest
    ) -> AnswerResponse:
        self._writable(cycle_id, session)
        if self._answers.get(cycle_id, session.playerId, day) is None:
            raise CycleError("NOT_FOUND")
        flag = self._screen_text(request.text)
        with self._repo.lock:
            record = self._commit(cycle_id, session)
            existing = self._answers.get(cycle_id, session.playerId, day)
            if existing is None:
                raise CycleError("NOT_FOUND")
            issued = record.followups.get(existing.answerId)
            follow_up_used = existing.followUpUsed or bool(
                request.answersFollowUp and issued is not None and issued.needsFollowup
            )
            answer = existing.model_copy(
                update={
                    "text": request.text,
                    "followUpUsed": follow_up_used,
                    # on-day vs catch-up is fixed by when the answer was first given
                    "weight": compute_weight(existing.isCatchUp, follow_up_used),
                    "editedAt": cal.iso(self._clock()),
                }
            )
            answer = DailyAnswer.model_validate(answer.model_dump())
            self._answers.save(answer, flag)
            if flag != "none":
                record.flagged.add(answer.answerId)
            else:
                record.flagged.discard(answer.answerId)
        return AnswerResponse(answer=answer, supportCard=flag != "none")

    def delete_answer(self, session: Session, cycle_id: str, day: int) -> None:
        self._writable(cycle_id, session)
        with self._repo.lock:
            record = self._commit(cycle_id, session)
            existing = self._answers.get(cycle_id, session.playerId, day)
            if existing is None:
                raise CycleError("NOT_FOUND")
            self._answers.delete(cycle_id, session.playerId, day, cal.iso(self._clock()))
            record.followups.pop(existing.answerId, None)
            record.flagged.discard(existing.answerId)

    def followup(self, session: Session, cycle_id: str, day: int) -> M2Out:
        """At most one Muse follow-up per answer; repeat calls return the same one."""
        record = self._writable(cycle_id, session)
        answer = self._answers.get(cycle_id, session.playerId, day)
        if answer is None:
            raise CycleError("NOT_FOUND")
        none = M2Out(needsFollowup=False, question="")
        issued = record.followups.get(answer.answerId)
        if issued is not None:
            return issued
        # Flagged text never reaches another Muse call; the player sees the support card.
        if answer.answerId in record.flagged or answer.followUpUsed or self._clarify is None:
            return none
        try:
            raw = self._clarify(self._question(record, day).question.text, answer.text)
            result = M2Out.model_validate(raw if isinstance(raw, dict) else raw.model_dump())
        except Exception:  # noqa: BLE001 - provider or schema failure; nothing recorded, retry allowed
            raise CycleError("PROVIDER_UNAVAILABLE") from None
        question = " ".join(result.question.split())
        usable = result.needsFollowup and 0 < len(question) <= 200
        if usable and self._guard is not None:
            try:
                usable = self._guard(question) is True
            except Exception:  # noqa: BLE001 - guard failure fails closed
                usable = False
        result = M2Out(needsFollowup=True, question=question) if usable else none
        with self._repo.lock:
            current = self._answers.get(cycle_id, session.playerId, day)
            if current is None or current.answerId != answer.answerId or current.text != answer.text:
                return none  # stale: the answer changed while Muse was thinking
            return record.followups.setdefault(answer.answerId, result)

    def put_guess(self, session: Session, cycle_id: str, request: GuessRequest) -> PrevalenceGuess:
        self._writable(cycle_id, session)
        guess = PrevalenceGuess(cycleId=cycle_id, playerId=session.playerId, percent=request.percent)
        with self._repo.lock:
            self._commit(cycle_id, session)
            self._answers.save_guess(guess)
        return guess

    def my_guess(self, session: Session, cycle_id: str) -> PrevalenceGuess | None:
        self._load(cycle_id, session)
        return self._answers.get_guess(cycle_id, session.playerId)
