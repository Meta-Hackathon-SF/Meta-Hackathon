"""Bounded formation job. Provider work is outside the store transaction."""

import asyncio
import math
from typing import Protocol

from server.app.errors import ServiceError
from server.orchestration.domain import validate_partition
from server.orchestration.repository import FormationStore
from server.orchestration.wire import FormationFailure, FormationSuccess


class FormationPort(Protocol):
    async def form(self, cycleId: str) -> dict: ...


async def form_once(
    store: FormationStore, formation: FormationPort, cycle_id: str, *, timeout_seconds: float = 120
):
    if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
        raise ValueError("Formation timeout must be positive and finite")
    job = await store.claim(cycle_id)
    if job is None:
        return None
    try:
        cycle = await store.cycle(cycle_id)
        if cycle.status not in {"locked", "forming"}:
            raise ServiceError("CYCLE_LOCKED")
        raw = await asyncio.wait_for(formation.form(cycle_id), timeout=timeout_seconds)
        if isinstance(raw, dict) and raw.get("status") == "failed":
            failed = FormationFailure.model_validate(raw)
            raise ServiceError(failed.error.code)
        result = FormationSuccess.model_validate(raw)
        if any(c.cycleId != cycle_id for c in result.constellations):
            raise ServiceError("INVALID_INPUT")
        validate_partition(result.constellations, job["eligibleIds"], job["blockedPairs"])
        # This operation must recheck current privacy state, including deletions.
        await store.commit(job, result)
        return result
    except asyncio.CancelledError:
        await store.fail(job, "PROVIDER_UNAVAILABLE")
        raise
    except ServiceError as error:
        await store.fail(job, error.code)
        raise
    except Exception:
        await store.fail(job, "PROVIDER_UNAVAILABLE")
        raise ServiceError("PROVIDER_UNAVAILABLE") from None
