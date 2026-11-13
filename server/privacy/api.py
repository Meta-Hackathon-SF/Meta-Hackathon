"""Privacy routes (contracts/API.md "Session, consent, safety") and the session
dependency for every authenticated route.

Kai's composition mounts ``build_router(service)`` under /api/v1 and uses
``actor_dependency(service)`` on all authenticated routes. Identity comes only
from the session cookie (``cst_session``) or ``Authorization: Bearer``.
"""

# No ``from __future__ import annotations``: FastAPI must see the real
# ``Annotated[Actor, Depends(...)]`` objects to resolve dependencies.

import os
import uuid
from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from .errors import PrivacyError
from .answers import AnswerStore
from .service import Actor, PrivacyService
from .wire import ApiError, ApiErrorBody, JoinRequest, UpdateConsentRequest

SESSION_COOKIE = "cst_session"


def _cookie_secure() -> bool:
    # Secure by default; local http dev must opt out explicitly.
    return os.environ.get("CST_COOKIE_INSECURE_DEV") != "1"


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
    """Resolve the session once per request and cache it on request.state."""

    def require_actor(request: Request) -> Actor:
        cached = getattr(request.state, "cst_actor", None)
        if isinstance(cached, Actor):
            return cached
        actor = service.require_session(session_token(request))
        request.state.cst_actor = actor
        return actor

    return require_actor


def error_response(request: Request, code: str, message: str, status: int, retryable: bool) -> JSONResponse:
    rid = request_id(request)
    body = ApiError(error=ApiErrorBody(code=code, message=message, request_id=rid, retryable=retryable))
    return JSONResponse(body.wire(), status_code=status, headers={"X-Request-Id": rid, "Cache-Control": "no-store"})


def install_privacy_error_handler(app: FastAPI) -> None:
    """PrivacyError -> ApiError envelope. The only handler a composed app needs
    from privacy; request ids and validation envelopes stay with Kai."""

    @app.exception_handler(PrivacyError)
    async def _privacy(request: Request, exc: PrivacyError) -> JSONResponse:
        return error_response(request, exc.code, exc.message, exc.status, exc.retryable)


def install_error_handlers(app: FastAPI) -> None:
    """Standalone setup (dev harness, tests): privacy errors, validation errors
    that never echo submitted values, and request ids."""
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


def build_router(service: PrivacyService, answers: AnswerStore | None = None) -> APIRouter:
    router = APIRouter()
    ActorDep = Annotated[Actor, Depends(actor_dependency(service))]

    @router.post("/communities/{community_id}/join")
    def join(community_id: str, body: JoinRequest, request: Request, response: Response) -> dict:
        """Pseudonymous player for this Group. Not linked to any Facebook
        identity; the mock shell's demo users are not accounts."""
        result = service.join(community_id, body, session_token(request))
        if result.token is not None:
            response.set_cookie(
                SESSION_COOKIE, result.token, httponly=True, secure=_cookie_secure(), samesite="lax",
                max_age=int(service.session_ttl.total_seconds()), path="/api",
            )
        response.status_code = 201 if result.created else 200
        return result.view.wire()

    @router.get("/session")
    def get_session(actor: ActorDep) -> dict:
        return service.session_view(actor).wire()

    @router.delete("/session", status_code=204)
    def delete_session(actor: ActorDep) -> Response:
        service.end_session(actor)
        response = Response(status_code=204)
        response.delete_cookie(SESSION_COOKIE, path="/api")
        return response

    @router.patch("/me/consent")
    def patch_consent(body: UpdateConsentRequest, actor: ActorDep) -> dict:
        return service.update_consent(actor, body).wire()

    if answers is not None:
        @router.delete("/me/data", status_code=202)
        def delete_my_data(actor: ActorDep) -> dict:
            """Deletes every answer and guess of this player now; Kai's listener
            drops chat authorship links on the ``data_deleted`` notice."""
            answers.delete_my_data(actor.player_id)
            return {"status": "deleted"}

    return router
