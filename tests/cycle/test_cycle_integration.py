"""Cycle service against teammates' real public ports that are on main.

Adam's ``CycleQuestionPort`` (server.planning) is the real implementation, run
offline from his curated bank. Patrik's ``Actor`` is imitated by a local
dataclass with the same attribute names because an Actor can only be created
by his service. Storage, M1 and M2 are still TEST-ONLY fixture adapters.
No model call, no network.
"""

from dataclasses import dataclass

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from server.cycle import CycleError, CycleService, Session
from server.cycle.api import build_router, install_cycle_error_handler
from server.cycle.testing import FixtureAnswerStore, fixture_screen
from server.cycle.wire import NewCycleRequest

planning = pytest.importorskip("server.planning")


def make_service(**overrides) -> CycleService:
    bank = planning.load_default_bank()
    questions = planning.QuestionService(bank, planning.InMemorySelectionStore(), lambda cycle_id: "2026-11-09")
    kwargs = dict(
        answers=FixtureAnswerStore(), questions=planning.CycleQuestionPort(questions), screen=fixture_screen
    )
    kwargs.update(overrides)
    return CycleService(**kwargs)


def test_real_question_port_fills_a_week_and_never_leaks_future_days():
    service = make_service()
    cycle = service.create_cycle(NewCycleRequest(communityId="community-demo", weekStart="2026-11-09"))
    player = Session("p-maya", "community-demo", False)
    released = service.released_questions(player, cycle.cycleId)
    assert [q.day for q in released] == [1]
    assert released[0].cycleId == cycle.cycleId and released[0].date == "2026-11-09"
    assert released[0].question.sensitivity == "low"  # Adam's rule: low-sensitivity Monday
    for _ in range(4):
        service.advance(cycle.cycleId)
    week = service.released_questions(player, cycle.cycleId)
    assert [q.date for q in week] == ["2026-11-09", "2026-11-10", "2026-11-11", "2026-11-12", "2026-11-13"]
    assert len({q.question.questionId for q in week}) == 5
    # A second week for the same community repeats none of the first week's questions.
    next_cycle = service.create_cycle(NewCycleRequest(communityId="community-demo", weekStart="2026-11-16"))
    for _ in range(4):
        service.advance(next_cycle.cycleId)
    second = {q.question.questionId for q in service.released_questions(player, next_cycle.cycleId)}
    assert second.isdisjoint({q.question.questionId for q in week})


@dataclass(frozen=True)
class ActorLike:
    """Same attribute names as server.privacy.service.Actor."""

    player_id: str
    session_id: str
    community_id: str
    is_operator: bool


def test_router_accepts_an_actor_and_checks_consent_before_writes():
    service = make_service()
    cycle = service.create_cycle(NewCycleRequest(communityId="community-demo", weekStart="2026-11-09"))
    revoked: set[str] = set()

    def actor(request: Request):
        name = request.headers.get("X-Test-Actor")
        if name == "junk":
            return {"player_id": "p-forged"}  # not a verified actor object
        if not name:
            raise CycleError("UNAUTHENTICATED")
        return ActorLike(f"p-{name}", f"s-{name}", "community-demo", name == "op")

    def require_consent(who):
        if who.player_id in revoked:
            raise CycleError("CONSENT_REQUIRED")

    app = FastAPI()
    install_cycle_error_handler(app)
    app.include_router(build_router(service, actor, require_consent=require_consent), prefix="/api/v1")
    client = TestClient(app)
    path = f"/api/v1/cycles/{cycle.cycleId}"
    body = {"day": 1, "text": "Mostly the dining hall with my floor", "source": "text"}

    ok = client.post(f"{path}/answers", headers={"X-Test-Actor": "maya"}, json=body)
    assert ok.status_code == 202 and ok.json()["answer"]["playerId"] == "p-maya"
    assert client.post(f"/api/v1/operator/cycles/{cycle.cycleId}/advance", headers={"X-Test-Actor": "maya"}).status_code == 403
    assert client.post(f"/api/v1/operator/cycles/{cycle.cycleId}/advance", headers={"X-Test-Actor": "op"}).json()["currentDay"] == 2
    assert client.get("/api/v1/cycles/current", headers={"X-Test-Actor": "junk"}).status_code == 401

    revoked.add("p-maya")
    for response in (
        client.post(f"{path}/answers", headers={"X-Test-Actor": "maya"}, json={**body, "day": 2}),
        client.patch(f"{path}/answers/1", headers={"X-Test-Actor": "maya"}, json={"text": "changed"}),
        client.put(f"{path}/guess", headers={"X-Test-Actor": "maya"}, json={"percent": 10}),
        client.get(f"{path}/answers/1/followup", headers={"X-Test-Actor": "maya"}),
    ):
        assert response.status_code == 403 and response.json()["error"]["code"] == "CONSENT_REQUIRED"
    # Reading and deleting your own answer still work after revocation.
    assert len(client.get(f"{path}/answers", headers={"X-Test-Actor": "maya"}).json()) == 1
    assert client.delete(f"{path}/answers/1", headers={"X-Test-Actor": "maya"}).status_code == 204
