"""TEST ONLY operator M7 composition using real owner services, scripted Muse.

No live calls or production persistence claim. PostgreSQL repository checks live
in test_storage; these cases exercise authorization and atomic publication.
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from server.privacy.fixtures import grant_operator, seed_community
from server.privacy.wire import UpdateConsentRequest
from server.providers.fixture import decode_user_message

from .runtime_helpers import runtime_environment
from .test_runtime import assert_private_fields_absent, call, join, revealed


def proposal(env):
    return {
        "title": "A short cafe break",
        "placeId": "v-cafe",
        "timeWindow": {
            "start": (env.clock() + timedelta(hours=1)).isoformat().replace("+00:00", "Z"),
            "end": (env.clock() + timedelta(hours=2)).isoformat().replace("+00:00", "Z"),
        },
        "why": "Drop by for a relaxed conversation.",
    }


def post(client, player, room_id):
    return call(client, player, "POST", f"/operator/rooms/{room_id}/nudge", json={})


def m7_calls(env):
    return [
        decode_user_message(c.user)["input"]
        for c in env.transport.calls
        if decode_user_message(c.user)["task"] == "event_nudge"
    ]


def messages(env, room_id):
    with env.repository.transaction() as state:
        return list(state.chat.rooms[room_id].messages.values())


def test_operator_nudge_posts_once_through_real_m1_guard_chat_and_replays():
    with runtime_environment() as env, TestClient(env.app, base_url="https://testserver") as client:
        players, _, _, room = revealed(env, client)
        env.transport.on("event_nudge", lambda _: proposal(env))
        first = post(client, players[0], room)
        assert first.status_code == 200, first.json()
        assert first.json()["evidence"]["source"] == "replay"
        assert first.json()["minAttendees"] == 3
        assert_private_fields_absent(first.json())
        second = post(client, players[0], room)
        assert second.status_code == 200 and second.json() == first.json()
        assert len(m7_calls(env)) == 1
        assert set(m7_calls(env)[0]) == {"sharedMeaning", "venues", "window", "campusEvents"}
        assert "Synthetic private submission" not in str(m7_calls(env))
        saved = messages(env, room)
        assert len(saved) == 1 and saved[0].kind == "muse_nudge"
        assert saved[0].handle == "Muse" and saved[0].moderation == "visible"
        env.clock.now += timedelta(days=14)
        env.app.state.runtime.purge_retention()
        with env.repository.transaction() as state:
            assert not state.records.get("nudges")


def test_nudge_rejects_non_operator_unknown_room_and_cross_group_before_model():
    with runtime_environment() as env, TestClient(env.app, base_url="https://testserver") as client:
        players, _, _, room = revealed(env, client)
        assert post(client, players[1], room).status_code == 403
        assert post(client, players[0], "unknown-synthetic-room").status_code == 404
        seed_community(env.privacy_store, "synthetic-other-group", "Synthetic other Group")
        other = join(client, "other operator", community="synthetic-other-group")
        grant_operator(env.privacy_store, other.player_id, other.community)
        assert post(client, other, room).status_code == 404
        assert m7_calls(env) == [] and messages(env, room) == []


@pytest.mark.parametrize("boundary", ["M7", "M1"])
def test_nudge_rechecks_operator_session_after_each_model_boundary(boundary):
    with runtime_environment() as env, TestClient(env.app, base_url="https://testserver") as client:
        players, _, _, room = revealed(env, client)
        actor = env.app.state.privacy.require_session(players[0].token)

        def propose(_):
            if boundary == "M7":
                env.app.state.privacy.end_session(actor)
            return proposal(env)

        def screen(_):
            if boundary == "M1":
                env.app.state.privacy.end_session(actor)
            return {"flag": "none", "reason": "synthetic fixture"}

        env.transport.on("event_nudge", propose)
        env.transport.on("safety_screen", screen)
        result = post(client, players[0], room)
        assert result.status_code == 401, result.json()
        assert messages(env, room) == []


def test_nudge_consent_change_during_m7_invalidates_private_formation():
    with runtime_environment() as env, TestClient(env.app, base_url="https://testserver") as client:
        players, _, _, room = revealed(env, client)
        actor = env.app.state.privacy.require_session(players[1].token)

        def propose(_):
            env.app.state.privacy.update_consent(
                actor,
                UpdateConsentRequest(
                    expectedVersion=1,
                    matchAnswers=False,
                    anonymousChat=True,
                    isAdult=True,
                ),
            )
            return proposal(env)

        env.transport.on("event_nudge", propose)
        response = post(client, players[0], room)
        assert response.status_code == 409, response.json()
        assert response.json()["error"]["code"] == "STALE_REVISION"
        assert messages(env, room) == []
        with env.repository.transaction() as state:
            assert state.records.get("nudges", {}) == {}


@pytest.mark.parametrize("unsafe", ["answer", "meaning", "venue", "safety"])
def test_nudge_unsafe_model_content_never_reaches_output(unsafe):
    with runtime_environment() as env, TestClient(env.app, base_url="https://testserver") as client:
        players, cycle, _, room = revealed(env, client)
        if unsafe == "meaning":
            with env.repository.transaction() as state:
                state.records["formations"][cycle]["result"]["constellations"][0][
                    "sharedMeaning"
                ] = "Private meaning with six secret words"

        def propose(ctx):
            value = proposal(env)
            if unsafe == "answer":
                value["why"] = "Synthetic private submission number 1 for this week"
            elif unsafe == "meaning":
                value["why"] = ctx["sharedMeaning"]
            elif unsafe == "venue":
                value["placeId"] = "unapproved-private-place"
            return value

        env.transport.on("event_nudge", propose)
        if unsafe == "safety":
            env.transport.on("safety_screen", lambda _: {"flag": "harm", "reason": "synthetic"})
        response = post(client, players[0], room)
        assert response.status_code in {422, 503}, response.json()
        assert "Synthetic private submission" not in response.text
        assert "six secret words" not in response.text
        assert messages(env, room) == []


@pytest.mark.parametrize("field", ["cycleId", "formationVersion"])
def test_saved_nudge_from_another_cycle_or_formation_fails_closed(field):
    with runtime_environment() as env, TestClient(env.app, base_url="https://testserver") as client:
        players, _, _, room = revealed(env, client)
        env.transport.on("event_nudge", lambda _: proposal(env))
        assert post(client, players[0], room).status_code == 200
        with env.repository.transaction() as state:
            row = next(iter(state.records["nudges"].values()))
            row[field] = "synthetic-stale-value"
        result = post(client, players[0], room)
        assert result.status_code == 409
        assert len(messages(env, room)) == 1 and len(m7_calls(env)) == 1


def test_post_crash_retries_the_same_chat_command_without_duplicate(monkeypatch):
    with (
        runtime_environment() as env,
        TestClient(
            env.app,
            base_url="https://testserver",
            raise_server_exceptions=False,
        ) as client,
    ):
        players, _, _, room = revealed(env, client)
        env.transport.on("event_nudge", lambda _: proposal(env))
        nudges = env.app.state.nudges
        original = nudges.mark_posted

        def crash(*_args):
            raise RuntimeError("synthetic crash after guarded post")

        monkeypatch.setattr(nudges, "mark_posted", crash)
        assert post(client, players[0], room).status_code == 503
        assert len(messages(env, room)) == 1
        monkeypatch.setattr(nudges, "mark_posted", original)
        assert post(client, players[0], room).status_code == 200
        assert len(messages(env, room)) == 1 and len(m7_calls(env)) == 1


def test_concurrent_operator_buttons_cannot_publish_distinct_nudges():
    with runtime_environment() as env, TestClient(env.app, base_url="https://testserver") as client:
        players, _, _, room = revealed(env, client)
        env.transport.delay_s = 0.03
        count = []

        def propose(_):
            count.append(True)
            value = proposal(env)
            value["title"] = "A short cafe break" if len(count) == 1 else "A relaxed cafe stop"
            return value

        env.transport.on("event_nudge", propose)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: post(client, players[0], room), range(2)))
        assert any(r.status_code == 200 for r in results), [r.json() for r in results]
        assert all(r.status_code in {200, 409} for r in results)
        assert len(messages(env, room)) == 1
