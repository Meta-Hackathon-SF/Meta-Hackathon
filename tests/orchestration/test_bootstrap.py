"""Configuration fails closed without creating fixture services or provider calls."""

import pytest
from fastapi.testclient import TestClient

from server.app.bootstrap import create_configured_app


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
