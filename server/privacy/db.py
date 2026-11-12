"""Database access scoped to a verified actor.

Every query runs inside ``Database.as_actor(...)``, which sets the transaction-
local ``gq.participant_id`` consumed by the RLS policies in
db/privacy/001_privacy_foundation.sql. The connection role must be a member of
gq_api: not the table owner, not a superuser, not a service-role key.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool


class Database:
    def __init__(self, dsn: str, *, min_size: int = 1, max_size: int = 10):
        self._pool = ConnectionPool(
            dsn,
            min_size=min_size,
            max_size=max_size,
            kwargs={"row_factory": dict_row, "autocommit": False},
            open=True,
        )
        self._check_role()

    def _check_role(self) -> None:
        with self._pool.connection() as conn:
            row = conn.execute(
                "SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user"
            ).fetchone()
            in_api = conn.execute("SELECT pg_has_role(current_user, 'gq_api', 'MEMBER') AS ok").fetchone()
        if row["rolsuper"] or row["rolbypassrls"]:
            raise RuntimeError("privacy Database must not connect as a superuser or BYPASSRLS role")
        if not in_api["ok"]:
            raise RuntimeError("privacy Database role must be a member of gq_api")

    @contextmanager
    def as_actor(self, participant_id: str | None) -> Iterator[psycopg.Connection]:
        """One transaction with RLS identity bound. ``None`` = anonymous (fails closed)."""
        with self._pool.connection() as conn:
            with conn.transaction():
                conn.execute(
                    "SELECT set_config('gq.participant_id', %s, true)",
                    (participant_id or "",),
                )
                yield conn

    def ping(self) -> bool:
        """Readiness: a pooled connection answers within 0.5 s. Never raises."""
        try:
            with self._pool.connection(timeout=0.5) as conn:
                return conn.execute("SELECT 1 AS ok").fetchone()["ok"] == 1
        except Exception:
            return False

    def close(self) -> None:
        self._pool.close()
