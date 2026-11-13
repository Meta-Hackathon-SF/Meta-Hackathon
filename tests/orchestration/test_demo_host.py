"""Offline authentication integration with synthetic sessions and random secrets."""

import asyncio
import secrets
from datetime import timedelta
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
        response = client.post(
            "/api/v1/operator/cycles",
            headers=headers(),
            json={"communityId": "facebook-space", "demoTiming": True},
        )
        assert response.status_code == 201, response.json()
        cycle_id = response.json()["cycleId"]
        response = client.post(
            f"/api/v1/operator/cycles/{cycle_id}/advance",
            headers=headers(),
            json={},
        )
        assert response.status_code == 200, response.json()
        assert response.json()["currentDay"] == 2
        assert (
            client.get(
                "/api/v1/session", headers={"Authorization": "Bearer " + old_token}
            ).status_code
            == 401
        )
        consent = {
            "expectedVersion": 1,
            "matchAnswers": False,
            "anonymousChat": True,
            "isAdult": True,
        }
        assert (
            client.patch("/api/v1/me/consent", headers=headers(), json=consent).status_code == 200
        )
        assert client.get("/api/v1/operator/reports").status_code == 403
        consent.update(expectedVersion=2, matchAnswers=True)
        assert (
            client.patch("/api/v1/me/consent", headers=headers(), json=consent).status_code == 200
        )
        assert client.get("/api/v1/operator/reports").status_code == 403
        assert (
            client.post(
                "/api/v1/operator/login", headers=headers(), json={"password": secret}
            ).status_code
            == 200
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
        env.clock.now += timedelta(minutes=5)
        assert (
            client.post(
                "/api/v1/operator/login", headers=headers(), json={"password": secret}
            ).status_code
            == 200
        )
        env.clock.now += timedelta(days=8)
        assert client.get("/api/v1/operator/reports").status_code == 401


def test_authenticated_demo_cycle_with_synthetic_players(monkeypatch):
    secret = secrets.token_urlsafe(40)
    monkeypatch.setenv("CST_DEMO_HOST_SECRET", secret)
    with runtime_environment() as env, TestClient(env.app, base_url="https://testserver") as client:
        seed_community(env.privacy_store, "facebook-space", "Synthetic community")
        assert (
            client.post(
                "/api/v1/communities/facebook-space/join",
                headers=headers(),
                json={
                    "displayName": "Synthetic host",
                    "matchAnswers": True,
                    "anonymousChat": True,
                    "isAdult": True,
                },
            ).status_code
            == 201
        )
        assert (
            client.post(
                "/api/v1/operator/login", headers=headers(), json={"password": secret}
            ).status_code
            == 200
        )
        response = client.post(
            "/api/v1/operator/cycles",
            headers=headers(),
            json={
                "communityId": "facebook-space",
                "demoTiming": True,
            },
        )
        assert response.status_code == 201
        cycle_id = response.json()["cycleId"]
        topup = client.post(
            f"/api/v1/operator/cycles/{cycle_id}/synthetic-topup", headers=headers()
        )
        assert topup.status_code == 200, topup.json()
        for day in range(1, 6):
            response = client.post(
                f"/api/v1/cycles/{cycle_id}/answers",
                headers=headers(),
                json={
                    "day": day,
                    "text": f"Synthetic demo answer number {day}",
                    "source": "text",
                },
            )
            assert response.status_code == 202, response.json()
            response = client.post(
                f"/api/v1/operator/cycles/{cycle_id}/advance", headers=headers(), json={}
            )
            assert response.status_code == 200, response.json()
        response = client.post(
            f"/api/v1/operator/cycles/{cycle_id}/advance", headers=headers(), json={}
        )
        assert response.status_code == 200 and response.json()["status"] == "forming"
        with env.repository.transaction() as state:
            job_id = state.records["activeJobs"][cycle_id]
        asyncio.run(env.app.state.runtime.run_job(job_id))
        response = client.post(
            f"/api/v1/operator/cycles/{cycle_id}/advance", headers=headers(), json={}
        )
        assert response.status_code == 200, response.json()
        assert response.json()["status"] == "revealed"
