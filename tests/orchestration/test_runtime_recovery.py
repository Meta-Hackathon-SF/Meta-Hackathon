"""TEST ONLY recovery/retention checks over synthetic owner-port fixtures."""

import asyncio
from copy import deepcopy
from datetime import timedelta
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from server.app.errors import ServiceError
from server.chat.policy import moment
from server.providers.fixture import decode_user_message

from .runtime_helpers import runtime_environment
from .test_runtime import call, formed, prepare_locked, revealed


def task_calls(env, name):
    return sum(decode_user_message(call.user)["task"] == name for call in env.transport.calls)


def fresh_sky_job(env, cycle_id):
    runtime = env.app.state.runtime
    with env.repository.transaction() as state:
        state.records.get("skies", {}).pop(cycle_id, None)
        state.records.get("skyVersions", {}).pop(cycle_id, None)
        entry = state.records["formations"][cycle_id]
        return runtime._enqueue_sky(state, cycle_id, entry)


def test_formation_commit_queues_sky_atomically_and_resume_never_regroups(monkeypatch):
    with runtime_environment() as env, TestClient(env.app, base_url="https://testserver") as client:
        runtime = env.app.state.runtime
        original = runtime._run_sky_job

        async def interrupted(_job_id):
            return None  # Synthetic crash boundary after the formation transaction.

        monkeypatch.setattr(runtime, "_run_sky_job", interrupted)
        _players, cycle_id, formation_id = formed(env, client)
        with env.repository.transaction() as state:
            assert state.records["jobs"][formation_id]["status"] == "succeeded"
            sky_id = state.records["activeSkyJobs"][cycle_id]
            assert state.records["jobs"][sky_id]["status"] == "pending"
            assert state.records["jobs"][sky_id]["formationJobId"] == formation_id
            assert cycle_id not in state.records.get("skies", {})
        before = task_calls(env, "constellation_formation")
        monkeypatch.setattr(runtime, "_run_sky_job", original)
        asyncio.run(runtime.run_job(formation_id))
        assert task_calls(env, "constellation_formation") == before
        with env.repository.transaction() as state:
            assert state.records["jobs"][sky_id]["status"] == "succeeded"
            assert state.records["skies"][cycle_id]["mutualReveals"] == 0


def test_sky_bounded_retries_backoff_and_explicit_operator_repair(monkeypatch):
    with runtime_environment() as env, TestClient(env.app, base_url="https://testserver") as client:
        players, cycle_id, formation_id = formed(env, client)
        runtime = env.app.state.runtime
        sky_id = fresh_sky_job(env, cycle_id)
        original = runtime.matching_factory
        calls = []

        class BrokenSky:
            async def compute_sky(self, *_args, **_kwargs):
                calls.append("synthetic failure")
                raise RuntimeError("PRIVATE SENTINEL must never persist")

        monkeypatch.setattr(runtime, "matching_factory", lambda *_args: BrokenSky())
        for attempt in range(1, 4):
            asyncio.run(runtime.run_job(sky_id))
            with env.repository.transaction() as state:
                job = deepcopy(state.records["jobs"][sky_id])
            assert job["status"] == "failed" and job["attempts"] == attempt
            assert job["failureCode"] == "PROVIDER_UNAVAILABLE"
            assert "PRIVATE SENTINEL" not in str(job)
            asyncio.run(runtime.run_job(sky_id))
            assert len(calls) == attempt  # Not runnable before its durable backoff.
            env.clock.now += timedelta(seconds=10)
        asyncio.run(runtime.run_job(sky_id))
        assert len(calls) == 3
        actor = env.app.state.privacy.require_session(players[0].token)
        repair = runtime.enqueue(actor, cycle_id, "explicit-fresh-sky-repair")["jobId"]
        assert repair != sky_id and repair != formation_id
        monkeypatch.setattr(runtime, "matching_factory", original)
        before = task_calls(env, "constellation_formation")
        asyncio.run(runtime.run_job(repair))
        assert task_calls(env, "constellation_formation") == before
        with env.repository.transaction() as state:
            assert state.records["jobs"][repair]["status"] == "succeeded"


def test_claim_time_failure_is_sanitized_terminal_and_operator_can_retry(monkeypatch):
    with runtime_environment() as env, TestClient(env.app, base_url="https://testserver") as client:
        players, cycle_id = prepare_locked(env, client)
        runtime = env.app.state.runtime
        actor = env.app.state.privacy.require_session(players[0].token)
        job_id = runtime.enqueue(actor, cycle_id, "claim-original")["jobId"]
        original = runtime.cycles.gate

        def missing(_cycle_id):
            raise ServiceError("NOT_FOUND")

        monkeypatch.setattr(runtime.cycles, "gate", missing)
        asyncio.run(runtime.run_job(job_id))
        with env.repository.transaction() as state:
            job = state.records["jobs"][job_id]
            assert job["status"] == "failed" and job["attempts"] == 3
            assert job["failureCode"] == "NOT_FOUND"
        monkeypatch.setattr(runtime.cycles, "gate", original)
        new_id = runtime.enqueue(actor, cycle_id, "claim-retry")["jobId"]
        assert new_id != job_id
        asyncio.run(runtime.run_job(new_id))
        assert runtime.job(actor, new_id, "synthetic-request")["status"] == "succeeded"


def test_original_privacy_revision_checked_before_any_new_m8_call():
    with runtime_environment() as env, TestClient(env.app, base_url="https://testserver") as client:
        players, cycle_id, _formation_id = formed(env, client)
        runtime = env.app.state.runtime
        sky_id = fresh_sky_job(env, cycle_id)
        before = task_calls(env, "sky_narration")
        env.app.state.answers.delete_my_data(players[1].player_id)
        asyncio.run(runtime.run_job(sky_id))
        assert task_calls(env, "sky_narration") == before
        with env.repository.transaction() as state:
            assert cycle_id not in state.records.get("skies", {})
            assert state.records["jobs"][sky_id]["status"] == "failed"
            assert state.records["jobs"][sky_id]["attempts"] == 3


def test_privacy_change_during_m8_cannot_publish(monkeypatch):
    with runtime_environment() as env, TestClient(env.app, base_url="https://testserver") as client:
        players, cycle_id, _formation_id = formed(env, client)
        runtime = env.app.state.runtime
        sky_id = fresh_sky_job(env, cycle_id)

        async def scenario():
            started, resume = asyncio.Event(), asyncio.Event()
            original = env.transport.complete

            async def paused(request):
                if decode_user_message(request.user)["task"] == "sky_narration":
                    started.set()
                    await resume.wait()
                return await original(request)

            monkeypatch.setattr(env.transport, "complete", paused)
            task = asyncio.create_task(runtime.run_job(sky_id))
            await asyncio.wait_for(started.wait(), timeout=5)
            env.app.state.answers.delete_my_data(players[1].player_id)
            resume.set()
            await task

        asyncio.run(scenario())
        with env.repository.transaction() as state:
            assert cycle_id not in state.records.get("skies", {})
            assert state.records["jobs"][sky_id]["status"] == "failed"


def test_unprocessed_privacy_notices_requeued_after_transient_failure(monkeypatch):
    with runtime_environment() as env:
        runtime = env.app.state.runtime
        notices = [
            SimpleNamespace(kind="data_deleted", player_id=f"synthetic-{n}", cycle_id=None)
            for n in range(3)
        ]
        for notice in notices:
            runtime.notices.put(notice)
        seen = []

        def forget(player_id, _cycle):
            seen.append(player_id)
            if player_id == "synthetic-1" and seen.count(player_id) == 1:
                raise RuntimeError("Synthetic transient database failure")

        monkeypatch.setattr(runtime.chat, "forget_player", forget)
        with pytest.raises(RuntimeError):
            runtime.drain_notices()
        runtime.drain_notices()
        assert seen == ["synthetic-0", "synthetic-1", "synthetic-1", "synthetic-2"]
        assert runtime.notices.empty()


def test_first_actual_lock_retains_then_purges_all_private_cycle_state():
    with runtime_environment() as env, TestClient(env.app, base_url="https://testserver") as client:
        _players, cycle_id, _job_id, room_id = revealed(env, client)
        runtime = env.app.state.runtime
        with env.repository.transaction() as state:
            first_lock = state.records["cycles"][cycle_id]["lockedAt"]
            cycle = deepcopy(state.records["cycles"][cycle_id]["cycle"])
            assert room_id in state.chat.rooms
        env.clock.now += timedelta(days=7)
        runtime.on_locked(cycle)
        runtime.purge_retention()
        with env.repository.transaction() as state:
            assert state.records["cycles"][cycle_id]["lockedAt"] == first_lock
            assert cycle_id in state.records["formations"]
        env.clock.now += timedelta(days=7)
        runtime.purge_retention()
        with env.repository.transaction() as state:
            assert room_id not in state.chat.rooms
            for name in ("formations", "skies", "activeJobs", "activeSkyJobs", "skyVersions"):
                assert cycle_id not in state.records.get(name, {})
            assert not any(j["cycleId"] == cycle_id for j in state.records["jobs"].values())
            assert not any(e["cycleId"] == cycle_id for e in state.records["publicEvents"].values())
            assert state.records["cycles"][cycle_id]["retentionPurgedAt"]
        with env.privacy_store.tx() as conn:
            assert (
                conn.execute(
                    "SELECT count(*) FROM answers WHERE cycle_id = ?", (cycle_id,)
                ).fetchone()[0]
                == 0
            )
            assert (
                conn.execute(
                    "SELECT count(*) FROM guesses WHERE cycle_id = ?", (cycle_id,)
                ).fetchone()[0]
                == 0
            )


def test_worker_survives_transient_store_error_and_propagates_cancellation(monkeypatch):
    with runtime_environment() as env:
        runtime = env.app.state.runtime

        async def scenario():
            recovered = asyncio.Event()
            calls = 0

            def purge():
                nonlocal calls
                calls += 1
                if calls == 1:
                    raise RuntimeError("Synthetic transient failure")
                recovered.set()

            monkeypatch.setattr(runtime, "purge_retention", purge)
            task = asyncio.create_task(runtime.loop(runtime.chat))
            await asyncio.wait_for(recovered.wait(), timeout=2)
            assert not task.done()
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task

        asyncio.run(scenario())


def test_reveal_precondition_blocks_phase_advance_until_formation_exists():
    with runtime_environment() as env, TestClient(env.app, base_url="https://testserver") as client:
        players, cycle_id = prepare_locked(env, client)
        runtime = env.app.state.runtime
        runtime.cycles.advance(cycle_id, "forming")
        response = call(
            client,
            players[0],
            "POST",
            f"/operator/cycles/{cycle_id}/advance",
            json={"to": "revealed"},
        )
        assert response.status_code == 503
        assert runtime.cycles.gate(cycle_id).cycle.status == "forming"


def test_legacy_missing_sky_job_is_repaired_without_formation_work():
    with runtime_environment() as env, TestClient(env.app, base_url="https://testserver") as client:
        _players, cycle_id, _formation_id = formed(env, client)
        runtime = env.app.state.runtime
        before = task_calls(env, "constellation_formation")
        with env.repository.transaction() as state:
            state.records["skies"].pop(cycle_id)
            state.records["skyVersions"].pop(cycle_id)
            old_id = state.records["activeSkyJobs"].pop(cycle_id)
            state.records["jobs"].pop(old_id)
        jobs, _cycles = runtime._pending_jobs()
        sky = next(j for j in jobs if j["kind"] == "sky" and j["cycleId"] == cycle_id)
        asyncio.run(runtime.run_job(sky["jobId"]))
        assert task_calls(env, "constellation_formation") == before
        with env.repository.transaction() as state:
            assert state.records["jobs"][sky["jobId"]]["status"] == "succeeded"


def test_expired_last_sky_lease_becomes_failed_and_accepts_manual_repair():
    with runtime_environment() as env, TestClient(env.app, base_url="https://testserver") as client:
        _players, cycle_id, _formation_id = formed(env, client)
        runtime = env.app.state.runtime
        sky_id = fresh_sky_job(env, cycle_id)
        with env.repository.transaction() as state:
            state.records["jobs"][sky_id].update(
                status="running",
                attempts=3,
                attemptToken="synthetic-expired",
                leaseUntil="2026-11-09T17:00:00Z",
            )
        runtime._pending_jobs()
        with env.repository.transaction() as state:
            assert state.records["jobs"][sky_id]["status"] == "failed"
            assert state.records["jobs"][sky_id]["attempts"] == 3
            assert cycle_id not in state.records["skies"]


@pytest.mark.parametrize("synthetic,fallback", [(True, False), (False, True), (True, True)])
def test_new_room_truth_labels_preserve_opaque_handles_and_fit_contract(synthetic, fallback):
    with runtime_environment() as env, TestClient(env.app, base_url="https://testserver") as client:
        players, cycle_id, _formation_id = formed(env, client)
        runtime = env.app.state.runtime
        with env.repository.transaction() as state:
            if synthetic:
                state.records["syntheticPlayers"] = {
                    p.player_id: {"communityId": p.community} for p in players
                }
            if fallback:
                for constellation in state.records["formations"][cycle_id]["result"][
                    "constellations"
                ]:
                    constellation["name"] += " (Fallback grouping)"
        response = call(
            client,
            players[0],
            "POST",
            f"/operator/cycles/{cycle_id}/advance",
            json={"to": "revealed"},
        )
        assert response.status_code == 200, response.json()
        room = call(client, players[0], "GET", f"/cycles/{cycle_id}/room").json()
        assert moment(room["opensAt"]) <= env.clock()
        handles = [m["handle"] for m in room["members"]]
        assert all(len(h) <= 40 for h in handles)
        assert all(("Synthetic player" in h) == synthetic for h in handles)
        assert all(("Fallback grouping" in h) == fallback for h in handles)
        assert all(p.name not in h for p in players for h in handles)
        with env.repository.transaction() as state:
            state.records["syntheticPlayers"] = {}
        runtime.on_revealed(runtime.cycles.gate(cycle_id).cycle.model_dump())
        again = call(client, players[0], "GET", f"/cycles/{cycle_id}/room").json()
        assert [m["handle"] for m in again["members"]] == handles


def test_reveal_during_m8_can_publish_without_regrouping(monkeypatch):
    with runtime_environment() as env, TestClient(env.app, base_url="https://testserver") as client:
        _players, cycle_id, _formation_id = formed(env, client)
        runtime = env.app.state.runtime
        sky_id = fresh_sky_job(env, cycle_id)
        before = task_calls(env, "constellation_formation")

        async def scenario():
            started, resume = asyncio.Event(), asyncio.Event()
            original = env.transport.complete

            async def paused(request):
                if decode_user_message(request.user)["task"] == "sky_narration":
                    started.set()
                    await resume.wait()
                return await original(request)

            monkeypatch.setattr(env.transport, "complete", paused)
            task = asyncio.create_task(runtime.run_job(sky_id))
            await asyncio.wait_for(started.wait(), timeout=5)
            runtime.cycles.advance(cycle_id, "revealed")
            resume.set()
            await task

        asyncio.run(scenario())
        assert task_calls(env, "constellation_formation") == before
        with env.repository.transaction() as state:
            assert state.records["jobs"][sky_id]["status"] == "succeeded"
            assert cycle_id in state.records["skies"]
            assert any(
                item["cycleId"] == cycle_id and item["event"]["type"] == "sky.updated"
                for item in state.records["publicEvents"].values()
            )
