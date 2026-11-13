"""Formation, guarded Sunday publication and private workflow job lifecycle.

Only this coordinator commits formation side effects. Provider calls run outside
cycle/privacy/database locks. The injected repository is durable in production;
no fixture or in-memory production fallback is installed here.
"""

import asyncio
import contextvars
from contextlib import contextmanager
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from queue import Empty, SimpleQueue
from uuid import uuid4

from server.app.cycles import effective_now
from server.app.errors import ERRORS, ServiceError
from server.chat import policy
from server.orchestration.stream import EVENT
from server.orchestration.wire import SkyStats, WeeklyCycle
from server.orchestration.worker import form_once

MODEL_COMMUNITY = contextvars.ContextVar("model_community", default=None)


def now_utc():
    return datetime.now(UTC)


def wire_cycle(cycle):
    return WeeklyCycle.model_validate(cycle.model_dump(mode="json"))


class WeeklyRuntime:
    def __init__(
        self,
        *,
        repository,
        cycles,
        privacy,
        formation,
        guard,
        matching_factory,
        clock=now_utc,
        timeout_seconds=120,
    ):
        self.repository = repository
        self.cycles = cycles
        self.privacy = privacy
        self.formation = formation
        self.guard = guard
        self.matching_factory = matching_factory
        self.clock = clock
        self.timeout_seconds = timeout_seconds
        self.notices = SimpleQueue()
        privacy.add_listener(self.notices.put)

    @staticmethod
    def _public_event(state, cycle, body):
        state.chat.seq += 1
        event = EVENT.validate_python({**body, "seq": state.chat.seq}).model_dump()
        state.records.setdefault("publicEvents", {})[str(state.chat.seq)] = {
            "communityId": cycle.communityId,
            "cycleId": cycle.cycleId,
            "event": event,
        }

    @staticmethod
    def _purge_cycle(state, cycle_id):
        rooms = {rid for rid, room in state.chat.rooms.items() if room.wire.cycleId == cycle_id}
        for rid in rooms:
            del state.chat.rooms[rid]
        state.chat.deliveries = [d for d in state.chat.deliveries if d.room_id not in rooms]
        state.chat.idempotency = {
            key: value
            for key, value in state.chat.idempotency.items()
            if cycle_id not in key[1] and not any(rid in key[1] for rid in rooms)
        }
        for name in ("formations", "skies", "activeJobs", "activeSkyJobs", "skyVersions"):
            state.records.setdefault(name, {}).pop(cycle_id, None)
        state.records["jobs"] = {
            key: value
            for key, value in state.records.get("jobs", {}).items()
            if value.get("cycleId") != cycle_id
        }
        state.records["publicEvents"] = {
            key: value
            for key, value in state.records.get("publicEvents", {}).items()
            if value.get("cycleId") != cycle_id
        }
        retained = {player for room in state.chat.rooms.values() for player in room.members}
        state.records["chatProfiles"] = {
            player: profile
            for player, profile in state.records.get("chatProfiles", {}).items()
            if player in retained
        }
        # The published ClarifyStore has only answer IDs, not cycle ownership.
        # Conservative cache deletion prevents derived decisions outliving deletion.
        state.records["clarifyDecisions"] = {}

    def purge_retention(self):
        """Actual first lock time governs all cycle-private workflow retention."""
        with self.cycles.serialized():
            answers = getattr(self, "answers", None)
            if answers is not None:
                answers.purge_expired()
            with self.repository.transaction() as state:
                for cycle_id, metadata in state.records.get("cycles", {}).items():
                    if metadata.get("retentionPurgedAt"):
                        continue
                    locked_at = metadata.get("lockedAt")
                    if locked_at and self.clock() >= policy.moment(locked_at) + timedelta(days=14):
                        self._purge_cycle(state, cycle_id)
                        metadata["retentionPurgedAt"] = policy.stamp(self.clock())

    def on_changed(self, value):
        cycle = WeeklyCycle.model_validate(value)
        with self.repository.transaction() as state:
            old = state.records.setdefault("cycles", {}).get(cycle.cycleId)
            if old and old["cycle"]["status"] != "open" and cycle.status == "open":
                self._purge_cycle(state, cycle.cycleId)
            metadata = {"cycle": cycle.model_dump()}
            if old and "lockedAt" in old and cycle.status != "open":
                metadata["lockedAt"] = old["lockedAt"]
            state.records["cycles"][cycle.cycleId] = metadata
            self._public_event(state, cycle, {"type": "cycle.updated", "cycle": cycle.model_dump()})

    def on_locked(self, value):
        cycle = WeeklyCycle.model_validate(value)
        with self.repository.transaction() as state:
            metadata = state.records.setdefault("cycles", {}).setdefault(
                cycle.cycleId, {"cycle": cycle.model_dump()}
            )
            metadata.setdefault("lockedAt", policy.stamp(self.clock()))
            self._enqueue(state, cycle)

    def _enqueue(self, state, cycle, *, manual_retry=False):
        active = state.records.setdefault("activeJobs", {}).get(cycle.cycleId)
        previous = state.records.get("jobs", {}).get(active)
        if previous and not (
            manual_retry and previous["status"] == "failed" and previous["attempts"] >= 3
        ):
            return active
        job_id = str(uuid4())
        state.records.setdefault("jobs", {})[job_id] = {
            "jobId": job_id,
            "kind": "formation",
            "cycleId": cycle.cycleId,
            "communityId": cycle.communityId,
            "status": "pending",
            "attempts": 0,
            "availableAt": policy.stamp(self.clock()),
        }
        state.records["activeJobs"][cycle.cycleId] = job_id
        return job_id

    @staticmethod
    def _mutual_count(state, cycle_id):
        return sum(
            len(room.reveals) for room in state.chat.rooms.values() if room.wire.cycleId == cycle_id
        )

    def _enqueue_sky(self, state, cycle_id, entry, *, force=False):
        """Called only inside a short workflow transaction; never calls owners."""
        mutual = self._mutual_count(state, cycle_id)
        cache = state.records.get("skies", {}).get(cycle_id)
        version = state.records.get("skyVersions", {}).get(cycle_id, {})
        if (
            cache is not None
            and cache.get("mutualReveals") == mutual
            and version.get("formationJobId") == entry["jobId"]
        ):
            return None
        active_map = state.records.setdefault("activeSkyJobs", {})
        active = state.records.get("jobs", {}).get(active_map.get(cycle_id))
        same_target = active and (
            active.get("formationJobId") == entry["jobId"]
            and active.get("targetMutualReveals") == mutual
        )
        if same_target and active["status"] in {"pending", "running", "failed"}:
            if active["attempts"] < 3:
                return active["jobId"]
            if not force:
                return None
        job_id = str(uuid4())
        state.records.setdefault("jobs", {})[job_id] = {
            "jobId": job_id,
            "kind": "sky",
            "cycleId": cycle_id,
            "communityId": entry["communityId"],
            "formationJobId": entry["jobId"],
            "targetMutualReveals": mutual,
            "status": "pending",
            "attempts": 0,
            "availableAt": policy.stamp(self.clock()),
        }
        active_map[cycle_id] = job_id
        return job_id

    def request_sky_for_room(self, room_id):
        """Queue a deduplicated count refresh after an authenticated mutual reveal."""
        with self.repository.transaction() as state:
            room = state.chat.rooms.get(room_id)
            if room is None:
                return None
            cycle_id = room.wire.cycleId
            metadata = state.records.get("cycles", {}).get(cycle_id, {})
            if metadata.get("cycle", {}).get("status") != "revealed":
                return None
            entry = state.records.get("formations", {}).get(cycle_id)
            return self._enqueue_sky(state, cycle_id, entry) if entry else None

    def _record_failure(self, job_id, code, *, attempt_token=None, terminal=False):
        code = code if code in ERRORS else "PROVIDER_UNAVAILABLE"
        with self.repository.transaction() as state:
            current = state.records.get("jobs", {}).get(job_id)
            if current is None or current["status"] == "succeeded":
                return
            if attempt_token is not None and current.get("attemptToken") != attempt_token:
                return
            if attempt_token is None and current["status"] == "running":
                until = current.get("leaseUntil")
                if until and policy.moment(until) > self.clock():
                    return
            attempts = max(1, min(3, current["attempts"]))
            if terminal or code in {
                "NOT_FOUND",
                "CYCLE_LOCKED",
                "STALE_REVISION",
                "FORBIDDEN",
                "INVALID_INPUT",
            }:
                attempts = 3
            current.update(
                status="failed",
                attempts=attempts,
                failureCode=code,
                availableAt=policy.stamp(self.clock() + timedelta(seconds=2**attempts)),
            )
            current.pop("leaseUntil", None)

    def enqueue(self, actor, cycle_id, key):
        self.privacy.require_operator(actor)
        gate = self.cycles.gate(cycle_id)
        if gate.cycle.communityId != actor.community_id:
            raise ServiceError("NOT_FOUND")
        if gate.cycle.status not in {"locked", "forming"}:
            raise ServiceError("CYCLE_LOCKED")
        with self.cycles.commit_guard(cycle_id, gate.revision):
            with self.repository.transaction() as state:
                route = f"/operator/cycles/{cycle_id}/form"
                fingerprint, previous = policy.replay_command(
                    state.chat, actor.player_id, route, key, {}
                )
                if previous:
                    return previous
                job_id = self._enqueue(state, gate.cycle, manual_retry=True)
                committed = state.records.get("formations", {}).get(cycle_id)
                if committed and state.records["jobs"][job_id]["status"] == "succeeded":
                    job_id = self._enqueue_sky(state, cycle_id, committed, force=True) or job_id
                result = {"jobId": job_id, "status": "pending"}
                state.chat.idempotency[(actor.player_id, route, key)] = (fingerprint, result)
                return result

    def job(self, actor, job_id, request_id):
        self.privacy.require_operator(actor)
        with self.repository.transaction() as state:
            job = state.records.get("jobs", {}).get(job_id)
            if not job or job["communityId"] != actor.community_id:
                raise ServiceError("NOT_FOUND")
            result = {"jobId": job_id, "status": job["status"]}
            if job["status"] == "succeeded":
                result["result"] = {"cycleId": job["cycleId"]}
            elif job["status"] == "failed":
                code = job.get("failureCode", "PROVIDER_UNAVAILABLE")
                code = code if code in ERRORS else "PROVIDER_UNAVAILABLE"
                _, message, retryable = ERRORS.get(code, ERRORS["PROVIDER_UNAVAILABLE"])
                result["error"] = {
                    "code": code,
                    "message": message,
                    "requestId": request_id,
                    "retryable": retryable,
                }
            return result

    def on_revealed(self, value):
        cycle = WeeklyCycle.model_validate(value)
        gate = self.cycles.gate(cycle.cycleId)
        with self.repository.transaction() as state:
            entry = deepcopy(state.records.get("formations", {}).get(cycle.cycleId))
        if entry is None:
            raise ServiceError("PROVIDER_UNAVAILABLE")
        from server.orchestration.wire import FormationSuccess

        result = FormationSuccess.model_validate(entry["result"])
        with self.cycles.commit_guard(cycle.cycleId, gate.revision, "revealed"):
            with self.formation.publish_guard(
                cycle.cycleId, entry["privacyRevision"], entry["eligibleIds"]
            ):
                with self.repository.transaction() as state:
                    previous_rooms = set(state.chat.rooms)
                    policy.open_rooms(
                        state.chat,
                        cycle,
                        result.constellations,
                        set(entry["eligibleIds"]),
                        entry["blockedPairs"],
                        effective_now(cycle, self.clock()),
                    )
                    by_id = {c.constellationId: c for c in result.constellations}
                    synthetic = state.records.get("syntheticPlayers", {})
                    for room_id in set(state.chat.rooms) - previous_rooms:
                        room = state.chat.rooms[room_id]
                        if cycle.demoTiming:
                            room.wire = room.wire.model_copy(
                                update={"opensAt": policy.stamp(self.clock())}
                            )
                        fallback = "(Fallback grouping)" in by_id[room.wire.constellationId].name
                        renamed = {}
                        for index, (player_id, handle) in enumerate(room.members.items(), 1):
                            seeded = (
                                synthetic.get(player_id, {}).get("communityId") == cycle.communityId
                            )
                            if seeded and fallback:
                                renamed[handle] = f"Star{index} Synthetic player Fallback grouping"
                            elif seeded:
                                renamed[handle] = f"Star {index} (Synthetic player)"
                            elif fallback:
                                renamed[handle] = f"Star {index} (Fallback grouping)"
                        room.members = {p: renamed.get(h, h) for p, h in room.members.items()}
                        room.wire = room.wire.model_copy(
                            update={
                                "members": [
                                    member.model_copy(
                                        update={"handle": renamed.get(member.handle, member.handle)}
                                    )
                                    for member in room.wire.members
                                ]
                            }
                        )
                    if cycle.cycleId in state.records.get("skies", {}):
                        self._public_event(
                            state, cycle, {"type": "sky.updated", "cycleId": cycle.cycleId}
                        )

    def can_reveal(self, cycle_id):
        """Short app-owned precondition before the cycle advances to revealed."""
        gate = self.cycles.gate(cycle_id)
        if gate.cycle.status not in {"forming", "revealed"}:
            raise ServiceError("CYCLE_LOCKED")
        with self.repository.transaction() as state:
            entry = deepcopy(state.records.get("formations", {}).get(cycle_id))
        if entry is None:
            raise ServiceError("PROVIDER_UNAVAILABLE")
        with self.cycles.commit_guard(cycle_id, gate.revision):
            with self.formation.publish_guard(
                cycle_id, entry["privacyRevision"], entry["eligibleIds"]
            ):
                return True

    async def run_job(self, job_id):
        token = None
        attempt = None
        try:
            with self.repository.transaction() as state:
                job = deepcopy(state.records.get("jobs", {}).get(job_id))
            if not job:
                return None
            token = MODEL_COMMUNITY.set(job["communityId"])
            if job.get("kind", "formation") == "sky":
                return await self._run_sky_job(job_id)
            attempt = FormationAttempt(self, job_id, job["cycleId"])
            result = None
            if job["status"] != "succeeded":
                result = await form_once(
                    attempt, attempt, job["cycleId"], timeout_seconds=self.timeout_seconds
                )
            # The formation commit and Sky enqueue are one durable transaction.
            # A resumed succeeded job repairs only its unfinished Sky phase.
            with self.repository.transaction() as state:
                entry = state.records.get("formations", {}).get(job["cycleId"])
                sky_id = self._enqueue_sky(state, job["cycleId"], entry) if entry else None
            if sky_id is not None:
                await self.run_job(sky_id)
            return result
        except asyncio.CancelledError:
            raise
        except Exception as error:
            task = asyncio.current_task()
            if task is not None and task.cancelling():
                raise asyncio.CancelledError() from None
            # claim() is outside form_once's try; record it instead of leaving a
            # forever-pending attempts=0 job. Lease owners remain CAS-protected.
            if attempt is not None:
                claimed = getattr(attempt, "claimed", None)
                try:
                    self._record_failure(
                        job_id,
                        getattr(error, "code", "PROVIDER_UNAVAILABLE"),
                        attempt_token=claimed.get("attemptToken") if claimed else None,
                        terminal=claimed is None,
                    )
                except Exception:
                    pass  # Retry from the durable lease after storage recovers.
            return None
        finally:
            if token is not None:
                MODEL_COMMUNITY.reset(token)

    async def refresh_sky(self, cycle_id):
        """Explicit server-side refresh; durable retries stay in a separate job."""
        with self.repository.transaction() as state:
            entry = state.records.get("formations", {}).get(cycle_id)
            if entry is None:
                raise ServiceError("NOT_FOUND")
            job_id = self._enqueue_sky(state, cycle_id, entry)
            cached = deepcopy(state.records.get("skies", {}).get(cycle_id))
        return await self.run_job(job_id) if job_id else cached

    def _claim_sky(self, job_id):
        with self.repository.transaction() as state:
            job = deepcopy(state.records.get("jobs", {}).get(job_id))
        if not job or not self._runnable(job):
            return None
        with self.cycles.serialized():
            gate = self.cycles.gate(job["cycleId"])
            if gate.cycle.status not in {"forming", "revealed"}:
                raise ServiceError("CYCLE_LOCKED")
            with self.repository.transaction() as state:
                entry = deepcopy(state.records.get("formations", {}).get(job["cycleId"]))
                mutual = self._mutual_count(state, job["cycleId"])
            if (
                entry is None
                or entry["jobId"] != job["formationJobId"]
                or mutual != job["targetMutualReveals"]
            ):
                raise ServiceError("STALE_REVISION")
            # Verify the ORIGINAL formation lease before M8 sees any aggregates.
            with self.formation.publish_guard(
                job["cycleId"], entry["privacyRevision"], entry["eligibleIds"]
            ):
                lease = self.formation.prepare_formation(job["cycleId"], gate.cycle.communityId)
                with self.repository.transaction() as state:
                    current = state.records["jobs"].get(job_id)
                    if current is None or not self._runnable(current):
                        return None
                    if state.records.get("activeSkyJobs", {}).get(job["cycleId"]) != job_id:
                        raise ServiceError("STALE_REVISION")
                    current.update(
                        status="running",
                        attempts=current["attempts"] + 1,
                        attemptToken=str(uuid4()),
                        leaseUntil=policy.stamp(
                            self.clock() + timedelta(seconds=self.timeout_seconds + 15)
                        ),
                    )
                    claimed = {**deepcopy(current), "cycleRevision": gate.revision}
            return claimed, entry, lease, gate.cycle

    async def _run_sky_job(self, job_id):
        from server.app.planning_stores import StagedThemeStore, load_matching_result

        claimed = None
        try:
            snapshot = self._claim_sky(job_id)
            if snapshot is None:
                return None
            claimed, entry, lease, cycle = snapshot
            themes = StagedThemeStore()
            themes.save(claimed["cycleId"], load_matching_result(entry["privateFormation"]))
            port = self.matching_factory(lease, themes)
            threshold = 3 if cycle.demoTiming else 25
            if hasattr(port, "compute_sky"):
                call = port.compute_sky(
                    claimed["cycleId"], threshold, mutual_reveals=claimed["targetMutualReveals"]
                )
            else:
                call = port.computeSky(claimed["cycleId"], threshold)
            raw = await asyncio.wait_for(call, timeout=self.timeout_seconds)
            sky = SkyStats.model_validate(raw)
            if (
                sky.cycleId != claimed["cycleId"]
                or sky.threshold != threshold
                or sky.mutualReveals != claimed["targetMutualReveals"]
            ):
                raise ServiceError("PROVIDER_UNAVAILABLE")
            texts = [answer["text"] for answer in lease.snapshot["answers"]]
            for text in [*(theme.label for theme in sky.themes), *sky.headlines]:
                if self.guard.check(text, texts) != {"ok": True, "reasons": []}:
                    raise ServiceError("PROVIDER_UNAVAILABLE")
            # A legitimate forming -> revealed transition may occur while M8
            # runs. The original formation ID and privacy lease still govern
            # publication; a mere phase revision must not strand Sky forever.
            with self._sky_publish_guard(claimed["cycleId"]) as publication:
                with self.formation.publish_guard(
                    claimed["cycleId"], entry["privacyRevision"], entry["eligibleIds"]
                ):
                    with self.repository.transaction() as state:
                        current = state.records["jobs"].get(job_id)
                        active = state.records.get("formations", {}).get(claimed["cycleId"])
                        if (
                            current is None
                            or current["status"] != "running"
                            or current.get("attemptToken") != claimed["attemptToken"]
                            or policy.moment(current["leaseUntil"]) <= self.clock()
                            or active is None
                            or active["jobId"] != claimed["formationJobId"]
                            or self._mutual_count(state, claimed["cycleId"])
                            != claimed["targetMutualReveals"]
                            or state.records.get("activeSkyJobs", {}).get(claimed["cycleId"])
                            != job_id
                        ):
                            raise ServiceError("STALE_REVISION")
                        state.records.setdefault("skies", {})[claimed["cycleId"]] = sky.model_dump()
                        state.records.setdefault("skyVersions", {})[claimed["cycleId"]] = {
                            "formationJobId": claimed["formationJobId"],
                            "skyJobId": job_id,
                        }
                        current["status"] = "succeeded"
                        current.pop("failureCode", None)
                        current.pop("leaseUntil", None)
                        if publication.status == "revealed":
                            self._public_event(
                                state,
                                publication,
                                {"type": "sky.updated", "cycleId": claimed["cycleId"]},
                            )
            return sky.model_dump()
        except asyncio.CancelledError:
            if claimed is not None:
                try:
                    self._record_failure(
                        job_id, "PROVIDER_UNAVAILABLE", attempt_token=claimed["attemptToken"]
                    )
                except Exception:
                    pass
            raise
        except Exception as error:
            self._record_failure(
                job_id,
                getattr(error, "code", "PROVIDER_UNAVAILABLE"),
                attempt_token=claimed.get("attemptToken") if claimed else None,
                terminal=claimed is None,
            )
            return None

    @contextmanager
    def _sky_publish_guard(self, cycle_id):
        with self.cycles.serialized():
            gate = self.cycles.gate(cycle_id)
            if gate.cycle.status not in {"forming", "revealed"}:
                raise ServiceError("CYCLE_LOCKED")
            with self.cycles.commit_guard(cycle_id, gate.revision):
                yield gate.cycle

    def sky(self, actor, cycle_id):
        self.drain_notices()
        self.privacy.require_consent(actor)
        gate = self.cycles.gate(cycle_id)
        if gate.cycle.communityId != actor.community_id or gate.cycle.status != "revealed":
            raise ServiceError("NOT_FOUND")
        with self.repository.transaction() as state:
            entry = deepcopy(state.records.get("formations", {}).get(cycle_id))
            sky = deepcopy(state.records.get("skies", {}).get(cycle_id))
        if not entry or not sky:
            raise ServiceError("PROVIDER_UNAVAILABLE")
        with self.cycles.commit_guard(cycle_id, gate.revision, "revealed"):
            with self.formation.publish_guard(
                cycle_id, entry["privacyRevision"], entry["eligibleIds"]
            ):
                return SkyStats.model_validate(sky).model_dump()

    def public_events(self, actor, after):
        with self.repository.transaction() as state:
            return [
                deepcopy(item["event"])
                for item in state.records.get("publicEvents", {}).values()
                if item["communityId"] == actor.community_id and item["event"]["seq"] > after
            ]

    def drain_notices(self):
        notices = []
        while True:
            try:
                notices.append(self.notices.get_nowait())
            except Empty:
                break
        for index, notice in enumerate(notices):
            try:
                if notice.kind not in {"consent_revoked", "answer_deleted", "data_deleted"}:
                    continue
                with self.cycles.serialized():
                    if hasattr(self, "chat"):
                        self.chat.forget_player(
                            notice.player_id,
                            notice.cycle_id if notice.kind == "answer_deleted" else None,
                        )
                    with self.repository.transaction() as state:
                        for cycle_id, entry in list(state.records.get("formations", {}).items()):
                            if notice.player_id in entry["eligibleIds"] and (
                                notice.kind != "answer_deleted" or cycle_id == notice.cycle_id
                            ):
                                state.records["formations"].pop(cycle_id, None)
                                state.records.get("skies", {}).pop(cycle_id, None)
            except BaseException:
                for unprocessed in notices[index:]:
                    self.notices.put(unprocessed)
                raise

    def _runnable(self, job):
        if job["attempts"] >= 3:
            return False
        if policy.moment(job.get("availableAt", policy.stamp(self.clock()))) > self.clock():
            return False
        return job["status"] in {"pending", "failed"} or (
            job["status"] == "running" and policy.moment(job["leaseUntil"]) <= self.clock()
        )

    def _pending_jobs(self):
        with self.repository.transaction() as state:
            # Repair legacy/crash gaps without another formation/model grouping.
            for cycle_id, entry in state.records.get("formations", {}).items():
                metadata = state.records.get("cycles", {}).get(cycle_id, {})
                if metadata.get("cycle", {}).get("status") in {"forming", "revealed"}:
                    self._enqueue_sky(state, cycle_id, entry)
            for job in state.records.get("jobs", {}).values():
                if (
                    job["status"] == "running"
                    and job["attempts"] >= 3
                    and policy.moment(job["leaseUntil"]) <= self.clock()
                ):
                    job.update(status="failed", failureCode="PROVIDER_UNAVAILABLE")
                    job.pop("leaseUntil", None)
            return list(deepcopy(state.records.get("jobs", {})).values()), list(
                state.records.get("cycles", {})
            )

    async def loop(self, chat):
        running = {}
        try:
            while True:
                try:
                    self.drain_notices()
                    self.purge_retention()
                    jobs, cycles = self._pending_jobs()
                    for cycle_id in cycles:
                        try:
                            self.cycles.gate(cycle_id)
                            chat.expire(cycle_id)
                        except Exception:
                            pass  # State remains fail-closed and is retried on the next iteration.
                    for job_id, task in list(running.items()):
                        if task.done():
                            if not task.cancelled():
                                task.exception()  # Do not log private errors.
                            del running[job_id]
                    for job in jobs:
                        if len(running) >= 2:
                            break
                        if job["jobId"] not in running and self._runnable(job):
                            running[job["jobId"]] = asyncio.create_task(self.run_job(job["jobId"]))
                except asyncio.CancelledError:
                    raise
                except Exception:
                    pass  # A transient database/privacy failure must not kill the worker.
                await asyncio.sleep(0.5)
        finally:
            for task in running.values():
                task.cancel()
            await asyncio.gather(*running.values(), return_exceptions=True)


class FormationAttempt:
    """Private adapter onto the existing bounded form_once worker."""

    def __init__(self, runtime, job_id, cycle_id):
        self.runtime = runtime
        self.job_id = job_id
        self.cycle_id = cycle_id
        self.lease = None
        self.themes = None
        self.port = None
        self.claimed = None

    async def claim(self, cycle_id):
        from server.app.planning_stores import StagedThemeStore

        rt = self.runtime
        with rt.cycles.serialized():
            with rt.repository.transaction() as state:
                pending = state.records.get("jobs", {}).get(self.job_id)
                if pending is None or not rt._runnable(pending):
                    return None
            gate = rt.cycles.gate(cycle_id)
            if gate.cycle.status == "locked":
                rt.cycles.advance(cycle_id, "forming")
                gate = rt.cycles.gate(cycle_id)
            if gate.cycle.status != "forming":
                raise ServiceError("CYCLE_LOCKED")
            self.lease = rt.formation.prepare_formation(cycle_id, gate.cycle.communityId)
            with rt.formation.publish_guard(cycle_id, self.lease.revision, self.lease.player_ids):
                with rt.repository.transaction() as state:
                    job = state.records["jobs"][self.job_id]
                    if job["status"] == "succeeded":
                        return None
                    if job["status"] == "running" and policy.moment(job["leaseUntil"]) > rt.clock():
                        return None
                    if job["attempts"] >= 3 or policy.moment(job["availableAt"]) > rt.clock():
                        return None
                    job.update(
                        status="running",
                        attempts=job["attempts"] + 1,
                        attemptToken=str(uuid4()),
                        leaseUntil=policy.stamp(
                            rt.clock() + timedelta(seconds=rt.timeout_seconds + 15)
                        ),
                    )
                    claimed = {
                        **deepcopy(job),
                        "cycleRevision": gate.revision,
                        "privacyRevision": self.lease.revision,
                        "eligibleIds": sorted(self.lease.player_ids),
                        "blockedPairs": deepcopy(self.lease.snapshot["blockedPairs"]),
                    }
            self.claimed = claimed
            self.themes = StagedThemeStore()
            self.port = rt.matching_factory(self.lease, self.themes)
            return claimed

    async def cycle(self, cycle_id):
        return wire_cycle(self.runtime.cycles.gate(cycle_id).cycle)

    async def form(self, cycle_id):
        return await self.port.form(cycle_id)

    async def commit(self, job, result):
        from server.app.planning_stores import dump_matching_result

        rt = self.runtime
        with rt.cycles.commit_guard(self.cycle_id, job["cycleRevision"], "forming"):
            with rt.formation.publish_guard(
                self.cycle_id, job["privacyRevision"], job["eligibleIds"]
            ):
                texts = [a["text"] for a in self.lease.snapshot["answers"]]
                if any(
                    rt.guard.check(c.name, texts) != {"ok": True, "reasons": []}
                    for c in result.constellations
                ):
                    raise ServiceError("PROVIDER_UNAVAILABLE")
                with rt.repository.transaction() as state:
                    current = state.records["jobs"][self.job_id]
                    if (
                        current["status"] != "running"
                        or current["attemptToken"] != job["attemptToken"]
                        or policy.moment(current["leaseUntil"]) <= rt.clock()
                    ):
                        raise ServiceError("STALE_REVISION")
                    private = self.themes.load(self.cycle_id)
                    if private is None:
                        raise ServiceError("PROVIDER_UNAVAILABLE")
                    state.records.setdefault("formations", {})[self.cycle_id] = {
                        "communityId": job["communityId"],
                        "cycleRevision": job["cycleRevision"],
                        "privacyRevision": job["privacyRevision"],
                        "eligibleIds": job["eligibleIds"],
                        "blockedPairs": job["blockedPairs"],
                        "result": result.model_dump(),
                        "privateFormation": dump_matching_result(private),
                        "jobId": self.job_id,
                    }
                    current["status"] = "succeeded"
                    current.pop("failureCode", None)
                    current.pop("leaseUntil", None)
                    rt._enqueue_sky(
                        state, self.cycle_id, state.records["formations"][self.cycle_id]
                    )

    async def fail(self, job, code):
        self.runtime._record_failure(self.job_id, code, attempt_token=job.get("attemptToken"))
