"""Reasoning trace: what Muse proposed and what server code did with it.

One entry per Muse call, keyed by requestId:

    {requestId, task, callType, promptVersion, model, source, outcome, attempts,
     latencyMs, at, checks: [{stage, code, count}]}

The adapter records the call itself (outcome ``ok`` / ``malformed_output`` /
``timeout`` ...). Services that consume the output then ``note`` their code
verdicts: ``note(rid, "guard", "rejected")``, ``note(rid, "fallback",
"curated_hint")``, ``note(rid, "kept", "questions", 3)``. This is the operator
and demo view of "Muse proposes, code enforces".

Privacy by construction: stage and code must match ``[a-z][a-z0-9_]{0,39}``
and count is a small integer, so a note can never carry an answer, a name, a
prompt or model text. Anything else is dropped, not stored. Entries hold no
payloads and no outputs. Bounded and in memory; ``source`` is "replay" for
fixture adapters, so a simulated run can never be shown as live.
"""
from __future__ import annotations

import re
import threading
from collections import OrderedDict
from datetime import datetime, timezone
from typing import Any

_CODE = re.compile(r"^[a-z][a-z0-9_]{0,39}$")
_RID = re.compile(r"^[A-Za-z0-9_.:-]{1,120}$")
MAX_CHECKS_PER_CALL = 40
MAX_COUNT = 100_000
CALL_FIELDS = ("task", "callType", "promptVersion", "model", "source", "outcome", "attempts", "latencyMs")


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


class ReasoningTrace:
    def __init__(self, maxlen: int = 300) -> None:
        self._maxlen = maxlen
        self._entries: OrderedDict[str, dict[str, Any]] = OrderedDict()
        self._lock = threading.Lock()

    def _entry(self, request_id: str) -> dict[str, Any] | None:
        if not isinstance(request_id, str) or not _RID.match(request_id):
            return None
        entry = self._entries.get(request_id)
        if entry is None:
            entry = {"requestId": request_id, "at": _now(), "checks": []}
            self._entries[request_id] = entry
            while len(self._entries) > self._maxlen:
                self._entries.popitem(last=False)
        return entry

    def record_call(self, record: dict[str, Any]) -> None:
        """Adapter hook: copy the sanitized call fields (no payload, no output)."""
        with self._lock:
            entry = self._entry(record.get("requestId", ""))
            if entry is None:
                return
            for key in CALL_FIELDS:
                value = record.get(key)
                if value is None or isinstance(value, (str, int, float, bool)):
                    entry[key] = value

    def note(self, request_id: str, stage: str, code: str, count: int = 1) -> bool:
        """A code verdict on a call's output. Returns False (and stores nothing) if invalid."""
        if not (isinstance(stage, str) and _CODE.match(stage) and isinstance(code, str) and _CODE.match(code)):
            return False
        if isinstance(count, bool) or not isinstance(count, int) or not (0 <= count <= MAX_COUNT):
            return False
        with self._lock:
            entry = self._entry(request_id)
            if entry is None or len(entry["checks"]) >= MAX_CHECKS_PER_CALL:
                return False
            entry["checks"].append({"stage": stage, "code": code, "count": count})
            return True

    def list(self, *, task: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        """Newest first."""
        with self._lock:
            rows = [
                {**e, "checks": [dict(c) for c in e["checks"]]}
                for e in reversed(self._entries.values())
                if task is None or e.get("task") == task
            ]
        return rows[: max(0, min(limit, self._maxlen))]


class NullTrace:
    """Default when a service is built without a trace."""

    def note(self, request_id: str, stage: str, code: str, count: int = 1) -> bool:
        return False
