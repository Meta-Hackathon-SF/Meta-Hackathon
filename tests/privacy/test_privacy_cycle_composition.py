"""Patrik's real AnswerStore + seed_players behind Will's real CycleService.

Composition check only: Will's and Adam's public code on main is imported the
way Kai's composition root would wire it. Will's M1 screen here is his own
labeled TEST-ONLY fixture screen (task 4 replaces it). No model call.
"""

from __future__ import annotations

import pytest

from privacy_helpers import COMMUNITY, consent_req, joined
from server.privacy.answers import AnswerStore
from server.privacy.fixtures import seed_players

cycle_mod = pytest.importorskip("server.cycle")
planning = pytest.importorskip("server.planning")
from server.cycle import CycleService, Session  # noqa: E402
from server.cycle.testing import fixture_screen  # noqa: E402  (Will's TEST-ONLY M1 stand-in)
from server.cycle.wire import (  # noqa: E402
    DailyAnswer,
    EditAnswerRequest,
    GuessRequest,
    NewCycleRequest,
    PrevalenceGuess,
    SubmitAnswerRequest,
)


class LockHooks:
    """What Kai's on_locked sink must do for privacy: start retention + freeze."""

    def __init__(self, answers: AnswerStore):
        self.answers = answers

    def on_changed(self, cycle): ...

    def on_locked(self, cycle):
        self.answers.mark_locked(cycle.cycleId, cycle.locksAt)

    def on_revealed(self, cycle): ...


@pytest.fixture
def env(store, service):
    answers = AnswerStore(store, service, answer_model=DailyAnswer, guess_model=PrevalenceGuess)
    bank = planning.load_default_bank()
    questions = planning.QuestionService(bank, planning.InMemorySelectionStore(), lambda cycle_id: "2026-11-09")
    cycles = CycleService(
        answers=answers,
        questions=planning.CycleQuestionPort(questions),
        screen=fixture_screen,
        hooks=LockHooks(answers),
        seed_synthetic=lambda community_id, players: seed_players(store, community_id, players),
    )
    cycle = cycles.create_cycle(NewCycleRequest(communityId=COMMUNITY, demoTiming=True, weekStart="2026-11-09"))
    return answers, cycles, cycle


def session_for(actor) -> Session:
    return Session(playerId=actor.player_id, communityId=actor.community_id, isOperator=actor.is_operator)


def test_answer_lifecycle_through_will_service(env, service):
    answers, cycles, cycle = env
    _, actor = joined(service, "Maya")
    me = session_for(actor)
    cycles.submit_answer(me, cycle.cycleId, SubmitAnswerRequest(day=1, text="Dining hall with my floor", source="text"))
    mine = cycles.my_answers(me, cycle.cycleId)
    assert [type(a) for a in mine] == [DailyAnswer]  # Will's own camelCase model back
    assert mine[0].text == "Dining hall with my floor" and mine[0].weight == 1.0
    cycles.edit_answer(me, cycle.cycleId, 1, EditAnswerRequest(text="Dining hall, loud but good"))
    edited = cycles.my_answers(me, cycle.cycleId)[0]
    assert edited.text == "Dining hall, loud but good" and edited.editedAt is not None
    assert answers.get(cycle.cycleId, actor.player_id, 1).answerId == mine[0].answerId
    cycles.put_guess(me, cycle.cycleId, GuessRequest(percent=30))
    assert cycles.my_guess(me, cycle.cycleId).percent == 30
    cycles.delete_answer(me, cycle.cycleId, 1)
    assert cycles.my_answers(me, cycle.cycleId) == []


def test_revoked_consent_blocks_submit_through_will_service(env, service):
    _, cycles, cycle = env
    _, actor = joined(service, "Dev")
    service.update_consent(actor, consent_req(1, chat=False))
    with pytest.raises(Exception) as e:
        cycles.submit_answer(session_for(actor), cycle.cycleId, SubmitAnswerRequest(day=1, text="hello there", source="text"))
    assert getattr(e.value, "code", None) == "CONSENT_REQUIRED"


def test_synthetic_topup_then_lock_freezes_and_filters(env, service):
    answers, cycles, cycle = env
    _, actor = joined(service, "Real player")
    cycles.submit_answer(session_for(actor), cycle.cycleId,
                         SubmitAnswerRequest(day=1, text="Eating alone most nights", source="text"))
    cycles.synthetic_topup(cycle.cycleId)
    rows = answers.eligible_answers(cycle.cycleId)
    assert {r["player_id"] for r in rows} >= {actor.player_id, "p-maya"}
    assert all("SYNTHETIC SAFETY TEST" not in r["text"] for r in rows)
    cycles.advance(cycle.cycleId, "locked")
    with pytest.raises(Exception) as e:
        answers.save_guess({"cycleId": cycle.cycleId, "playerId": actor.player_id, "percent": 5})
    assert getattr(e.value, "code", None) == "CYCLE_LOCKED"



def test_real_m1_screen_flags_distress_through_will_service(store, service):
    providers = pytest.importorskip("server.providers")
    from server.privacy.safety import SafetyScreener, register_safety_task
    from server.providers.fixture import FixtureMuse, ScriptedTransport

    muse = FixtureMuse(register_safety_task(providers.TaskRegistry()),
                       ScriptedTransport().on("safety_screen", lambda inp: {"flag": "none", "reason": "ok"}))
    answers = AnswerStore(store, service, answer_model=DailyAnswer, guess_model=PrevalenceGuess)
    bank = planning.load_default_bank()
    questions = planning.QuestionService(bank, planning.InMemorySelectionStore(), lambda cycle_id: "2026-11-09")
    cycles = CycleService(answers=answers, questions=planning.CycleQuestionPort(questions),
                          screen=SafetyScreener(muse).sync_screen())
    cycle = cycles.create_cycle(NewCycleRequest(communityId=COMMUNITY, demoTiming=True, weekStart="2026-11-09"))
    _, ok_player = joined(service, "Ok player")
    _, crisis_player = joined(service, "Crisis player")
    cycles.submit_answer(session_for(ok_player), cycle.cycleId,
                         SubmitAnswerRequest(day=1, text="Dining hall with my floor", source="text"))
    cycles.submit_answer(session_for(crisis_player), cycle.cycleId,
                         SubmitAnswerRequest(day=1, text="SYNTHETIC SAFETY TEST: I want to die", source="text"))
    assert [r["player_id"] for r in answers.eligible_answers(cycle.cycleId)] == [ok_player.player_id]
