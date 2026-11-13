"""HTTP boundary: session-only identity, ApiError envelope, cookie flags, no value echo."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from privacy_helpers import COMMUNITY, consent_body, join_body
from server.privacy import build_router, install_error_handlers
from server.privacy.fixtures import seed_synthetic_players

JOIN = f"/api/v1/communities/{COMMUNITY}/join"


@pytest.fixture
def app(service):
    app = FastAPI()
    install_error_handlers(app)
    app.include_router(build_router(service), prefix="/api/v1")
    return app


def client(app) -> TestClient:
    return TestClient(app, base_url="https://testserver")


def joined(app, name="Tester (synthetic)") -> TestClient:
    c = client(app)
    r = c.post(JOIN, json=join_body(name))
    assert r.status_code == 201, r.text
    return c


def assert_error(resp, status, code):
    assert resp.status_code == status, resp.text
    body = resp.json()
    assert set(body) == {"error"} and body["error"]["code"] == code
    assert set(body["error"]) == {"code", "message", "requestId", "retryable"}
    assert body["error"]["requestId"] == resp.headers["x-request-id"]


def test_join_sets_hardened_cookie_and_returns_session_view(app):
    c = client(app)
    r = c.post(JOIN, json=join_body("Maya"))
    assert r.status_code == 201
    cookie = r.headers["set-cookie"].lower()
    for flag in ("cst_session=", "httponly", "secure", "samesite=lax", "path=/api"):
        assert flag in cookie
    body = r.json()
    assert set(body) == {"player", "consent", "isOperator"}
    assert body["player"]["displayName"] == "Maya" and body["isOperator"] is False
    assert body["consent"]["version"] == 1 and body["consent"]["communityId"] == COMMUNITY
    assert c.get("/api/v1/session").json() == body


def test_rejoin_with_cookie_is_idempotent(app):
    c = joined(app)
    first = c.get("/api/v1/session").json()
    r = c.post(JOIN, json=join_body("Someone else"))
    assert r.status_code == 200 and "set-cookie" not in r.headers
    assert r.json() == first


@pytest.mark.parametrize("route", [("get", "/api/v1/session"), ("delete", "/api/v1/session"),
                                   ("patch", "/api/v1/me/consent")])
def test_authenticated_routes_need_a_session(app, route):
    method, path = route
    kwargs = {"json": consent_body(1)} if method == "patch" else {}
    assert_error(getattr(client(app), method)(path, **kwargs), 401, "UNAUTHENTICATED")


def test_bearer_token_works_and_forged_player_id_is_ignored(app, service):
    c = client(app)
    r = c.post(JOIN, json=join_body())
    token = r.cookies["cst_session"]
    other = joined(app, "Other").get("/api/v1/session").json()["player"]["playerId"]
    bare = client(app)
    me = bare.get("/api/v1/session", headers={"Authorization": f"Bearer {token}"}).json()
    assert me["player"]["playerId"] != other
    # A body naming another player is rejected, never used as identity.
    resp = bare.patch("/api/v1/me/consent", headers={"Authorization": f"Bearer {token}"},
                      json={**consent_body(1, match=False), "playerId": other})
    assert_error(resp, 400, "INVALID_INPUT")


def test_synthetic_player_cannot_be_impersonated(app, store):
    seed_synthetic_players(store)
    c = client(app)
    c.cookies.set("cst_session", "p-maya")
    assert_error(c.get("/api/v1/session"), 401, "UNAUTHENTICATED")


def test_join_without_all_consents_is_403_and_sets_no_cookie(app):
    r = client(app).post(JOIN, json=join_body(adult=False))
    assert_error(r, 403, "CONSENT_REQUIRED")
    assert "set-cookie" not in r.headers


def test_unknown_community_404(app):
    assert_error(client(app).post("/api/v1/communities/nope/join", json=join_body()), 404, "NOT_FOUND")


def test_validation_error_never_echoes_values(app):
    secret = "my-private-value-123"
    r = client(app).post(JOIN, json={**join_body(), "displayName": secret * 5})
    assert_error(r, 400, "INVALID_INPUT")
    assert secret not in r.text


def test_consent_flow_over_http(app):
    c = joined(app)
    r = c.patch("/api/v1/me/consent", json=consent_body(1, chat=False))
    assert r.status_code == 200 and r.json()["revokedAt"] is not None
    assert_error(c.patch("/api/v1/me/consent", json=consent_body(1, match=False)), 409, "STALE_REVISION")
    r = c.patch("/api/v1/me/consent", json=consent_body(2))
    assert r.json()["version"] == 3 and r.json()["revokedAt"] is None


def test_sign_out_clears_session(app):
    c = joined(app)
    r = c.delete("/api/v1/session")
    assert r.status_code == 204
    assert_error(c.get("/api/v1/session"), 401, "UNAUTHENTICATED")


def test_responses_are_not_cacheable(app):
    r = joined(app).get("/api/v1/session")
    assert r.headers["cache-control"] == "no-store"
