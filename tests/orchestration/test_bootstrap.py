"""Configuration fails closed without creating fixture services or provider calls."""

import pytest
from fastapi.testclient import TestClient

from server.app.bootstrap import create_configured_app
from tests.orchestration.storage_adapter import TestWorkflowRepository


def test_missing_backend_configuration_is_honest_not_ready(monkeypatch):
    monkeypatch.delenv("CONSTELLATIONS_WORKFLOW_DSN", raising=False)
    monkeypatch.delenv("CST_PRIVACY_DB", raising=False)
    with TestClient(create_configured_app()) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/health/ready").status_code == 503
        assert client.get("/api/v1/session").status_code == 404


def test_configured_backend_refuses_ephemeral_privacy_store(monkeypatch):
    monkeypatch.setenv("CONSTELLATIONS_WORKFLOW_DSN", "synthetic-unused-dsn")
    monkeypatch.setenv("CST_PRIVACY_DB", ":memory:")
    with pytest.raises(ValueError, match="durable privacy"):
        create_configured_app()


@pytest.mark.parametrize(
    "muse_key, status, voice", [("test-key", 200, "ready"), ("", 503, "unavailable")]
)
def test_configured_backend_readiness_tracks_voice_configuration(
    monkeypatch, tmp_path, muse_key, status, voice
):
    monkeypatch.setenv("CONSTELLATIONS_ENV", "production")
    monkeypatch.setenv("CONSTELLATIONS_ALLOWED_ORIGINS", "https://demo.example")
    monkeypatch.setenv("CONSTELLATIONS_WORKFLOW_DSN", "test-only-dsn")
    monkeypatch.setenv("CST_PRIVACY_DB", str(tmp_path / "privacy.sqlite"))
    monkeypatch.setenv("MUSE_API_KEY", muse_key)
    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    monkeypatch.setattr(
        "server.app.bootstrap.PostgresWorkflowRepository", lambda _dsn: TestWorkflowRepository()
    )

    with TestClient(create_configured_app()) as client:
        response = client.get("/health/ready")
        assert response.status_code == status
        assert response.json()["services"]["voice"] == voice
        assert client.post("/api/v1/voice/transcribe").status_code == 401
