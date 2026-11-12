"""Durable workflow evidence with real PostgreSQL, fixture plans, and test sessions."""

from __future__ import annotations

import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

import psycopg
import pytest

from server.orchestration.domain import WorkflowError
from server.orchestration.repository import WorkflowRepository
from server.privacy import PrivacyError
from server.privacy.projections import project_plan, project_proposal

if TYPE_CHECKING:
    from workflow_fixtures import WorkflowCase

pytest_plugins = ("workflow_fixtures",)

PUBLIC_SNAPSHOT_FIELDS = {
    "questId",
    "communityId",
    "revision",
    "status",
    "members",
    "acceptedCount",
    "capacity",
    "minimumSize",
    "event",
}
PUBLIC_EVENT_FIELDS = {
    "eventId",
    "questId",
    "planId",
    "revision",
    "status",
    "title",
    "venueId",
    "start",
    "end",
    "acceptedMemberIds",
    "conversationId",
}
ERRORS = (WorkflowError, PrivacyError)


def assert_public_snapshot(snapshot: dict) -> None:
    assert set(snapshot) == PUBLIC_SNAPSHOT_FIELDS
    assert snapshot["capacity"] == 5 and snapshot["minimumSize"] == 3
    for member in snapshot["members"]:
        assert set(member) == {"participantId", "displayName", "publicInterests", "isSynthetic"}
    if snapshot["event"] is not None:
        assert set(snapshot["event"]) == PUBLIC_EVENT_FIELDS
    raw = json.dumps(snapshot)
    for forbidden in ["memberVersions", "maxBudgetMinor", "maxDurationMinutes", "confirmedAt"]:
        assert forbidden not in raw


def test_three_verified_test_sessions_create_one_persistent_event(workflow_scenario: WorkflowCase):
    case = workflow_scenario
    initial = case.repository.snapshot(case.actors[0], case.quest_id)
    assert initial["status"] == "proposed" and initial["event"] is None
    outcomes = case.quorum()
    assert [item["snapshot"]["acceptedCount"] for item in outcomes] == [1, 2, 3]
    assert outcomes[-1]["snapshot"]["status"] == "planning"
    assert outcomes[-1]["snapshot"]["event"] is None
    _, final = case.finalize()
    assert final["status"] == "scheduled"
    assert set(final["event"]["acceptedMemberIds"]) == {
        actor.participant_id for actor in case.actors
    }
    assert final["event"]["questId"] == case.quest_id
    assert_public_snapshot(final)
    for actor in case.actors:
        assert case.repository.snapshot(actor, case.quest_id)["event"] == final["event"]
    with psycopg.connect(case.dsn["admin_dsn"]) as admin:
        assert admin.execute(
            "SELECT count(*) FROM workflow.events WHERE quest_id = %s", (case.quest_id,)
        ).fetchone() == (1,)


def test_duplicate_acceptance_and_job_completion_do_not_duplicate_effects(
    workflow_scenario: WorkflowCase,
):
    case = workflow_scenario
    first = case.accept(0, key="one-accept")
    assert case.accept(0, key="one-accept") == first
    repeated_choice = case.accept(0, key="different-key-same-choice")
    assert repeated_choice["snapshot"]["acceptedCount"] == 1
    case.accept(1)
    case.accept(2)
    job, first_event = case.finalize(worker_id="worker-once")
    duplicate = case.repository.complete_job(job["jobId"], worker_id="worker-once", plan=case.plan)
    assert duplicate["event"] == first_event["event"]
    messages = case.repository.messages(case.actors[0], case.quest_id)
    openers = [message for message in messages if message["sender"] == {"kind": "assistant"}]
    assert len(openers) == 1
    assert openers[0]["text"] == case.plan["opener"]
    assert case.repository.claim_job(worker_id="second-worker") is None


def test_same_idempotency_key_changed_body_conflicts_without_effect(
    workflow_scenario: WorkflowCase,
):
    case = workflow_scenario
    case.accept(0, key="bound-request")
    with pytest.raises(ERRORS) as caught:
        case.accept(0, key="bound-request", choice="decline")
    assert caught.value.code == "IDEMPOTENCY_CONFLICT"
    assert case.repository.snapshot(case.actors[0], case.quest_id)["acceptedCount"] == 1


def test_idempotency_keys_are_scoped_to_the_actor(workflow_scenario: WorkflowCase):
    case = workflow_scenario
    first = case.accept(0, key="shared-key-text")
    second = case.accept(1, key="shared-key-text")
    assert first["acceptance"]["participantId"] == case.actors[0].participant_id
    assert second["acceptance"]["participantId"] == case.actors[1].participant_id
    assert second["snapshot"]["acceptedCount"] == 2


def test_stale_revision_does_not_record_acceptance(workflow_scenario: WorkflowCase):
    case = workflow_scenario
    with pytest.raises(ERRORS) as caught:
        case.repository.accept(
            case.actors[0],
            case.quest_id,
            revision=99,
            choice="accept",
            idempotency_key="stale-revision",
        )
    assert caught.value.code == "STALE_REVISION"
    assert case.repository.snapshot(case.actors[0], case.quest_id)["acceptedCount"] == 0


def test_concurrent_retries_freeze_one_quorum_and_one_job(workflow_case_factory):
    case = workflow_case_factory(members=5)

    def accept(index: int):
        try:
            return case.accept(index, key=f"parallel-{index}")
        except ERRORS as error:
            return error.code

    with ThreadPoolExecutor(max_workers=10) as pool:
        outcomes = list(pool.map(accept, [0, 1, 2, 3, 4, 0, 1, 2, 3, 4]))
    for outcome in outcomes:
        if isinstance(outcome, str):
            assert outcome in {"CAPACITY_REACHED", "STALE_REVISION"}
    snapshot = case.repository.snapshot(case.actors[0], case.quest_id)
    assert snapshot["acceptedCount"] == 3
    assert snapshot["status"] == "planning"
    _, final = case.finalize()
    assert len(final["event"]["acceptedMemberIds"]) == 3
    assert case.repository.claim_job(worker_id="no-duplicate-job") is None
    with psycopg.connect(case.dsn["admin_dsn"]) as admin:
        assert admin.execute(
            "SELECT count(*) FROM workflow.events WHERE quest_id = %s", (case.quest_id,)
        ).fetchone() == (1,)


def test_pending_job_and_scheduled_event_survive_a_fresh_python_process(
    workflow_scenario: WorkflowCase,
):
    case = workflow_scenario
    case.quorum()
    # A distinct instance must discover the job from PostgreSQL rather than a process-local queue.
    restarted = WorkflowRepository(
        case.database,
        case.privacy,
        worker_database=case.worker_database,
        mode="fixture",
        proposal_projection=project_proposal,
        plan_projection=project_plan,
    )
    job = restarted.claim_job(worker_id="restarted-process")
    assert job is not None
    final = restarted.complete_job(job["jobId"], worker_id="restarted-process", plan=case.plan)
    script = """
import json, sys
from server.privacy import Database, PrivacyService
from server.orchestration.repository import WorkflowRepository
from server.privacy.projections import project_plan, project_proposal
request = json.load(sys.stdin)
database = Database(request['apiDsn'])
worker = Database(request['workerDsn'])
try:
    privacy = PrivacyService(database)
    actor = privacy.resolve(request['session'])
    repository = WorkflowRepository(
        database, privacy, worker_database=worker, mode='fixture',
        proposal_projection=project_proposal, plan_projection=project_plan,
    )
    print(json.dumps(repository.snapshot(actor, request['questId'])))
finally:
    worker.close()
    database.close()
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        input=json.dumps(
            {
                "apiDsn": case.dsn["api_dsn"],
                "workerDsn": case.dsn["worker_dsn"],
                "session": case.tokens[0],
                "questId": case.quest_id,
            }
        ),
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[2],
        timeout=20,
        check=True,
    )
    restored = json.loads(result.stdout)
    assert restored["event"] == final["event"]
    assert restored["acceptedCount"] == 3


def test_a_member_revoked_before_worker_publication_cannot_create_event(
    workflow_scenario: WorkflowCase,
):
    case = workflow_scenario
    case.quorum()
    job = case.repository.claim_job(worker_id="before-revoke")
    assert job is not None
    case.privacy_patch(
        1,
        f"communities/{case.proposal['communityId']}/consent",
        {
            "expectedVersion": 1,
            "matching": False,
            "modelProcessing": False,
            "publicInterests": False,
        },
    )
    with pytest.raises(ERRORS) as caught:
        case.repository.complete_job(job["jobId"], worker_id="before-revoke", plan=case.plan)
    assert caught.value.code in {"CONSENT_REQUIRED", "STALE_REVISION", "FORBIDDEN"}
    with psycopg.connect(case.dsn["admin_dsn"]) as admin:
        assert admin.execute("SELECT count(*) FROM workflow.events").fetchone() == (0,)


def test_changed_intent_makes_an_in_flight_plan_stale(workflow_scenario: WorkflowCase):
    case = workflow_scenario
    case.quorum()
    job = case.repository.claim_job(worker_id="old-intent")
    assert job is not None
    case.privacy_patch(
        1,
        "intents/me/availability",
        {
            "communityId": case.proposal["communityId"],
            "expectedVersion": 1,
            "availability": [
                {
                    "start": (datetime.fromisoformat(case.plan["start"]) + timedelta(minutes=1))
                    .isoformat()
                    .replace("+00:00", "Z"),
                    "end": case.proposal["feasibleWindows"][0]["end"],
                }
            ],
        },
    )
    with pytest.raises(ERRORS) as caught:
        case.repository.complete_job(job["jobId"], worker_id="old-intent", plan=case.plan)
    assert caught.value.code == "STALE_REVISION"


def test_material_final_plan_change_requires_reconfirmation(workflow_scenario: WorkflowCase):
    case = workflow_scenario
    case.quorum()
    changed = deepcopy(case.plan)
    # This remains feasible, but participants did not accept this exact time.
    changed["start"] = (
        (datetime.fromisoformat(changed["start"]) + timedelta(minutes=5))
        .isoformat()
        .replace("+00:00", "Z")
    )
    changed["end"] = (
        (datetime.fromisoformat(changed["end"]) + timedelta(minutes=5))
        .isoformat()
        .replace("+00:00", "Z")
    )
    job = case.repository.claim_job(worker_id="changed-details")
    assert job is not None
    revised = case.repository.complete_job(job["jobId"], worker_id="changed-details", plan=changed)
    assert revised["status"] == "proposed"
    assert revised["revision"] > 1 and revised["acceptedCount"] == 0
    assert revised["event"] is None


def test_unrelated_community_member_cannot_read_or_accept_another_quest(workflow_case_factory):
    first = workflow_case_factory()
    other = workflow_case_factory()
    for action in [
        lambda: first.repository.snapshot(other.actors[0], first.quest_id),
        lambda: first.repository.messages(other.actors[0], first.quest_id),
        lambda: first.repository.accept(
            other.actors[0], first.quest_id, revision=1, choice="accept", idempotency_key="intruder"
        ),
    ]:
        with pytest.raises(ERRORS) as caught:
            action()
        assert caught.value.code in {"NOT_FOUND", "FORBIDDEN"}


def test_api_role_cannot_claim_worker_jobs(workflow_scenario: WorkflowCase):
    case = workflow_scenario
    case.quorum()
    with pytest.raises((WorkflowError, psycopg.errors.InsufficientPrivilege)):
        unauthorized_worker = WorkflowRepository(
            case.database,
            case.privacy,
            worker_database=case.database,
            mode="fixture",
            proposal_projection=project_proposal,
            plan_projection=project_plan,
        )
        unauthorized_worker.claim_job(worker_id="ordinary-api-role")


def test_rls_does_not_return_quests_without_an_actor(workflow_scenario: WorkflowCase):
    case = workflow_scenario
    with case.database.as_actor(None) as connection:
        assert (
            connection.execute("SELECT count(*) AS total FROM workflow.quests").fetchone()["total"]
            == 0
        )


def test_worker_capabilities_are_absent_from_the_api_database_role(workflow_scenario):
    case = workflow_scenario
    signatures = [
        "workflow.claim_job(text,integer)",
        "workflow.lock_job(text,text)",
        "workflow.finish_job(text,text,jsonb,boolean)",
        "workflow.fail_job(text,text,text)",
    ]
    for signature in signatures:
        with case.database.as_actor(case.actors[0].participant_id) as connection:
            allowed = connection.execute(
                "SELECT has_function_privilege(current_user, %s, 'EXECUTE') AS allowed",
                (signature,),
            ).fetchone()["allowed"]
            assert allowed is False, signature
        with case.worker_database.as_actor(case.actors[0].participant_id) as connection:
            allowed = connection.execute(
                "SELECT has_function_privilege(current_user, %s, 'EXECUTE') AS allowed",
                (signature,),
            ).fetchone()["allowed"]
            assert allowed is True, signature
    with case.database.as_actor(case.actors[0].participant_id) as connection:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            connection.execute("SELECT workflow.claim_job('api-intruder', 30)")


def test_expired_worker_cannot_publish_a_late_provider_result(workflow_scenario):
    case = workflow_scenario
    case.quorum()
    first = case.repository.claim_job(worker_id="expired-worker")
    assert first is not None
    # Advance only this fixture lease deterministically; do not wait on wall-clock timing.
    with psycopg.connect(case.dsn["admin_dsn"]) as admin:
        admin.execute(
            "UPDATE workflow.jobs SET lease_expires_at = clock_timestamp() - interval '1 second' "
            "WHERE job_id = %s",
            (first["jobId"],),
        )
    replacement = case.repository.claim_job(worker_id="current-worker")
    assert replacement is not None and replacement["jobId"] == first["jobId"]
    with pytest.raises(ERRORS) as caught:
        case.repository.complete_job(first["jobId"], worker_id="expired-worker", plan=case.plan)
    assert caught.value.code == "STALE_REVISION"
    assert case.repository.snapshot(case.actors[0], case.quest_id)["event"] is None
    final = case.repository.complete_job(
        replacement["jobId"], worker_id="current-worker", plan=case.plan
    )
    assert final["status"] == "scheduled"


def test_publication_failure_rolls_back_event_opener_and_outbox_together(workflow_scenario):
    case = workflow_scenario
    case.quorum()
    job = case.repository.claim_job(worker_id="atomic-publication")
    assert job is not None
    # Force a storage failure after event INSERT, proving that the complete transaction rolls back.
    with psycopg.connect(case.dsn["admin_dsn"], autocommit=True) as admin:
        admin.execute("""
            CREATE FUNCTION workflow.fixture_reject_opener() RETURNS trigger
            LANGUAGE plpgsql AS $$ BEGIN
              RAISE EXCEPTION 'fixture storage failure' USING ERRCODE = '23514';
            END $$;
            CREATE TRIGGER fixture_opener_failure BEFORE INSERT ON workflow.messages
            FOR EACH ROW EXECUTE FUNCTION workflow.fixture_reject_opener();
        """)
    try:
        with pytest.raises((WorkflowError, psycopg.Error)):
            case.repository.complete_job(
                job["jobId"], worker_id="atomic-publication", plan=case.plan
            )
        with psycopg.connect(case.dsn["admin_dsn"]) as admin:
            for table in ["events", "event_revisions", "messages"]:
                assert admin.execute(
                    psycopg.sql.SQL("SELECT count(*) FROM workflow.{}").format(
                        psycopg.sql.Identifier(table)
                    )
                ).fetchone() == (0,)
            assert admin.execute(
                "SELECT count(*) FROM workflow.outbox WHERE type = 'event.created'"
            ).fetchone() == (0,)
        assert case.repository.snapshot(case.actors[0], case.quest_id)["event"] is None
    finally:
        with psycopg.connect(case.dsn["admin_dsn"], autocommit=True) as admin:
            admin.execute("DROP TRIGGER fixture_opener_failure ON workflow.messages")
            admin.execute("DROP FUNCTION workflow.fixture_reject_opener()")
    final = case.repository.complete_job(
        job["jobId"], worker_id="atomic-publication", plan=case.plan
    )
    assert final["status"] == "scheduled"
    assert len(case.repository.messages(case.actors[0], case.quest_id)) == 1
