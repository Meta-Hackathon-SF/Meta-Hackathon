"""MatchingPort: the wire surface Kai's lock job consumes (offline, TEST-ONLY adapters)."""
from __future__ import annotations

import asyncio
import json

import pytest

from server.matching.models import MatchingError
from server.matching.port import build_matching_port
from tests.matching.adapters import FakeMuse, FixtureGuard, FixtureSnapshotSource, load_week
from tests.matching.test_formation import BLOCKED, GOOD

CONSTELLATION_KEYS = {"constellationId", "cycleId", "memberIds", "sharedMeaning", "confidence",
                      "isLooseMatch", "name", "shapeId", "colorId", "baselineAgrees"}
EVIDENCE_KEYS = {"callType", "model", "source", "generatedAt", "latencyMs"}


class FixtureGuesses:
    label = "TEST-ONLY adapter"

    async def prevalence_guesses(self, cycle_id):
        return {g["playerId"]: g["percent"] for g in load_week()["guesses"]}


class SkyMuse(FakeMuse):
    async def run(self, *, task, requestId, promptVersion, payload, signal=None):
        if task == "sky_narration":
            return {"output": {"headlines": [f"{payload['eligiblePlayers']} people answered."]},
                    "evidence": {"callType": "M8", "model": "fake-muse", "source": "replay",
                                 "generatedAt": "2026-11-15T18:00:00Z", "latencyMs": 1}}
        return await super().run(task=task, requestId=requestId,
                                 promptVersion=promptVersion, payload=payload)


def port(m4_script=("good",), **kw):
    source = FixtureSnapshotSource()
    source.snapshot()
    muse = SkyMuse(source.ref_of, GOOD, m4_script=m4_script, blocked_groups=BLOCKED)
    return build_matching_port(muse=muse, snapshots=source, guesses=FixtureGuesses(),
                               guard=FixtureGuard(), **kw)


def run(coro):
    return asyncio.run(coro)


def test_form_returns_exact_formation_success_wire():
    raw = run(port().form("cycle-1"))
    assert set(raw) == {"status", "constellations", "evidence"} and raw["status"] == "ok"
    for c in raw["constellations"]:
        assert set(c) == CONSTELLATION_KEYS
        assert c["cycleId"] == "cycle-1" and 3 <= len(c["memberIds"]) <= 5
        assert len(set(c["memberIds"])) == len(c["memberIds"])
    assert all(set(e) == EVIDENCE_KEYS for e in raw["evidence"])
    json.dumps(raw)  # plain JSON, no dataclasses


def test_form_wire_hides_internal_fields_and_themes():
    blob = json.dumps(run(port(m4_script=("raise",)).form("c")))
    for internal in ("isFallback", "repairedGroups", "timings", "themes", "weightedSupport"):
        assert internal not in blob
    assert "Fallback grouping" in blob


def test_form_failure_is_wire_not_exception():
    raw = run(port(m4_script=("raise",), allow_fallback=False).form("c"))
    assert raw["status"] == "failed"
    assert set(raw["error"]) == {"code", "message", "requestId", "retryable"}
    assert raw["error"]["code"] == "PROVIDER_UNAVAILABLE" and raw["error"]["retryable"]


def test_compute_sky_after_form_uses_private_themes():
    p = port()
    run(p.form("c"))
    sky = run(p.computeSky("c", 3))
    assert sky["cycleId"] == "c" and sky["threshold"] == 3
    assert sky["headlines"] and all(t["count"] >= 3 for t in sky["themes"])
    assert "memberIds" not in json.dumps(sky)


def test_compute_sky_with_synthetic_signals_labeled():
    p = port(synthetic_tags=("skipped a plan",))
    run(p.form("c"))
    sig = run(p.computeSky("c", 3))["syntheticSignals"]
    assert sig and sig[0]["source"] == "synthetic" and "Synthetic signal" in sig[0]["label"]


def test_compute_sky_unknown_cycle_not_found():
    with pytest.raises(MatchingError) as err:
        run(port().computeSky("never-formed", 3))
    assert err.value.code == "NOT_FOUND"


def test_compute_sky_bad_guesses_invalid_input():
    class BadGuesses:
        async def prevalence_guesses(self, cycle_id):
            return {"p-maya": 150}

    source = FixtureSnapshotSource()
    source.snapshot()
    p = build_matching_port(muse=SkyMuse(source.ref_of, GOOD), snapshots=source,
                            guesses=BadGuesses(), guard=FixtureGuard())
    run(p.form("c"))
    with pytest.raises(MatchingError) as err:
        run(p.computeSky("c", 3))
    assert err.value.code == "INVALID_INPUT"
