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

SCHEMA = Path(__file__).resolve().parents[2] / "db" / "privacy" / "001_privacy.sql"


class PrivacyStore:
    def __init__(self, path: str = ":memory:"):
        self._conn = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        if path != ":memory:":
            self._conn.execute("PRAGMA journal_mode = WAL")
        self._lock = threading.RLock()
        self._conn.executescript(SCHEMA.read_text())

    @contextmanager
    def tx(self) -> Iterator[sqlite3.Connection]:
        """One serialized write transaction; rolls back on any exception."""
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                yield self._conn
            except BaseException:
                self._conn.execute("ROLLBACK")
                raise
            else:
                self._conn.execute("COMMIT")

    def ping(self) -> bool:
        try:
            with self._lock:
                return self._conn.execute("SELECT 1").fetchone()[0] == 1
        except sqlite3.Error:
            return False

    def close(self) -> None:
        with self._lock:
            self._conn.close()
