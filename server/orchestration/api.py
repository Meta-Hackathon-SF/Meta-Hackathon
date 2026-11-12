"""Authenticated, strict HTTP boundary for the independently verifiable P1 workflow."""

import asyncio
from collections.abc import Callable
from typing import Annotated, Any, cast

from fastapi import APIRouter, Body, Depends, FastAPI, Request

from server.app.config import Settings
from server.app.errors import ErrorCode, ServiceError, error_response
from server.app.main import create_app
from server.app.registry import ServiceRegistration, require_idempotency_key
from server.privacy import Actor, PrivacyError, PrivacyService, actor_dependency

from .repository import WorkflowRepository
from .wire import (
    validate_acceptance,
    validate_acceptance_record,
    validate_message,
    validate_snapshot,
)

ProposalLoader = Callable[[Actor, str, int], tuple[dict, list[dict]]]


def install_workflow_error_handlers(app: FastAPI) -> None:
    """Translate only public privacy error codes; never publish their raw details."""

    @app.exception_handler(PrivacyError)
    async def privacy_error(request: Request, error: PrivacyError):
        return error_response(request, cast(ErrorCode, error.code))


def _key(request: Request) -> str:
    require_idempotency_key(request)
    return request.headers["Idempotency-Key"]


def build_router(
    repository: WorkflowRepository,
    privacy: PrivacyService,
    *,
    proposal_loader: ProposalLoader | None = None,
) -> APIRouter:
    """The optional loader reads a server-held proposal, never a client-supplied group."""
    router = APIRouter(tags=["quests"])
    get_actor = actor_dependency(privacy)

    @router.post("/quests", status_code=201)
    def create_quest(
        request: Request,
        body: Annotated[dict[str, Any], Body()],
        actor: Annotated[Actor, Depends(get_actor)],
    ) -> dict:
        if (
            set(body) != {"proposalId", "proposalRevision"}
            or not isinstance(body["proposalId"], str)
            or not body["proposalId"]
            or type(body["proposalRevision"]) is not int
            or body["proposalRevision"] < 1
        ):
            raise ServiceError("INVALID_INPUT")
        key = _key(request)
        if proposal_loader is None:
            raise ServiceError("PROVIDER_UNAVAILABLE")
        proposal, members = proposal_loader(actor, body["proposalId"], body["proposalRevision"])
        if (
            proposal.get("proposalId") != body["proposalId"]
            or proposal.get("revision") != body["proposalRevision"]
        ):
            raise ServiceError("STALE_REVISION")
        snapshot = repository.create_quest(actor, proposal, members, idempotency_key=key)
        return validate_snapshot(snapshot)

    @router.get("/quests/{quest_id}")
    def snapshot(quest_id: str, actor: Annotated[Actor, Depends(get_actor)]) -> dict:
        return validate_snapshot(repository.snapshot(actor, quest_id))

    @router.post("/quests/{quest_id}/accept")
    def accept(
        quest_id: str,
        request: Request,
        body: Annotated[dict[str, Any], Body()],
        actor: Annotated[Actor, Depends(get_actor)],
    ) -> dict:
        command = validate_acceptance(body)
        result = repository.accept(
            actor,
            quest_id,
            revision=command["revision"],
            choice=command["choice"],
            idempotency_key=_key(request),
        )
        if set(result) != {"acceptance", "snapshot"}:
            raise ServiceError("PROVIDER_UNAVAILABLE")
        return {
            "acceptance": validate_acceptance_record(result["acceptance"]),
            "snapshot": validate_snapshot(result["snapshot"]),
        }

    @router.get("/quests/{quest_id}/messages")
    def messages(quest_id: str, actor: Annotated[Actor, Depends(get_actor)]) -> list[dict]:
        # Repository performs current room authorization before returning persisted messages.
        return [validate_message(message) for message in repository.messages(actor, quest_id)]

    return router


def create_workflow_app(
    *,
    repository: WorkflowRepository,
    privacy: PrivacyService,
    settings: Settings | None = None,
    proposal_loader: ProposalLoader | None = None,
) -> FastAPI:
    """Compose supplied real services. No environment-controlled fixture or auth bypass."""
    from server.privacy import build_router as privacy_router

    def probe_database() -> bool:
        # Readiness is exposed separately from liveness and does not invoke a model.
        # The repository supplies its own schema/connection probe.
        return repository.ready()

    async def workflow_ready() -> bool:
        return await asyncio.to_thread(probe_database)

    app = create_app(
        settings=settings,
        registrations=[
            ServiceRegistration(
                "privacy", privacy_router(privacy), actor_dependency(privacy), workflow_ready
            ),
            ServiceRegistration(
                "orchestration",
                build_router(repository, privacy, proposal_loader=proposal_loader),
                actor_dependency(privacy),
                workflow_ready,
            ),
        ],
    )
    install_workflow_error_handlers(app)
    return app
