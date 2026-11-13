"""Durable lifecycle regressions using labeled TEST ONLY v3 owner adapters."""

import asyncio
from datetime import timedelta

import pytest

from server.app.errors import ServiceError
from server.chat import policy
from server.chat.lifetime import require_daily_access
from server.orchestration.lifecycle import LifecycleRunner
from tests.orchestration.v3_lifecycle_adapter import FixtureLifecycle


@pytest.mark.parametrize(
    "kind,day",
    [
        ("day_close", 1),
        ("day_close", 5),
        ("week_lock", None),
        ("main_formation", None),
        ("reveal", None),
        ("room_expiry", None),
    ],
)
def test_each_lifecycle_effect_commits_once_and_reload_keeps_idempotency(kind, day):
    env = FixtureLifecycle()
    job_id = env.enqueue(kind, day=day)
    assert env.enqueue(kind, day=day) == job_id
    assert asyncio.run(env.runner.run(job_id))
    runner = LifecycleRunner(
        env.repository, guard=env.guard, handlers=env.handlers, clock=lambda: env.now
    )
    assert not asyncio.run(runner.run(job_id))
    assert env.prepared == 1
    with env.repository.transaction() as state:
        assert list(state.records["fixtureEffects"]) == [job_id]


def test_day_close_identity_is_per_day_and_changed_schedule_conflicts():
    env = FixtureLifecycle()
    assert env.enqueue("day_close", day=1) != env.enqueue("day_close", day=2)
    with pytest.raises(ServiceError, match="IDEMPOTENCY_CONFLICT"):
        env.enqueue("day_close", day=1, due=env.now + timedelta(seconds=1))
    for day in (None, True, 0, 6):
        with pytest.raises(ServiceError, match="INVALID_INPUT"):
            env.enqueue("day_close", day=day)


def test_future_job_runs_only_when_due():
    env = FixtureLifecycle()
    job_id = env.enqueue("week_lock", due=env.now + timedelta(hours=1))
    assert not asyncio.run(env.runner.run(job_id))
    assert env.prepared == 0
    env.now += timedelta(hours=1)
    assert asyncio.run(env.runner.run(job_id))


@pytest.mark.parametrize("change", ["consent", "revision"])
def test_inflight_preparation_rechecks_current_privacy_and_cycle(change):
    async def scenario():
        env = FixtureLifecycle()
        job_id = env.enqueue("week_lock")

        async def invalidate(_job):
            if change == "consent":
                env.allowed = False
            else:
                env.revision = "synthetic-next-revision"

        env.handlers["week_lock"].on_prepare = invalidate
        with pytest.raises(ServiceError):
            await env.runner.run(job_id)
        with env.repository.transaction() as state:
            assert not state.records.get("fixtureEffects")

    asyncio.run(scenario())


def test_commit_failure_rolls_back_effect_and_bounded_retry_has_sanitized_error():
    env = FixtureLifecycle()
    job_id = env.enqueue("week_lock")
    env.handlers["week_lock"].fail = True
    for attempt in range(1, 4):
        with pytest.raises(ServiceError, match="PROVIDER_UNAVAILABLE"):
            asyncio.run(env.runner.run(job_id))
        with env.repository.transaction() as state:
            assert not state.records.get("fixtureEffects")
            assert "PRIVATE" not in str(state.records)
        assert not asyncio.run(env.runner.run(job_id))
        env.now += timedelta(seconds=2**attempt)
    assert not asyncio.run(env.runner.run(job_id))
    assert env.prepared == 3


def test_competing_workers_and_expired_lease_cannot_publish_stale_effect():
    async def scenario():
        env = FixtureLifecycle()
        job_id = env.enqueue("week_lock")
        started, release = asyncio.Event(), asyncio.Event()

        async def delayed(_job):
            started.set()
            await release.wait()

        env.handlers["week_lock"].on_prepare = delayed
        first = asyncio.create_task(env.runner.run(job_id))
        await started.wait()
        assert not await env.runner.run(job_id)
        env.now += timedelta(seconds=11)
        env.handlers["week_lock"].on_prepare = None
        assert await env.runner.run(job_id)
        release.set()
        with pytest.raises(ServiceError, match="STALE_REVISION"):
            await first
        with env.repository.transaction() as state:
            assert len(state.records["fixtureEffects"]) == 1
            assert state.records["lifecycleJobs"][job_id]["status"] == "succeeded"

    asyncio.run(scenario())


def test_cancelled_prepare_can_retry_after_backoff():
    async def scenario():
        env = FixtureLifecycle()
        job_id = env.enqueue("week_lock")

        async def cancelled(_job):
            raise asyncio.CancelledError()

        env.handlers["week_lock"].on_prepare = cancelled
        with pytest.raises(asyncio.CancelledError):
            await env.runner.run(job_id)
        env.now += timedelta(seconds=2)
        env.handlers["week_lock"].on_prepare = None
        assert await env.runner.run(job_id)

    asyncio.run(scenario())


def test_reveal_atomically_schedules_24_hour_expiry_and_denies_all_access_at_deadline():
    env = FixtureLifecycle()
    job_id = env.enqueue("reveal")
    assert asyncio.run(env.runner.run(job_id))
    with env.repository.transaction() as state:
        room = state.chat.rooms[env.chat.room_id]
        assert policy.moment(room.wire.expiresAt) - policy.moment(room.wire.opensAt) == timedelta(
            hours=24
        )
        expiry = next(
            j for j in state.records["lifecycleJobs"].values() if j["kind"] == "room_expiry"
        )
        room.requests.add((env.chat.players[0], env.chat.players[1]))
        require_daily_access(room, env.now + timedelta(hours=24, microseconds=-1))
    env.now += timedelta(hours=24)
    with env.repository.transaction() as state:
        with pytest.raises(ServiceError, match="ROOM_EXPIRED"):
            require_daily_access(state.chat.rooms[env.chat.room_id], env.now)
    assert asyncio.run(env.runner.run(expiry["jobId"]))
    assert not asyncio.run(env.runner.run(expiry["jobId"]))
    with env.repository.transaction() as state:
        room = state.chat.rooms[env.chat.room_id]
        assert room.wire.status == "expired" and not room.requests and not room.reveals
        assert sum(d.event["type"] == "room.expired" for d in state.chat.deliveries) == 1
