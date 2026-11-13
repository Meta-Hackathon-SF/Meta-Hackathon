"""TEST ONLY serialized workflow repository; never imported by server code.

This adapter proves policy/repository behavior offline, not PostgreSQL durability.
Use PostgresWorkflowRepository for configured production execution.
"""

import threading
from contextlib import contextmanager

from server.app.errors import ServiceError
from server.orchestration.storage import WorkflowState, dump_state, load_state


class TestWorkflowRepository:
    __test__ = False

    def __init__(self, initial: WorkflowState | None = None):
        self._body = dump_state(initial if initial is not None else WorkflowState())
        self._lock = threading.RLock()
        self._closed = False
        self._active = threading.local()

    @contextmanager
    def transaction(self):
        with self._lock:
            if self._closed or getattr(self._active, "value", False):
                raise ServiceError("PROVIDER_UNAVAILABLE")
            self._active.value = True
            try:
                state = load_state(self._body)
                yield state
                self._body = dump_state(state)
            finally:
                self._active.value = False

    def ready(self):
        return not self._closed

    def close(self):
        with self._lock:
            self._closed = True
