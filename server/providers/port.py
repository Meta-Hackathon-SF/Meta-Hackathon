"""MusePort: the provider-independent service port from contracts/protocol.ts 2.0.0.

    run({task, requestId, promptVersion, payload, signal?})
        -> {output, evidence: MuseCallEvidence}

Python form: ``await port.run(MuseRequest(...)) -> MuseResult``. asyncio
cancellation plays the role of the TypeScript AbortSignal. ``KeywordMusePort``
offers the camelCase keyword form for owners who prefer the wire spelling.

Every task is registered as a TaskSpec by the system that owns its prompt:
Patrik safety_screen (M1); Adam clarify (M2), question_generation (M6),
event_nudge (M7); Rishi theme_discovery (M3), constellation_formation (M4),
constellation_naming (M5), sky_narration (M8). The adapter only executes
registered (task, promptVersion) pairs, so neither player text nor model output
can choose instructions, tools or URLs.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, TypedDict, get_args

from .schema import check_schema_supported

# MuseTask in contracts/protocol.ts (2.2.0). Order is M1..M10.
Task = Literal[
    "safety_screen", "clarify", "theme_discovery", "constellation_formation",
    "constellation_naming", "question_generation", "event_nudge", "sky_narration",
    "activity_classification", "sensitivity_screen",
]
TASKS: frozenset[str] = frozenset(get_args(Task))

CallType = Literal["M1", "M2", "M3", "M4", "M5", "M6", "M7", "M8", "M9", "M10"]
CALL_TYPES: dict[str, CallType] = {
    task: f"M{i}" for i, task in enumerate(get_args(Task), start=1)  # type: ignore[misc]
}


class MuseCallEvidence(TypedDict):
    """MuseCallEvidence in contracts/protocol.ts (ModelEvidence + callType)."""

    model: str
    source: Literal["live", "replay"]
    generatedAt: str
    latencyMs: int
    callType: CallType


@dataclass(frozen=True)
class TaskSpec:
    """Static instructions + I/O schemas for one (task, promptVersion)."""

    task: Task
    prompt_version: str
    instructions: str
    output_schema: dict[str, Any]
    schema_name: str
    # When set, the payload is validated before any provider call, so a prompt
    # can never carry fields outside the contract (names, emails, session ids).
    input_schema: dict[str, Any] | None = None
    max_output_tokens: int = 8000
    temperature: float | None = 0.4

    def __post_init__(self) -> None:
        if self.task not in TASKS:
            raise ValueError(f"unknown task {self.task!r}")
        if not self.prompt_version or len(self.prompt_version) > 40:
            raise ValueError("prompt_version must be 1..40 chars")
        if not self.schema_name.replace("_", "").isalnum():
            raise ValueError("schema_name must be alphanumeric/underscore")
        check_schema_supported(self.output_schema)
        if self.input_schema is not None:
            check_schema_supported(self.input_schema)


@dataclass(frozen=True)
class MuseRequest:
    task: Task
    request_id: str
    prompt_version: str
    payload: Any
    # Overall deadline across retries; defaults to the adapter's configuration.
    deadline_s: float | None = None
    # Validator feedback from a previous semantic rejection (caller's re-ask).
    # Code-generated strings only; never raw player text.
    correction: str | None = None


@dataclass(frozen=True)
class MuseResult:
    output: Any
    evidence: MuseCallEvidence
    attempts: int = 1


class MusePort(Protocol):
    async def run(self, request: MuseRequest) -> MuseResult: ...


@dataclass
class TaskRegistry:
    """Allowlist of executable task specs, keyed by (task, promptVersion)."""

    _specs: dict[tuple[str, str], TaskSpec] = field(default_factory=dict)

    def register(self, spec: TaskSpec) -> TaskSpec:
        key = (spec.task, spec.prompt_version)
        existing = self._specs.get(key)
        if existing is not None and existing != spec:
            raise ValueError(f"conflicting spec for {key}")
        self._specs[key] = spec
        return spec

    def get(self, task: str, prompt_version: str) -> TaskSpec | None:
        return self._specs.get((task, prompt_version))

    def keys(self) -> list[tuple[str, str]]:
        return sorted(self._specs)


class KeywordMusePort:
    """camelCase keyword form of MusePort.run, mirroring contracts/protocol.ts:

        await port.run(task=..., requestId=..., promptVersion=..., payload=..., signal=None,
                       correction=None)
            -> {"output": {...}, "evidence": MuseCallEvidence}

    ``signal`` is accepted for protocol parity and ignored: cancel the awaiting
    asyncio task instead, which propagates into the HTTP attempt.
    ``deadline_s`` is the caller's overall cap for this call (the router never
    starts a fallback past it); it defaults to the port's.
    ``correction`` is the caller's re-ask feedback after its own validator
    rejected the previous answer (e.g. "2 unknown member ids; group 3 has 6
    members"). It must be code-generated: never player or model text. The
    adapter bounds its length.
    """

    def __init__(self, muse: MusePort, *, deadline_s: float | None = None) -> None:
        self._muse = muse
        self._deadline_s = deadline_s

    async def run(self, *, task: str, requestId: str, promptVersion: str,
                  payload: Any, signal: Any = None, correction: str | None = None,
                  deadline_s: float | None = None) -> dict[str, Any]:
        if correction is not None and not isinstance(correction, str):
            raise TypeError("correction must be a string")
        result = await self._muse.run(MuseRequest(
            task=task,  # type: ignore[arg-type]  # unknown tasks fail closed in the adapter
            request_id=requestId,
            prompt_version=promptVersion,
            payload=payload,
            # A caller's own cap (e.g. naming's 20 s) lets the router budget its fallback.
            deadline_s=deadline_s if deadline_s is not None else self._deadline_s,
            correction=correction or None,
        ))
        return {"output": result.output, "evidence": dict(result.evidence)}
