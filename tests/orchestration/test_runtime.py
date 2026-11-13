"""HTTP integration of actual owner ports over synthetic transport/test storage.

No live provider call. These checks prove the composed path and safety gates,
not semantic matching quality, deployment, or PostgreSQL durability.
"""

import asyncio
import json
from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient

from server.orchestration.api import event_stream
from server.privacy.fixtures import grant_operator, seed_community
from server.providers.fixture import decode_user_message

from .runtime_helpers import COMMUNITY, runtime_environment


def test_composition_uses_approved_router_without_live_calls(monkeypatch):
    from server.app.config import Settings
    from server.app.weekly import build_weekly_app
    from server.privacy import PrivacyStore
    from server.providers import MuseRouter
    from tests.orchestration.storage_adapter import TestWorkflowRepository

    monkeypatch.setattr("server.app.weekly.load_muse_config", lambda: None)
    repository = TestWorkflowRepository()
    privacy_store = PrivacyStore(":memory:")
    try:
        app = build_weekly_app(
            repository=repository,
            privacy_store=privacy_store,
            settings=Settings(environment="test"),
            start_worker=False,
        )
        router = app.state.muse.muse
        assert isinstance(router, MuseRouter)
        assert router.route_for("safety_screen").model == "muse-ember-1.0"
        assert not router.configured
    finally:
        repository.close()
        privacy_store.close()

    with runtime_environment() as env:
        assert not isinstance(env.app.state.muse.muse, MuseRouter)


def test_composition_registers_activity_and_sensitivity_tasks():
    with runtime_environment() as env:
        registry = env.app.state.muse.muse._registry
        assert registry.get("activity_classification", "activity_classification.v1")
        assert registry.get("sensitivity_screen", "sensitivity_screen.v1")


class SyntheticPlayer(SimpleNamespace):
    def __repr__(self):
        return "<SyntheticPlayer>"


def join(client, label, community=COMMUNITY):
    client.cookies.clear()
    response = client.post(
        f"/api/v1/communities/{community}/join",
        headers={"Idempotency-Key": "join-" + uuid4().hex},
        json={
            "displayName": "Synthetic " + label,
            "matchAnswers": True,
            "anonymousChat": True,
            "isAdult": True,
        },
    )
    assert response.status_code == 201
    token = client.cookies.get("cst_session")
    client.cookies.clear()
    return SyntheticPlayer(
        player_id=response.json()["player"]["playerId"],
        token=token,
        name=response.json()["player"]["displayName"],
        community=community,
    )


def call(client, player, method, path, *, key=None, **kwargs):
    headers = {"Authorization": "Bearer " + player.token}
    if method.upper() in {"POST", "PUT", "PATCH", "DELETE"}:
        headers["Idempotency-Key"] = key or uuid4().hex
    headers.update(kwargs.pop("headers", {}))
    return client.request(method, "/api/v1" + path, headers=headers, **kwargs)


def assert_private_fields_absent(value):
    forbidden = {"answers", "memberIds", "sharedMeaning", "weight", "playerId", "reporterId"}
    if isinstance(value, dict):
        assert not (set(value) & forbidden)
        for item in value.values():
            assert_private_fields_absent(item)
    elif isinstance(value, list):
        for item in value:
            assert_private_fields_absent(item)


def prepare_locked(env, client):
    players = [join(client, f"player {index}") for index in range(3)]
    grant_operator(env.privacy_store, players[0].player_id, COMMUNITY)
    response = call(
        client,
        players[0],
        "POST",
        "/operator/cycles",
        json={"communityId": COMMUNITY, "weekStart": "2026-11-09", "demoTiming": True},
    )
    assert response.status_code == 201
    cycle_id = response.json()["cycleId"]
    for index, player in enumerate(players):
        response = call(
            client,
            player,
            "POST",
            f"/cycles/{cycle_id}/answers",
            json={
                "day": 1,
                "text": f"Synthetic private submission number {index} for this week",
                "source": "text",
            },
        )
        assert response.status_code == 202
        assert response.json()["answer"]["playerId"] == player.player_id
        response = call(client, player, "PUT", f"/cycles/{cycle_id}/guess", json={"percent": 25})
        assert response.status_code == 200
    response = call(
        client, players[0], "POST", f"/operator/cycles/{cycle_id}/advance", json={"to": "locked"}
    )
    assert response.status_code == 200
    return players, cycle_id


def formed(env, client):
    players, cycle_id = prepare_locked(env, client)
    response = call(
        client, players[0], "POST", f"/operator/cycles/{cycle_id}/form", key="form-once", json={}
    )
    assert response.status_code == 202
    job_id = response.json()["jobId"]
    response = call(client, players[0], "GET", f"/jobs/{job_id}")
    assert response.status_code == 200
    assert response.json()["status"] == "succeeded", response.json()
    return players, cycle_id, job_id


def revealed(env, client):
    players, cycle_id, job_id = formed(env, client)
    response = call(
        client, players[0], "POST", f"/operator/cycles/{cycle_id}/advance", json={"to": "revealed"}
    )
    assert response.status_code == 200, response.json()
    response = call(client, players[0], "GET", f"/cycles/{cycle_id}/room")
    assert response.status_code == 200
    return players, cycle_id, job_id, response.json()["roomId"]


def test_formation_uses_released_question_context_and_approved_catalog(monkeypatch):
    import server.app.weekly as weekly
    from server.planning import VenueCatalog

    actual_factory = weekly.build_matching_port
    seen_catalogs = []

    def recording_factory(**kwargs):
        seen_catalogs.append(kwargs["approved_event_ids"])
        return actual_factory(**kwargs)

    monkeypatch.setattr(weekly, "build_matching_port", recording_factory)
    with runtime_environment() as env, TestClient(env.app, base_url="https://testserver") as client:
        formed(env, client)
        payloads = [
            decode_user_message(request.user)["input"]
            for request in env.transport.calls
            if decode_user_message(request.user)["task"] == "constellation_formation"
        ]
        assert payloads and payloads[0]["questions"]
        question_ids = {q["questionId"] for q in payloads[0]["questions"]}
        assert all(answer["questionId"] in question_ids for answer in payloads[0]["answers"])
        approved = VenueCatalog.load().event_ids()
        assert seen_catalogs and all(ids == approved for ids in seen_catalogs)


def test_composed_daily_loop_formation_reveal_chat_sky_and_expiry():
    with runtime_environment() as env, TestClient(env.app, base_url="https://testserver") as client:
        players, cycle_id, job_id = formed(env, client)
        a, b, c = players
        before = call(client, b, "GET", f"/cycles/{cycle_id}/room")
        assert before.status_code == 404
        response = call(
            client,
            b,
            "POST",
            f"/cycles/{cycle_id}/answers",
            json={"day": 2, "text": "Late answer", "source": "text"},
        )
        assert response.status_code == 409 and response.json()["error"]["code"] == "CYCLE_LOCKED"
        response = call(
            client, a, "POST", f"/operator/cycles/{cycle_id}/advance", json={"to": "revealed"}
        )
        assert response.status_code == 200
        rooms = [
            call(client, player, "GET", f"/cycles/{cycle_id}/room").json() for player in players
        ]
        assert len({room["roomId"] for room in rooms}) == 1
        for room in rooms:
            assert sum(member["isSelf"] for member in room["members"]) == 1
            assert_private_fields_absent(room)
        room_id = rooms[0]["roomId"]
        handle_a = next(m["handle"] for m in rooms[0]["members"] if m["isSelf"])
        handle_b = next(m["handle"] for m in rooms[1]["members"] if m["isSelf"])
        response = call(
            client,
            a,
            "POST",
            f"/rooms/{room_id}/messages",
            key="hello",
            json={"text": "A small synthetic hello"},
        )
        assert response.status_code == 200
        message = response.json()
        assert_private_fields_absent(message)
        assert (
            call(
                client,
                a,
                "POST",
                f"/rooms/{room_id}/messages",
                key="hello",
                json={"text": "A small synthetic hello"},
            ).json()
            == message
        )
        visible = call(client, b, "GET", f"/rooms/{room_id}/messages").json()
        assert [m["messageId"] for m in visible] == [message["messageId"]]
        assert_private_fields_absent(visible)
        response = call(
            client, a, "POST", f"/rooms/{room_id}/messages", json={"text": "text me at 555-0100"}
        )
        assert response.status_code == 422
        one = call(
            client,
            a,
            "POST",
            f"/rooms/{room_id}/reveal",
            key="a-reveal",
            json={"toHandle": handle_b},
        )
        assert one.json() == {"result": "pending"}
        assert b.name not in one.text
        reverse = call(
            client,
            b,
            "POST",
            f"/rooms/{room_id}/reveal",
            key="b-reveal",
            json={"toHandle": handle_a},
        )
        assert reverse.json() == {"result": "revealed"}
        assert call(
            client,
            b,
            "POST",
            f"/rooms/{room_id}/reveal",
            key="b-reveal",
            json={"toHandle": handle_a},
        ).json() == {"result": "revealed"}
        actor_a = env.app.state.privacy.require_session(a.token)
        actor_c = env.app.state.privacy.require_session(c.token)
        pair_events = [
            e for e in env.app.state.chat.events(actor_a) if e["type"] == "reveal.mutual"
        ]
        assert len(pair_events) == 1
        assert not any(e["type"] == "reveal.mutual" for e in env.app.state.chat.events(actor_c))
        response = call(client, c, "GET", f"/cycles/{cycle_id}/sky")
        assert response.status_code == 200, response.json()
        sky = response.json()
        assert sky["threshold"] == 3
        assert all(t["count"] >= sky["threshold"] for t in sky["themes"])
        assert_private_fields_absent(sky)
        assert "Synthetic private submission" not in response.text
        response = call(
            client, a, "POST", f"/operator/cycles/{cycle_id}/advance", json={"to": "closed"}
        )
        assert response.status_code == 200
        response = call(
            client, b, "POST", f"/rooms/{room_id}/messages", json={"text": "After expiry"}
        )
        assert response.status_code == 410 and response.json()["error"]["code"] == "ROOM_EXPIRED"
        assert call(client, b, "GET", f"/cycles/{cycle_id}/room").json()["status"] == "expired"
        assert call(client, a, "GET", f"/jobs/{job_id}").json()["status"] == "succeeded"


def test_http_auth_cross_community_forged_fields_and_scoped_metadata():
    with runtime_environment() as env, TestClient(env.app, base_url="https://testserver") as client:
        assert client.get("/api/v1/session").status_code == 401
        players, cycle_id, job_id, room_id = revealed(env, client)
        a, b, _ = players
        assert call(client, b, "GET", "/operator/calls").status_code == 403
        assert call(client, b, "GET", "/operator/reports").status_code == 403
        assert call(client, b, "GET", f"/jobs/{job_id}").status_code == 403
        calls = call(client, a, "GET", "/operator/calls")
        assert calls.status_code == 200 and calls.json()
        assert all(
            set(row) == {"model", "source", "generatedAt", "latencyMs", "callType"}
            for row in calls.json()
        )
        assert all(row["source"] == "replay" for row in calls.json())
        for body in [
            {"text": "hello", "playerId": "SYNTHETIC FORGED PRIVATE"},
            {"text": "hello", "moderation": "visible"},
        ]:
            response = call(client, a, "POST", f"/rooms/{room_id}/messages", json=body)
            assert response.status_code == 400
            assert "SYNTHETIC FORGED PRIVATE" not in response.text
        response = call(
            client,
            a,
            "POST",
            f"/operator/cycles/{cycle_id}/form",
            json={"memberIds": ["SYNTHETIC FORGED PRIVATE"]},
        )
        assert response.status_code == 400
        assert "SYNTHETIC FORGED PRIVATE" not in response.text
        response = call(client, a, "GET", "/stream", headers={"Last-Event-ID": "-1"})
        assert response.status_code == 400
        assert response.json()["error"]["requestId"] == response.headers["X-Request-Id"]
        seed_community(env.privacy_store, "synthetic-other", "Synthetic other Group")
        outsider = join(client, "other operator", "synthetic-other")
        grant_operator(env.privacy_store, outsider.player_id, outsider.community)
        for path in [
            f"/cycles/{cycle_id}/room",
            f"/rooms/{room_id}/messages",
            f"/jobs/{job_id}",
            f"/cycles/{cycle_id}/sky",
        ]:
            assert call(client, outsider, "GET", path).status_code == 404
        assert call(client, outsider, "GET", "/operator/calls").json() == []
        assert call(client, outsider, "GET", "/operator/reports").json() == []


def test_privacy_delete_and_revocation_clear_chat_replay_and_cached_sky():
    with runtime_environment() as env, TestClient(env.app, base_url="https://testserver") as client:
        players, cycle_id, _job_id, room_id = revealed(env, client)
        a, b, c = players
        response = call(
            client,
            a,
            "POST",
            f"/rooms/{room_id}/messages",
            json={"text": "Synthetic message to delete"},
        )
        assert response.status_code == 200
        assert call(client, a, "DELETE", "/me/data").status_code == 202
        response = call(client, b, "GET", f"/rooms/{room_id}/messages")
        assert response.status_code == 200 and response.json() == []
        response = call(client, c, "GET", f"/cycles/{cycle_id}/sky")
        assert response.status_code == 503
        response = call(
            client,
            b,
            "PATCH",
            "/me/consent",
            json={
                "expectedVersion": 1,
                "matchAnswers": False,
                "anonymousChat": True,
                "isAdult": True,
            },
        )
        assert response.status_code == 200
        response = call(client, b, "GET", f"/rooms/{room_id}/messages")
        assert response.status_code == 403
        response = call(client, b, "GET", "/stream")
        assert response.status_code == 403
        assert "Synthetic message to delete" not in response.text


def test_stale_private_snapshot_cannot_commit_formation(monkeypatch):
    with runtime_environment() as env, TestClient(env.app, base_url="https://testserver") as client:
        players, cycle_id = prepare_locked(env, client)
        actor = env.app.state.privacy.require_session(players[0].token)
        job = env.app.state.runtime.enqueue(actor, cycle_id, "manual-job")

        async def scenario():
            started, resume = asyncio.Event(), asyncio.Event()
            original = env.transport.complete

            async def paused(request):
                if decode_user_message(request.user)["task"] == "constellation_formation":
                    started.set()
                    await resume.wait()
                return await original(request)

            monkeypatch.setattr(env.transport, "complete", paused)
            task = asyncio.create_task(env.app.state.runtime.run_job(job["jobId"]))
            await asyncio.wait_for(started.wait(), timeout=5)
            env.app.state.answers.delete_my_data(players[1].player_id)
            resume.set()
            await task

        asyncio.run(scenario())
        result = env.app.state.runtime.job(actor, job["jobId"], "synthetic-request")
        assert result["status"] == "failed"
        with env.repository.transaction() as state:
            assert cycle_id not in state.records.get("formations", {})
            assert not state.chat.rooms


def test_sse_seq_replay_and_session_revocation_use_real_current_checks():
    with runtime_environment() as env, TestClient(env.app, base_url="https://testserver") as client:
        players, _cycle_id, _job_id, room_id = revealed(env, client)
        a, b, _c = players
        actor_b = env.app.state.privacy.require_session(b.token)
        with env.repository.transaction() as state:
            previous = state.chat.seq
        response = call(
            client, a, "POST", f"/rooms/{room_id}/messages", json={"text": "Synthetic replay hello"}
        )
        assert response.status_code == 200

        class FiniteRequest:
            def __init__(self):
                self.polls = 0

            async def is_disconnected(self):
                self.polls += 1
                return self.polls > 1

        async def replay():
            frames = [
                frame
                async for frame in event_stream(
                    env.app.state.runtime,
                    env.app.state.chat,
                    env.app.state.privacy,
                    b.token,
                    FiniteRequest(),
                    previous,
                )
            ]
            data = [
                json.loads(frame.split("data: ", 1)[1].split("\n", 1)[0])
                for frame in frames
                if "data: " in frame
            ]
            assert len(data) == 1 and data[0]["type"] == "chat.message"
            assert data[0]["message"]["text"] == "Synthetic replay hello"
            assert data[0]["seq"] > previous
            stream = event_stream(
                env.app.state.runtime,
                env.app.state.chat,
                env.app.state.privacy,
                b.token,
                FiniteRequest(),
                0,
            )
            await anext(stream)
            env.app.state.privacy.end_session(actor_b)
            assert [frame async for frame in stream] == []

        asyncio.run(replay())


def test_http_reports_and_blocks_use_real_canonical_privacy_stores():
    with runtime_environment() as env, TestClient(env.app, base_url="https://testserver") as client:
        players, _cycle_id, _job_id, room_id = revealed(env, client)
        a, b, c = players
        message = call(
            client, a, "POST", f"/rooms/{room_id}/messages", json={"text": "First synthetic hello"}
        ).json()
        body = {"messageId": message["messageId"], "handle": message["handle"], "reason": "spam"}
        assert (
            call(
                client, b, "POST", f"/rooms/{room_id}/reports", key="report-b", json=body
            ).status_code
            == 204
        )
        assert call(client, b, "GET", f"/rooms/{room_id}/messages").json() == []
        assert len(call(client, c, "GET", f"/rooms/{room_id}/messages").json()) == 1
        assert call(client, c, "POST", f"/rooms/{room_id}/reports", json=body).status_code == 204
        assert call(client, a, "GET", f"/rooms/{room_id}/messages").json() == []
        queue = call(client, a, "GET", "/operator/reports")
        assert queue.status_code == 200 and len(queue.json()) == 2
        assert all("text" not in item for item in queue.json())
        new_message = call(
            client, a, "POST", f"/rooms/{room_id}/messages", json={"text": "Second synthetic hello"}
        ).json()
        assert (
            call(
                client,
                b,
                "POST",
                "/me/blocks",
                json={"roomId": room_id, "handle": new_message["handle"]},
            ).status_code
            == 204
        )
        assert call(client, b, "GET", f"/rooms/{room_id}/messages").json() == []
        assert len(call(client, c, "GET", f"/rooms/{room_id}/messages").json()) == 1
        outsider = join(client, "nonmember")
        for body in [
            {"roomId": room_id, "handle": new_message["handle"]},
            {"roomId": "unknown-room", "handle": "Star 1"},
        ]:
            response = call(client, outsider, "POST", "/me/blocks", json=body)
            assert response.status_code == 204 and response.content == b""
        assert not env.app.state.chat.moderation.blocked_by(outsider.player_id, COMMUNITY)


def test_real_m1_outage_cannot_accept_chat_or_persist_a_message():
    with runtime_environment() as env, TestClient(env.app, base_url="https://testserver") as client:
        players, _cycle_id, _job_id, room_id = revealed(env, client)
        env.transport.handlers.pop("safety_screen")
        response = call(
            client,
            players[0],
            "POST",
            f"/rooms/{room_id}/messages",
            json={"text": "Synthetic provider outage check"},
        )
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "PROVIDER_UNAVAILABLE"
        assert response.json()["error"]["retryable"] is True
        assert call(client, players[1], "GET", f"/rooms/{room_id}/messages").json() == []


def test_mutual_reveal_updates_sky_count_without_duplicate_narration():
    with runtime_environment() as env, TestClient(env.app, base_url="https://testserver") as client:
        players, cycle_id, _job_id, room_id = revealed(env, client)
        a, b, _c = players

        def m8_calls():
            return sum(
                decode_user_message(request.user)["task"] == "sky_narration"
                for request in env.transport.calls
            )

        assert m8_calls() == 1  # Sky job only; formation does not precompute it.
        assert call(client, a, "GET", f"/cycles/{cycle_id}/sky").json()["mutualReveals"] == 0
        room_a = call(client, a, "GET", f"/cycles/{cycle_id}/room").json()
        room_b = call(client, b, "GET", f"/cycles/{cycle_id}/room").json()
        handle_a = next(member["handle"] for member in room_a["members"] if member["isSelf"])
        handle_b = next(member["handle"] for member in room_b["members"] if member["isSelf"])
        first = call(
            client,
            a,
            "POST",
            f"/rooms/{room_id}/reveal",
            key="a-mutual-count",
            json={"toHandle": handle_b},
        )
        assert first.json() == {"result": "pending"}
        before = m8_calls()
        response = call(
            client,
            b,
            "POST",
            f"/rooms/{room_id}/reveal",
            key="b-mutual-count",
            json={"toHandle": handle_a},
        )
        assert response.status_code == 200 and response.json() == {"result": "revealed"}
        sky = call(client, a, "GET", f"/cycles/{cycle_id}/sky")
        assert sky.status_code == 200 and sky.json()["mutualReveals"] == 1
        assert m8_calls() == before + 1
        after = m8_calls()
        response = call(
            client,
            b,
            "POST",
            f"/rooms/{room_id}/reveal",
            key="b-mutual-count",
            json={"toHandle": handle_a},
        )
        assert response.json() == {"result": "revealed"}
        assert call(client, a, "GET", f"/cycles/{cycle_id}/sky").json()["mutualReveals"] == 1
        assert m8_calls() == after


def test_operator_topup_records_canonical_synthetic_labels():
    with runtime_environment() as env, TestClient(env.app, base_url="https://testserver") as client:
        operator = join(client, "operator")
        grant_operator(env.privacy_store, operator.player_id, COMMUNITY)
        created = call(
            client,
            operator,
            "POST",
            "/operator/cycles",
            json={"communityId": COMMUNITY, "weekStart": "2026-11-09", "demoTiming": True},
        )
        assert created.status_code == 201
        cycle_id = created.json()["cycleId"]
        response = call(client, operator, "POST", f"/operator/cycles/{cycle_id}/synthetic-topup")
        assert response.status_code == 200
        with env.repository.transaction() as state:
            labeled = state.records["syntheticPlayers"]
            assert len(labeled) == 8
            assert all(row["communityId"] == COMMUNITY for row in labeled.values())
