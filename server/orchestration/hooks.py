"""Will's published CycleHooks, with explicit persistence/delivery callbacks.

No NoHooks or in-memory fallback: production composition must supply durable,
privacy-aware idempotent sinks. Tests pass labeled fixture sinks. These hooks run
after the cycle commits, so a sink failure remains a retryable operator error.
"""

from collections.abc import Callable

from server.app.errors import ServiceError
from server.orchestration.wire import WeeklyCycle


class CycleHooks:
    def __init__(
        self, *, publish_cycle: Callable, enqueue_formation: Callable, reveal_cycle: Callable
    ):
        if not all(callable(fn) for fn in (publish_cycle, enqueue_formation, reveal_cycle)):
            raise ValueError("Explicit durable cycle hooks required")
        self.publish_cycle = publish_cycle
        self.enqueue_formation = enqueue_formation
        self.reveal_cycle = reveal_cycle

    @staticmethod
    def _cycle(cycle):
        if hasattr(cycle, "model_dump"):
            cycle = cycle.model_dump(mode="json")
        return WeeklyCycle.model_validate(cycle)

    @staticmethod
    def _call(sink, cycle):
        try:
            sink(cycle.model_dump(mode="json"))
        except Exception:
            raise ServiceError("PROVIDER_UNAVAILABLE") from None

    def on_changed(self, cycle):
        self._call(self.publish_cycle, self._cycle(cycle))

    def on_locked(self, cycle):
        current = self._cycle(cycle)
        if current.status != "locked":
            raise ServiceError("STALE_REVISION")
        self._call(self.enqueue_formation, current)

    def on_revealed(self, cycle):
        current = self._cycle(cycle)
        if current.status != "revealed":
            raise ServiceError("STALE_REVISION")
        self._call(self.reveal_cycle, current)
