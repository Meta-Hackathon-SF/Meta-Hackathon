"""Top-down formation budget (audit #72): every Muse call gets the REMAINING time as deadline_s,
and when the budget is gone formation falls back to labeled keyword grouping instead of hanging."""

from __future__ import annotations

import asyncio

from server.matching.formation import FALLBACK_RESERVE_S, FormationService
from tests.matching.adapters import FakeMuse, FixtureGuard, FixtureSnapshotSource
from tests.matching.test_formation import BLOCKED, GOOD


class DeadlineMuse(FakeMuse):
    """FakeMuse that records the deadline_s it was handed."""

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.deadlines: list[float | None] = []

    async def run(
        self,
        *,
        task,
        requestId,
        promptVersion,
        payload,
        signal=None,
        correction=None,
        deadline_s=None,
    ):
        self.deadlines.append(deadline_s)
        return await super().run(
            task=task,
            requestId=requestId,
            promptVersion=promptVersion,
            payload=payload,
            signal=signal,
            correction=correction,
        )


def build(budget_s, clock=None):
    source = FixtureSnapshotSource()
    source.snapshot()
    muse = DeadlineMuse(source.ref_of, GOOD, blocked_groups=BLOCKED)
    kw = {"clock": clock} if clock else {}
    return FormationService(muse, source, FixtureGuard(), budget_s=budget_s, **kw), muse


def test_every_call_receives_deadline_within_budget():
    service, muse = build(budget_s=40.0)
    result = asyncio.run(service.form("c1"))
    assert result.status == "ok" and muse.deadlines
    assert all(d is not None and 0 < d <= 40.0 - FALLBACK_RESERVE_S for d in muse.deadlines)


def test_no_budget_keeps_old_behaviour():
    service, muse = build(budget_s=None)
    asyncio.run(service.form("c1"))
    assert all(d is not None for d in muse.deadlines)  # per-call cap still passed


def test_exhausted_budget_falls_back_without_calling_muse():
    service, muse = build(budget_s=FALLBACK_RESERVE_S)  # nothing left after the reserve
    result = asyncio.run(service.form("c1"))
    assert result.status == "ok" and result.used_fallback and not muse.deadlines
    assert all("Fallback grouping" in c.name for c in result.constellations)
