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
from server.privacy import demo_population
from server.privacy.fixtures import grant_operator, seed_community
from server.providers.fixture import decode_user_message

from .runtime_helpers import COMMUNITY, runtime_environment


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


def prepare_locked(env, client, count=5):
    players = [join(client, f"player {index}") for index in range(count)]
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


def formed(env, client, count=5):
    players, cycle_id = prepare_locked(env, client, count)
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


def test_composed_daily_loop_formation_reveal_chat_sky_and_expiry():
    with runtime_environment() as env, TestClient(env.app, base_url="https://testserver") as client:
        players, cycle_id, job_id = formed(env, client)
        a, b, c, *_ = players
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
        a, b, _, *__ = players
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
        a, b, c, *_ = players
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
        a, b, _c, *_rest = players
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
        a, b, c, *_ = players
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
        a, b, _c, *_rest = players

        def m8_calls():
            return sum(
                decode_user_message(request.user)["task"] == "sky_narration"
                for request in env.transport.calls
            )

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
            assert len(labeled) == CAST_SIZE
            assert all(row["communityId"] == COMMUNITY for row in labeled.values())


ANSWER = "Synthetic private submission number {} for this week"
CAST_SIZE = 8 + len(demo_population.players())  # fixture players + the synthetic demo cast


def test_stage_shows_only_opted_in_players_answers_to_operators():
    with runtime_environment() as env, TestClient(env.app, base_url="https://testserver") as client:
        players, cycle_id, _job = formed(env, client)
        operator, on_stage, private_player = players[:3]
        assert call(client, on_stage, "GET", "/operator/stage").status_code == 403
        assert call(client, on_stage, "GET", "/me/stage").json() == {"slot": None}
        bad = call(client, on_stage, "POST", "/me/stage", json={"slot": "C"})
        assert bad.status_code in (400, 422)
        chosen = call(client, on_stage, "POST", "/me/stage", json={"slot": "A"})
        assert chosen.json() == {"slot": "A"}
        assert call(client, on_stage, "GET", "/me/stage").json() == {"slot": "A"}

        stage = call(client, operator, "GET", "/operator/stage")
        assert stage.status_code == 200, stage.json()
        body = stage.json()
        a, b = body["panels"]
        assert (a["slot"], a["joined"], b["joined"]) == ("A", True, False)
        assert [x["text"] for x in a["answers"]] == [ANSWER.format(1)]
        assert b["answers"] == [] and b["constellation"] is None
        assert a["constellation"]["size"] == len(players)
        assert body["population"]["players"] == len(players)
        assert body["population"]["answersByDay"][0] == len(players)
        assert body["formation"]["formed"] is True and body["cycle"]["cycleId"] == cycle_id
        assert body["calls"] and all("callType" in c for c in body["calls"])
        # Nobody else's text, ids or private meaning leaves the server.
        assert "submission number 0" not in stage.text
        assert "submission number 2" not in stage.text
        assert private_player.player_id not in stage.text
        assert on_stage.player_id not in stage.text
        assert "memberIds" not in stage.text and "sharedMeaning" not in stage.text

        # Opting out removes the text again; a second player can take the slot.
        left = call(client, on_stage, "POST", "/me/stage", json={"slot": None})
        assert left.json() == {"slot": None}
        panels = call(client, operator, "GET", "/operator/stage").json()["panels"]
        assert panels[0]["answers"] == []
        call(client, on_stage, "POST", "/me/stage", json={"slot": "B"})
        call(client, private_player, "POST", "/me/stage", json={"slot": "B"})
        panels = call(client, operator, "GET", "/operator/stage").json()["panels"]
        assert [x["text"] for x in panels[1]["answers"]] == [ANSWER.format(2)]


def test_stage_without_a_week_is_empty_not_an_error():
    with runtime_environment() as env, TestClient(env.app, base_url="https://testserver") as client:
        player = join(client, "operator")
        grant_operator(env.privacy_store, player.player_id, COMMUNITY)
        body = call(client, player, "GET", "/operator/stage").json()
        assert body["cycle"] is None and body["constellations"] == []
        assert body["population"]["answersByDay"] == [0, 0, 0, 0, 0]


def test_topup_needs_a_session_is_labeled_and_seeds_the_maya_dev_pair():
    with runtime_environment() as env, TestClient(env.app, base_url="https://testserver") as client:
        operator = join(client, "operator")
        grant_operator(env.privacy_store, operator.player_id, COMMUNITY)
        player = join(client, "player")
        created = call(
            client,
            operator,
            "POST",
            "/operator/cycles",
            json={"communityId": COMMUNITY, "weekStart": "2026-11-09", "demoTiming": True},
        )
        cycle_id = created.json()["cycleId"]
        path = f"/operator/cycles/{cycle_id}/synthetic-topup"

        # #103: on a demo-timed week every signed-in account may run the demo controls,
        # so the gate here is the session, not the operator role.
        client.cookies.clear()
        denied = client.post("/api/v1" + path, headers={"Idempotency-Key": "no-session"})
        assert denied.status_code == 401
        with env.privacy_store.tx() as conn:
            assert (
                conn.execute("SELECT count(*) FROM players WHERE is_synthetic = 1").fetchone()[0]
                == 0
            )

        topped = call(client, operator, "POST", path)
        assert topped.status_code == 200
        assert (
            topped.json()["label"] == "Synthetic player"
            and topped.json()["syntheticPlayers"] == CAST_SIZE
        )
        with env.privacy_store.tx() as conn:
            rows = conn.execute(
                "SELECT player_id, display_name, is_synthetic FROM players"
            ).fetchall()
            seeded = {r[0]: r for r in rows if r[0] not in (operator.player_id, player.player_id)}
            # Every generated account carries the synthetic flag and says so in its name.
            assert len(seeded) == CAST_SIZE
            assert all(r[2] == 1 and "(synthetic)" in r[1] for r in seeded.values())
            assert {"p-maya", "p-dev"} <= set(seeded)
            day_one = dict(
                conn.execute(
                    "SELECT player_id, text FROM answers WHERE cycle_id = ? AND day = 1"
                    " AND player_id IN ('p-maya', 'p-dev')",
                    (cycle_id,),
                ).fetchall()
            )
        # The semantic pair: no shared keywords, same meaning.
        assert "alone" in day_one["p-maya"] and "cooking for one" in day_one["p-dev"]
        # A normal player may repeat it on a demo week; it stays labeled and adds nobody new.
        again = call(client, player, "POST", path)
        assert again.status_code == 200 and again.json()["label"] == "Synthetic player"
        with env.privacy_store.tx() as conn:
            count = conn.execute("SELECT count(*) FROM players WHERE is_synthetic = 1").fetchone()
        assert count[0] == CAST_SIZE


def test_v3_live_routes_serve_indices_only_from_the_verified_session():
    with runtime_environment() as env, TestClient(env.app, base_url="https://testserver") as client:
        players, cycle_id, _job = formed(env, client)
        a = players[0]
        close = call(
            client,
            a,
            "POST",
            f"/operator/cycles/{cycle_id}/close-day",
            key="close-1",
            json={"day": 1},
        )
        assert close.status_code == 200 and close.json()["status"] == "ok"
        view = call(client, a, "GET", f"/cycles/{cycle_id}/days/1/constellations")
        assert view.status_code == 200
        body = view.json()
        assert "myStarIndex" in body and all("starIndices" in c for c in body["constellations"])
        assert "player" not in str(body).lower().replace("placement", "")
        sky = call(client, a, "GET", f"/cycles/{cycle_id}/sky/stars")
        assert sky.status_code == 200 and sky.json()["stars"]["count"] == 10000


def test_v3_scheduler_closes_days_and_forms_main_from_cycle_hooks():
    import time

    with runtime_environment() as env, TestClient(env.app, base_url="https://testserver") as client:
        _players, cycle_id = prepare_locked(env, client)  # advance to locked fires the publish hook
        store = env.app.state.v3_store
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and not (
            store.load_days(cycle_id).get(1) and store.load_main(cycle_id) is not None
        ):
            time.sleep(0.02)
        day = store.load_days(cycle_id).get(1)
        assert day is not None and day.final  # closed by the hook, no operator close-day call
        assert store.load_main(cycle_id) is not None


def test_a_constellation_larger_than_five_forms_saves_and_reveals():
    # D016 removed the maximum size in matching; the stored wire shape, the partition
    # check and the nudge guard still capped it at 5, so any group of 6+ failed on Sunday.
    with runtime_environment() as env, TestClient(env.app, base_url="https://testserver") as client:
        players, cycle_id, _job = formed(env, client, count=7)
        with env.repository.transaction() as state:
            saved = state.records["formations"][cycle_id]["privateFormation"]["wire"]
        assert [len(c["memberIds"]) for c in saved["constellations"]] == [7]
        response = call(
            client,
            players[0],
            "POST",
            f"/operator/cycles/{cycle_id}/advance",
            json={"to": "revealed"},
        )
        assert response.status_code == 200, response.json()
        room = call(client, players[6], "GET", f"/cycles/{cycle_id}/room")
        assert room.status_code == 200 and len(room.json()["members"]) == 7
