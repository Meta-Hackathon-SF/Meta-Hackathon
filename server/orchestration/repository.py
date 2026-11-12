"""Durable workflow commands. Credentials stay in the API/worker processes.

Only validated internal proposal/plan artifacts enter this repository; public
HTTP commands never supply candidate data, actor identity, or fixture mode.
"""

import hashlib
import json
import re
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import psycopg
from psycopg.types.json import Jsonb

from server.orchestration.domain import WorkflowError, requires_reconfirmation
from server.orchestration.wire import validate_acceptance, validate_plan, validate_proposal
from server.privacy import Actor, Database, PrivacyService

SQL_ERRORS = {
    "GQ400": "INVALID_INPUT",
    "GQ401": "UNAUTHENTICATED",
    "GQ403": "CONSENT_REQUIRED",
    "GQ404": "NOT_FOUND",
    "GQ409": "STALE_REVISION",
    "GQ410": "CAPACITY_REACHED",
    "42501": "FORBIDDEN",
    "23503": "INVALID_INPUT",
    "23505": "IDEMPOTENCY_CONFLICT",
    "23514": "INVALID_INPUT",
}


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _stamp(value: datetime | str | None) -> str | None:
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
    return value


def _identity(actor: Actor) -> str:
    if not isinstance(actor, Actor):
        raise WorkflowError("UNAUTHENTICATED")
    return actor.participant_id


class WorkflowRepository:
    """One transaction per durable command, independent of provider calls.

    ``worker_database`` is a separate non-owner connection role belonging to
    both gq_api and workflow_worker. Ordinary API credentials cannot lease or
    publish jobs. ``mode`` is trusted server configuration, never request data.
    """

    def __init__(
        self,
        database: Database,
        privacy: PrivacyService,
        *,
        worker_database: Database | None = None,
        mode: str = "live",
        proposal_projection: Callable | None = None,
        plan_projection: Callable | None = None,
    ):
        if mode not in {"live", "fixture", "replay"}:
            raise ValueError("Unknown server workflow mode")
        self.database = database
        self.privacy = privacy
        self.worker_database = worker_database
        self.mode = mode
        # Projection ports require privacy-owner acknowledgment/public export.
        # Inject approved adapters instead of importing another owner's internals.
        self.proposal_projection = proposal_projection
        self.plan_projection = plan_projection

    @staticmethod
    def _project(projection: Callable | None, artifact: dict, candidates: list) -> dict:
        if projection is None:
            raise WorkflowError("PROVIDER_UNAVAILABLE")
        result = projection(artifact, candidates)
        return result if isinstance(result, dict) else result.wire()

    @contextmanager
    def _transaction(self, participant_id: str | None, *, worker: bool = False) -> Iterator:
        database = self.worker_database if worker else self.database
        if database is None:
            raise WorkflowError("PROVIDER_UNAVAILABLE")
        try:
            with database.as_actor(participant_id) as connection:
                yield connection
        except psycopg.Error as error:
            # Never publish database exception text or connection details.
            raise WorkflowError(SQL_ERRORS.get(error.sqlstate, "PROVIDER_UNAVAILABLE")) from None

    def ready(self) -> bool:
        try:
            with self._transaction(None) as connection:
                row = connection.execute(
                    "SELECT to_regclass('workflow.quests') IS NOT NULL AS ready"
                ).fetchone()
                return row["ready"] is True
        except Exception:
            return False

    def _command(
        self,
        actor: Actor,
        route: str,
        key: str,
        body: dict,
        operation: Callable,
    ) -> dict:
        participant_id = _identity(actor)
        if not isinstance(key, str) or not re.fullmatch(r"[!-~]{1,128}", key):
            raise WorkflowError("INVALID_INPUT")
        body_hash = hashlib.sha256(_canonical(body).encode()).hexdigest()
        with self._transaction(participant_id) as connection:
            # Serialize reuse of one actor/route/key before querying the ledger.
            connection.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                (_canonical([participant_id, route, key]),),
            )
            previous = connection.execute(
                "SELECT body_hash,result FROM workflow.idempotency "
                "WHERE participant_id=%s AND route=%s AND key=%s",
                (participant_id, route, key),
            ).fetchone()
            if previous:
                if previous["body_hash"] != body_hash:
                    raise WorkflowError("IDEMPOTENCY_CONFLICT")
                return previous["result"]
            result = operation(connection)
            # Store operation identity/ack, not copied peer profiles or private constraints.
            connection.execute(
                "INSERT INTO workflow.idempotency(participant_id,route,key,body_hash,result) "
                "VALUES(%s,%s,%s,%s,%s)",
                (participant_id, route, key, body_hash, Jsonb(result)),
            )
            return result

    @staticmethod
    def _load(connection, quest_id: str) -> dict:
        return connection.execute("SELECT workflow.lock_quest(%s) AS body", (quest_id,)).fetchone()[
            "body"
        ]

    @staticmethod
    def _check_versions(connection, community_id: str, versions: list[dict]) -> None:
        ids = [version["participantId"] for version in versions]
        rows = connection.execute(
            "SELECT * FROM privacy.member_versions(%s,%s)", (community_id, ids)
        ).fetchall()
        by_id = {row["participant_id"]: row for row in rows}
        for version in versions:
            row = by_id.get(version["participantId"])
            if row is None or not row["eligible"]:
                raise WorkflowError("CONSENT_REQUIRED")
            if (row["intent_version"], row["consent_version"]) != (
                version["intentVersion"],
                version["consentVersion"],
            ):
                raise WorkflowError("STALE_REVISION")

    def _candidates(self, actor: Actor, community_id: str) -> list:
        self.privacy.require_eligible(actor, community_id)
        return self.privacy.authorized_candidates(actor, community_id)

    def _guard_mode(self, proposal: dict, candidates: list) -> None:
        if self.mode != "live":
            return
        if proposal["evidence"]["source"] != "live":
            raise WorkflowError("FORBIDDEN")
        ids = set(proposal["memberIds"])
        if any(
            candidate.public_profile.is_synthetic
            for candidate in candidates
            if candidate.public_profile.participant_id in ids
        ):
            raise WorkflowError("FORBIDDEN")

    def create_quest(
        self,
        actor: Actor,
        proposal: dict,
        members: list[dict],
        *,
        idempotency_key: str,
    ) -> dict:
        participant_id = _identity(actor)
        proposal = validate_proposal(proposal)
        if participant_id not in proposal["memberIds"]:
            raise WorkflowError("FORBIDDEN")
        candidates = self._candidates(actor, proposal["communityId"])
        public = self._project(self.proposal_projection, proposal, candidates)
        if members != public["members"]:
            raise WorkflowError("INVALID_INPUT")
        self._guard_mode(proposal, candidates)

        def create(connection):
            self._check_versions(connection, proposal["communityId"], proposal["memberVersions"])
            quest_id = connection.execute(
                "SELECT workflow.create_quest(%s,%s,%s) AS quest_id",
                ("quest_" + uuid4().hex, Jsonb(proposal), self.mode),
            ).fetchone()["quest_id"]
            return {"questId": quest_id}

        result = self._command(
            actor,
            "POST /quests",
            idempotency_key,
            {"proposal": proposal, "members": members},
            create,
        )
        return self.snapshot(actor, result["questId"])

    def propose_plan(
        self, actor: Actor, quest_id: str, plan: dict, *, idempotency_key: str
    ) -> dict:
        plan = validate_plan(plan)
        current = self._get(actor, quest_id)
        candidates = self._candidates(actor, current["community_id"])
        self._project(self.plan_projection, plan, candidates)
        if self.mode == "live" and plan["evidence"]["source"] != "live":
            raise WorkflowError("FORBIDDEN")

        def propose(connection):
            quest = self._load(connection, quest_id)
            if plan["proposalId"] != quest["proposal_id"]:
                raise WorkflowError("INVALID_INPUT")
            expected_ids = set(quest["proposal"]["memberIds"])
            if {version["participantId"] for version in plan["memberVersions"]} != expected_ids:
                raise WorkflowError("INVALID_INPUT")
            if quest["plan"] is not None and requires_reconfirmation(quest["plan"], plan):
                if plan["revision"] != quest["revision"] + 1:
                    raise WorkflowError("STALE_REVISION")
            elif plan["revision"] != quest["revision"]:
                raise WorkflowError("STALE_REVISION")
            self._check_versions(connection, quest["community_id"], plan["memberVersions"])
            connection.execute("SELECT workflow.save_plan(%s,%s)", (quest_id, Jsonb(plan)))
            return {"questId": quest_id}

        self._command(actor, f"POST /quests/{quest_id}/plan", idempotency_key, plan, propose)
        return self.snapshot(actor, quest_id)

    def accept(
        self,
        actor: Actor,
        quest_id: str,
        *,
        revision: int,
        choice: str,
        idempotency_key: str,
    ) -> dict:
        body = validate_acceptance({"revision": revision, "choice": choice})
        current = self._get(actor, quest_id)
        self._candidates(actor, current["community_id"])

        def accept(connection):
            quest = self._load(connection, quest_id)
            if quest["mode"] != self.mode:
                raise WorkflowError("FORBIDDEN")
            if quest["plan"] is None:
                raise WorkflowError("STALE_REVISION")
            self._check_versions(connection, quest["community_id"], quest["plan"]["memberVersions"])
            acceptance = connection.execute(
                "SELECT workflow.record_acceptance(%s,%s,%s) AS body",
                (quest_id, body["revision"], body["choice"]),
            ).fetchone()["body"]
            return {"acceptance": acceptance}

        result = self._command(
            actor, f"POST /quests/{quest_id}/accept", idempotency_key, body, accept
        )
        return {"acceptance": result["acceptance"], "snapshot": self.snapshot(actor, quest_id)}

    def _get(self, actor: Actor, quest_id: str) -> dict:
        with self._transaction(_identity(actor)) as connection:
            return self._load(connection, quest_id)

    def snapshot(self, actor: Actor, quest_id: str) -> dict:
        # Hold the quest lock while reading the event so publication cannot produce
        # a snapshot with a pre-publication status and a post-publication event.
        with self._transaction(_identity(actor)) as connection:
            quest = self._load(connection, quest_id)
            row = connection.execute(
                "SELECT body FROM workflow.events WHERE quest_id=%s", (quest_id,)
            ).fetchone()
        candidates = self._candidates(actor, quest["community_id"])
        profiles = {
            candidate.public_profile.participant_id: candidate.public_profile.wire()
            for candidate in candidates
        }
        ids = quest["proposal"]["memberIds"]
        if not set(ids).issubset(profiles):
            raise WorkflowError("CONSENT_REQUIRED")
        # Re-run the public leak gate when consented interests change after persistence.
        if quest["plan"] is not None:
            self._project(self.plan_projection, quest["plan"], candidates)
        return {
            "questId": quest_id,
            "communityId": quest["community_id"],
            "revision": quest["revision"],
            "status": quest["status"],
            "members": [profiles[participant_id] for participant_id in ids],
            "acceptedCount": len(quest["acceptedIds"]),
            "capacity": 5,
            "minimumSize": 3,
            "event": row["body"] if row else None,
        }

    @staticmethod
    def _job_wire(job: dict) -> dict:
        return {
            "jobId": job["job_id"],
            "questId": job["quest_id"],
            "communityId": job["community_id"],
            "revision": job["revision"],
            "enqueuedBy": job["enqueued_by"],
            "memberVersions": job["member_versions"],
            "status": job["status"],
            "attempts": job["attempts"],
            "workerId": job["lease_owner"],
            "leaseExpiresAt": _stamp(job["lease_expires_at"]),
            "plan": job["plan"],
            "proposal": job["proposal"],
            "mode": job["mode"],
        }

    def claim_job(self, *, worker_id: str, lease_seconds: int = 30) -> dict | None:
        if not isinstance(worker_id, str) or not 1 <= len(worker_id) <= 128:
            raise WorkflowError("INVALID_INPUT")
        if type(lease_seconds) is not int or not 1 <= lease_seconds <= 300:
            raise WorkflowError("INVALID_INPUT")
        with self._transaction(None, worker=True) as connection:
            job = connection.execute(
                "SELECT workflow.claim_job(%s,%s) AS body", (worker_id, lease_seconds)
            ).fetchone()["body"]
        if job is None:
            return None
        try:
            self.privacy.reauthorize_for_job(job["enqueued_by"], job["community_id"])
        except Exception:
            self.fail_job(job["job_id"], worker_id=worker_id, code="CONSENT_REQUIRED")
            raise
        return self._job_wire(job)

    def complete_job(self, job_id: str, *, worker_id: str, plan: dict) -> dict:
        plan = validate_plan(plan)
        with self._transaction(None, worker=True) as connection:
            job = connection.execute(
                "SELECT workflow.lock_job(%s,%s) AS body", (job_id, worker_id)
            ).fetchone()["body"]
        actor = self.privacy.reauthorize_for_job(job["enqueued_by"], job["community_id"])
        candidates = self._candidates(actor, job["community_id"])
        self._project(self.plan_projection, plan, candidates)
        if job["mode"] != self.mode:
            raise WorkflowError("FORBIDDEN")
        if self.mode == "live" and plan["evidence"]["source"] != "live":
            raise WorkflowError("FORBIDDEN")
        with self._transaction(_identity(actor), worker=True) as connection:
            # Recheck lease and stored version inside the publication transaction.
            job = connection.execute(
                "SELECT workflow.lock_job(%s,%s) AS body", (job_id, worker_id)
            ).fetchone()["body"]
            quest = self._load(connection, job["quest_id"])
            if plan["proposalId"] != quest["proposal_id"]:
                raise WorkflowError("INVALID_INPUT")
            if plan["revision"] != job["revision"]:
                raise WorkflowError("STALE_REVISION")
            if not {version["participantId"] for version in plan["memberVersions"]}.issubset(
                quest["proposal"]["memberIds"]
            ):
                raise WorkflowError("FORBIDDEN")
            self._check_versions(connection, quest["community_id"], job["member_versions"])
            self._check_versions(connection, quest["community_id"], plan["memberVersions"])
            material = requires_reconfirmation(quest["plan"], plan)
            quest_id = connection.execute(
                "SELECT workflow.finish_job(%s,%s,%s,%s) AS quest_id",
                (job_id, worker_id, Jsonb(plan), material),
            ).fetchone()["quest_id"]
        return self.snapshot(actor, quest_id)

    def fail_job(self, job_id: str, *, worker_id: str, code: str) -> None:
        allowed = {
            "INVALID_INPUT",
            "UNAUTHENTICATED",
            "FORBIDDEN",
            "NOT_FOUND",
            "CONSENT_REQUIRED",
            "STALE_REVISION",
            "CAPACITY_REACHED",
            "PROVIDER_UNAVAILABLE",
            "RATE_LIMITED",
            "IDEMPOTENCY_CONFLICT",
        }
        if code not in allowed:
            raise WorkflowError("INVALID_INPUT")
        with self._transaction(None, worker=True) as connection:
            connection.execute("SELECT workflow.fail_job(%s,%s,%s)", (job_id, worker_id, code))

    def messages(self, actor: Actor, quest_id: str) -> list[dict]:
        self.snapshot(actor, quest_id)  # Includes current membership/consent and leak checks.
        with self._transaction(_identity(actor)) as connection:
            rows = connection.execute(
                "SELECT message_id,conversation_id,text,created_at FROM workflow.messages "
                "WHERE quest_id=%s ORDER BY created_at,message_id",
                (quest_id,),
            ).fetchall()
        return [
            {
                "messageId": row["message_id"],
                "conversationId": row["conversation_id"],
                "createdAt": _stamp(row["created_at"]),
                "sender": {"kind": "assistant"},
                "text": row["text"],
            }
            for row in rows
        ]
