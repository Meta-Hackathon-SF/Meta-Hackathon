"""HTTP tests for server/cycle/api.py behind a TEST-ONLY session dependency.

The header-based session below stands in for Patrik's verified session and
exists only in this test file. No model, no network.
"""

import json

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from server.cycle import CycleError, CycleService, Session
from server.cycle.api import build_router, install_cycle_error_handler
from server.cycle.testing import (
    FixtureAnswerStore,
    FixtureQuestionPort,
    FixtureSeeder,
    fixture_clarify,
    fixture_screen,
)
from server.voice import FixtureTranscriber

SESSIONS = {
    "maya": Session("p-maya", "community-demo", False),
    "dev": Session("p-dev", "community-demo", False),
    "op": Session("p-op", "community-demo", True),
    "other-op": Session("p-op2", "community-other", True),
}
WEBM = b"\x1a\x45\xdf\xa3" + b"\x00" * 64


def fake_session_for_tests(request: Request) -> Session:
    session = SESSIONS.get(request.headers.get("X-Test-Session", ""))
    if session is None:
        raise CycleError("UNAUTHENTICATED")
    return session


def make_client(transcriber=None) -> TestClient:
    service = CycleService(
        answers=FixtureAnswerStore(),
        questions=FixtureQuestionPort(),
        screen=fixture_screen,
        clarify=fixture_clarify,
        seed_synthetic=FixtureSeeder(),
    )
    app = FastAPI()
    install_cycle_error_handler(app)
    app.include_router(build_router(service, fake_session_for_tests, transcriber=transcriber), prefix="/api/v1")
    return TestClient(app)


def as_(name: str) -> dict:
    return {"X-Test-Session": name}


@pytest.fixture
def client() -> TestClient:
    return make_client()


@pytest.fixture
def cycle(client) -> dict:
    response = client.post(
        "/api/v1/operator/cycles",
        headers=as_("op"),
        json={"communityId": "community-demo", "weekStart": "2026-11-09"},
    )
    assert response.status_code == 201
    return response.json()


def assert_error(response, status: int, code: str) -> None:
    assert response.status_code == status
    body = response.json()
    assert set(body) == {"error"} and set(body["error"]) == {"code", "message", "requestId", "retryable"}
    assert body["error"]["code"] == code
    assert response.headers["X-Request-Id"] == body["error"]["requestId"]


def test_happy_path_answer_followup_guess(client, cycle):
    cid = cycle["cycleId"]
    current = client.get("/api/v1/cycles/current", headers=as_("maya")).json()
    assert set(current) == {"cycle", "question", "streak", "catchUp"}
    assert current["cycle"]["demoTiming"] is True and current["question"]["day"] == 1
    assert current["streak"] == {
        "playerId": "p-maya", "communityId": "community-demo", "current": 0, "longest": 0, "lastOnDayDate": None,
    }
    submitted = client.post(
        f"/api/v1/cycles/{cid}/answers", headers=as_("maya"), json={"day": 1, "text": "alone mostly", "source": "text"}
    )
    assert submitted.status_code == 202
    answer = submitted.json()["answer"]
    assert set(answer) == {
        "answerId", "cycleId", "day", "questionId", "playerId", "text", "source", "isCatchUp",
        "weight", "followUpUsed", "createdAt", "editedAt", "deletedAt",
    }
    assert answer["weight"] == 1.0 and answer["playerId"] == "p-maya" and submitted.json()["supportCard"] is False
    followup = client.get(f"/api/v1/cycles/{cid}/answers/1/followup", headers=as_("maya")).json()
    assert followup["needsFollowup"] is True
    edited = client.patch(
        f"/api/v1/cycles/{cid}/answers/1", headers=as_("maya"),
        json={"text": "alone mostly, by choice", "answersFollowUp": True},
    ).json()["answer"]
    assert edited["followUpUsed"] is True and edited["weight"] == 1.1
    guess = client.put(f"/api/v1/cycles/{cid}/guess", headers=as_("maya"), json={"percent": 12})
    assert guess.json() == {"cycleId": cid, "playerId": "p-maya", "percent": 12}
    assert client.get("/api/v1/cycles/current", headers=as_("maya")).json()["streak"]["current"] == 1
    assert client.delete(f"/api/v1/cycles/{cid}/answers/1", headers=as_("maya")).status_code == 204
    assert client.get(f"/api/v1/cycles/{cid}/answers", headers=as_("maya")).json() == []


def test_unauthenticated_and_non_operator_are_rejected(client, cycle):
    cid = cycle["cycleId"]
    assert_error(client.get("/api/v1/cycles/current"), 401, "UNAUTHENTICATED")
    for path in ("advance", "reset", "synthetic-topup"):
        assert_error(client.post(f"/api/v1/operator/cycles/{cid}/{path}", headers=as_("maya")), 403, "FORBIDDEN")
    assert_error(
        client.post("/api/v1/operator/cycles", headers=as_("maya"), json={"communityId": "community-demo"}),
        403, "FORBIDDEN",
    )
    # An operator of another community cannot create here or touch this cycle.
    assert_error(
        client.post("/api/v1/operator/cycles", headers=as_("other-op"), json={"communityId": "community-demo"}),
        403, "FORBIDDEN",
    )
    assert_error(client.post(f"/api/v1/operator/cycles/{cid}/advance", headers=as_("other-op")), 404, "NOT_FOUND")


@pytest.mark.parametrize(
    "body",
    [
        {"day": 1, "text": "hello there", "source": "text", "weight": 1.1},
        {"day": 1, "text": "hello there", "source": "text", "playerId": "p-dev"},
        {"day": 1, "text": "hello there", "source": "text", "isCatchUp": False},
        {"day": 1, "text": "a" * 401, "source": "text"},
        {"day": 7, "text": "hello there", "source": "text"},
        [],
        "not json",
    ],
)
def test_bad_bodies_return_invalid_input_without_echo(client, cycle, body):
    raw = body if isinstance(body, str) else json.dumps(body)
    response = client.post(
        f"/api/v1/cycles/{cycle['cycleId']}/answers", headers={**as_("maya"), "Content-Type": "application/json"},
        content=raw,
    )
    assert_error(response, 400, "INVALID_INPUT")
    assert "hello there" not in response.text
    assert client.get(f"/api/v1/cycles/{cycle['cycleId']}/answers", headers=as_("maya")).json() == []


def test_forged_identity_never_writes_for_someone_else(client, cycle):
    cid = cycle["cycleId"]
    client.post(f"/api/v1/cycles/{cid}/answers", headers=as_("maya"),
                json={"day": 1, "text": "I eat in my room so no one sees me alone", "source": "text"})
    forged = client.post(f"/api/v1/cycles/{cid}/answers?playerId=p-maya", headers=as_("dev"),
                         json={"day": 1, "text": "this is dev speaking for dev", "source": "text"})
    assert forged.json()["answer"]["playerId"] == "p-dev"
    dev_view = client.get(f"/api/v1/cycles/{cid}/answers", headers=as_("dev")).text
    assert "my room" not in dev_view
    assert_error(client.get(f"/api/v1/cycles/{cid}/answers/2/followup", headers=as_("dev")), 404, "NOT_FOUND")
    assert_error(client.patch(f"/api/v1/cycles/{cid}/answers/9", headers=as_("dev"), json={"text": "x"}), 400, "INVALID_INPUT")


def test_operator_runs_a_week_and_writes_lock(client, cycle):
    cid = cycle["cycleId"]
    assert_error(
        client.post(f"/api/v1/cycles/{cid}/answers", headers=as_("maya"), json={"day": 3, "text": "too early", "source": "text"}),
        400, "INVALID_INPUT",
    )
    assert client.post(f"/api/v1/operator/cycles/{cid}/advance", headers=as_("op")).json()["currentDay"] == 2
    topup = client.post(f"/api/v1/operator/cycles/{cid}/synthetic-topup", headers=as_("op")).json()
    assert topup["label"] == "Synthetic player" and topup["answersAdded"] > 0
    released = client.get(f"/api/v1/cycles/{cid}/questions", headers=as_("maya")).json()
    assert [q["day"] for q in released] == [1, 2]
    assert_error(
        client.post(f"/api/v1/operator/cycles/{cid}/advance", headers=as_("op"), json={"to": "revealed"}),
        400, "INVALID_INPUT",
    )
    for expected in ({"day": 3}, {"day": 4}, {"day": 5}, "locked"):
        response = client.post(f"/api/v1/operator/cycles/{cid}/advance", headers=as_("op"), json={"to": expected})
        assert response.status_code == 200
    assert response.json()["status"] == "locked"
    assert_error(
        client.post(f"/api/v1/cycles/{cid}/answers", headers=as_("dev"), json={"day": 5, "text": "after the lock", "source": "text"}),
        409, "CYCLE_LOCKED",
    )
    assert_error(client.put(f"/api/v1/cycles/{cid}/guess", headers=as_("dev"), json={"percent": 3}), 409, "CYCLE_LOCKED")
    assert client.post(f"/api/v1/operator/cycles/{cid}/reset", headers=as_("op")).json()["status"] == "open"


def test_voice_route_is_honest_when_unconfigured_and_labeled_in_fixture_mode(client):
    headers = {**as_("maya"), "Content-Type": "audio/webm;codecs=opus"}
    assert_error(client.post("/api/v1/voice/transcribe", headers=headers, content=WEBM), 503, "PROVIDER_UNAVAILABLE")
    assert_error(
        client.post("/api/v1/voice/transcribe", headers={**as_("maya"), "Content-Type": "text/plain"}, content=b"hi"),
        400, "INVALID_INPUT",
    )
    assert_error(client.post("/api/v1/voice/transcribe", headers={"Content-Type": "audio/webm"}, content=WEBM), 401, "UNAUTHENTICATED")
    fixture = make_client(FixtureTranscriber()).post("/api/v1/voice/transcribe", headers=headers, content=WEBM)
    assert fixture.status_code == 200 and fixture.json()["mode"] == "fixture"
    assert fixture.json()["transcript"].startswith("Synthetic transcript")
