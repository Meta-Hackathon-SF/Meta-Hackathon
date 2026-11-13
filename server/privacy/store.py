"""SQLite storage for the privacy module. Standard library only; no server.

``PrivacyStore(":memory:")`` for tests, a file path for the local demo
(``CST_PRIVACY_DB``). Only server/privacy/service.py uses this; other owners
call the service ports, never the store.

One connection guarded by a lock; every unit of work is a ``BEGIN IMMEDIATE``
transaction so compare-and-set consent updates cannot interleave.
"""

from __future__ import annotations

import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

MIGRATIONS = Path(__file__).resolve().parents[2] / "db" / "privacy"


class PrivacyStore:
    def __init__(self, path: str = ":memory:"):
        self._conn = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        if path != ":memory:":
            self._conn.execute("PRAGMA journal_mode = WAL")
        self._lock = threading.RLock()
        self._depth = 0
        for migration in sorted(MIGRATIONS.glob("[0-9][0-9][0-9]_*.sql")):  # idempotent, in order
            self._conn.executescript(migration.read_text())

    @contextmanager
    def tx(self) -> Iterator[sqlite3.Connection]:
        """One serialized write transaction; rolls back on any exception.

        Reentrant on the same thread: a nested ``tx()`` (for example a privacy
        call made inside Kai's commit under ``publish_guard``) becomes a
        SAVEPOINT of the outer transaction instead of a second BEGIN."""
        with self._lock:
            depth = self._depth
            savepoint = f"sp{depth}"
            self._conn.execute(f"SAVEPOINT {savepoint}" if depth else "BEGIN IMMEDIATE")
            self._depth += 1  # only after the transaction really started
            try:
                yield self._conn
            except BaseException:
                if depth:
                    self._conn.execute(f"ROLLBACK TO {savepoint}")
                    self._conn.execute(f"RELEASE {savepoint}")
                else:
                    self._conn.execute("ROLLBACK")
                raise
            else:
                self._conn.execute(f"RELEASE {savepoint}" if depth else "COMMIT")
            finally:
                self._depth -= 1

    def ping(self) -> bool:
        try:
            with self._lock:
                return self._conn.execute("SELECT 1").fetchone()[0] == 1
        except sqlite3.Error:
            return False

    def close(self) -> None:
        with self._lock:
            self._conn.close()
