"""HTTP boundary: session-only identity, ApiError envelope, no value echo."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from privacy_helpers import COMMUNITY, intent_body
from server.privacy import build_router, install_error_handlers


@pytest.fixture
def app(service):
    app = FastAPI()
    install_error_handlers(app)
    app.include_router(build_router(service), prefix="/api/v1")
    return app


def client(app) -> TestClient:
    return TestClient(app, base_url="https://testserver")


def signed_in(app, name="A") -> TestClient:
    c = client(app)
    assert c.post("/api/v1/session").status_code == 201
    r = c.post(f"/api/v1/communities/{COMMUNITY}/join", json={
        "displayName": name,
        "consent": {"matching": True, "modelProcessing": True, "publicInterests": True}})
    assert r.status_code == 200, r.text
    return c


def assert_error(resp, status, code):
    assert resp.status_code == status, resp.text
    body = resp.json()
    assert set(body) == {"error"} and body["error"]["code"] == code
    assert body["error"]["requestId"] == resp.headers["x-request-id"]


def test_unauthenticated_requests_fail_closed(app):
    c = client(app)
    assert_error(c.get("/api/v1/session"), 401, "UNAUTHENTICATED")
    assert_error(c.put("/api/v1/intents/me", json=intent_body()), 401, "UNAUTHENTICATED")
    assert_error(c.get("/api/v1/intents/me", params={"communityId": COMMUNITY}), 401, "UNAUTHENTICATED")
    c.cookies.set("gq_session", "forged")
    assert_error(c.get("/api/v1/session"), 401, "UNAUTHENTICATED")


def test_session_cookie_is_httponly_and_secure(app):
    resp = client(app).post("/api/v1/session")
    cookie = resp.headers["set-cookie"].lower()
    assert "httponly" in cookie and "secure" in cookie and "samesite=lax" in cookie
    assert "token" not in resp.json() and "gq_session" not in resp.text


def test_forged_participant_id_in_body_rejected(app):
    a = signed_in(app, "A")
    b = signed_in(app, "B")
    b_id = b.get("/api/v1/session").json()["participantId"]
    resp = a.put("/api/v1/intents/me", json={**intent_body(), "participantId": b_id})
    assert_error(resp, 400, "INVALID_INPUT")
    assert b_id not in resp.text


def test_cross_user_reads_return_only_self(app):
    a = signed_in(app, "A")
    b = signed_in(app, "B")
    created = a.put("/api/v1/intents/me", json=intent_body())
    assert created.status_code == 200, created.text
    assert_error(b.get("/api/v1/intents/me", params={"communityId": COMMUNITY}), 404, "NOT_FOUND")
    own = a.get("/api/v1/intents/me", params={"communityId": COMMUNITY}).json()
    assert own["maxBudgetMinor"] == 1200 and own["participantId"] == created.json()["participantId"]
    session_b = b.get("/api/v1/session").json()
    assert "maxBudgetMinor" not in str(session_b) and "goal" not in str(session_b)


def test_validation_errors_do_not_echo_private_values(app):
    a = signed_in(app)
    secret_goal = "SENSITIVE-" + "x" * 600
    resp = a.put("/api/v1/intents/me", json=intent_body(goal=secret_goal, maxBudgetMinor=-5))
    assert_error(resp, 400, "INVALID_INPUT")
    assert "SENSITIVE" not in resp.text and "-5" not in resp.text


def test_consent_patch_and_stale(app):
    a = signed_in(app)
    ok = a.patch(f"/api/v1/communities/{COMMUNITY}/consent", json={
        "expectedVersion": 1, "matching": True, "modelProcessing": False, "publicInterests": True})
    assert ok.status_code == 200 and ok.json()["version"] == 2
    stale = a.patch(f"/api/v1/communities/{COMMUNITY}/consent", json={
        "expectedVersion": 1, "matching": False, "modelProcessing": False, "publicInterests": False})
    assert_error(stale, 409, "STALE_REVISION")


def test_logout_revokes_session(app):
    a = signed_in(app)
    token = a.cookies.get("gq_session")
    assert a.delete("/api/v1/session").status_code == 204
    replay = client(app)
    replay.headers["Authorization"] = f"Bearer {token}"
    assert_error(replay.get("/api/v1/session"), 401, "UNAUTHENTICATED")


def test_bearer_header_works_for_multi_device_tests(app):
    a = signed_in(app)
    token = a.cookies.get("gq_session")
    other = client(app)
    other.headers["Authorization"] = f"Bearer {token}"
    assert other.get("/api/v1/session").status_code == 200


def test_session_resolved_once_per_request(app, service, monkeypatch):
    a = signed_in(app)
    calls = []
    original = service.resolve
    monkeypatch.setattr(service, "resolve", lambda token: calls.append(1) or original(token))
    # Simulate Kai's router-level guard plus the route-level dependency.
    from fastapi import Depends
    from server.privacy import actor_dependency
    guard = actor_dependency(service)
    app.router.dependencies.append(Depends(guard))
    try:
        assert a.get("/api/v1/session").status_code == 200
    finally:
        app.router.dependencies.pop()
    assert len(calls) == 1
