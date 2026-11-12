"""Fixture/test doubles for MusePort. NEVER wire these into a live path.

``FixtureMuse`` runs the real MuseAdapter pipeline (task allowlist, payload
encoding, schema validation, retries) over a scripted in-process transport, so
consumers (Rishi's rank_group, Kai's workflow tests) exercise the same
validation as production. Evidence is labeled ``source: "replay"`` with a
``fixture:`` model prefix because the output is scripted, not live Muse. (A
first-class "fixture" source is proposed in docs/DECISIONS.md D005.)

Handlers receive the decoded payload dict and return either a JSON-compatible
object (serialized for the adapter to parse), a raw string (to simulate
malformed text), or raise ProviderError to simulate provider failures.
"""
from __future__ import annotations

import asyncio
import json
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable, Deque

from .config import MuseConfig
from .errors import ProviderError
from .muse import MuseAdapter
from .port import TaskRegistry
from .transport import ChatRequest, ChatResponse

FIXTURE_MODEL = "fixture:scripted-muse"

Handler = Callable[[dict[str, Any]], Any]
Step = Any  # Handler | ProviderError | str | dict


def decode_user_message(user: str) -> dict[str, Any]:
    _, _, data = user.partition("\n")
    return json.loads(data)


@dataclass
class ScriptedTransport:
    """In-process ChatTransport. Queue steps per task, or set a default handler."""

    steps: dict[str, Deque[Step]] = field(default_factory=dict)
    handlers: dict[str, Handler] = field(default_factory=dict)
    delay_s: float = 0.0
    calls: list[ChatRequest] = field(default_factory=list)

    def queue(self, task: str, *steps: Step) -> "ScriptedTransport":
        self.steps.setdefault(task, deque()).extend(steps)
        return self

    def on(self, task: str, handler: Handler) -> "ScriptedTransport":
        self.handlers[task] = handler
        return self

    async def complete(self, request: ChatRequest) -> ChatResponse:
        self.calls.append(request)
        if self.delay_s:
            await asyncio.sleep(self.delay_s)
        message = decode_user_message(request.user)
        task = message["task"]
        queued = self.steps.get(task)
        step: Step
        if queued:
            step = queued.popleft()
        elif task in self.handlers:
            step = self.handlers[task]
        else:
            raise ProviderError("unavailable", f"fixture has no response for task {task}")
        if callable(step) and not isinstance(step, ProviderError):
            step = step(message["input"])
        if isinstance(step, ProviderError):
            raise step
        text = step if isinstance(step, str) else json.dumps(step)
        return ChatResponse(text=text, model=FIXTURE_MODEL)


_FIXTURE_CONFIG = MuseConfig(api_key="fixture-not-a-key", model="muse-spark-1.3", timeout_s=5.0, max_attempts=2)


class FixtureMuse(MuseAdapter):
    """MusePort double whose evidence is never labeled live."""

    _evidence_source = "replay"

    def __init__(self, registry: TaskRegistry, transport: ScriptedTransport | None = None, **kwargs: Any) -> None:
        self.transport = transport or ScriptedTransport()
        kwargs.setdefault("sleep", _no_sleep)
        kwargs.setdefault("telemetry", lambda _r: None)
        super().__init__(registry, config=kwargs.pop("config", _FIXTURE_CONFIG), transport=self.transport, **kwargs)

    def _evidence_model(self, reported: str | None) -> str:
        return FIXTURE_MODEL


async def _no_sleep(_s: float) -> None:
    return None
