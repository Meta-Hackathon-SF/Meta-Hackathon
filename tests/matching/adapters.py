"""TEST-ONLY adapters. Not production code; never import from server/.

- FixtureSnapshotSource stands in for Patrik's PrivacyPort.formationSnapshot over
  contracts/fixtures/week-sample.json (all synthetic players).
- FakeMuse stands in for Adam's MusePort. Its groupings are scripted, so passing tests
  prove pipeline mechanics and guards, NOT Muse grouping quality.
- FixtureGuard is a minimal stand-in for Patrik's OutputGuard (5-word quote + a few terms).
"""
from __future__ import annotations

import json
import random
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from server.matching.models import shapes_for

FIXTURE = Path(__file__).resolve().parents[2] / "contracts" / "fixtures" / "week-sample.json"
LABEL = "TEST-ONLY adapter"


EXTRA_PLAYERS = {  # D016: a constellation needs 5+, so the matching tests get 3 more players
    "p-x1": ["Cooking for one feels pointless so I skip it", "I scroll my phone through every meal"],
    "p-x2": ["Lunch alone in the library is easier than the dining hall"],
    "p-x3": ["I wait until the dining room empties so nobody sees me alone"],
}


def load_week() -> dict:
    """The shared week fixture plus matching-only extras (other suites read the JSON directly)."""
    week = json.loads(FIXTURE.read_text())
    extra = [{"playerId": p, "day": 1 + i, "text": t, "isCatchUp": False}
             for p, texts in EXTRA_PLAYERS.items() for i, t in enumerate(texts)]
    return {**week, "answers": week["answers"] + extra}


class FixtureSnapshotSource:
    label = LABEL

    def __init__(self, week: dict | None = None, seed: int = 7,
                 include_injection: bool = True) -> None:
        self.week = week or load_week()
        self.seed = seed
        self.include_injection = include_injection
        self.ref_of: dict[str, str] = {}

    def snapshot(self) -> dict:
        week = self.week
        flagged = {week["distressFixture"]["playerId"]} if "distressFixture" in week else set()
        rows = [a for a in week["answers"] if a["playerId"] not in flagged]
        inj = week.get("injectionFixture")
        if self.include_injection and inj and inj["playerId"] not in flagged:
            rows = rows + [{"playerId": inj["playerId"], "day": inj["day"], "text": inj["text"],
                            "isCatchUp": False}]
        players = sorted({r["playerId"] for r in rows})
        shuffled = players[:]
        random.Random(self.seed).shuffle(shuffled)
        self.ref_of = {p: f"r{i + 1}" for i, p in enumerate(shuffled)}
        answers = [{"id": self.ref_of[r["playerId"]], "text": r["text"],
                    "weight": 0.6 if r["isCatchUp"] else 1.0} for r in rows]
        blocked = [[b["blockerId"], b["blockedId"]] for b in week.get("blocks", [])]
        return {"answers": answers, "idMap": {v: k for k, v in self.ref_of.items()},
                "blockedPairs": blocked}

    async def formation_snapshot(self, cycle_id: str) -> Mapping[str, Any]:
        return self.snapshot()


def evidence(call_type: str) -> dict:
    return {"callType": call_type, "model": "fake-muse", "source": "replay",
            "generatedAt": "2026-11-14T20:00:00Z", "latencyMs": 1}


class FakeMuse:
    """Scripted Muse. `groups` are lists of playerIds; mapped to refs via `ref_of`."""
    label = LABEL

    def __init__(self, ref_of: Mapping[str, str], groups: Sequence[Sequence[str]],
                 *, m4_script: Sequence[str] = ("good",), m3_mode: str = "good",
                 m5_name: str = "Quiet Lanterns",
                 blocked_groups: Sequence[Sequence[str]] = (),
                 meaning: str = "fake meaning") -> None:
        self.meaning = meaning
        self.ref_of = ref_of
        self.groups = [[ref_of[p] for p in g] for g in groups]
        self.m4_script = list(m4_script)
        self.m3_mode = m3_mode
        self.m5_name = m5_name
        self.blocked_groups = [[ref_of[p] for p in g] for g in blocked_groups]
        self.calls: list[dict] = []

    async def run(self, *, task: str, requestId: str, promptVersion: str, payload: Any,
                  signal: Any = None, correction: str | None = None) -> Mapping[str, Any]:
        self.calls.append({"task": task, "payload": payload, "correction": correction,
                           "promptVersion": promptVersion})
        if task == "theme_discovery":
            if self.m3_mode == "raise":
                raise RuntimeError("provider down")
            if self.m3_mode == "quote":  # first label quotes 5+ words of a fixture answer
                return {"output": {"themes": [
                    {"id": f"t{i}", "label": "eat in my room so no one" if i == 0 else f"Shared week {i}",
                     "description": "fake", "memberIds": g} for i, g in enumerate(self.groups)]},
                    "evidence": evidence("M3")}
            return {"output": {"themes": [
                {"id": f"t{i}", "label": f"Shared week {i}", "description": "fake",
                 "memberIds": g} for i, g in enumerate(self.groups)]},
                "evidence": evidence("M3")}
        if task == "constellation_formation":
            mode = self.m4_script.pop(0) if len(self.m4_script) > 1 else self.m4_script[0]
            if mode == "raise":
                raise RuntimeError("provider down")
            if mode == "invalid_json":
                return {"output": "{not json", "evidence": evidence("M4")}
            if mode == "garbage":  # too few refs kept to repair -> re-solve
                return {"output": {"constellations": [
                    {"memberIds": self.groups[0][:2], "sharedMeaning": "fake meaning",
                     "confidence": 0.8}]}, "evidence": evidence("M4")}
            groups = self.groups
            if mode == "blocked":
                groups = self.blocked_groups
            return {"output": {"constellations": [
                {"memberIds": g, "sharedMeaning": self.meaning, "confidence": 0.8}
                for g in groups]}, "evidence": evidence("M4")}
        if task == "constellation_naming":
            shape = shapes_for(payload["size"])[0]
            return {"output": {"name": self.m5_name, "shapeId": shape,
                               "colorId": "dusk"}, "evidence": evidence("M5")}
        raise ValueError(f"unexpected task {task}")


_WORD_RE = re.compile(r"[a-z0-9']+")
_SENSITIVE = ("depress", "suicid", "religio", "sexual", "debt", "diagnos")


class FixtureGuard:
    label = LABEL

    def check(self, text: str, against_answers: Sequence[str]) -> Mapping[str, Any]:
        reasons = []
        words = _WORD_RE.findall(text.lower())
        grams = {tuple(words[i:i + 5]) for i in range(len(words) - 4)}
        for answer in against_answers:
            aw = _WORD_RE.findall(answer.lower())
            if grams & {tuple(aw[i:i + 5]) for i in range(len(aw) - 4)}:
                reasons.append("quote_5_words")
                break
        if any(term in text.lower() for term in _SENSITIVE):
            reasons.append("sensitive_term")
        return {"ok": not reasons, "reasons": reasons}
