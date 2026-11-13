"""Offline composition tests. Synthetic guards/routers below are never installed in production."""

import asyncio
import re
from pathlib import Path
from typing import Literal, get_args
from uuid import UUID

import pytest
from fastapi import APIRouter, Request
from fastapi.testclient import TestClient
from pydantic import BaseModel, ConfigDict
from starlette.exceptions import HTTPException

from server.app.config import CONTRACT_VERSION, Settings
from server.app.errors import ApiError, ErrorCode, ServiceError
from server.app.main import create_app
from server.app.registry import OWNERS, ServiceRegistration


class SyntheticCommand(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    revision: int
    choice: Literal["accept", "decline"]


async def synthetic_guard(request: Request) -> None:
    """TEST ONLY. Not a real session, and not importable from server code."""
    if request.headers.get("Authorization") != "Bearer synthetic-test-session":
        raise ServiceError("UNAUTHENTICATED")


async def ready() -> bool:
    return True


def registration(owner="orchestration", *, probe=ready, guard=synthetic_guard):
    router = APIRouter()

    @router.get(f"/fixture/{owner}")
    async def get_fixture() -> dict[str, str]:
        return {"mode": "fixture", "owner": owner}

    @router.post(f"/fixture/{owner}")
    async def command(body: SyntheticCommand) -> dict:
        return {"mode": "fixture", **body.model_dump()}

    return ServiceRegistration(owner=owner, router=router, authorize=guard, ready=probe)


@pytest.fixture
def client():
    app = create_app(settings=Settings(environment="test"), registrations=[registration()])
    with TestClient(app) as client:
        yield client


def authenticated_headers(*, key="test-command-1") -> dict[str, str]:
    return {"Authorization": "Bearer synthetic-test-session", "Idempotency-Key": key}


def test_operator_login_bootstrap_is_explicit_and_privacy_only():
    router = APIRouter()

    @router.post("/operator/login")
    async def synthetic_login():
        return {"mode": "test-only"}

    @router.post("/operator/other")
    async def protected():
        return {"mode": "test-only"}

    def app(enabled):
        return create_app(
            settings=Settings(environment="test"),
            registrations=[ServiceRegistration("privacy", router, synthetic_guard, ready, enabled)],
        )

    with TestClient(app(False)) as client:
        response = client.post("/api/v1/operator/login", headers={"Idempotency-Key": "a"})
        assert response.status_code == 401
    with TestClient(app(True)) as client:
        assert client.post("/api/v1/operator/login").status_code == 400
        response = client.post("/api/v1/operator/login", headers={"Idempotency-Key": "a"})
        assert response.status_code == 200
        response = client.post("/api/v1/operator/other", headers={"Idempotency-Key": "b"})
        assert response.status_code == 401
    with pytest.raises(ValueError, match="Only privacy"):
        create_app(
            settings=Settings(environment="test"),
            registrations=[ServiceRegistration("planning", router, synthetic_guard, ready, True)],
        )


def assert_api_error(response, status: int, code: ErrorCode) -> ApiError:
    assert response.status_code == status
    error = ApiError.model_validate(response.json())
    assert error.error.code == code
    assert error.error.requestId == response.headers["X-Request-Id"]
    UUID(error.error.requestId)
    return error


def test_default_server_is_alive_but_not_ready():
    with TestClient(create_app(settings=Settings(environment="test"))) as client:
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {
            "status": "ok",
            "service": "constellations",
            "contractVersion": "3.0.0",
        }
        UUID(response.headers["X-Request-Id"])
        response = client.get("/health/ready")
        assert response.status_code == 503
        assert response.json() == {
            "status": "not_ready",
            "services": dict.fromkeys(OWNERS, "unavailable"),
        }
        # A mock Facebook participant ID or a supplied bearer string does not create a session.
        response = client.get("/api/v1/session", headers=authenticated_headers())
        assert_api_error(response, 404, "NOT_FOUND")


def test_every_owner_must_be_registered_and_ready():
    registrations = [registration(owner) for owner in OWNERS]
    with TestClient(
        create_app(settings=Settings(environment="test"), registrations=registrations)
    ) as client:
        response = client.get("/health/ready")
        assert response.status_code == 200
        assert response.json() == {"status": "ready", "services": dict.fromkeys(OWNERS, "ready")}


@pytest.mark.parametrize("failure", ["false", "error", "timeout", "wrong_type"])
def test_readiness_fails_closed_and_hides_dependency_details(failure):
    async def failing_probe():
        if failure == "false":
            return False
        if failure == "error":
            raise RuntimeError("synthetic-private-connection-details")
        if failure == "timeout":
            await asyncio.Event().wait()
        return "ready"  # Truthy strings must never imply a healthy dependency.

    registrations = [
        registration(owner, probe=failing_probe if owner == "privacy" else ready)
        for owner in OWNERS
    ]
    with TestClient(
        create_app(settings=Settings(environment="test"), registrations=registrations)
    ) as client:
        response = client.get("/health/ready")
        assert response.status_code == 503
        assert response.json()["services"]["privacy"] == "unavailable"
        assert "synthetic-private" not in response.text


def test_registered_routes_require_the_injected_server_guard(client):
    assert_api_error(client.get("/api/v1/fixture/orchestration"), 401, "UNAUTHENTICATED")
    assert_api_error(
        client.get("/api/v1/fixture/orchestration?participantId=synthetic-person"),
        401,
        "UNAUTHENTICATED",
    )
    response = client.get("/api/v1/fixture/orchestration", headers=authenticated_headers())
    assert response.status_code == 200
    assert response.json()["mode"] == "fixture"
    assert response.headers["Cache-Control"] == "no-store"


@pytest.mark.parametrize("key", [None, "", "contains space", "x" * 129])
def test_mutations_require_one_bounded_idempotency_key(client, key):
    headers = {"Authorization": "Bearer synthetic-test-session"}
    if key is not None:
        headers["Idempotency-Key"] = key
    assert_api_error(
        client.post(
            "/api/v1/fixture/orchestration",
            headers=headers,
            json={"revision": 1, "choice": "accept"},
        ),
        400,
        "INVALID_INPUT",
    )


def test_duplicate_key_headers_are_rejected(client):
    response = client.post(
        "/api/v1/fixture/orchestration",
        headers=[
            ("Authorization", "Bearer synthetic-test-session"),
            ("Idempotency-Key", "key-one"),
            ("Idempotency-Key", "key-two"),
        ],
        json={"revision": 1, "choice": "accept"},
    )
    assert_api_error(response, 400, "INVALID_INPUT")


def test_valid_mutation_reaches_the_registered_owner(client):
    response = client.post(
        "/api/v1/fixture/orchestration",
        headers=authenticated_headers(),
        json={"revision": 1, "choice": "accept"},
    )
    assert response.status_code == 200
    assert response.json() == {"mode": "fixture", "revision": 1, "choice": "accept"}


def test_only_community_join_can_skip_the_privacy_guard():
    router = APIRouter()

    @router.post("/communities/{communityId}/join", status_code=201)
    async def synthetic_session():
        return {"mode": "fixture"}

    @router.get("/session")
    async def synthetic_session_view():
        return {"mode": "fixture"}

    @router.delete("/session", status_code=204)
    async def synthetic_logout():
        return None

    routes_before = list(router.routes)
    app = create_app(
        settings=Settings(environment="test"),
        registrations=[ServiceRegistration("privacy", router, synthetic_guard, ready)],
    )
    assert router.routes == routes_before
    with TestClient(app) as client:
        assert_api_error(client.post("/api/v1/communities/synthetic/join"), 400, "INVALID_INPUT")
        response = client.post(
            "/api/v1/communities/synthetic/join", headers={"Idempotency-Key": "session-bootstrap"}
        )
        assert response.status_code == 201
        assert response.json() == {"mode": "fixture"}
        assert_api_error(client.get("/api/v1/session"), 401, "UNAUTHENTICATED")
        assert_api_error(
            client.delete("/api/v1/session", headers={"Idempotency-Key": "logout"}),
            401,
            "UNAUTHENTICATED",
        )
        assert client.get("/api/v1/session", headers=authenticated_headers()).status_code == 200


def test_other_owners_cannot_claim_the_public_session_bootstrap():
    router = APIRouter()
    router.post("/communities/{communityId}/join")(lambda: {"mode": "fixture"})
    with pytest.raises(ValueError, match="Only privacy"):
        create_app(
            registrations=[ServiceRegistration("orchestration", router, synthetic_guard, ready)]
        )


@pytest.mark.parametrize(
    "body",
    [
        {"revision": "synthetic-private-value", "choice": "accept"},
        {"revision": True, "choice": "accept"},
        {"revision": 1, "choice": "grant-admin"},
        {"revision": 1, "choice": "accept", "participantId": "synthetic-private-value"},
    ],
)
def test_validation_errors_never_echo_values_or_extra_private_fields(client, body):
    response = client.post(
        "/api/v1/fixture/orchestration", headers=authenticated_headers(), json=body
    )
    assert_api_error(response, 400, "INVALID_INPUT")
    assert "synthetic-private-value" not in response.text
    assert "participantId" not in response.text


def test_malformed_json_is_a_sanitized_contract_error(client):
    response = client.post(
        "/api/v1/fixture/orchestration",
        headers={**authenticated_headers(), "Content-Type": "application/json"},
        content='{"synthetic-private-value":',
    )
    assert_api_error(response, 400, "INVALID_INPUT")
    assert "synthetic-private-value" not in response.text


def test_request_ids_are_generated_and_not_trusted_from_the_client(client):
    response = client.get("/health", headers={"X-Request-Id": "synthetic-private-value"})
    UUID(response.headers["X-Request-Id"])
    assert response.headers["X-Request-Id"] != "synthetic-private-value"
    assert response.headers["X-Request-Id"] != client.get("/health").headers["X-Request-Id"]


def test_cors_is_explicit_including_preflight_request_id(client):
    response = client.options(
        "/api/v1/fixture/orchestration",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,idempotency-key,authorization",
        },
    )
    assert response.status_code == 200
    assert response.headers["Access-Control-Allow-Origin"] == "http://localhost:5173"
    assert response.headers["Access-Control-Allow-Credentials"] == "true"
    UUID(response.headers["X-Request-Id"])
    response = client.get("/health", headers={"Origin": "https://untrusted.invalid"})
    assert "Access-Control-Allow-Origin" not in response.headers


def test_unexpected_errors_hide_private_details_in_responses_and_logs(caplog):
    router = APIRouter()

    @router.get("/fixture/failure")
    async def fail():
        raise RuntimeError("synthetic-private-body-token-transcript")

    app = create_app(
        settings=Settings(environment="test"),
        registrations=[
            ServiceRegistration(
                owner="orchestration", router=router, authorize=synthetic_guard, ready=ready
            )
        ],
    )
    with TestClient(app) as client:
        response = client.get(
            "/api/v1/fixture/failure",
            headers={**authenticated_headers(), "Origin": "http://localhost:5173"},
        )
    error = assert_api_error(response, 503, "PROVIDER_UNAVAILABLE")
    assert error.error.retryable is True
    assert response.headers["Access-Control-Allow-Origin"] == "http://localhost:5173"
    assert "synthetic-private" not in response.text
    assert "synthetic-private" not in caplog.text
    assert error.error.requestId in caplog.text


@pytest.mark.parametrize(
    "code,status",
    [
        ("CONSENT_REQUIRED", 403),
        ("STALE_REVISION", 409),
        ("CYCLE_LOCKED", 409),
        ("ROOM_EXPIRED", 410),
        ("MESSAGE_REJECTED", 422),
        ("IDEMPOTENCY_CONFLICT", 409),
        ("RATE_LIMITED", 429),
    ],
)
def test_owner_errors_preserve_protocol_codes(code, status):
    async def guard():
        raise ServiceError(code)

    app = create_app(
        settings=Settings(environment="test"), registrations=[registration(guard=guard)]
    )
    with TestClient(app) as client:
        assert_api_error(client.get("/api/v1/fixture/orchestration"), status, code)


@pytest.mark.parametrize("status", [403, 500, 502])
def test_http_errors_do_not_publish_exception_details(status):
    async def guard():
        raise HTTPException(status, detail="synthetic-private-permission-details")

    app = create_app(
        settings=Settings(environment="test"), registrations=[registration(guard=guard)]
    )
    with TestClient(app) as client:
        response = client.get("/api/v1/fixture/orchestration")
        assert_api_error(
            response,
            403 if status == 403 else 503,
            "FORBIDDEN" if status == 403 else "PROVIDER_UNAVAILABLE",
        )
        assert "synthetic-private" not in response.text


def test_duplicate_owners_and_dynamic_route_collisions_fail_at_startup():
    with pytest.raises(ValueError, match="duplicate service owner"):
        create_app(registrations=[registration(), registration()])
    first, second = APIRouter(), APIRouter()
    first.get("/cycles/{cycleId}")(lambda: {})
    second.get("/cycles/{id}")(lambda: {})
    with pytest.raises(ValueError, match="Duplicate service method/path"):
        create_app(
            registrations=[
                ServiceRegistration("privacy", first, synthetic_guard, ready),
                ServiceRegistration("orchestration", second, synthetic_guard, ready),
            ]
        )


def test_registrations_cannot_omit_authorization_or_routes():
    with pytest.raises(ValueError, match="authorization and readiness"):
        create_app(registrations=[registration(guard=None)])
    with pytest.raises(ValueError, match="must include routes"):
        create_app(
            registrations=[ServiceRegistration("privacy", APIRouter(), synthetic_guard, ready)]
        )


def test_python_contract_version_and_error_codes_match_shared_types():
    protocol = (Path(__file__).parents[2] / "contracts" / "protocol.ts").read_text()
    assert f'CONTRACT_VERSION = "{CONTRACT_VERSION}"' in protocol
    declared = re.search(r"export type ErrorCode =(.+?);", protocol, flags=re.S).group(1)
    assert set(re.findall(r'"([A-Z_]+)"', declared)) == set(get_args(ErrorCode))


@pytest.mark.parametrize(
    "origin",
    [
        "*",
        "https://user:pass@example.invalid",
        "file:///local",
        "https://example.invalid/path",
        "https://example.invalid?q=x",
        "https://example.invalid:wrong-port",
    ],
)
def test_invalid_or_wildcard_cors_origins_are_rejected(origin):
    with pytest.raises(ValueError):
        Settings(allowed_origins=(origin,))


def test_production_requires_explicit_environment_configuration(monkeypatch):
    monkeypatch.setenv("CONSTELLATIONS_ENV", "production")
    monkeypatch.delenv("CONSTELLATIONS_ALLOWED_ORIGINS", raising=False)
    with pytest.raises(ValueError, match="Production requires"):
        Settings.from_env()
    monkeypatch.setenv("CONSTELLATIONS_ALLOWED_ORIGINS", "https://app.example.invalid")
    settings = Settings.from_env()
    with TestClient(create_app(settings=settings)) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/docs").status_code == 404
        assert client.get("/openapi.json").status_code == 404


def test_bad_environment_name_fails_before_startup(monkeypatch):
    monkeypatch.setenv("CONSTELLATIONS_ENV", "pretend-live")
    with pytest.raises(ValueError, match="Invalid CONSTELLATIONS_ENV"):
        Settings.from_env()
