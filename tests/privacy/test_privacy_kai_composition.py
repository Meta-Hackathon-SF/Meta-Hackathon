"""Privacy mounted inside Kai's composed app (server/app/).

Skips where Kai's composition is not importable (e.g. main before Kai's PR).
Run against Kai's branch by exporting server/app onto PYTHONPATH; see
docs/handoffs/patrik.md. This is local integration evidence, not deployment.
"""

from __future__ import annotations

import pytest

registry = pytest.importorskip("server.app.registry", reason="Kai's server/app not on this branch yet")
main = pytest.importorskip("server.app.main")
config = pytest.importorskip("server.app.config")

from fastapi.testclient import TestClient  # noqa: E402

from privacy_helpers import COMMUNITY, intent_body  # noqa: E402
from server.privacy.registration import install_privacy_error_handler, privacy_registration  # noqa: E402


@pytest.fixture
def composed(service):
    app = main.create_app(
        settings=config.Settings(environment="test"),
        registrations=[privacy_registration(service)],
    )
    install_privacy_error_handler(app)
    return TestClient(app, base_url="https://testserver", raise_server_exceptions=False)


def key(n: int) -> dict:
    return {"Idempotency-Key": f"test-key-{n}"}


def assert_code(resp, status, code):
    assert resp.status_code == status, resp.text
    assert resp.json()["error"]["code"] == code
    assert resp.json()["error"]["requestId"] == resp.headers["x-request-id"]


def test_bootstrap_requires_idempotency_key_but_no_session(composed):
    assert_code(composed.post("/api/v1/session"), 400, "INVALID_INPUT")
    created = composed.post("/api/v1/session", headers=key(1))
    assert created.status_code == 201 and "httponly" in created.headers["set-cookie"].lower()
    assert composed.get("/api/v1/session").status_code == 200


def test_protected_routes_fail_closed(composed):
    assert_code(composed.get("/api/v1/session"), 401, "UNAUTHENTICATED")
    assert_code(composed.put("/api/v1/intents/me", json=intent_body(), headers=key(2)), 401, "UNAUTHENTICATED")
    composed.cookies.set("gq_session", "forged")
    assert_code(composed.get("/api/v1/intents/me", params={"communityId": COMMUNITY}), 401, "UNAUTHENTICATED")


def test_privacy_errors_keep_their_codes_not_500(composed):
    composed.post("/api/v1/session", headers=key(3))
    join = composed.post(f"/api/v1/communities/{COMMUNITY}/join", headers=key(4), json={
        "displayName": "A", "consent": {"matching": True, "modelProcessing": True, "publicInterests": True}})
    assert join.status_code == 200, join.text
    patch = {"expectedVersion": 1, "matching": True, "modelProcessing": False, "publicInterests": True}
    assert composed.patch(f"/api/v1/communities/{COMMUNITY}/consent", json=patch, headers=key(5)).status_code == 200
    assert_code(composed.patch(f"/api/v1/communities/{COMMUNITY}/consent", json={**patch, "matching": False},
                               headers=key(6)), 409, "STALE_REVISION")
    assert_code(composed.get("/api/v1/intents/me", params={"communityId": COMMUNITY}), 404, "NOT_FOUND")
    assert_code(composed.put("/api/v1/intents/me", json={**intent_body(), "participantId": "p_x"},
                             headers=key(7)), 400, "INVALID_INPUT")


def test_will_communities_joinable(composed):
    composed.post("/api/v1/session", headers=key(8))
    for community in ("hackathon-builders", "meta-ai-explorers", "xr-student-collective"):
        r = composed.post(f"/api/v1/communities/{community}/join", headers=key(9), json={
            "displayName": "A", "consent": {"matching": False, "modelProcessing": False, "publicInterests": False}})
        assert r.status_code == 200, (community, r.text)


def test_readiness_reports_privacy(composed):
    body = composed.get("/health/ready").json()
    assert body["services"]["privacy"] == "ready"
