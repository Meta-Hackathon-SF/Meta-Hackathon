"""MusePort: the provider-independent service port from contracts/protocol.ts.

    generate({task, requestId, promptVersion, payload, signal?})
        -> {output, evidence: ModelEvidence}

Python form: ``await port.generate(GenerateRequest(...)) -> GenerateResult``.
asyncio cancellation plays the role of the TypeScript AbortSignal.

Every task is registered as a TaskSpec owned by the calling system: planning
owns extract_intent/extract_preferences/plan/revise/continue/create_event/
negotiate/venue_persona/challenge; matching (Rishi) owns rank_group.
The adapter only executes registered (task, promptVersion) pairs, so neither
user text nor model output can choose instructions, tools or URLs.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, TypedDict, get_args

from .schema import check_schema_supported

Task = Literal[
    "extract_intent", "rank_group", "plan", "revise", "continue",
    # PROPOSED (D008, target 1.1.0); additive to the MusePort task enum.
    "extract_preferences", "create_event", "negotiate", "venue_persona", "challenge",
]
TASKS: frozenset[str] = frozenset(get_args(Task))


class ModelEvidence(TypedDict):
    model: str
    source: Literal["live", "replay"]
    generatedAt: str
    latencyMs: int


@dataclass(frozen=True)
class TaskSpec:
    """Static instructions + output schema for one (task, promptVersion)."""

    task: Task
    prompt_version: str
    instructions: str
    output_schema: dict[str, Any]
    schema_name: str
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


@dataclass(frozen=True)
class GenerateRequest:
    task: Task
    request_id: str
    prompt_version: str
    payload: Any
    # Overall deadline across retries; defaults to the adapter's configuration.
    deadline_s: float | None = None
    # Validator feedback from a previous semantic rejection (planning retry).
    # Code-generated strings only; never raw user text.
    correction: str | None = None


@dataclass(frozen=True)
class GenerateResult:
    output: Any
    evidence: ModelEvidence
    attempts: int = 1


class MusePort(Protocol):
    async def generate(self, request: GenerateRequest) -> GenerateResult: ...


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
