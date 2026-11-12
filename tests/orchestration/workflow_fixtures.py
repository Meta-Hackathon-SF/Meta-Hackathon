"""Synthetic workflow fixtures backed by real PostgreSQL and verified test sessions.

No provider is called. The accepted plan is explicitly fixture/replay evidence.
The disposable database and non-bypass roles never contain real participants.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from psycopg import sql
from server.orchestration.repository import WorkflowRepository

from server.privacy import (
    Actor,
    Database,
    PrivacyService,
    build_router,
    install_error_handlers,
)
from server.privacy.fixtures import DEMO_COMMUNITY, seed_community

ROOT = Path(__file__).resolve().parents[2]
COMMUNITY = DEMO_COMMUNITY["community_id"]
AREA = DEMO_COMMUNITY["area_ids"][0]


def utc(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _dsn(dsn: str, *, database: str, user: str | None = None) -> str:
    info = psycopg.conninfo.conninfo_to_dict(dsn)
    info["dbname"] = database
    if user:
        info["user"] = user
    return psycopg.conninfo.make_conninfo(**info)


@pytest.fixture(scope="session")
def workflow_pg() -> Iterator[dict[str, str]]:
    admin_dsn = os.environ.get(
        "GQ_TEST_ADMIN_DSN", "postgresql://postgres@127.0.0.1:54329/postgres"
    )
    try:
        root = psycopg.connect(admin_dsn, autocommit=True, connect_timeout=3)
    except psycopg.OperationalError:
        pytest.skip("Workflow PostgreSQL tests require the disposable test PostgreSQL service")
    suffix = uuid4().hex[:10]
    database, api_login, worker_login = (
        f"gq_workflow_test_{suffix}",
        f"gq_workflow_api_{suffix}",
        f"gq_workflow_worker_{suffix}",
    )
    root.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
    target = _dsn(admin_dsn, database=database)
    try:
        with psycopg.connect(target, autocommit=True) as admin:
            admin.execute((ROOT / "db/privacy/001_privacy_foundation.sql").read_text())
            admin.execute((ROOT / "db/workflow/001_workflow.sql").read_text())
            admin.execute(
                sql.SQL("CREATE ROLE {} LOGIN IN ROLE gq_api").format(sql.Identifier(api_login))
            )
            admin.execute(
                sql.SQL("CREATE ROLE {} LOGIN IN ROLE gq_api, workflow_worker").format(
                    sql.Identifier(worker_login)
                )
            )
        yield {
            "admin_dsn": target,
            "api_dsn": _dsn(admin_dsn, database=database, user=api_login),
            "worker_dsn": _dsn(admin_dsn, database=database, user=worker_login),
        }
    finally:
        root.execute(
            sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(database))
        )
        root.execute(sql.SQL("DROP ROLE IF EXISTS {}").format(sql.Identifier(worker_login)))
        root.execute(sql.SQL("DROP ROLE IF EXISTS {}").format(sql.Identifier(api_login)))
        root.close()


@dataclass
class WorkflowCase:
    repository: WorkflowRepository
    privacy: PrivacyService
    database: Database
    worker_database: Database
    privacy_client: TestClient
    actors: list[Actor]
    tokens: list[str]
    proposal: dict
    plan: dict
    members: list[dict]
    quest_id: str
    dsn: dict[str, str]

    def headers(self, index: int = 0, *, key: str | None = None) -> dict[str, str]:
        result = {"Authorization": f"Bearer {self.tokens[index]}"}
        if key is not None:
            result["Idempotency-Key"] = key
        return result

    def accept(self, index: int, *, key: str | None = None, choice: str = "accept") -> dict:
        return self.repository.accept(
            self.actors[index],
            self.quest_id,
            revision=1,
            choice=choice,
            idempotency_key=key or f"accept-{index}",
        )

    def quorum(self) -> list[dict]:
        return [self.accept(index) for index in range(3)]

    def finalize(self, *, worker_id: str = "fixture-worker") -> tuple[dict, dict]:
        job = self.repository.claim_job(worker_id=worker_id)
        assert job is not None, "Quorum did not persist a pending finalization job"
        snapshot = self.repository.complete_job(job["jobId"], worker_id=worker_id, plan=self.plan)
        return job, snapshot

    def privacy_patch(self, index: int, path: str, body: dict) -> None:
        response = self.privacy_client.patch(
            f"/api/v1/{path}", headers=self.headers(index), json=body
        )
        assert response.status_code == 200


@pytest.fixture
def workflow_case_factory(workflow_pg) -> Iterator[Callable[..., WorkflowCase]]:
    """Each test resets only its own disposable database, then creates labeled guest sessions."""
    with psycopg.connect(workflow_pg["admin_dsn"], autocommit=True) as admin:
        workflow_tables = admin.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'workflow'"
        ).fetchall()
        if workflow_tables:
            admin.execute(
                sql.SQL("TRUNCATE {} CASCADE").format(
                    sql.SQL(", ").join(
                        sql.Identifier("workflow", row[0]) for row in workflow_tables
                    )
                )
            )
        admin.execute("TRUNCATE privacy.participants, privacy.communities CASCADE")
        seed_community(admin)
    database = Database(workflow_pg["api_dsn"], max_size=16)
    worker_database = Database(workflow_pg["worker_dsn"], max_size=8)
    privacy = PrivacyService(database)
    repository = WorkflowRepository(
        database, privacy, worker_database=worker_database, mode="fixture"
    )
    app = FastAPI()
    app.include_router(build_router(privacy), prefix="/api/v1")
    install_error_handlers(app)
    client = TestClient(app)

    def create(*, members: int = 3, proposed: bool = True) -> WorkflowCase:
        actors, tokens = [], []
        start = (datetime.now(UTC) + timedelta(days=1)).replace(microsecond=0)
        window = {"start": utc(start), "end": utc(start + timedelta(hours=2))}
        for index in range(members):
            token, actor, _ = privacy.create_guest_session()
            headers = {"Authorization": f"Bearer {token}"}
            join = client.post(
                f"/api/v1/communities/{COMMUNITY}/join",
                headers=headers,
                json={
                    "displayName": f"Workflow fixture {index + 1} (demo)",
                    "consent": {"matching": True, "modelProcessing": True, "publicInterests": True},
                },
            )
            assert join.status_code == 200
            save = client.put(
                "/api/v1/intents/me",
                headers=headers,
                json={
                    "communityId": COMMUNITY,
                    "expectedVersion": 0,
                    "goal": "meet others through a shared public photo activity",
                    "interests": ["photography", "walking"],
                    "areaId": AREA,
                    "timeZone": "America/Los_Angeles",
                    "availability": [window],
                    "maxBudgetMinor": 1000,
                    "currency": "USD",
                    "maxDurationMinutes": 120,
                    "groupPreference": "small",
                },
            )
            assert save.status_code == 200
            actors.append(actor)
            tokens.append(token)
        wanted = {actor.participant_id for actor in actors}
        candidates = [
            candidate.wire()
            for candidate in privacy.authorized_candidates(actors[0], COMMUNITY)
            if candidate.public_profile.participant_id in wanted
        ]
        by_id = {candidate["publicProfile"]["participantId"]: candidate for candidate in candidates}
        versions = [
            {
                "participantId": actor.participant_id,
                "intentVersion": by_id[actor.participant_id]["intent"]["intentVersion"],
                "consentVersion": by_id[actor.participant_id]["intent"]["consentVersion"],
            }
            for actor in actors
        ]
        evidence = {
            "model": "fixture:accepted-photo-plan",
            "source": "replay",
            "generatedAt": utc(datetime.now(UTC)),
            "latencyMs": 0,
        }
        proposal = {
            "proposalId": f"proposal_fixture_{uuid4().hex}",
            "communityId": COMMUNITY,
            "revision": 1,
            "memberIds": [actor.participant_id for actor in actors],
            "memberVersions": versions,
            "feasibleWindows": [window],
            "sharedInterests": ["photography", "walking"],
            "publicRationale": "A shared public activity fits the group.",
            "evidence": evidence,
        }
        profiles = [by_id[actor.participant_id]["publicProfile"] for actor in actors]
        plan = {
            "planId": f"plan_fixture_{uuid4().hex}",
            "proposalId": proposal["proposalId"],
            "revision": 1,
            "basedOnRevision": None,
            "memberVersions": versions,
            "title": "Public photo walk (fixture)",
            "activity": "Explore a public plaza together.",
            "collaborationTask": "Create a three-photo group story.",
            "venueId": "fixture-approved-public-plaza",
            "start": window["start"],
            "end": utc(start + timedelta(minutes=30)),
            "timeZone": "America/Los_Angeles",
            "costPerPersonMinor": 0,
            "currency": "USD",
            "minimumSize": 3,
            "maximumSize": 5,
            "publicRationale": "A free public activity fits the group.",
            "opener": "Welcome! Pick one photo idea to try together.",
            "evidence": evidence,
        }
        snapshot = repository.create_quest(
            actors[0], proposal, profiles, idempotency_key=f"create-{proposal['proposalId']}"
        )
        if proposed:
            snapshot = repository.propose_plan(
                actors[0], snapshot["questId"], plan, idempotency_key="propose-fixture-plan"
            )
        return WorkflowCase(
            repository,
            privacy,
            database,
            worker_database,
            client,
            actors,
            tokens,
            proposal,
            plan,
            profiles,
            snapshot["questId"],
            workflow_pg,
        )

    try:
        yield create
    finally:
        client.close()
        worker_database.close()
        database.close()


@pytest.fixture
def workflow_scenario(workflow_case_factory) -> WorkflowCase:
    return workflow_case_factory()
