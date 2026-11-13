"""Labeled test-only sinks verify dispatch, not durable delivery."""

import pytest

from server.app.errors import ServiceError
from server.orchestration.hooks import CycleHooks

from .adapters import cycle_wire


def test_hooks_dispatch_only_valid_status_and_never_silent_noops():
    calls = []
    hooks = CycleHooks(
        publish_cycle=lambda c: calls.append(("changed", c)),
        enqueue_formation=lambda c: calls.append(("locked", c)),
        reveal_cycle=lambda c: calls.append(("revealed", c)),
    )
    hooks.on_changed(cycle_wire())
    hooks.on_locked(cycle_wire())
    hooks.on_revealed({**cycle_wire(), "status": "revealed"})
    assert [kind for kind, _ in calls] == ["changed", "locked", "revealed"]
    with pytest.raises(ServiceError):
        hooks.on_revealed(cycle_wire())
    with pytest.raises(ValueError):
        CycleHooks(publish_cycle=None, enqueue_formation=None, reveal_cycle=None)


def test_hook_failure_is_sanitized_for_operator_retry():
    def failing_sink(cycle):
        raise RuntimeError("SYNTHETIC PRIVATE DB DETAILS")

    hooks = CycleHooks(
        publish_cycle=failing_sink, enqueue_formation=failing_sink, reveal_cycle=failing_sink
    )
    with pytest.raises(ServiceError) as error:
        hooks.on_locked(cycle_wire())
    assert str(error.value) == "PROVIDER_UNAVAILABLE"
