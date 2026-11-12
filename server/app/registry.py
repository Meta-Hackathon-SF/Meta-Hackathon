"""Explicit composition boundary; auth/session behavior remains owned by Patrik."""

import re
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import Literal

from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.routing import APIRoute

from server.app.errors import ServiceError

Owner = Literal["privacy", "matching", "planning", "orchestration", "voice"]
OWNERS: tuple[Owner, ...] = ("privacy", "matching", "planning", "orchestration", "voice")


@dataclass(frozen=True)
class ServiceRegistration:
    owner: Owner
    router: APIRouter
    authorize: Callable[..., object]
    ready: Callable[[], Awaitable[bool]]


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
        if not registration.router.routes:
            raise ValueError("A service registration must include routes")
        seen_owners.add(registration.owner)
        for route in registration.router.routes:
            if not isinstance(route, APIRoute):
                raise ValueError("Only HTTP API routes may be registered in this baseline")
            normalized = re.sub(r"\{[^}]+\}", "{}", route.path)
            for method in route.methods:
                identity = (method, normalized)
                if identity in seen_routes:
                    raise ValueError("Duplicate service method/path registration")
                seen_routes.add(identity)
        app.include_router(
            registration.router,
            prefix="/api/v1",
            dependencies=[Depends(registration.authorize), Depends(require_idempotency_key)],
        )
