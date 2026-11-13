"""TEST-ONLY adapters for ports owned by other people. Never import from server code.

These stand in until the real implementations land:
  - TestOnlyOutputGuard  -> Patrik's OutputGuard.check (server/privacy)
  - TestOnlyWeekStart    -> Will's cycle data (server/cycle), read from the shared fixture
  - TestOnlyChat         -> Kai's ChatPort.postSystem (server/chat)
They match the shapes in contracts/protocol.ts 2.0.0 and are deliberately crude.
Passing tests against them is fixture evidence, not integration evidence.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

FIXTURES = Path(__file__).resolve().parents[2] / "contracts" / "fixtures"

_SENSITIVE = re.compile(
    r"\b(diagnos\w*|therap\w*|depress\w*|anxiety|medication|gay|lesbian|church|mosque|pray\w*|"
    r"rent|debt|salary|divorce\w*|abus\w*|dorm room|apartment)\b", re.IGNORECASE)
_CONTACT = re.compile(r"(\S+@\S+\.\S+)|(\+?\d[\d\s().-]{6,}\d)|(https?://|www\.)", re.IGNORECASE)


class TestOnlyOutputGuard:
    """Crude stand-in for Patrik's OutputGuard. TEST ONLY."""

    __test__ = False  # not a pytest class

    def __init__(self) -> None:
        self.calls: list[tuple[str, list[str]]] = []

    def check(self, text: str, against_answers: list[str]) -> dict[str, Any]:
        self.calls.append((text, list(against_answers)))
        reasons: list[str] = []
        words = re.findall(r"[a-z0-9']+", text.lower())
        for answer in against_answers:
            answer_words = " ".join(re.findall(r"[a-z0-9']+", answer.lower()))
            if any(" ".join(words[i:i + 5]) in answer_words for i in range(len(words) - 4)):
                reasons.append("quote_5_words")
                break
        if _SENSITIVE.search(text):
            reasons.append("sensitive_term")
        if _CONTACT.search(text):
            reasons.append("contact_info")
        return {"ok": not reasons, "reasons": reasons}


class TestOnlyWeekStart:
    """Stand-in for Will's cycle lookup. TEST ONLY."""

    __test__ = False

    def __init__(self, starts: dict[str, str] | None = None) -> None:
        cycle = json.loads((FIXTURES / "week-sample.json").read_text())["cycle"]
        self.starts = {cycle["cycleId"]: cycle["weekStart"], **(starts or {})}

    async def __call__(self, cycle_id: str) -> str:
        return self.starts[cycle_id]


class TestOnlyChat:
    """Stand-in for Kai's ChatPort.postSystem. TEST ONLY."""

    __test__ = False

    def __init__(self) -> None:
        self.posted: list[tuple[str, dict[str, Any]]] = []

    async def post_system(self, room_id: str, message: dict[str, Any]) -> dict[str, Any]:
        self.posted.append((room_id, dict(message)))
        return {**message, "messageId": f"m-test-{len(self.posted)}",
                "createdAt": "2026-11-18T15:00:00Z", "moderation": "visible"}
