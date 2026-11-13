"""TEST ONLY synthetic formation/store adapters. Never imported by server code."""

import asyncio
import json
from copy import deepcopy
from pathlib import Path

from server.app.errors import ServiceError
from server.orchestration.wire import WeeklyCycle

FIXTURES = Path(__file__).parents[2] / "contracts" / "fixtures"


def cycle_wire():
    value = json.loads((FIXTURES / "week-sample.json").read_text())["cycle"]
    return {**value, "status": "locked"}


def formation_wire():
    return {
        "status": "ok",
        "constellations": [
            {
                "constellationId": "synthetic-c1",
                "cycleId": "cycle-demo-w1",
                "memberIds": ["synthetic-p1", "synthetic-p2", "synthetic-p3"],
                "sharedMeaning": "Synthetic shared meaning",
                "confidence": 0.7,
                "isLooseMatch": False,
                "name": "Synthetic stars",
                "shapeId": "arc-3",
                "colorId": "blue",
                "baselineAgrees": True,
            }
        ],
        "evidence": [],
    }


class TestFormation:
    __test__ = False

    def __init__(self, result=None, pause=None):
        self.result = formation_wire() if result is None else result
        self.pause = pause
        self.calls = 0

    async def form(self, cycleId):
        self.calls += 1
        if self.pause:
            await self.pause.wait()
        if isinstance(self.result, Exception):
            raise self.result
        return deepcopy(self.result)


class TestFormationStore:
    __test__ = False

    def __init__(self):
        self.lock = asyncio.Lock()
        self.claimed = asyncio.Event()
        self.revision = 1
        self.job = None
        self.committed = None
        self.failures = []
        self.cycle_value = cycle_wire()

    async def claim(self, cycle_id):
        async with self.lock:
            if self.job is not None or self.committed is not None:
                return None
            self.job = {
                "cycleId": cycle_id,
                "revision": self.revision,
                "eligibleIds": ["synthetic-p1", "synthetic-p2", "synthetic-p3"],
                "blockedPairs": [],
            }
            self.claimed.set()
            return deepcopy(self.job)

    async def cycle(self, cycle_id):
        return WeeklyCycle.model_validate(self.cycle_value)

    async def commit(self, job, result):
        async with self.lock:
            if job["revision"] != self.revision or job != self.job:
                raise ServiceError("STALE_REVISION")
            self.committed = result.model_dump()

    async def fail(self, job, code):
        self.failures.append(code)
