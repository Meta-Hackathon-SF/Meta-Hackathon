"""Repair of near-valid M4 proposals (offline, synthetic refs)."""
from __future__ import annotations

import asyncio

from server.matching.formation import FormationService
from server.matching.repair import REPAIRED_CONFIDENCE_CAP, repair_proposal
from server.matching.validation import violations
from tests.matching.adapters import FakeMuse, FixtureGuard, evidence

REFS = [f"r{i}" for i in range(1, 16)]  # 15 players -> 3 groups of 5
GOOD = [REFS[0:5], REFS[5:10], REFS[10:15]]


def prop(groups, conf=0.8):
    return [(tuple(g), f"meaning {i}", conf) for i, g in enumerate(groups)]


def test_valid_groups_untouched_missing_ref_placed():
    groups = [REFS[0:5], REFS[5:10], REFS[10:14]]  # r15 dropped by the model
    fixed = repair_proposal(prop(groups), REFS, [], {})
    assert fixed is not None and violations(fixed.groups, REFS, []) == []
    assert fixed.touched == (False, False, True)
    assert fixed.confidences[2] <= REPAIRED_CONFIDENCE_CAP
    assert fixed.meanings[0] == "meaning 0"


def test_duplicate_and_unknown_refs_removed():
    groups = [REFS[0:5] + ["ghost"], REFS[5:10] + ["r1"], REFS[10:15]]
    fixed = repair_proposal(prop(groups), REFS, [], {})
    assert fixed is not None and violations(fixed.groups, REFS, []) == []
    assert all("ghost" not in g for g in fixed.groups)


def test_oversize_group_trimmed_by_affinity():
    groups = [REFS[0:6], REFS[6:10], REFS[10:15]]  # 6 / 4 / 5
    sim = {("r1", "r6"): 0.0, ("r6", "r7"): 0.9}
    fixed = repair_proposal(prop(groups), REFS, [], sim)
    assert fixed is not None and violations(fixed.groups, REFS, []) == []
    assert all(3 <= len(g) <= 5 for g in fixed.groups)


def test_blocked_pair_evicted_and_kept_apart():
    blocked = [("r1", "r2")]
    fixed = repair_proposal(prop(GOOD), REFS, blocked, {})
    assert fixed is not None
    assert violations(fixed.groups, REFS, blocked) == []


def test_garbage_proposal_not_repaired():
    groups = [["r1", "r2"], ["r3"], ["ghost", "r4"]]
    assert repair_proposal(prop(groups), REFS, [], {}) is None


def test_formation_repairs_without_second_m4_call():
    class Snap:
        async def formation_snapshot(self, cycle_id):
            return {"answers": [{"id": r, "text": f"answer about topic {r}"} for r in REFS],
                    "idMap": {r: f"p-{r}" for r in REFS}, "blockedPairs": []}

    class DropsOne(FakeMuse):
        async def run(self, *, task, requestId, promptVersion, payload, signal=None):
            if task == "constellation_formation":
                self.calls.append({"task": task, "payload": payload})
                return {"output": {"constellations": [
                    {"memberIds": g, "sharedMeaning": "m", "confidence": 0.8}
                    for g in [REFS[0:5], REFS[5:10], REFS[10:14]]]},
                    "evidence": evidence("M4")}
            return await super().run(task=task, requestId=requestId,
                                     promptVersion=promptVersion, payload=payload)

    muse = DropsOne({}, [])
    result = asyncio.run(FormationService(muse, Snap(), FixtureGuard()).form("c"))
    assert result.status == "ok" and not result.used_fallback
    assert result.repaired_groups == 1
    assert [c["task"] for c in muse.calls].count("constellation_formation") == 1
    loose = [c for c in result.constellations if c.is_loose_match]
    assert len(loose) == 1 and "p-r15" in loose[0].member_ids


def test_fuzz_repair_is_valid_or_none():
    import random

    rng = random.Random(1)
    repaired = 0
    for trial in range(400):
        n = rng.randint(6, 40)
        refs = [f"r{i}" for i in range(n)]
        order = refs[:]
        rng.shuffle(order)
        groups = [order[i:i + 4] for i in range(0, n, 4)]
        for _ in range(rng.randint(0, 3)):  # break a few things
            kind = rng.choice(["drop", "dup", "ghost", "grow"])
            g = rng.choice(groups)
            if kind == "drop" and g:
                g.pop()
            elif kind == "dup":
                g.append(rng.choice(refs))
            elif kind == "ghost":
                g.append(f"ghost{trial}")
            elif kind == "grow":
                g.extend(rng.sample(refs, 2))
        blocked = {tuple(sorted(rng.sample(refs, 2))) for _ in range(rng.randint(0, n // 4))}
        sim = {(a, b): rng.random() for a in refs for b in refs if a < b}
        fixed = repair_proposal(prop(groups), refs, blocked, sim)
        if fixed is not None:
            repaired += 1
            assert violations(fixed.groups, refs, blocked) == [], trial
    assert repaired > 200
