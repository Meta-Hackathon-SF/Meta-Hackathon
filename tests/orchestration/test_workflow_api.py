"""HTTP contract checks for the persistence milestone; all people/plans are test fixtures."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from server.orchestration.api import create_workflow_app
from server.orchestration.repository import WorkflowRepository

from server.app.config import Settings

if TYPE_CHECKING:
    from workflow_fixtures import WorkflowCase

pytest_plugins = ("workflow_fixtures",)


def app_for(case: WorkflowCase, *, repository=None):
    return create_workflow_app(
        repository=repository or case.repository,
        privacy=case.privacy,
        settings=Settings(environment="test"),
    )


def assert_error(response, status: int, code: str) -> None:
    assert response.status_code == status
    assert set(response.json()) == {"error"}
    error = response.json()["error"]
    assert set(error) == {"code", "message", "requestId", "retryable"}
    assert error["code"] == code
    assert error["requestId"] == response.headers["X-Request-Id"]
    UUID(error["requestId"])
    assert response.headers["Cache-Control"] == "no-store"


def test_http_acceptance_ack_and_reload_restore_the_scheduled_event(
    workflow_scenario: WorkflowCase,
):
    case = workflow_scenario
    with TestClient(app_for(case)) as client:
        for index in range(3):
            response = client.post(
                f"/api/v1/quests/{case.quest_id}/accept",
                headers=case.headers(index, key=f"http-accept-{index}"),
                json={"revision": 1, "choice": "accept"},
            )
            assert response.status_code == 200
            body = response.json()
            assert set(body) == {"acceptance", "snapshot"}
            assert body["acceptance"]["participantId"] == case.actors[index].participant_id
            assert body["snapshot"]["acceptedCount"] == index + 1
            UUID(response.headers["X-Request-Id"])
            assert response.headers["Cache-Control"] == "no-store"
    _, scheduled = case.finalize()
    restored_repository = WorkflowRepository(
        case.database, case.privacy, worker_database=case.worker_database, mode="fixture"
    )
    with TestClient(app_for(case, repository=restored_repository)) as reloaded_client:
        response = reloaded_client.get(f"/api/v1/quests/{case.quest_id}", headers=case.headers(1))
        assert response.status_code == 200
        assert response.json()["event"] == scheduled["event"]
        assert response.json()["status"] == "scheduled"
        messages = reloaded_client.get(
            f"/api/v1/quests/{case.quest_id}/messages", headers=case.headers(2)
        )
        assert messages.status_code == 200
        payload = messages.json()
        items = payload if isinstance(payload, list) else payload["messages"]
        assert len([item for item in items if item["sender"] == {"kind": "assistant"}]) == 1


@pytest.mark.parametrize("suffix", ["", "/messages", "/accept"])
def test_anonymous_workflow_requests_require_a_session(workflow_scenario, suffix):
    case = workflow_scenario
    with TestClient(app_for(case)) as client:
        path = f"/api/v1/quests/{case.quest_id}{suffix}"
        response = (
            client.post(
                path,
                headers={"Idempotency-Key": "anonymous"},
                json={"revision": 1, "choice": "accept"},
            )
            if suffix == "/accept"
            else client.get(path)
        )
        assert_error(response, 401, "UNAUTHENTICATED")


@pytest.mark.parametrize(
    "payload",
    [
        {"revision": 1, "choice": "accept", "participantId": "forged-actor"},
        {"revision": 1, "choice": "accept", "mode": "fixture"},
        {"revision": True, "choice": "accept"},
        {"revision": "1", "choice": "accept"},
        {"revision": 1, "choice": "maybe"},
    ],
)
def test_client_identity_mode_and_coerced_acceptance_fields_are_rejected(
    workflow_scenario, payload
):
    case = workflow_scenario
    with TestClient(app_for(case)) as client:
        response = client.post(
            f"/api/v1/quests/{case.quest_id}/accept",
            headers=case.headers(key="forged-fields"),
            json=payload,
        )
        assert_error(response, 400, "INVALID_INPUT")
        assert "forged-actor" not in response.text
    assert case.repository.snapshot(case.actors[0], case.quest_id)["acceptedCount"] == 0


def test_http_idempotency_conflict_is_409_and_does_not_increment_count(workflow_scenario):
    case = workflow_scenario
    with TestClient(app_for(case)) as client:
        path = f"/api/v1/quests/{case.quest_id}/accept"
        headers = case.headers(key="http-command")
        first = client.post(path, headers=headers, json={"revision": 1, "choice": "accept"})
        replay = client.post(path, headers=headers, json={"revision": 1, "choice": "accept"})
        assert first.status_code == replay.status_code == 200
        assert replay.json() == first.json()
        conflict = client.post(path, headers=headers, json={"revision": 1, "choice": "decline"})
        assert_error(conflict, 409, "IDEMPOTENCY_CONFLICT")
    assert case.repository.snapshot(case.actors[0], case.quest_id)["acceptedCount"] == 1


def test_revoked_session_cannot_replay_an_old_successful_response(workflow_scenario):
    case = workflow_scenario
    with TestClient(app_for(case)) as client:
        path = f"/api/v1/quests/{case.quest_id}/accept"
        headers = case.headers(key="before-session-revoke")
        assert (
            client.post(path, headers=headers, json={"revision": 1, "choice": "accept"}).status_code
            == 200
        )
        case.privacy.revoke_session(case.tokens[0])
        replay = client.post(path, headers=headers, json={"revision": 1, "choice": "accept"})
        assert_error(replay, 401, "UNAUTHENTICATED")


def test_non_member_cannot_read_another_rooms_snapshot_or_messages(workflow_case_factory):
    case = workflow_case_factory()
    outsider = workflow_case_factory()
    with TestClient(app_for(case)) as client:
        for suffix in ["", "/messages"]:
            response = client.get(
                f"/api/v1/quests/{case.quest_id}{suffix}", headers=outsider.headers()
            )
            assert response.status_code in {403, 404}
            assert response.json()["error"]["code"] in {"FORBIDDEN", "NOT_FOUND"}
            assert case.plan["title"] not in response.text


def test_withdrawn_matching_consent_blocks_even_an_idempotent_replay(workflow_scenario):
    case = workflow_scenario
    headers = case.headers(key="before-consent-revoke")
    with TestClient(app_for(case)) as client:
        path = f"/api/v1/quests/{case.quest_id}/accept"
        assert (
            client.post(path, headers=headers, json={"revision": 1, "choice": "accept"}).status_code
            == 200
        )
        case.privacy_patch(
            0,
            f"communities/{case.proposal['communityId']}/consent",
            {
                "expectedVersion": 1,
                "matching": False,
                "modelProcessing": False,
                "publicInterests": False,
            },
        )
        response = client.post(path, headers=headers, json={"revision": 1, "choice": "accept"})
        assert response.status_code == 403
        assert response.json()["error"]["code"] in {"CONSENT_REQUIRED", "FORBIDDEN"}
