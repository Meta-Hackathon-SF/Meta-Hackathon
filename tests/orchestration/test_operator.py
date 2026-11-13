"""Offline real-session authorization; sources below contain only synthetic data."""

import json

import pytest
from fastapi.testclient import TestClient

from server.app.composition import compose
from server.app.config import Settings
from server.app.operator import operator_registration
from server.privacy import PrivacyService, PrivacyStore, actor_dependency
from server.privacy.fixtures import grant_operator, seed_community

from .adapters import FIXTURES


@pytest.fixture
def operator_app():
    store = PrivacyStore(":memory:")
    seed_community(store, "synthetic-community", "Synthetic Group")
    service = PrivacyService(store)
    evidence = json.loads((FIXTURES / "sky-stats.json").read_text())["sky"]["evidence"]
    reads = []

    def source(actor):
        reads.append(actor.community_id)
        return [
            {**item, "requestId": "internal", "payload": "SYNTHETIC PRIVATE BODY"}
            for item in evidence
        ]

    session = actor_dependency(service)
    registration = operator_registration(
        session_dependency=session, require_operator=service.require_operator, calls_source=source
    )
    app = compose(
        privacy=service, settings=Settings(environment="test"), registrations=[registration]
    )
    with TestClient(app, base_url="https://testserver") as client:
        yield client, store, reads
    store.close()


def join(client):
    response = client.post(
        "/api/v1/communities/synthetic-community/join",
        headers={"Idempotency-Key": "synthetic-join"},
        json={
            "displayName": "Synthetic operator test",
            "matchAnswers": True,
            "anonymousChat": True,
            "isAdult": True,
        },
    )
    assert response.status_code == 201
    return response.json()["player"]["playerId"]


def test_operator_readers_require_real_operator_and_never_echo_private_source(operator_app):
    client, store, reads = operator_app
    assert client.get("/api/v1/operator/calls").status_code == 401
    player_id = join(client)
    assert client.get("/api/v1/operator/calls").status_code == 403
    assert reads == []
    grant_operator(store, player_id, "synthetic-community")
    result = client.get("/api/v1/operator/calls")
    assert result.status_code == 200
    assert "payload" not in result.text and "requestId" not in result.text
    assert "SYNTHETIC PRIVATE BODY" not in result.text
    assert reads == ["synthetic-community"]
    assert result.headers["Cache-Control"] == "no-store"


def test_missing_report_store_is_honest_503_not_fake_empty_queue(operator_app):
    client, store, _ = operator_app
    player_id = join(client)
    grant_operator(store, player_id, "synthetic-community")
    response = client.get("/api/v1/operator/reports")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "PROVIDER_UNAVAILABLE"
    response = client.get("/health/ready")
    assert response.json()["services"]["orchestration"] == "unavailable"
