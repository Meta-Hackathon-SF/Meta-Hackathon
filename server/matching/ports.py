"""Ports Rishi's formation consumes. Python mirrors of contracts/protocol.ts 2.0.0.

Producers: MusePort (Adam), PrivacyPort.formationSnapshot and OutputGuard (Patrik).
Formation depends only on these protocols, never on other owners' internals.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Protocol


class MusePortLike(Protocol):
    async def run(self, *, task: str, requestId: str, promptVersion: str,
                  payload: Any, signal: Any | None = None,
                  correction: str | None = None) -> Mapping[str, Any]:
        """Returns {"output": <task output>, "evidence": MuseCallEvidence wire dict}.

        `correction` (optional) is code-generated re-ask feedback; formation only passes it
        when the port's run() accepts it."""
        ...


class SnapshotSource(Protocol):
    async def formation_snapshot(self, cycle_id: str) -> Mapping[str, Any]:
        """PrivacyPort.formationSnapshot wire dict: {answers, idMap, blockedPairs}."""
        ...


class OutputGuardLike(Protocol):
    def check(self, text: str, against_answers: Sequence[str]) -> Mapping[str, Any]:
        """{"ok": bool, "reasons": [...]} per OutputGuard in protocol.ts."""
        ...
