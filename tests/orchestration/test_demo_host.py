"""Offline authentication integration with synthetic sessions and random secrets."""

import secrets
from uuid import uuid4

from fastapi.testclient import TestClient

from server.privacy.fixtures import seed_community

from .runtime_helpers import runtime_environment


def headers():
    return {"Idempotency-Key": uuid4().hex}


def test_host_login_is_session_scoped_and_logout_revokes(monkeypatch):
    secret = secrets.token_urlsafe(40)
    monkeypatch.setenv("CST_DEMO_HOST_SECRET", secret)
    with runtime_environment() as env, TestClient(env.app, base_url="https://testserver") as client:
        seed_community(env.privacy_store, "facebook-space", "Synthetic community")
        join = client.post(
            "/api/v1/communities/facebook-space/join",
            headers=headers(),
            json={
                "displayName": "Synthetic player",
                "matchAnswers": True,
                "anonymousChat": True,
                "isAdult": True,
            },
        )
        assert join.status_code == 201
        old_token = client.cookies.get("cst_session")
        assert client.get("/api/v1/session").json()["isOperator"] is False
        assert client.get("/api/v1/operator/reports").status_code == 403
        bad = client.post(
            "/api/v1/operator/login",
            headers=headers(),
            json={"password": secrets.token_urlsafe(40)},
        )
        assert bad.status_code == 403
        assert client.get("/api/v1/session").json()["isOperator"] is False
        good = client.post("/api/v1/operator/login", headers=headers(), json={"password": secret})
        assert good.status_code == 200 and good.json()["isOperator"] is True
        assert "HttpOnly" in good.headers["set-cookie"] and "Secure" in good.headers["set-cookie"]
        assert client.cookies.get("cst_session") != old_token
        assert client.get("/api/v1/session").json()["isOperator"] is True
        assert client.get("/api/v1/operator/reports").status_code == 200
        assert (
            client.get(
                "/api/v1/session", headers={"Authorization": "Bearer " + old_token}
            ).status_code
            == 401
        )
        assert client.delete("/api/v1/session", headers=headers()).status_code == 204
        assert client.get("/api/v1/operator/reports").status_code == 401


def test_host_login_rate_limit_and_missing_configuration(monkeypatch):
    secret = secrets.token_urlsafe(40)
    monkeypatch.setenv("CST_DEMO_HOST_SECRET", secret)
    with runtime_environment() as env, TestClient(env.app, base_url="https://testserver") as client:
        seed_community(env.privacy_store, "facebook-space", "Synthetic community")
        assert (
            client.post(
                "/api/v1/communities/facebook-space/join",
                headers=headers(),
                json={
                    "displayName": "Synthetic player",
                    "matchAnswers": True,
                    "anonymousChat": True,
                    "isAdult": True,
                },
            ).status_code
            == 201
        )
        monkeypatch.delenv("CST_DEMO_HOST_SECRET")
        assert (
            client.post(
                "/api/v1/operator/login", headers=headers(), json={"password": secret}
            ).status_code
            == 503
        )
        monkeypatch.setenv("CST_DEMO_HOST_SECRET", secret)
        for _ in range(5):
            assert (
                client.post(
                    "/api/v1/operator/login",
                    headers=headers(),
                    json={
                        "password": secrets.token_urlsafe(40),
                    },
                ).status_code
                == 403
            )
        assert (
            client.post(
                "/api/v1/operator/login", headers=headers(), json={"password": secret}
            ).status_code
            == 429
        )
