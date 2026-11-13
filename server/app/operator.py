"""Operator metadata only. Sources receive the verified, Group-scoped actor.

No provider call, fixture source or report queue is fabricated. The caller must
supply actor-scoped approved readers; never expose a multi-Group global log.
"""

from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, Depends

from server.app.errors import ServiceError
from server.app.registry import ServiceRegistration
from server.chat.wire import Report
from server.orchestration.wire import MuseCallEvidence


def operator_registration(
    *,
    session_dependency: Callable,
    require_operator: Callable,
    calls_source: Callable | None = None,
    reports_source: Callable | None = None,
) -> ServiceRegistration:
    router = APIRouter()

    def read(actor, source, model):
        require_operator(actor)
        if source is None:
            raise ServiceError("PROVIDER_UNAVAILABLE")
        try:
            rows = source(actor)
            if not isinstance(rows, list):
                raise ValueError("invalid source")
            fields = set(model.model_fields)
            # Allowlist projection removes internal requestId or accidental raw
            # payload fields before runtime validation; never serialize a source.
            return [model.model_validate({k: row[k] for k in fields}).model_dump() for row in rows]
        except Exception:
            raise ServiceError("PROVIDER_UNAVAILABLE") from None

    @router.get("/operator/calls")
    def calls(actor: Annotated[object, Depends(session_dependency)]):
        return read(actor, calls_source, MuseCallEvidence)

    @router.get("/operator/reports")
    def reports(actor: Annotated[object, Depends(session_dependency)]):
        return read(actor, reports_source, Report)

    async def ready():
        # These are configured readers; readiness makes no provider/network call.
        return calls_source is not None and reports_source is not None

    return ServiceRegistration("orchestration", router, session_dependency, ready)
