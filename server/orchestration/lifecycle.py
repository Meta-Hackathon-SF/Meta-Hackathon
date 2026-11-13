"""Durable lifecycle effects for the v3 composition boundary.

Handlers prepare outside locks and commit workflow effects within the supplied
current-cycle/privacy guard. Production registration awaits the v3 owner ports.
The guard and handlers are required. Job records contain scheduling metadata.
"""

import asyncio
import inspect
import json
from copy import deepcopy
from datetime import timedelta
from hashlib import sha256
from uuid import uuid4

from server.app.errors import ServiceError
from server.chat.policy import moment, stamp

KINDS = frozenset({"day_close", "week_lock", "main_formation", "reveal", "room_expiry"})


class LifecycleRunner:
    def __init__(self, repository, *, guard, handlers, clock, lease_seconds=120):
        if not callable(guard) or not handlers or not set(handlers) <= KINDS:
            raise ValueError("Explicit lifecycle guard and handlers required")
        if type(lease_seconds) is not int or lease_seconds < 1:
            raise ValueError("Positive lifecycle lease required")
        if any(
            not callable(getattr(h, "prepare", None))
            or not callable(getattr(h, "commit", None))
            or inspect.iscoroutinefunction(h.commit)
            for h in handlers.values()
        ):
            raise ValueError("Lifecycle handlers require prepare and synchronous commit")
        self.repository, self.guard, self.handlers = repository, guard, handlers
        self.clock, self.lease_seconds = clock, lease_seconds

    @staticmethod
    def enqueue_in_state(
        state, *, community_id, cycle_id, revision, kind, due_at, day=None, room_id=None
    ):
        """May run in a guarded reveal commit to schedule expiry atomically."""
        if (
            kind not in KINDS
            or not all(
                isinstance(v, str) and 0 < len(v) <= 200 for v in (community_id, cycle_id, revision)
            )
            or (kind == "day_close" and (type(day) is not int or not 1 <= day <= 5))
            or (kind != "day_close" and day is not None)
            or (
                room_id is not None
                and (
                    kind != "room_expiry"
                    or not isinstance(room_id, str)
                    or not 0 < len(room_id) <= 200
                )
            )
        ):
            raise ServiceError("INVALID_INPUT")
        identity = [community_id, cycle_id, kind, day]
        if room_id is not None:
            identity.append(room_id)
        job_id = "lifecycle-" + sha256(json.dumps(identity).encode()).hexdigest()
        record = {
            "jobId": job_id,
            "communityId": community_id,
            "cycleId": cycle_id,
            "revision": revision,
            "kind": kind,
            "day": day,
            "dueAt": stamp(due_at),
        }
        if room_id is not None:
            record["roomId"] = room_id
        jobs = state.records.setdefault("lifecycleJobs", {})
        previous = jobs.get(job_id)
        if previous is not None:
            if any(previous[key] != value for key, value in record.items()):
                raise ServiceError("IDEMPOTENCY_CONFLICT")
        else:
            jobs[job_id] = {**record, "status": "pending", "attempts": 0}
        return job_id

    def enqueue(self, **kwargs):
        # Validate before entering any owner's guard or opening storage.
        from server.orchestration.storage import WorkflowState

        scratch = WorkflowState()
        job_id = self.enqueue_in_state(scratch, **kwargs)
        job = scratch.records["lifecycleJobs"][job_id]
        if job["kind"] not in self.handlers:
            raise ServiceError("PROVIDER_UNAVAILABLE")
        with self.guard(deepcopy(job)):
            with self.repository.transaction() as state:
                return self.enqueue_in_state(state, **kwargs)

    def _claim(self, job_id):
        with self.repository.transaction() as state:
            job = deepcopy(state.records.get("lifecycleJobs", {}).get(job_id))
        if job is None:
            raise ServiceError("NOT_FOUND")
        with self.guard(job):
            with self.repository.transaction() as state:
                job = state.records["lifecycleJobs"][job_id]
                now = self.clock()
                if (
                    job["status"] == "running"
                    and job["attempts"] >= 3
                    and moment(job["leaseUntil"]) <= now
                ):
                    job.update(status="failed", failureCode="PROVIDER_UNAVAILABLE")
                    job.pop("claimId", None)
                    job.pop("leaseUntil", None)
                    return None
                if (
                    job["status"] == "succeeded"
                    or job["attempts"] >= 3
                    or moment(job["dueAt"]) > now
                    or moment(job.get("retryAt", job["dueAt"])) > now
                    or (job["status"] == "running" and moment(job["leaseUntil"]) > now)
                ):
                    return None
                job.update(
                    status="running",
                    attempts=job["attempts"] + 1,
                    claimId=uuid4().hex,
                    leaseUntil=stamp(now + timedelta(seconds=self.lease_seconds)),
                )
                job.pop("failureCode", None)
                return deepcopy(job)

    async def run(self, job_id):
        job = self._claim(job_id)
        if job is None:
            return False
        try:
            handler = self.handlers[job["kind"]]
            prepared = await handler.prepare(deepcopy(job))
            with self.guard(deepcopy(job)):
                with self.repository.transaction() as state:
                    current = state.records["lifecycleJobs"][job_id]
                    if (
                        current["status"] != "running"
                        or current["claimId"] != job["claimId"]
                        or moment(current["leaseUntil"]) <= self.clock()
                    ):
                        raise ServiceError("STALE_REVISION")
                    result = handler.commit(state, deepcopy(job), prepared)
                    if inspect.isawaitable(result):
                        if inspect.iscoroutine(result):
                            result.close()
                        raise ServiceError("INVALID_INPUT")
                    current.update(status="succeeded")
                    for key in ("claimId", "leaseUntil", "retryAt", "failureCode"):
                        current.pop(key, None)
            return True
        except (Exception, asyncio.CancelledError) as error:
            with self.repository.transaction() as state:
                current = state.records["lifecycleJobs"][job_id]
                if current.get("claimId") == job["claimId"]:
                    code = error.code if isinstance(error, ServiceError) else "PROVIDER_UNAVAILABLE"
                    current.update(
                        status="failed",
                        failureCode=code,
                        retryAt=stamp(self.clock() + timedelta(seconds=2 ** job["attempts"])),
                    )
                    current.pop("claimId", None)
                    current.pop("leaseUntil", None)
            if isinstance(error, asyncio.CancelledError):
                raise
            raise ServiceError(
                error.code if isinstance(error, ServiceError) else "PROVIDER_UNAVAILABLE"
            ) from None

    def pending(self):
        with self.repository.transaction() as state:
            return [
                job["jobId"]
                for job in state.records.get("lifecycleJobs", {}).values()
                if job["status"] != "succeeded"
                and (job["attempts"] < 3 or job["status"] == "running")
            ]
