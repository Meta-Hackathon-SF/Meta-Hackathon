"""Task -> model router across the Muse text models (one MusePort, several models).

    port = build_muse_router(registry, base_config, routes=DEFAULT_ROUTES)
    await port.run(MuseRequest(task="clarify", ...))   # served by the route's model

Each task has a ``Route``: primary model, reasoning effort, per-attempt timeout
and an ordered fallback list. The router owns one ``MuseAdapter`` per model
(same key, same registry, so the same allowlisted prompts and schema checks),
and all of them share one ``EvidenceLog`` and one ``ReasoningTrace``, so the
operator views show every call with the model that actually served it.

Fallback happens only for failures a different model could fix: rate limits,
outages, timeouts and malformed output. Auth, invalid requests, unknown tasks
and cancellation never fall back. When the caller set ``deadline_s`` the
fallback only gets the time that is left, so routing can never extend a
caller's budget (e.g. naming's 20 s cap). Without a route a task uses the base
config's model, which is today's single-model behaviour.

Routes are code, chosen from measured evals (docs/audits), and can be
overridden with ``MUSE_ROUTES`` (see ``parse_routes``). Contributor-mode models
are rejected by ``MuseConfig``.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, replace
from typing import Any, Callable, Mapping

from .config import KNOWN_MODELS, MODEL_EFFORTS, MuseConfig
from .errors import ProviderError
from .muse import EvidenceLog, MuseAdapter
from .port import TASKS, MuseRequest, MuseResult, TaskRegistry
from .trace import ReasoningTrace

FALLBACK_KINDS = frozenset({"rate_limited", "unavailable", "timeout", "malformed_output"})
MIN_FALLBACK_S = 2.0  # do not start a fallback with less time than this


@dataclass(frozen=True)
class Route:
    model: str
    effort: str | None = "low"
    timeout_s: float | None = None          # per attempt; None keeps the base config's
    fallbacks: tuple[str, ...] = ()
    max_attempts: int | None = None         # None keeps the base config's

    def __post_init__(self) -> None:
        for m in (self.model, *self.fallbacks):
            if m not in KNOWN_MODELS:
                raise ValueError(f"unknown model {m!r} in route")
        if self.effort is not None and self.effort not in MODEL_EFFORTS[self.model]:
            raise ValueError(f"effort {self.effort!r} not allowed for {self.model}")
        if len(set((self.model, *self.fallbacks))) != 1 + len(self.fallbacks):
            raise ValueError("route repeats a model")
        if self.timeout_s is not None and not (1.0 <= self.timeout_s <= 120.0):
            raise ValueError("route timeout_s must be within [1, 120]")
        if self.max_attempts is not None and not (1 <= self.max_attempts <= 3):
            raise ValueError("route max_attempts must be within [1, 3]")


SPARK, WONDER, EMBER = "muse-spark-1.3", "muse-wonder-1.0", "muse-ember-1.0"

# Measured 2026-11-13 on synthetic inputs through the real services, prompts and
# OutputGuard (74 live calls, 2-10 per cell; docs/audits/2026-11-13-live-evals.md).
#  - clarify (M2, interactive, high volume): Ember minimal 10/10 valid, p50 0.9 s,
#    $0.0001; Spark low p50 7.3 s. Ember low stalled ~68 s on 3 of 10, hence one
#    short attempt; the service already falls back to the curated hint.
#  - naming (M5) and Sky narration (M8): Wonder rated clearly best (Spark failed
#    M8 number/guard checks on 3 of 6 runs: never Spark for M8). Both run between
#    the Saturday lock and the Sunday reveal; the caller's own deadline still caps
#    them, so short per-attempt timeouts leave room for the Ember fallback.
#  - question_generation (M6) and event_nudge (M7): Spark good, Wonder not
#    clearly better, Ember weaker on nudge fit.
#  - safety_screen (M1, hot path for every answer and chat message): production
#    prompt safety.v1, Ember low exact on 56 calls (26 base, 10 hard x3), p50
#    1.2 s, $0.0002; Spark low missed one indirect distress case. One 8 s attempt
#    covers Ember's rare stalls; the Spark fallback keeps the screen available.
#    If both fail, M1 still fails closed in the privacy service.
#  - activity_classification (M9) and sensitivity_screen (M10): Ember low was
#    F1 0.98 with 34/34 sensitive texts flagged (M9) and 113/114 recall with 1/70
#    false positives (M10, Spark 114/114 but one 72.8 s call). Callers run after
#    OutputGuard, which stays as the code backstop; Spark is the fallback.
#  - constellation_formation (M4) with D014 questions: Ember low gold-set P/R
#    1.0, 1.0, 0.89/0.77, 0.87/0.87 and question-dependent set 1.0 x2 (v2 prompt,
#    sequential), M4 2-17 s; Spark's first M4 attempt timed out at 75 s in 3 of 4
#    runs in the same session. Ember v1 (no questions) was 0.98/0.89. One attempt
#    per call: FormationService does its own re-solve with a correction.
# theme_discovery (M3) stays on the base model (not compared head to head).
MEASURED_ROUTES: dict[str, Route] = {
    "safety_screen": Route(EMBER, "low", 8.0, (SPARK,), max_attempts=1),
    "constellation_formation": Route(EMBER, "low", 30.0, (SPARK,), max_attempts=1),
    "activity_classification": Route(EMBER, "low", 20.0, (SPARK,)),
    "sensitivity_screen": Route(EMBER, "low", 15.0, (SPARK,), max_attempts=1),
    "clarify": Route(EMBER, "minimal", 6.0, (SPARK,), max_attempts=1),
    "question_generation": Route(SPARK, "low", 45.0, (EMBER,)),
    "event_nudge": Route(SPARK, "low", 45.0, (EMBER,)),
    "constellation_naming": Route(WONDER, "low", 12.0, (EMBER,), max_attempts=1),
    "sky_narration": Route(WONDER, "low", 30.0, (EMBER,), max_attempts=1),
}

DEFAULT_ROUTES: dict[str, Route] = MEASURED_ROUTES


def parse_routes(spec: str) -> dict[str, Route]:
    """``"clarify=muse-ember-1.0:low:20>muse-spark-1.3;event_nudge=muse-spark-1.3:low"``.

    Per task: model[:effort[:timeout_s]] then optional ``>fallback>fallback``.
    """
    routes: dict[str, Route] = {}
    for part in filter(None, (p.strip() for p in spec.split(";"))):
        task, sep, rest = part.partition("=")
        if not sep or task.strip() not in TASKS:
            raise ValueError(f"bad route {part!r}")
        primary, *fallbacks = [x.strip() for x in rest.split(">")]
        model, effort, timeout = (primary.split(":") + [None, None])[:3]
        routes[task.strip()] = Route(model=model, effort=effort or None,
                                     timeout_s=float(timeout) if timeout else None,
                                     fallbacks=tuple(fallbacks))
    return routes


class MuseRouter:
    """MusePort that picks the model per task. Exposes ``evidence_log``,
    ``reasoning_trace`` and ``configured`` like ``MuseAdapter``."""

    def __init__(self, registry: TaskRegistry, base: MuseConfig | None, routes: Mapping[str, Route] | None = None, *,
                 adapter_factory: Callable[..., MuseAdapter] | None = None,
                 clock: Callable[[], float] = time.monotonic, **adapter_kwargs: Any) -> None:
        self._registry = registry
        self._base = base
        self._routes = dict(routes or {})
        for task in self._routes:
            if task not in TASKS:
                raise ValueError(f"unknown task {task!r} in routes")
        self._clock = clock
        self.evidence_log = adapter_kwargs.pop("evidence_log", None) or EvidenceLog()
        self.reasoning_trace = adapter_kwargs.pop("reasoning_trace", None) or ReasoningTrace()
        self._factory = adapter_factory or MuseAdapter
        self._adapter_kwargs = adapter_kwargs
        self._adapters: dict[tuple[str, str | None, float | None, int | None], MuseAdapter] = {}

    @property
    def configured(self) -> bool:
        return self._base is not None

    def route_for(self, task: str) -> Route | None:
        return self._routes.get(task)

    def _adapter(self, model: str, effort: str | None, timeout_s: float | None,
                 attempts: int | None = None) -> MuseAdapter:
        key = (model, effort, timeout_s, attempts)
        adapter = self._adapters.get(key)
        if adapter is None:
            config = None
            if self._base is not None:
                config = replace(self._base, model=model,
                                 reasoning_effort=effort if effort in MODEL_EFFORTS[model] else None,
                                 timeout_s=timeout_s or self._base.timeout_s,
                                 max_attempts=attempts or self._base.max_attempts)
            adapter = self._factory(self._registry, config=config, evidence_log=self.evidence_log,
                                    reasoning_trace=self.reasoning_trace, **self._adapter_kwargs)
            self._adapters[key] = adapter
        return adapter

    def _chain(self, task: str) -> list[tuple[str, str | None, float | None, int | None]]:
        route = self._routes.get(task)
        if route is None:
            base = self._base
            return [(base.model if base else SPARK, base.reasoning_effort if base else None, None, None)]
        chain = [(route.model, route.effort, route.timeout_s, route.max_attempts)]
        for m in route.fallbacks:
            effort = route.effort if route.effort in MODEL_EFFORTS[m] else "low"
            chain.append((m, effort, route.timeout_s, route.max_attempts))
        return chain

    async def run(self, request: MuseRequest) -> MuseResult:
        started = self._clock()
        last: ProviderError | None = None
        for i, (model, effort, timeout_s, attempts) in enumerate(self._chain(request.task)):
            attempt_request = request
            if request.deadline_s is not None:
                remaining = request.deadline_s - (self._clock() - started)
                if i > 0 and remaining < MIN_FALLBACK_S:
                    break
                attempt_request = replace(request, deadline_s=remaining)
            try:
                result = await self._adapter(model, effort, timeout_s, attempts).run(attempt_request)
            except ProviderError as exc:
                last = exc
                if exc.kind not in FALLBACK_KINDS:
                    raise
                self.reasoning_trace.note(request.request_id, "router", f"fallback_after_{exc.kind}")
                continue
            if i > 0:
                self.reasoning_trace.note(request.request_id, "router", "served_by_fallback")
            return result
        assert last is not None
        raise last


def build_muse_router(registry: TaskRegistry, config: MuseConfig | None,
                      routes: Mapping[str, Route] | None = None, **kwargs: Any) -> MuseRouter:
    return MuseRouter(registry, config, DEFAULT_ROUTES if routes is None else routes, **kwargs)
