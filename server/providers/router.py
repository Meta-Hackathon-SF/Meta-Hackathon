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


# Today's behaviour: every task on the base model. Replaced by measured routes.
DEFAULT_ROUTES: dict[str, Route] = {}


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
        self._adapters: dict[tuple[str, str | None, float | None], MuseAdapter] = {}

    @property
    def configured(self) -> bool:
        return self._base is not None

    def route_for(self, task: str) -> Route | None:
        return self._routes.get(task)

    def _adapter(self, model: str, effort: str | None, timeout_s: float | None) -> MuseAdapter:
        key = (model, effort, timeout_s)
        adapter = self._adapters.get(key)
        if adapter is None:
            config = None
            if self._base is not None:
                config = replace(self._base, model=model,
                                 reasoning_effort=effort if effort in MODEL_EFFORTS[model] else None,
                                 timeout_s=timeout_s or self._base.timeout_s)
            adapter = self._factory(self._registry, config=config, evidence_log=self.evidence_log,
                                    reasoning_trace=self.reasoning_trace, **self._adapter_kwargs)
            self._adapters[key] = adapter
        return adapter

    def _chain(self, task: str) -> list[tuple[str, str | None, float | None]]:
        route = self._routes.get(task)
        if route is None:
            base = self._base
            return [(base.model if base else "muse-spark-1.3", base.reasoning_effort if base else None, None)]
        chain = [(route.model, route.effort, route.timeout_s)]
        for m in route.fallbacks:
            effort = route.effort if route.effort in MODEL_EFFORTS[m] else "low"
            chain.append((m, effort, route.timeout_s))
        return chain

    async def run(self, request: MuseRequest) -> MuseResult:
        started = self._clock()
        last: ProviderError | None = None
        for i, (model, effort, timeout_s) in enumerate(self._chain(request.task)):
            attempt_request = request
            if request.deadline_s is not None:
                remaining = request.deadline_s - (self._clock() - started)
                if i > 0 and remaining < MIN_FALLBACK_S:
                    break
                attempt_request = replace(request, deadline_s=remaining)
            try:
                result = await self._adapter(model, effort, timeout_s).run(attempt_request)
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
