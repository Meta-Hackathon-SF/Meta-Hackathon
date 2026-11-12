"""Privacy routes (contracts/API.md) and the auth dependency for every route.

Kai's server composition mounts ``build_router(service)`` under /api/v1 and
uses ``actor_dependency(service)`` on all authenticated routes. Identity comes
only from the session cookie (``gq_session``) or ``Authorization: Bearer``.
"""


import os
import uuid
from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from .errors import PrivacyError
from .service import Actor, PrivacyService
from .wire import (
    ApiError,
    ApiErrorBody,
    JoinCommunityRequest,
    PutIntentRequest,
    UpdateAvailabilityRequest,
    UpdateConsentRequest,
)

SESSION_COOKIE = "gq_session"


def _cookie_secure() -> bool:
    # Secure by default; local http dev must opt out explicitly.
    return os.environ.get("GQ_COOKIE_INSECURE_DEV") != "1"


def request_id(request: Request) -> str:
    rid = getattr(request.state, "request_id", None)
    if rid is None:
        rid = "req_" + uuid.uuid4().hex
        request.state.request_id = rid
    return rid


def session_token(request: Request) -> str | None:
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip() or None
    return request.cookies.get(SESSION_COOKIE)


def actor_dependency(service: PrivacyService) -> Callable[[Request], Actor]:
    """Resolve the session once per request; Kai's router-level guard and the
    route-level dependency then share the same verified Actor."""

    def require_actor(request: Request) -> Actor:
        cached = getattr(request.state, "gq_actor", None)
        if isinstance(cached, Actor):
            return cached
        actor = service.resolve(session_token(request))
        request.state.gq_actor = actor
        return actor

    return require_actor


def error_response(request: Request, code: str, message: str, status: int, retryable: bool) -> JSONResponse:
    rid = request_id(request)
    body = ApiError(error=ApiErrorBody(code=code, message=message, request_id=rid, retryable=retryable))
    return JSONResponse(body.wire(), status_code=status, headers={"X-Request-Id": rid})


def install_privacy_error_handler(app: FastAPI) -> None:
    """PrivacyError -> ApiError. The only handler Kai's composed app needs from
    privacy; request ids, validation errors and sanitizing stay Kai's."""

    @app.exception_handler(PrivacyError)
    async def _privacy(request: Request, exc: PrivacyError) -> JSONResponse:
        return error_response(request, exc.code, exc.message, exc.status, exc.retryable)


def install_error_handlers(app: FastAPI) -> None:
    """Standalone setup for the privacy dev harness and tests: privacy errors plus
    request ids and validation envelopes. Kai's app uses install_privacy_error_handler."""
    install_privacy_error_handler(app)

    @app.exception_handler(RequestValidationError)
    async def _invalid(request: Request, exc: RequestValidationError) -> JSONResponse:
        fields = sorted({".".join(str(p) for p in e.get("loc", ())[1:]) or "body" for e in exc.errors()})
        return error_response(request, "INVALID_INPUT", "Invalid fields: " + ", ".join(fields), 400, False)

    @app.middleware("http")
    async def _request_id(request: Request, call_next):
        rid = request_id(request)
        response = await call_next(request)
        response.headers.setdefault("X-Request-Id", rid)
        response.headers.setdefault("Cache-Control", "no-store")
        return response


def build_router(service: PrivacyService) -> APIRouter:
    router = APIRouter()
    ActorDep = Annotated[Actor, Depends(actor_dependency(service))]

    @router.post("/session", status_code=201)
    def create_session(request: Request, response: Response) -> dict:
        """Create a pseudonymous guest participant on this device. Not linked to
        any Facebook identity; the mock shell's demo users are not accounts."""
        token, actor, expires_at = service.create_guest_session()
        response.set_cookie(
            SESSION_COOKIE, token, httponly=True, secure=_cookie_secure(), samesite="lax",
            expires=expires_at, path="/api",
        )
        return service.session_view(actor, token).wire()

    @router.get("/session")
    def get_session(request: Request, actor: ActorDep) -> dict:
        return service.session_view(actor, session_token(request) or "").wire()

    @router.delete("/session", status_code=204)
    def delete_session(request: Request, actor: ActorDep) -> Response:
        service.revoke_session(session_token(request) or "")
        response = Response(status_code=204)
        response.delete_cookie(SESSION_COOKIE, path="/api")
        return response

    @router.post("/communities/{community_id}/join")
    def join(community_id: str, body: JoinCommunityRequest, actor: ActorDep) -> dict:
        return service.join(actor, community_id, body).wire()

    @router.get("/communities/{community_id}/consent")
    def get_consent(community_id: str, actor: ActorDep) -> dict:
        return service.get_consent(actor, community_id).wire()

    @router.patch("/communities/{community_id}/consent")
    def patch_consent(community_id: str, body: UpdateConsentRequest, actor: ActorDep) -> dict:
        return service.update_consent(actor, community_id, body).wire()

    @router.post("/communities/{community_id}/leave")
    def leave(community_id: str, actor: ActorDep) -> dict:
        return service.leave_community(actor, community_id).wire()

    @router.get("/intents/me")
    def get_intent(communityId: str, actor: ActorDep) -> dict:  # noqa: N803 (camelCase query)
        return service.get_intent(actor, communityId).wire()

    @router.put("/intents/me")
    def put_intent(body: PutIntentRequest, actor: ActorDep) -> dict:
        return service.put_intent(actor, body).wire()

    @router.patch("/intents/me/availability")
    def patch_availability(body: UpdateAvailabilityRequest, actor: ActorDep) -> dict:
        return service.update_availability(actor, body).wire()

    return router
