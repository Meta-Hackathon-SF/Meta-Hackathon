"""Fixture evidence only: real production persistence/privacy ports are absent."""

import asyncio
from copy import deepcopy
from pathlib import Path

import pytest
from pydantic import ValidationError

from server.app.errors import ServiceError
from server.orchestration.wire import Constellation, FormationSuccess, WeeklyCycle
from server.orchestration.worker import form_once

from .adapters import TestFormation, TestFormationStore, cycle_wire, formation_wire


def test_shared_weekly_fixture_validates_without_changing_keys():
    wire = cycle_wire()
    assert WeeklyCycle.model_validate(wire).model_dump() == wire


@pytest.mark.parametrize(
    "field,value",
    [
        ("currentDay", True),
        ("currentDay", 0),
        ("weekStart", "2026-11-10"),
        ("locksAt", "2026-11-14T12:00:00-08:00"),
        ("status", "proposed"),
        ("demoTiming", "true"),
        ("chatExpiresAt", "2026-11-14T20:00:00Z"),
    ],
)
def test_invalid_weekly_boundary(field, value):
    with pytest.raises(ValidationError):
        WeeklyCycle.model_validate({**cycle_wire(), field: value})


@pytest.mark.parametrize(
    "change",
    [
        {"memberIds": ["x", "x", "y"]},
        {"memberIds": ["x", "y"]},
        {"isFallback": True},
        {"confidence": float("nan")},
        {"confidence": 1.1},
        {"isLooseMatch": 1},
        {"member_ids": ["x", "y", "z"]},
    ],
)
def test_formation_boundary_rejects_invalid_or_extra_fields(change):
    value = {**formation_wire()["constellations"][0], **change}
    with pytest.raises(ValidationError):
        Constellation.model_validate(value)


def test_formation_keys_are_exact_shared_contract_fields():
    protocol = (Path(__file__).parents[2] / "contracts/protocol.ts").read_text()
    import re

    body = re.search(r"export interface Constellation \{(.*?)\n\}", protocol, re.S)[1]
    body = re.sub(r"//[^\n]*", "", body)
    # Inline private pair objects have their own keys; compare top-level fields.
    top_level = re.sub(r"\{[^{}]*\}", "", body)
    keys = set(re.findall(r"(\w+)\??\s*:", top_level))
    assert keys == set(Constellation.model_fields)
    assert FormationSuccess.model_validate(formation_wire()).model_dump() == formation_wire()


def test_duplicate_workers_commit_once_without_provider_inside_transaction():
    async def scenario():
        store, model = TestFormationStore(), TestFormation()
        results = await asyncio.gather(
            *(form_once(store, model, "cycle-demo-w1") for _ in range(5))
        )
        assert sum(r is not None for r in results) == 1
        assert model.calls == 1 and store.committed is not None
        assert await form_once(store, model, "cycle-demo-w1") is None

    asyncio.run(scenario())


def test_revoked_consent_or_deleted_answer_revision_drops_stale_completion():
    async def scenario():
        store, resume = TestFormationStore(), asyncio.Event()
        task = asyncio.create_task(form_once(store, TestFormation(pause=resume), "cycle-demo-w1"))
        await store.claimed.wait()
        store.revision += 1  # synthetic revoke/delete after snapshot
        resume.set()
        with pytest.raises(ServiceError) as error:
            await task
        assert error.value.code == "STALE_REVISION"
        assert store.committed is None

    asyncio.run(scenario())


@pytest.mark.parametrize("mutation", ["blocked", "missing", "duplicate", "wrong_cycle", "extra"])
def test_invalid_provider_result_never_commits(mutation):
    async def scenario():
        store = TestFormationStore()
        value = deepcopy(formation_wire())
        c = value["constellations"][0]
        if mutation == "blocked":
            store.claim_original = store.claim

            async def claim(cycle_id):
                job = await store.claim_original(cycle_id)
                job["blockedPairs"] = [("synthetic-p1", "synthetic-p2")]
                return job

            store.claim = claim
        elif mutation == "missing":
            c["memberIds"][-1] = "other"
        elif mutation == "duplicate":
            value["constellations"].append(deepcopy(c))
        elif mutation == "wrong_cycle":
            c["cycleId"] = "other"
        else:
            c["isFallback"] = True
        with pytest.raises(ServiceError):
            await form_once(store, TestFormation(value), "cycle-demo-w1")
        assert store.committed is None and store.failures

    asyncio.run(scenario())


def test_cancellation_and_provider_failure_store_only_safe_codes():
    async def scenario():
        for result in [
            RuntimeError("SYNTHETIC PRIVATE PROVIDER BODY"),
            {
                "status": "failed",
                "error": {
                    "code": "PROVIDER_UNAVAILABLE",
                    "message": "synthetic",
                    "requestId": "request-1",
                    "retryable": True,
                },
            },
        ]:
            store = TestFormationStore()
            with pytest.raises(ServiceError) as error:
                await form_once(store, TestFormation(result), "cycle-demo-w1")
            assert str(error.value) == "PROVIDER_UNAVAILABLE"
            assert store.failures == ["PROVIDER_UNAVAILABLE"]
        store = TestFormationStore()
        task = asyncio.create_task(
            form_once(store, TestFormation(pause=asyncio.Event()), "cycle-demo-w1")
        )
        await store.claimed.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert store.committed is None and store.failures == ["PROVIDER_UNAVAILABLE"]

    asyncio.run(scenario())


def test_configured_formation_timeout_holds_no_transaction_and_records_safe_failure():
    async def scenario():
        store = TestFormationStore()
        with pytest.raises(ServiceError) as error:
            await form_once(
                store, TestFormation(pause=asyncio.Event()), "cycle-demo-w1", timeout_seconds=0.001
            )
        assert error.value.code == "PROVIDER_UNAVAILABLE"
        assert store.committed is None
        assert store.failures == ["PROVIDER_UNAVAILABLE"]

    asyncio.run(scenario())


@pytest.mark.parametrize("timeout", [0, -1, float("inf"), float("nan")])
def test_formation_timeout_must_be_bounded_positive_configuration(timeout):
    with pytest.raises(ValueError):
        asyncio.run(
            form_once(
                TestFormationStore(), TestFormation(), "cycle-demo-w1", timeout_seconds=timeout
            )
        )
