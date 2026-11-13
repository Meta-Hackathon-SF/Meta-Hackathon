"""One-process cycle serialization through Will's public service only.

All production consumers must receive this wrapper, including Will's HTTP
router. The same app lock protects a short guarded orchestration commit. Provider
callbacks release it explicitly; no provider operation runs inside a commit.
The underlying cycle repository remains process-local and is not crash-durable.
"""

import threading
from collections.abc import Callable, Iterator
from contextlib import ExitStack, contextmanager
from copy import deepcopy
from datetime import datetime
from functools import wraps

from server.app.errors import ServiceError


class SerializedCycle:
    def __init__(self, service, *, after_provider=None, before_reveal=None):
        self.__service = service
        self.__lock = threading.RLock()
        self.__local = threading.local()
        self.__after_provider = after_provider
        self.__before_reveal = before_reveal

    @contextmanager
    def _locked(self):
        with self.__lock:
            self.__local.depth = getattr(self.__local, "depth", 0) + 1
            try:
                yield
            finally:
                self.__local.depth -= 1

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        value = getattr(self.__service, name)
        if not callable(value):
            return deepcopy(value)

        @wraps(value)
        def synchronized(*args, **kwargs):
            with self._locked():
                previous_call = getattr(self.__local, "call", None)
                previous_stack = getattr(self.__local, "stack", None)
                previous_commit = getattr(self.__local, "in_commit", False)
                previous_error = getattr(self.__local, "provider_error", None)
                self.__local.provider_error = None
                try:
                    with ExitStack() as stack:
                        self.__local.call = (name, args, kwargs)
                        self.__local.stack = stack
                        if name == "advance" and self.__before_reveal is not None:
                            cycle_id = args[0]
                            target = args[1] if len(args) > 1 else kwargs.get("to")
                            current = self.__service.gate(cycle_id).cycle
                            if current.status == "forming" and target in (None, "revealed"):
                                self.__before_reveal(cycle_id)
                        result = value(*args, **kwargs)
                        if self.__local.provider_error is not None:
                            raise self.__local.provider_error
                        return deepcopy(result)
                except Exception:
                    if self.__local.provider_error is not None:
                        raise self.__local.provider_error from None
                    raise
                finally:
                    self.__local.call = previous_call
                    self.__local.stack = previous_stack
                    self.__local.in_commit = previous_commit
                    self.__local.provider_error = previous_error

        return synchronized

    @contextmanager
    def serialized(self):
        """Coordinate a short composite operation through the same public lock."""
        with self._locked():
            yield

    @contextmanager
    def commit_guard(self, cycle_id: str, revision: int, status=None) -> Iterator:
        with self._locked():
            cycle = self.__service.check_gate(cycle_id, revision, status=status)
            previous_commit = getattr(self.__local, "in_commit", False)
            self.__local.in_commit = True
            try:
                yield deepcopy(cycle)
            finally:
                self.__local.in_commit = previous_commit

    def provider_call(self, callback: Callable, *args, **kwargs):
        """Use only for injected synchronous M1/M2 callbacks of the cycle service.

        Release the wrapper lock during the slow call so another request can
        lock/revoke the cycle; Will rechecks status before the answer write.
        """
        depth = getattr(self.__local, "depth", 0)
        if getattr(self.__local, "in_commit", False) or depth > 1:
            raise ServiceError("PROVIDER_UNAVAILABLE")
        if depth == 0:
            return callback(*args, **kwargs)
        invocation = getattr(self.__local, "call", None)
        captured = None
        if invocation is not None:
            name, call_args, _ = invocation
            if name in {"submit_answer", "edit_answer", "followup"} and len(call_args) >= 2:
                session, cycle_id = call_args[:2]
                gate = self.__service.gate(cycle_id)
                if gate.cycle.status != "open":
                    raise ServiceError("CYCLE_LOCKED")
                captured = (session, cycle_id, gate.revision)
        self.__local.depth = 0
        self.__lock.release()
        try:
            result = callback(*args, **kwargs)
        finally:
            self.__lock.acquire()
            self.__local.depth = depth
        try:
            if captured is not None:
                session, cycle_id, revision = captured
                current = self.__service.gate(cycle_id)
                if current.cycle.status != "open":
                    raise ServiceError("CYCLE_LOCKED")
                self.__service.check_gate(cycle_id, revision, status="open")
                if self.__after_provider is not None:
                    self.__local.stack.enter_context(self.__after_provider(cycle_id, session))
                    # The guard remains held until the public method returns/caches.
                    self.__local.in_commit = True
            elif self.__after_provider is not None:
                raise ServiceError("PROVIDER_UNAVAILABLE")
        except Exception as error:
            self.__local.provider_error = error
            raise
        return result


def effective_now(cycle, now: datetime) -> datetime:
    """Demo timing comes only from operator-committed cycle state."""
    if cycle.demoTiming and cycle.status in {"revealed", "closed"}:
        timestamp = cycle.chatExpiresAt if cycle.status == "closed" else cycle.revealsAt
        return max(now, datetime.fromisoformat(timestamp.replace("Z", "+00:00")))
    return now
