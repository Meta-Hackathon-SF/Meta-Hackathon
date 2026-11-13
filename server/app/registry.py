"""Explicit composition boundary; auth/session behavior remains owned by Patrik."""

import re
from collections.abc import Awaitable, Callable, Sequence
from copy import copy
from dataclasses import dataclass
from typing import Literal

from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.routing import APIRoute

from server.app.errors import ServiceError

Owner = Literal["privacy", "matching", "planning", "orchestration", "voice", "cycle", "chat"]
OWNERS: tuple[Owner, ...] = (
    "privacy",
    "matching",
    "planning",
    "orchestration",
    "voice",
    "cycle",
    "chat",
)


@dataclass(frozen=True)
class ServiceRegistration:
    owner: Owner
    router: APIRouter
    authorize: Callable[..., object]
    ready: Callable[[], Awaitable[bool]]
    operator_login_bootstrap: bool = False


def require_idempotency_key(request: Request) -> None:
    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        keys = request.headers.getlist("Idempotency-Key")
        if len(keys) != 1 or not re.fullmatch(r"[!-~]{1,128}", keys[0]):
            raise ServiceError("INVALID_INPUT")


def register_services(app: FastAPI, registrations: Sequence[ServiceRegistration]) -> None:
    seen_owners: set[str] = set()
    seen_routes: set[tuple[str, str]] = set()
    for registration in registrations:
        if registration.owner not in OWNERS or registration.owner in seen_owners:
            raise ValueError("Unknown or duplicate service owner")
        if not callable(registration.authorize) or not callable(registration.ready):
            raise ValueError("A service requires authorization and readiness adapters")
        if registration.operator_login_bootstrap and registration.owner != "privacy":
            raise ValueError("Only privacy may enable operator login bootstrap")
        if not registration.router.routes:
            raise ValueError("A service registration must include routes")
        seen_owners.add(registration.owner)
        bootstrap_routes: list[APIRoute] = []
        protected_routes: list[APIRoute] = []
        for route in registration.router.routes:
            if not isinstance(route, APIRoute):
                raise ValueError("Only HTTP API routes may be registered in this baseline")
            is_join = re.fullmatch(r"/communities/\{[^}]+\}/join", route.path) is not None
            is_login = route.path == "/operator/login" and registration.operator_login_bootstrap
            if is_login and route.methods != {"POST"}:
                raise ValueError("Operator login bootstrap requires POST only")
            if (is_join or is_login) and "POST" in route.methods:
                if registration.owner != "privacy" or route.methods != {"POST"}:
                    raise ValueError("Only privacy may register an authentication bootstrap route")
                bootstrap_routes.append(route)
            else:
                protected_routes.append(route)
            normalized = re.sub(r"\{[^}]+\}", "{}", route.path)
            for method in route.methods:
                identity = (method, normalized)
                if identity in seen_routes:
                    raise ValueError("Duplicate service method/path registration")
                seen_routes.add(identity)
        # Keep the owner's lifespan handlers once; do not mutate its router or remove
        # route-level dependencies. Only reviewed, explicit bootstrap routes skip
        # the global verified-session dependency, so a new browser can obtain one.
        protected_router = copy(registration.router)
        protected_router.routes = protected_routes
        app.include_router(
            protected_router,
            prefix="/api/v1",
            dependencies=[Depends(registration.authorize), Depends(require_idempotency_key)],
        )
        if bootstrap_routes:
            bootstrap_router = APIRouter()
            bootstrap_router.routes = bootstrap_routes
            app.include_router(
                bootstrap_router,
                prefix="/api/v1",
                dependencies=[Depends(require_idempotency_key)],
            )
