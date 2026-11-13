"""Offline tests for server/cycle. TEST-ONLY fixture adapters; no model, no network.

Run from the repository root:  python -m pytest tests/cycle
"""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from server.cycle import CycleError, CycleService, Session, compute_streak, compute_weight
from server.cycle import calendar as cal
from server.cycle.testing import (
    FixtureAnswerStore,
    FixtureQuestionPort,
    FixtureSeeder,
    fixture_clarify,
    fixture_screen,
)
from server.cycle.wire import (
    WEIGHTS,
    EditAnswerRequest,
    GuessRequest,
    NewCycleRequest,
    SubmitAnswerRequest,
    WeeklyCycle,
)

FIXTURES = Path(__file__).resolve().parents[2] / "contracts" / "fixtures"
COMMUNITY = "community-demo"
MAYA = Session(playerId="p-maya", communityId=COMMUNITY, isOperator=False)
DEV = Session(playerId="p-dev", communityId=COMMUNITY, isOperator=False)
OUTSIDER = Session(playerId="p-else", communityId="community-other", isOperator=False)


class Clock:
    def __init__(self, at: str = "2026-11-09T17:00:00Z") -> None:  # Mon 09:00 PST
        self.now = cal.parse_iso(at)

    def __call__(self) -> datetime:
        return self.now

    def set(self, at: str) -> None:
        self.now = cal.parse_iso(at)


class Hooks:
    def __init__(self) -> None:
        self.events: list[tuple[str, str]] = []

    def on_changed(self, cycle):
        self.events.append(("changed", cycle.status))

    def on_locked(self, cycle):
        self.events.append(("locked", cycle.status))

    def on_revealed(self, cycle):
        self.events.append(("revealed", cycle.status))


class Env:
    def __init__(self, **overrides) -> None:
        self.clock = Clock()
        self.store = FixtureAnswerStore()
        self.hooks = Hooks()
        self.seeder = FixtureSeeder()
        self.clarify_calls: list[tuple[str, str]] = []

        def clarify(question, answer):
            self.clarify_calls.append((question, answer))
            return fixture_clarify(question, answer)

        kwargs = dict(
            answers=self.store,
            questions=FixtureQuestionPort(),
            screen=fixture_screen,
            clarify=clarify,
            hooks=self.hooks,
            seed_synthetic=self.seeder,
            clock=self.clock,
        )
        kwargs.update(overrides)
        self.service = CycleService(**kwargs)

    def new(self, demo: bool = True, week_start: str | None = "2026-11-09") -> WeeklyCycle:
        return self.service.create_cycle(
            NewCycleRequest(communityId=COMMUNITY, demoTiming=demo, weekStart=week_start)
        )

    def submit(self, session, cycle, day, text="Mostly the dining hall with my floor, loud but good", source="text"):
        return self.service.submit_answer(
            session, cycle.cycleId, SubmitAnswerRequest(day=day, text=text, source=source)
        )


def code(excinfo) -> str:
    return excinfo.value.code


# ---- calendar ----------------------------------------------------------------
def test_calendar_matches_contract_fixture():
    fixture = json.loads((FIXTURES / "week-sample.json").read_text())["cycle"]
    cycle = Env().new()
    for key in ("weekStart", "locksAt", "revealsAt", "chatExpiresAt"):
        assert getattr(cycle, key) == fixture[key]
    assert (cycle.status, cycle.currentDay, cycle.demoTiming) == ("open", 1, True)
    assert set(cycle.model_dump()) == set(fixture)  # exact camelCase wire keys


def test_week_start_defaults_to_local_monday_and_must_be_monday():
    env = Env()
    env.clock.set("2026-11-16T07:30:00Z")  # Sunday 23:30 PST -> still the week of Nov 9
    assert env.new(week_start=None).weekStart == "2026-11-09"
    with pytest.raises(CycleError) as exc:
        env.new(week_start="2026-11-10")
    assert code(exc) == "INVALID_INPUT"


def test_questions_are_never_released_for_future_days():
    env = Env()
    cycle = env.new()
    assert [q.day for q in env.service.released_questions(MAYA, cycle.cycleId)] == [1]
    env.service.advance(cycle.cycleId)
    env.service.advance(cycle.cycleId, {"day": 3})
    released = env.service.released_questions(MAYA, cycle.cycleId)
    assert [q.day for q in released] == [1, 2, 3]
    assert released[0].date == "2026-11-09" and released[0].cycleId == cycle.cycleId
    view = env.service.current_view(MAYA)
    assert view.question.day == 3 and view.cycle.currentDay == 3


# ---- state machine -----------------------------------------------------------
def test_full_demo_week_is_forward_only_and_fires_hooks_after_commit():
    env = Env()
    cycle = env.new()
    statuses = []
    for _ in range(8):
        cycle = env.service.advance(cycle.cycleId)
        statuses.append((cycle.status, cycle.currentDay))
    assert statuses == [
        ("open", 2), ("open", 3), ("open", 4), ("open", 5),
        ("locked", 5), ("forming", 5), ("revealed", 5), ("closed", 5),
    ]
    assert ("locked", "locked") in env.hooks.events and ("revealed", "revealed") in env.hooks.events
    with pytest.raises(CycleError) as exc:
        env.service.advance(cycle.cycleId)
    assert code(exc) == "INVALID_INPUT"


@pytest.mark.parametrize("target", ["open", "forming", "revealed", "closed", {"day": 3}, {"day": 1}, {"day": 9}])
def test_no_skipped_or_backward_transitions(target):
    env = Env()
    cycle = env.new()
    with pytest.raises(CycleError) as exc:
        env.service.advance(cycle.cycleId, target)
    assert code(exc) == "INVALID_INPUT"
    assert env.service.current(COMMUNITY).status == "open"


def test_day_cannot_advance_after_lock_and_real_time_cycles_ignore_day_buttons():
    env = Env()
    cycle = env.new()
    for _ in range(5):
        env.service.advance(cycle.cycleId)
    with pytest.raises(CycleError) as exc:
        env.service.advance(cycle.cycleId, {"day": 5})
    assert code(exc) == "CYCLE_LOCKED"
    real = env.new(demo=False)
    with pytest.raises(CycleError) as exc:
        env.service.advance(real.cycleId, {"day": 2})
    assert code(exc) == "INVALID_INPUT"


def test_real_time_cycle_follows_the_community_clock():
    env = Env()
    cycle = env.new(demo=False)
    env.clock.set("2026-11-11T20:00:00Z")  # Wed noon PST
    assert env.service.current(COMMUNITY).currentDay == 3
    env.clock.set("2026-11-14T19:59:00Z")  # Sat 11:59 PST: still open, Friday is "past"
    assert env.service.current(COMMUNITY).status == "open"
    assert env.submit(MAYA, cycle, 5).answer.isCatchUp is True
    env.clock.set("2026-11-14T20:00:00Z")  # Sat 12:00 PST
    assert env.service.current(COMMUNITY).status == "locked"
    assert ("locked", "locked") in env.hooks.events
    with pytest.raises(CycleError) as exc:
        env.submit(DEV, cycle, 5)
    assert code(exc) == "CYCLE_LOCKED"


def test_hook_failure_is_sanitized_and_does_not_undo_the_lock():
    class Broken(Hooks):
        def on_locked(self, cycle):
            raise RuntimeError("queue password=hunter2")

    env = Env(hooks=Broken())
    cycle = env.new()
    for _ in range(4):
        env.service.advance(cycle.cycleId)
    with pytest.raises(CycleError) as exc:
        env.service.advance(cycle.cycleId)
    assert code(exc) == "PROVIDER_UNAVAILABLE" and "hunter2" not in str(exc.value.to_api_error("r"))
    assert env.service.current(COMMUNITY).status == "locked"


# ---- answers -------------------------------------------------------------------
def test_on_day_answer_gets_server_weight_and_session_identity():
    env = Env()
    cycle = env.new()
    answer = env.submit(MAYA, cycle, 1, source="voice").answer
    assert (answer.playerId, answer.isCatchUp, answer.weight, answer.source) == ("p-maya", False, 1.0, "voice")
    assert answer.questionId == "q-routine-meals" and answer.followUpUsed is False
    assert answer.createdAt.endswith("Z") and answer.editedAt is None and answer.deletedAt is None


@pytest.mark.parametrize("extra", [{"weight": 1.1}, {"playerId": "p-dev"}, {"isCatchUp": False}, {"followUpUsed": True}])
def test_client_cannot_supply_server_set_fields(extra):
    with pytest.raises(ValidationError):
        SubmitAnswerRequest.model_validate({"day": 1, "text": "hello there", "source": "text", **extra})


@pytest.mark.parametrize(
    "body",
    [
        {"day": 0, "text": "x", "source": "text"},
        {"day": 6, "text": "x", "source": "text"},
        {"day": "1", "text": "x", "source": "text"},
        {"day": 1, "text": "", "source": "text"},
        {"day": 1, "text": "   ", "source": "text"},
        {"day": 1, "text": "a" * 401, "source": "text"},
        {"day": 1, "text": "x", "source": "upload"},
        {"day": 1, "source": "text"},
    ],
)
def test_invalid_answer_bodies_are_rejected(body):
    with pytest.raises(ValidationError):
        SubmitAnswerRequest.model_validate(body)


def test_future_day_is_rejected_and_catch_up_is_weighted_lower():
    env = Env()
    cycle = env.new()
    with pytest.raises(CycleError) as exc:
        env.submit(MAYA, cycle, 2)
    assert code(exc) == "INVALID_INPUT"
    env.service.advance(cycle.cycleId)
    env.service.advance(cycle.cycleId)  # Wednesday
    assert env.service.current_view(MAYA).catchUp.missedDays == [1, 2]
    late = env.submit(MAYA, cycle, 1).answer
    assert (late.isCatchUp, late.weight) == (True, WEIGHTS["catchUp"])
    view = env.service.current_view(MAYA)
    assert view.catchUp.missedDays == [2] and view.catchUp.closesAt == cycle.locksAt
    with pytest.raises(CycleError) as exc:
        env.submit(MAYA, cycle, 4)
    assert code(exc) == "INVALID_INPUT"


def test_second_submit_for_a_day_conflicts_instead_of_overwriting():
    env = Env()
    cycle = env.new()
    first = env.submit(MAYA, cycle, 1).answer
    with pytest.raises(CycleError) as exc:
        env.submit(MAYA, cycle, 1, text="a different answer entirely")
    assert code(exc) == "STALE_REVISION"
    assert env.service.my_answers(MAYA, cycle.cycleId)[0].text == first.text


def test_answer_edit_delete_and_guess_after_lock_return_cycle_locked():
    env = Env()
    cycle = env.new()
    env.submit(MAYA, cycle, 1)
    env.service.put_guess(MAYA, cycle.cycleId, GuessRequest(percent=12))
    for _ in range(5):
        env.service.advance(cycle.cycleId)
    attempts = [
        lambda: env.submit(DEV, cycle, 1),
        lambda: env.service.edit_answer(MAYA, cycle.cycleId, 1, EditAnswerRequest(text="changed my mind")),
        lambda: env.service.delete_answer(MAYA, cycle.cycleId, 1),
        lambda: env.service.put_guess(MAYA, cycle.cycleId, GuessRequest(percent=90)),
        lambda: env.service.followup(MAYA, cycle.cycleId, 1),
    ]
    for attempt in attempts:
        with pytest.raises(CycleError) as exc:
            attempt()
        assert code(exc) == "CYCLE_LOCKED"
    assert env.service.my_guess(MAYA, cycle.cycleId).percent == 12
    assert len(env.store.answers) == 1
    view = env.service.current_view(MAYA)
    assert view.question is None and view.catchUp.missedDays == []


def test_lock_during_safety_screening_rejects_the_write_at_commit():
    env = Env()
    cycle = env.new()
    for _ in range(4):
        env.service.advance(cycle.cycleId)

    def slow_screen(text, subject_type):
        env.service.advance(cycle.cycleId)  # operator locks while M1 is in flight
        return "none"

    env.service._screen = slow_screen
    with pytest.raises(CycleError) as exc:
        env.submit(MAYA, cycle, 5)
    assert code(exc) == "CYCLE_LOCKED"
    assert env.store.answers == {}


def test_players_only_ever_read_their_own_answers():
    env = Env()
    cycle = env.new()
    env.submit(MAYA, cycle, 1, text="I eat in my room so no one sees me alone")
    assert env.service.my_answers(DEV, cycle.cycleId) == []
    for call in (
        lambda: env.service.edit_answer(DEV, cycle.cycleId, 1, EditAnswerRequest(text="not mine")),
        lambda: env.service.delete_answer(DEV, cycle.cycleId, 1),
        lambda: env.service.followup(DEV, cycle.cycleId, 1),
    ):
        with pytest.raises(CycleError) as exc:
            call()
        assert code(exc) == "NOT_FOUND"
    assert "room" not in json.dumps(env.service.current_view(DEV).model_dump(mode="json"))


def test_another_community_cannot_see_or_write_the_cycle():
    env = Env()
    cycle = env.new()
    for call in (
        lambda: env.service.released_questions(OUTSIDER, cycle.cycleId),
        lambda: env.submit(OUTSIDER, cycle, 1),
        lambda: env.service.put_guess(OUTSIDER, cycle.cycleId, GuessRequest(percent=5)),
        lambda: env.service.current_view(OUTSIDER),
    ):
        with pytest.raises(CycleError) as exc:
            call()
        assert code(exc) == "NOT_FOUND"


def test_edit_keeps_on_day_status_and_delete_allows_a_catch_up_later():
    env = Env()
    cycle = env.new()
    env.submit(MAYA, cycle, 1)
    env.service.advance(cycle.cycleId)
    edited = env.service.edit_answer(MAYA, cycle.cycleId, 1, EditAnswerRequest(text="edited on Tuesday")).answer
    assert (edited.isCatchUp, edited.weight, edited.text) == (False, 1.0, "edited on Tuesday")
    assert edited.editedAt is not None
    env.service.delete_answer(MAYA, cycle.cycleId, 1)
    assert env.service.my_answers(MAYA, cycle.cycleId) == []
    again = env.submit(MAYA, cycle, 1).answer
    assert (again.isCatchUp, again.weight) == (True, 0.6)


def test_guess_is_validated_and_stored_apart_from_answers():
    env = Env()
    cycle = env.new()
    for bad in (-1, 101, 12.5, "50"):
        with pytest.raises(ValidationError):
            GuessRequest.model_validate({"percent": bad})
    env.service.put_guess(MAYA, cycle.cycleId, GuessRequest(percent=12))
    env.service.put_guess(MAYA, cycle.cycleId, GuessRequest(percent=30))
    assert env.service.my_guess(MAYA, cycle.cycleId).percent == 30
    assert env.store.answers == {} and env.service.my_guess(DEV, cycle.cycleId) is None


# ---- safety and follow-up ------------------------------------------------------
def test_flagged_answer_shows_support_card_and_never_reaches_muse_again():
    env = Env()
    cycle = env.new()
    distress = json.loads((FIXTURES / "week-sample.json").read_text())["distressFixture"]
    result = env.submit(MAYA, cycle, 1, text=distress["text"])
    assert result.supportCard is True
    assert env.store.flags[result.answer.answerId] == "distress"
    assert env.service.followup(MAYA, cycle.cycleId, 1).needsFollowup is False
    assert env.clarify_calls == []


def test_screen_failure_fails_closed_without_storing_or_leaking():
    def broken(text, subject_type):
        raise RuntimeError(f"provider echoed: {text}")

    env = Env(screen=broken)
    cycle = env.new()
    with pytest.raises(CycleError) as exc:
        env.submit(MAYA, cycle, 1, text="my private answer")
    assert code(exc) == "PROVIDER_UNAVAILABLE" and exc.value.retryable
    assert "private" not in json.dumps(exc.value.to_api_error("r1")) and exc.value.__cause__ is None
    assert env.store.answers == {}


def test_one_follow_up_per_answer_and_bonus_only_when_the_server_issued_it():
    env = Env()
    cycle = env.new()
    env.submit(MAYA, cycle, 1, text="alone mostly")
    first = env.service.followup(MAYA, cycle.cycleId, 1)
    again = env.service.followup(MAYA, cycle.cycleId, 1)
    assert first.needsFollowup and first == again and len(env.clarify_calls) == 1
    replied = env.service.edit_answer(
        MAYA, cycle.cycleId, 1, EditAnswerRequest(text="alone mostly. by choice, I think", answersFollowUp=True)
    ).answer
    assert (replied.followUpUsed, replied.weight) == (True, WEIGHTS["max"])
    # A long answer gets no follow-up, so claiming the bonus does nothing.
    env.submit(DEV, cycle, 1)
    assert env.service.followup(DEV, cycle.cycleId, 1).needsFollowup is False
    claimed = env.service.edit_answer(
        DEV, cycle.cycleId, 1, EditAnswerRequest(text="claiming a bonus I was not offered", answersFollowUp=True)
    ).answer
    assert (claimed.followUpUsed, claimed.weight) == (False, 1.0)
    assert compute_weight(True, True) == 0.7 and compute_weight(False, True) == 1.1


def test_follow_up_is_dropped_when_guard_rejects_or_muse_output_is_malformed():
    env = Env(guard=lambda text: False)
    cycle = env.new()
    env.submit(MAYA, cycle, 1, text="alone mostly")
    assert env.service.followup(MAYA, cycle.cycleId, 1).needsFollowup is False

    env = Env(clarify=lambda q, a: {"needsFollowup": "yes", "question": 7, "tool": "x"})
    cycle = env.new()
    env.submit(MAYA, cycle, 1, text="alone mostly")
    with pytest.raises(CycleError) as exc:
        env.service.followup(MAYA, cycle.cycleId, 1)
    assert code(exc) == "PROVIDER_UNAVAILABLE"


def test_prompt_injection_text_is_stored_as_data_only():
    env = Env()
    cycle = env.new()
    injection = json.loads((FIXTURES / "week-sample.json").read_text())["injectionFixture"]["text"]
    answer = env.submit(MAYA, cycle, 1, text=injection).answer
    assert (answer.text, answer.weight, answer.playerId) == (injection, 1.0, "p-maya")
    assert env.service.current(COMMUNITY).status == "open"


# ---- streaks -------------------------------------------------------------------
def test_streak_acceptance_fixture_mon_tue_on_day_wed_catch_up():
    env = Env()
    cycle = env.new()
    env.submit(MAYA, cycle, 1)
    assert env.service.streak(MAYA).current == 1
    env.service.advance(cycle.cycleId)
    assert env.service.streak(MAYA).current == 1  # Tuesday still pending
    env.submit(MAYA, cycle, 2)
    env.service.advance(cycle.cycleId)  # Wednesday
    env.service.advance(cycle.cycleId)  # Wednesday ends
    assert env.service.streak(MAYA).current == 0  # missed until caught up
    env.submit(MAYA, cycle, 3)  # catch-up
    streak = env.service.streak(MAYA)
    assert (streak.current, streak.longest, streak.lastOnDayDate) == (2, 2, "2026-11-10")
    env.submit(MAYA, cycle, 4)  # Thursday on the day
    assert env.service.streak(MAYA).current == 3
    assert env.service.streak(DEV).current == 0  # private per player


def test_streak_spans_weekends_and_cycles_and_resets_on_a_missed_day():
    env = Env()
    week1 = env.new()
    for day in range(1, 6):
        if day > 1:
            env.service.advance(week1.cycleId)
        if day >= 4:
            env.submit(MAYA, week1, day)
    for _ in range(4):
        env.service.advance(week1.cycleId)  # lock .. closed
    assert env.service.streak(MAYA).current == 2
    week2 = env.new(week_start="2026-11-16")
    env.submit(MAYA, week2, 1)
    assert env.service.streak(MAYA).current == 3  # Thu, Fri, Mon
    env.service.advance(week2.cycleId)
    env.service.advance(week2.cycleId)  # Tuesday missed entirely
    streak = env.service.streak(MAYA)
    assert (streak.current, streak.longest) == (0, 3)


def test_compute_streak_rules():
    assert compute_streak([]) == (0, 0, None)
    assert compute_streak([("d1", "on_day"), ("d2", "on_day"), ("d3", "catch_up")]) == (2, 2, "d2")
    assert compute_streak([("d1", "on_day"), ("d2", "missed"), ("d3", "on_day"), ("d4", "pending")]) == (1, 1, "d3")
    assert compute_streak([("d1", "catch_up"), ("d2", "catch_up")]) == (0, 0, None)


# ---- operator: reset and synthetic top-up ----------------------------------------
def test_synthetic_topup_is_labeled_weighted_and_keeps_the_distress_flag():
    env = Env()
    cycle = env.new()
    env.service.advance(cycle.cycleId)
    env.service.advance(cycle.cycleId)  # Wednesday, like the fixture
    result = env.service.synthetic_topup(cycle.cycleId)
    assert result == {"label": "Synthetic player", "syntheticPlayers": 8, "answersAdded": 14}
    assert all(p["isSynthetic"] for p in env.seeder.players.values())
    day1 = env.store.get(cycle.cycleId, "p-maya", 1)
    assert (day1.isCatchUp, day1.weight) == (True, 0.6)  # day 1 answered on Wednesday
    assert env.store.get(cycle.cycleId, "p-maya", 3).weight == 1.0
    flagged = env.store.get(cycle.cycleId, "p-ana", 2)
    assert env.store.flags[flagged.answerId] == "distress"
    assert env.service.synthetic_topup(cycle.cycleId)["answersAdded"] == 0  # idempotent
    assert env.store.get_guess(cycle.cycleId, "p-omar").percent == 5


def test_reset_only_touches_fixture_cycles():
    env = Env()
    demo = env.new()
    env.submit(MAYA, demo, 1)
    for _ in range(6):
        env.service.advance(demo.cycleId)
    reset = env.service.reset(demo.cycleId)
    assert (reset.status, reset.currentDay) == ("open", 1) and env.store.answers == {}
    real = env.new(demo=False)
    env.submit(MAYA, real, 1)
    for call in (lambda: env.service.reset(real.cycleId), lambda: env.service.synthetic_topup(real.cycleId)):
        with pytest.raises(CycleError) as exc:
            call()
        assert code(exc) == "FORBIDDEN"
    assert len(env.store.answers) == 1


def test_clock_is_utc_aware():
    assert cal.iso(datetime(2026, 11, 14, 20, 0, tzinfo=UTC)) == "2026-11-14T20:00:00Z"


# ---- gates for other owners (Kai's formation / reveal / expiry) -----------------
def test_gate_revision_detects_any_change_since_it_was_read():
    env = Env()
    cycle = env.new()
    for _ in range(5):
        env.service.advance(cycle.cycleId)
    gate = env.service.gate(cycle.cycleId)
    assert gate.cycle.status == "locked"
    assert env.service.check_gate(cycle.cycleId, gate.revision, "locked").status == "locked"
    with pytest.raises(CycleError) as exc:
        env.service.check_gate(cycle.cycleId, gate.revision, "forming")
    assert code(exc) == "STALE_REVISION"
    env.service.reset(cycle.cycleId)  # operator reset while a formation job is in flight
    for call in (
        lambda: env.service.check_gate(cycle.cycleId, gate.revision),
        lambda: env.service.check_gate(cycle.cycleId, gate.revision, "locked"),
    ):
        with pytest.raises(CycleError) as exc:
            call()
        assert code(exc) == "STALE_REVISION"
    with pytest.raises(CycleError) as exc:
        env.service.check_gate("cycle-missing", 1)
    assert code(exc) == "NOT_FOUND"


def test_lock_tells_the_answer_store_once_with_the_lock_time():
    class LockAwareStore(FixtureAnswerStore):
        def __init__(self):
            super().__init__()
            self.locked = []

        def mark_locked(self, cycle_id, locked_at):
            self.locked.append((cycle_id, locked_at))

    env = Env(answers=LockAwareStore())
    env.store = env.service._answers
    cycle = env.new()
    for _ in range(7):
        env.service.advance(cycle.cycleId)
    assert env.store.locked == [(cycle.cycleId, "2026-11-09T17:00:00Z")]


def test_answered_today_counts_distinct_unflagged_players_for_the_current_day():
    env = Env()
    cycle = env.new()
    assert env.service.answered_today(cycle.cycleId) == 0
    env.submit(MAYA, cycle, 1)
    env.submit(DEV, cycle, 1)
    assert env.service.answered_today(cycle.cycleId) == 2
    # editing never double counts; a flagged edit drops out, an unflagged one returns
    env.service.edit_answer(MAYA, cycle.cycleId, 1, EditAnswerRequest(text="SYNTHETIC SAFETY TEST"))
    assert env.service.answered_today(cycle.cycleId) == 1
    env.service.edit_answer(MAYA, cycle.cycleId, 1, EditAnswerRequest(text="dining hall again"))
    assert env.service.answered_today(cycle.cycleId) == 2
    env.service.delete_answer(DEV, cycle.cycleId, 1)
    assert env.service.answered_today(cycle.cycleId) == 1
    # a new day starts at zero; a catch-up answer counts for its own day, not today
    env.service.advance(cycle.cycleId)
    assert env.service.answered_today(cycle.cycleId) == 0
    env.submit(DEV, cycle, 1)
    assert (env.service.answered_today(cycle.cycleId), env.service.answered_today(cycle.cycleId, 1)) == (0, 2)


def test_answered_today_excludes_flagged_answers_and_resets_with_the_cycle():
    env = Env()
    cycle = env.new()
    env.submit(MAYA, cycle, 1, text="SYNTHETIC SAFETY TEST")
    assert env.service.answered_today(cycle.cycleId) == 0
    env.service.synthetic_topup(cycle.cycleId)
    seeded = env.service.answered_today(cycle.cycleId)
    assert seeded > 0
    env.service.reset(cycle.cycleId)
    assert env.service.answered_today(cycle.cycleId) == 0
    with pytest.raises(CycleError) as excinfo:
        env.service.answered_today("cycle-missing")
    assert code(excinfo) == "NOT_FOUND"
    with pytest.raises(CycleError) as excinfo:
        env.service.answered_today(cycle.cycleId, 6)
    assert code(excinfo) == "INVALID_INPUT"


def test_answered_today_is_zero_once_the_week_locks():
    env = Env()
    cycle = env.new()
    env.submit(MAYA, cycle, 1)
    for _ in range(5):
        env.service.advance(cycle.cycleId)
    assert env.service.current(COMMUNITY).status != "open"
    assert env.service.answered_today(cycle.cycleId) == 0
    assert env.service.answered_today(cycle.cycleId, 1) == 1
