"""Real privacy code composed offline using only synthetic test input."""

from fastapi.testclient import TestClient

from server.app.composition import compose
from server.app.config import Settings
from server.app.errors import ApiError
from server.privacy import PrivacyService, PrivacyStore
from server.privacy.fixtures import seed_community


def test_real_privacy_registration_join_session_consent_and_signout():
    store = PrivacyStore(":memory:")
    seed_community(store, "synthetic-community", "Synthetic test Group")
    try:
        app = compose(privacy=PrivacyService(store), settings=Settings(environment="test"))
        with TestClient(app, base_url="https://testserver") as client:
            assert client.get("/api/v1/session").status_code == 401
            response = client.post(
                "/api/v1/communities/synthetic-community/join",
                headers={"Idempotency-Key": "join"},
                json={
                    "displayName": "Synthetic test player",
                    "matchAnswers": True,
                    "anonymousChat": True,
                    "isAdult": True,
                },
            )
            assert response.status_code == 201
            assert "HttpOnly" in response.headers["set-cookie"]
            assert "Secure" in response.headers["set-cookie"]
            me = client.get("/api/v1/session")
            assert me.status_code == 200
            assert me.json()["player"]["displayName"] == "Synthetic test player"
            consent = me.json()["consent"]
            response = client.patch(
                "/api/v1/me/consent",
                headers={"Idempotency-Key": "revoke"},
                json={
                    "expectedVersion": consent["version"],
                    "matchAnswers": False,
                    "anonymousChat": True,
                    "isAdult": True,
                },
            )
            assert response.status_code == 200
            assert response.json()["revokedAt"] is not None
            health = client.get("/health/ready")
            assert health.status_code == 503
            assert health.json()["services"]["privacy"] == "ready"
            assert health.json()["services"]["chat"] == "unavailable"
            assert (
                client.delete("/api/v1/session", headers={"Idempotency-Key": "signout"}).status_code
                == 204
            )
            assert client.get("/api/v1/session").status_code == 401
    finally:
        store.close()


def test_join_needs_idempotency_and_sanitizes_forged_identity():
    store = PrivacyStore(":memory:")
    try:
        app = compose(privacy=PrivacyService(store), settings=Settings(environment="test"))
        with TestClient(app) as client:
            response = client.post("/api/v1/communities/synthetic/join", json={})
            assert response.status_code == 400
            response = client.post(
                "/api/v1/communities/synthetic/join",
                headers={
                    "Idempotency-Key": "forged",
                    "X-Request-Id": "synthetic-client-controlled",
                },
                json={"playerId": "SYNTHETIC PRIVATE INPUT"},
            )
            assert response.status_code == 400
            assert "SYNTHETIC PRIVATE INPUT" not in response.text
            error = ApiError.model_validate(response.json())
            assert error.error.requestId == response.headers["X-Request-Id"]
            assert error.error.requestId != "synthetic-client-controlled"
    finally:
        store.close()
