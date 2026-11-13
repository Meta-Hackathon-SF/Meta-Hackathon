"""TEST ONLY v3 lifecycle boundaries pending contract and owner ports.

Uses the existing serialized workflow test repository and 2.1 fixture chat state
to verify private effects. The configured app never imports this adapter.
"""

from contextlib import contextmanager
from datetime import timedelta

from server.app.errors import ServiceError
from server.chat import policy
from server.chat.lifetime import daily_expiry
from server.orchestration.lifecycle import KINDS, LifecycleRunner
from server.orchestration.storage import WorkflowState
from tests.chat.adapters import Driver
from tests.orchestration.storage_adapter import TestWorkflowRepository


class FixtureLifecycle:
    def __init__(self):
        self.chat = Driver()
        self.now = self.chat.now
        self.revision = "synthetic-revision"
        self.allowed = True
        self.depth = 0
        self.prepared = 0
        self.repository = TestWorkflowRepository(WorkflowState(chat=self.chat.state))
        self.handlers = {kind: FixtureHandler(self) for kind in KINDS}
        self.runner = LifecycleRunner(
            self.repository,
            guard=self.guard,
            handlers=self.handlers,
            clock=lambda: self.now,
            lease_seconds=10,
        )

    @contextmanager
    def guard(self, job):
        if not self.allowed:
            raise ServiceError("CONSENT_REQUIRED")
        if job["revision"] != self.revision:
            raise ServiceError("STALE_REVISION")
        self.depth += 1
        try:
            yield
        finally:
            self.depth -= 1

    def enqueue(self, kind, *, day=None, due=None):
        return self.runner.enqueue(
            community_id="synthetic-group",
            cycle_id=self.chat.cycle.cycleId,
            revision=self.revision,
            kind=kind,
            due_at=due or self.now,
            day=day,
        )


class FixtureHandler:
    def __init__(self, env):
        self.env = env
        self.fail = False
        self.on_prepare = None

    async def prepare(self, job):
        assert self.env.depth == 0
        with self.env.repository.transaction():
            pass  # Provider work has no workflow transaction around it.
        self.env.prepared += 1
        if self.on_prepare:
            await self.on_prepare(job)
        return {"synthetic": True}

    def commit(self, state, job, prepared):
        assert self.env.depth > 0 and prepared == {"synthetic": True}
        state.records.setdefault("fixtureEffects", {})[job["jobId"]] = {"kind": job["kind"]}
        if self.fail:
            raise RuntimeError("PRIVATE fixture failure must never persist")
        if job["kind"] == "reveal":
            room = state.chat.rooms[self.env.chat.room_id]
            room.wire = room.wire.model_copy(
                update={
                    "opensAt": policy.stamp(self.env.now),
                    "expiresAt": policy.stamp(daily_expiry(self.env.now)),
                }
            )
            LifecycleRunner.enqueue_in_state(
                state,
                community_id=job["communityId"],
                cycle_id=job["cycleId"],
                revision=job["revision"],
                kind="room_expiry",
                room_id=room.wire.roomId,
                due_at=self.env.now + timedelta(hours=24),
            )
        elif job["kind"] == "room_expiry":
            policy.expire(state.chat, job["cycleId"], self.env.now)
