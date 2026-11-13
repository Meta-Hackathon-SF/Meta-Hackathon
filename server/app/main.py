"""Run with python -m uvicorn server.app.main:app from the repository root."""

import asyncio
from collections.abc import Sequence

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse

from server.app.config import CONTRACT_VERSION, Settings
from server.app.errors import ErrorCode, ServiceError, error_response
from server.app.middleware import RequestContextMiddleware, SanitizedErrorsMiddleware
from server.app.registry import OWNERS, ServiceRegistration, register_services


def create_app(
    *,
    settings: Settings | None = None,
    registrations: Sequence[ServiceRegistration] = (),
) -> FastAPI:
    settings = settings or Settings.from_env()
    registrations = tuple(registrations)
    app = FastAPI(
        title="Constellations API",
        version=CONTRACT_VERSION,
        docs_url=None if settings.environment == "production" else "/docs",
        redoc_url=None,
        openapi_url=None if settings.environment == "production" else "/openapi.json",
        middleware=[
            Middleware(RequestContextMiddleware),
            Middleware(
                CORSMiddleware,
                allow_origins=list(settings.allowed_origins),
                allow_credentials=True,
                allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
                allow_headers=["Content-Type", "Authorization", "Idempotency-Key", "Last-Event-ID"],
                expose_headers=["X-Request-Id"],
            ),
            Middleware(SanitizedErrorsMiddleware),
        ],
    )

    @app.exception_handler(ServiceError)
    async def service_error(request: Request, error: ServiceError) -> JSONResponse:
        return error_response(request, error.code)

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request: Request, _error: RequestValidationError) -> JSONResponse:
        return error_response(request, "INVALID_INPUT")

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, error: HTTPException) -> JSONResponse:
        code: ErrorCode = {
            401: "UNAUTHENTICATED",
            403: "FORBIDDEN",
            404: "NOT_FOUND",
            429: "RATE_LIMITED",
            503: "PROVIDER_UNAVAILABLE",
        }.get(
            error.status_code,
            "PROVIDER_UNAVAILABLE" if error.status_code >= 500 else "INVALID_INPUT",
        )
        return error_response(request, code)

    @app.get("/health", tags=["health"])
    async def health() -> dict[str, str]:
        return {"status": "ok", "service": "constellations", "contractVersion": CONTRACT_VERSION}

    @app.get("/health/ready", tags=["health"])
    async def readiness() -> JSONResponse:
        registered = {registration.owner: registration for registration in registrations}

        async def check(owner: str) -> tuple[str, str]:
            registration = registered.get(owner)
            if registration is not None:
                try:
                    if await asyncio.wait_for(registration.ready(), timeout=0.5) is True:
                        return owner, "ready"
                except Exception:
                    pass  # Readiness must not expose connection strings or provider details.
            return owner, "unavailable"

        services = dict(await asyncio.gather(*(check(owner) for owner in OWNERS)))
        ready = all(status == "ready" for status in services.values())
        return JSONResponse(
            {"status": "ready" if ready else "not_ready", "services": services},
            status_code=200 if ready else 503,
        )

    register_services(app, registrations)
    return app


# No fake participants, providers, routes, or session bypass are installed by default.
app = create_app()
