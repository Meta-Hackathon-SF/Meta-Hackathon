"""Post-M2 authorization races over the real HTTPS-composed app.

TEST ONLY synthetic player/answer/model input. The scripted provider is held by
bounded thread events; no ordinary test calls a live model or external endpoint.
"""

import json
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import timedelta
from types import SimpleNamespace

from fastapi.testclient import TestClient

from server.privacy.fixtures import grant_operator

from .runtime_helpers import COMMUNITY, runtime_environment
from .test_runtime import call, join

HELD_QUESTION = "What made your campus routine different this week?"
FRESH_QUESTION = "Which small activity would you like to try next?"


def open_answer(env, client):
    player = join(client, "post-provider player")
    grant_operator(env.privacy_store, player.player_id, COMMUNITY)
    created = call(
        client,
        player,
        "POST",
        "/operator/cycles",
        json={"communityId": COMMUNITY, "weekStart": "2026-11-09", "demoTiming": True},
    )
    assert created.status_code == 201
    cycle_id = created.json()["cycleId"]
    submitted = call(
        client,
        player,
        "POST",
        f"/cycles/{cycle_id}/answers",
        json={"day": 1, "text": "Synthetic campus routines feel familiar", "source": "text"},
    )
    assert submitted.status_code == 202
    return player, cycle_id


@contextmanager
def pending_followup(env, client, player, cycle_id):
    started, release = threading.Event(), threading.Event()

    def held_provider(_payload):
        started.set()
        if not release.wait(10):
            raise RuntimeError("Synthetic M2 wait exceeded its bounded test deadline")
        return {"needsFollowup": True, "question": HELD_QUESTION}

    env.transport.on("clarify", held_provider)
    with ThreadPoolExecutor(max_workers=2) as pool:
        pending = pool.submit(call, client, player, "GET", f"/cycles/{cycle_id}/answers/1/followup")
        try:
            assert started.wait(5), "Synthetic M2 did not begin"
            yield SimpleNamespace(pool=pool, pending=pending, release=release)
        finally:
            release.set()


def assert_no_question(repository, response, status, codes):
    assert response.status_code == status
    assert response.json()["error"]["code"] in codes
    assert HELD_QUESTION not in response.text
    assert "question" not in response.json()
    with repository.transaction() as state:
        # Workflow caches may retain minimized call evidence, never a stale M2.
        assert HELD_QUESTION not in json.dumps(state.records)


def test_held_synthetic_m2_succeeds_when_session_consent_and_cycle_stay_current():
    with runtime_environment() as env, TestClient(env.app, base_url="https://testserver") as client:
        player, cycle_id = open_answer(env, client)
        with pending_followup(env, client, player, cycle_id) as work:
            work.release.set()
            response = work.pending.result(timeout=5)
        assert response.status_code == 200
        assert response.json()["needsFollowup"] is True
        assert response.json()["question"] == HELD_QUESTION


def test_m2_consent_revoked_in_flight_returns_403_without_leaking_or_caching_question():
    with runtime_environment() as env, TestClient(env.app, base_url="https://testserver") as client:
        player, cycle_id = open_answer(env, client)
        current = call(client, player, "GET", "/session").json()["consent"]
        with pending_followup(env, client, player, cycle_id) as work:
            revoke = work.pool.submit(
                call,
                client,
                player,
                "PATCH",
                "/me/consent",
                json={
                    "expectedVersion": current["version"],
                    "matchAnswers": False,
                    "anonymousChat": True,
                    "isAdult": True,
                },
            ).result(timeout=5)
            assert revoke.status_code == 200
            work.release.set()
            response = work.pending.result(timeout=5)
        assert_no_question(env.repository, response, 403, {"CONSENT_REQUIRED", "FORBIDDEN"})

        restored = call(
            client,
            player,
            "PATCH",
            "/me/consent",
            json={
                "expectedVersion": revoke.json()["version"],
                "matchAnswers": True,
                "anonymousChat": True,
                "isAdult": True,
            },
        )
        assert restored.status_code == 200
        env.transport.on(
            "clarify", lambda _payload: {"needsFollowup": True, "question": FRESH_QUESTION}
        )
        retried = call(client, player, "GET", f"/cycles/{cycle_id}/answers/1/followup")
        assert retried.status_code == 200
        assert retried.json()["question"] == FRESH_QUESTION
        assert HELD_QUESTION not in retried.text


def test_m2_cycle_locked_in_flight_returns_conflict_without_question():
    with runtime_environment() as env, TestClient(env.app, base_url="https://testserver") as client:
        player, cycle_id = open_answer(env, client)
        with pending_followup(env, client, player, cycle_id) as work:
            locked = work.pool.submit(
                call,
                client,
                player,
                "POST",
                f"/operator/cycles/{cycle_id}/advance",
                json={"to": "locked"},
            ).result(timeout=5)
            assert locked.status_code == 200
            work.release.set()
            response = work.pending.result(timeout=5)
        assert_no_question(env.repository, response, 409, {"CYCLE_LOCKED", "STALE_REVISION"})


def test_m2_session_expires_in_flight_returns_401_without_question():
    with runtime_environment() as env, TestClient(env.app, base_url="https://testserver") as client:
        player, cycle_id = open_answer(env, client)
        with pending_followup(env, client, player, cycle_id) as work:
            env.clock.now += timedelta(days=8)
            work.release.set()
            response = work.pending.result(timeout=5)
        assert_no_question(env.repository, response, 401, {"UNAUTHENTICATED"})
