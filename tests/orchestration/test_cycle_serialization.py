"""Concurrency guarantees of Kai's adapter; real CycleService tested in composition."""

import threading
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest

from server.app.cycles import SerializedCycle
from server.app.errors import ServiceError


class TestCycle:
    __test__ = False

    def __init__(self):
        self.revision = 1
        self.status = "forming"

    def check_gate(self, cycle_id, revision, status=None):
        if self.revision != revision or (status and status != self.status):
            raise ServiceError("STALE_REVISION")
        return SimpleNamespace(status=self.status)

    def advance(self):
        self.status = "revealed"
        self.revision += 1

    def slow_submit(self, callback):
        callback()
        return self.status


def test_cycle_commit_holds_the_same_lock_as_all_public_cycle_calls():
    wrapped = SerializedCycle(TestCycle())
    entered, finished = threading.Event(), threading.Event()

    def advance():
        entered.set()
        wrapped.advance()
        finished.set()

    with ThreadPoolExecutor(max_workers=1) as pool:
        with wrapped.commit_guard("synthetic-cycle", 1, "forming"):
            future = pool.submit(advance)
            assert entered.wait(1)
            assert not finished.wait(0.03)
        future.result(timeout=2)
    with pytest.raises(ServiceError):
        with wrapped.commit_guard("synthetic-cycle", 1, "forming"):
            pytest.fail("stale commit must not execute")


def test_provider_callback_releases_cycle_lock_and_rechecks_can_see_new_state():
    wrapped = SerializedCycle(TestCycle())
    entered, release = threading.Event(), threading.Event()

    def screen():
        entered.set()
        assert release.wait(2)

    with ThreadPoolExecutor(max_workers=2) as pool:
        pending = pool.submit(wrapped.slow_submit, lambda: wrapped.provider_call(screen))
        assert entered.wait(1)
        pool.submit(wrapped.advance).result(timeout=1)
        release.set()
        assert pending.result(timeout=2) == "revealed"
    with wrapped.commit_guard("synthetic-cycle", 2, "revealed"):
        with pytest.raises(ServiceError):
            wrapped.provider_call(lambda: None)


def test_wrapper_does_not_expose_service_internals():
    wrapped = SerializedCycle(TestCycle())
    with pytest.raises(AttributeError):
        _ = wrapped._repo


def test_nested_commit_guards_keep_the_outer_provider_prohibition():
    wrapped = SerializedCycle(TestCycle())
    with wrapped.commit_guard("synthetic-cycle", 1, "forming"):
        with wrapped.commit_guard("synthetic-cycle", 1, "forming"):
            pass
        with pytest.raises(ServiceError):
            wrapped.provider_call(lambda: None)
