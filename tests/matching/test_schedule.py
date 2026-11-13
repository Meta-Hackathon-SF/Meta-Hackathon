"""Replays Adam's live latencies (2026-11-13, 30 players) at 1/100 scale to check the
schedule: M3 || M4, then M5 (capped) || M8. Simulated timing, not a live measurement."""
from __future__ import annotations

import asyncio
import time

from server.matching.formation import NAME_TIMEOUT_S, FormationService
from server.matching.live_eval import synthetic_snapshot
from server.matching.port import MatchingPort
from server.matching.sky import SkyService
from tests.matching.adapters import FixtureGuard, evidence

SCALE = 0.01
LIVE_S = {"theme_discovery": 21.5, "constellation_formation": 38.8, "sky_narration": 18.8}
M5_S = [12.7, 14.0, 15.5, 17.2, 20.9, 999.0, 999.0]  # two hung calls in the live run


class LatencyMuse:
    label = "TEST-ONLY adapter (simulated latency)"

    def __init__(self):
        self.m5 = list(M5_S)

    async def run(self, *, task, requestId, promptVersion, payload, signal=None):
        if task == "constellation_naming":
            delay = self.m5.pop(0) if self.m5 else 15.0
            await asyncio.sleep(delay * SCALE)
            shape = {3: "triangle", 4: "kite", 5: "pentagon"}[payload["size"]]
            return {"output": {"name": "Quiet Lanterns", "shapeId": shape, "colorId": "dusk"},
                    "evidence": evidence("M5")}
        await asyncio.sleep(LIVE_S[task] * SCALE)
        if task == "theme_discovery":
            refs = sorted({a["id"] for a in payload["answers"]})
            return {"output": {"themes": [{"id": "t0", "label": "Quiet weeks",
                                           "description": "d", "memberIds": refs[:6]}]},
                    "evidence": evidence("M3")}
        if task == "constellation_formation":
            refs = sorted({a["id"] for a in payload["answers"]}, key=lambda r: int(r[1:]))
            sizes = [5, 5, 5, 5, 4, 3, 3]
            groups, i = [], 0
            for n in sizes:
                groups.append(refs[i:i + n])
                i += n
            return {"output": {"constellations": [
                {"memberIds": g, "sharedMeaning": "s", "confidence": 0.7} for g in groups]},
                "evidence": evidence("M4")}
        return {"output": {"headlines": ["30 people shared their week."]},
                "evidence": evidence("M8")}


class Snap:
    async def formation_snapshot(self, cycle_id):
        snap = synthetic_snapshot(30)
        return {**snap, "blockedPairs": []}


class Guesses:
    async def prevalence_guesses(self, cycle_id):
        return {f"syn-{i}": 20 for i in range(1, 31)}


def test_live_latency_replay_fits_sixty_seconds():
    muse = LatencyMuse()
    formation = FormationService(muse, Snap(), FixtureGuard(), timeout_s=75 * SCALE,
                                 name_timeout_s=NAME_TIMEOUT_S * SCALE)
    port = MatchingPort(formation, SkyService(muse, FixtureGuard(), timeout_s=75 * SCALE),
                        Guesses())
    started = time.monotonic()
    raw = asyncio.run(port.form("c"))
    elapsed = (time.monotonic() - started) / SCALE
    assert raw["status"] == "ok" and len(raw["constellations"]) == 7
    print(f"simulated formation {elapsed:.1f} s")
    assert elapsed < 60, f"simulated {elapsed:.1f} s"
    sky = asyncio.run(port.computeSky("c", 3))  # precomputed during naming
    assert sky["headlines"] == ["30 people shared their week."]
    hung = [c for c in raw["constellations"] if c["name"] != "Quiet Lanterns"]
    assert len(hung) == 3  # 2 hung + the 20.9 s call exceed the 20 s cap: fixed names


def test_sequential_schedule_is_slower():
    muse = LatencyMuse()
    formation = FormationService(muse, Snap(), FixtureGuard(), timeout_s=75 * SCALE,
                                 name_timeout_s=NAME_TIMEOUT_S * SCALE, parallel_themes=False)
    started = time.monotonic()
    asyncio.run(formation.form("c"))
    assert (time.monotonic() - started) / SCALE > 60
