"""Private answer + guess storage (role task 3). Implements Will's proposed
``AnswerStore`` port (server/cycle/ports.py) with the same method names.

Callers are server code that already resolved a session through
``PrivacyService.require_session``; ``player_id`` always comes from that Actor
or Session, never from a request body. Reads return only the named player's
own rows. Defense in depth on write:

* the answer must be for a player who is an active member with all three
  consents on (CONSENT_REQUIRED otherwise), and nothing is written or
  deleted for a cycle marked locked here (CYCLE_LOCKED);
* ``weight`` must equal the contract rule (WEIGHTS); a client-set weight
  is rejected rather than stored;
* ``flag`` (the M1 result) is stored with the row; only ``none`` may ever
  reach formation (see ``eligible_answers``).

Retention: ``mark_locked(cycle_id, locked_at)`` when a cycle locks;
``purge_expired()`` deletes that cycle's answers and guesses 14 days later.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from typing import Any

from . import errors
from .service import ChangeNotice, PrivacyService, new_id
from .store import PrivacyStore
from .wire import DailyAnswer, PrevalenceGuess, SafetyLevel, format_time

RETENTION = timedelta(days=14)
_FLAGS = ("none", "distress", "harm")


def _as_dict(value: Any) -> dict:
    """Accept a pydantic model (any owner's mirror) or a camelCase mapping."""
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json", by_alias=True)
    if isinstance(value, Mapping):
        return dict(value)
    raise TypeError("expected a camelCase mapping or pydantic model")


def _parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def _row_to_answer(row: sqlite3.Row) -> DailyAnswer:
    return DailyAnswer(
        answer_id=row["answer_id"], cycle_id=row["cycle_id"], day=row["day"],
        question_id=row["question_id"], player_id=row["player_id"], text=row["text"],
        source=row["source"], is_catch_up=bool(row["is_catch_up"]), weight=row["weight"],
        follow_up_used=bool(row["follow_up_used"]), created_at=row["created_at"],
        edited_at=row["edited_at"], deleted_at=None,
    )


class AnswerStore:
    """``answer_model`` / ``guess_model``: optional pydantic classes the caller
    wants back (e.g. Will's camelCase ``server.cycle.wire.DailyAnswer``), passed
    in by the composition root so privacy never imports another owner's code.
    Rows are validated by privacy's own models first, then re-validated into
    the caller's model from the camelCase wire form."""

    def __init__(self, store: PrivacyStore, privacy: PrivacyService, *,
                 answer_model: Any = None, guess_model: Any = None):
        self._store = store
        self._privacy = privacy
        self._answer_model = answer_model
        self._guess_model = guess_model

    def _out_answer(self, row: sqlite3.Row) -> Any:
        a = _row_to_answer(row)
        return self._answer_model.model_validate(a.wire()) if self._answer_model else a

    def _out_guess(self, g: PrevalenceGuess) -> Any:
        return self._guess_model.model_validate(g.wire()) if self._guess_model else g

    def _now(self) -> datetime:
        return self._privacy.now()  # same injected clock as sessions

    # ---------------------------------------------------------------- guards
    @staticmethod
    def _require_playable(conn: sqlite3.Connection, player_id: str) -> None:
        ok = conn.execute(
            """
            SELECT 1 FROM memberships m
            JOIN current_consents c ON c.player_id = m.player_id AND c.community_id = m.community_id
            WHERE m.player_id = ? AND m.left_at IS NULL
              AND c.match_answers = 1 AND c.anonymous_chat = 1 AND c.is_adult = 1
            """,
            (player_id,),
        ).fetchone()
        if ok is None:
            raise errors.consent_required()

    @staticmethod
    def _require_open(conn: sqlite3.Connection, cycle_id: str) -> None:
        if conn.execute("SELECT 1 FROM cycle_locks WHERE cycle_id = ?", (cycle_id,)).fetchone():
            raise errors.cycle_locked()

    # ----------------------------------------------------------------- reads
    def get(self, cycle_id: str, player_id: str, day: int) -> DailyAnswer | None:
        with self._store.tx() as conn:
            row = conn.execute(
                "SELECT * FROM answers WHERE cycle_id = ? AND player_id = ? AND day = ?",
                (cycle_id, player_id, day),
            ).fetchone()
        return self._out_answer(row) if row else None

    def list_for_player(self, cycle_id: str, player_id: str) -> list[DailyAnswer]:
        with self._store.tx() as conn:
            rows = conn.execute(
                "SELECT * FROM answers WHERE cycle_id = ? AND player_id = ? ORDER BY day",
                (cycle_id, player_id),
            ).fetchall()
        return [self._out_answer(r) for r in rows]

    # ---------------------------------------------------------------- writes
    def save(self, answer: Any, flag: SafetyLevel) -> None:
        """Insert or replace by (cycleId, playerId, day)."""
        a = DailyAnswer.model_validate(_as_dict(answer))
        if flag not in _FLAGS:
            raise ValueError("flag must be a SafetyLevel")
        if not a.weight_is_server_rule():
            raise errors.invalid_input("weight is server-set")
        if a.deleted_at is not None:
            raise errors.invalid_input("use delete() to delete an answer")
        with self._store.tx() as conn:
            self._require_playable(conn, a.player_id)
            self._require_open(conn, a.cycle_id)
            conn.execute(
                """
                INSERT INTO answers (answer_id, player_id, cycle_id, day, question_id, text, source,
                  is_catch_up, follow_up_used, weight, safety_flag, created_at, edited_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (player_id, cycle_id, day) DO UPDATE SET
                  answer_id = excluded.answer_id, question_id = excluded.question_id,
                  text = excluded.text, source = excluded.source, is_catch_up = excluded.is_catch_up,
                  follow_up_used = excluded.follow_up_used, weight = excluded.weight,
                  safety_flag = excluded.safety_flag, edited_at = excluded.edited_at
                """,
                (a.answer_id, a.player_id, a.cycle_id, a.day, a.question_id, a.text, a.source,
                 int(a.is_catch_up), int(a.follow_up_used), a.weight, flag, a.created_at, a.edited_at),
            )

    def delete(self, cycle_id: str, player_id: str, day: int, deleted_at: str) -> bool:
        with self._store.tx() as conn:
            self._require_open(conn, cycle_id)
            cur = conn.execute(
                "DELETE FROM answers WHERE cycle_id = ? AND player_id = ? AND day = ?",
                (cycle_id, player_id, day),
            )
        if cur.rowcount:
            self._privacy.notify(ChangeNotice("answer_deleted", player_id, None, None, deleted_at, cycle_id))
        return cur.rowcount == 1

    def save_guess(self, guess: Any) -> None:
        g = PrevalenceGuess.model_validate(_as_dict(guess))
        with self._store.tx() as conn:
            self._require_playable(conn, g.player_id)
            self._require_open(conn, g.cycle_id)
            conn.execute(
                "INSERT INTO guesses (player_id, cycle_id, percent, updated_at) VALUES (?, ?, ?, ?)"
                " ON CONFLICT (player_id, cycle_id) DO UPDATE SET percent = excluded.percent,"
                " updated_at = excluded.updated_at",
                (g.player_id, g.cycle_id, g.percent, format_time(self._now())),
            )

    def get_guess(self, cycle_id: str, player_id: str) -> PrevalenceGuess | None:
        with self._store.tx() as conn:
            row = conn.execute(
                "SELECT percent FROM guesses WHERE cycle_id = ? AND player_id = ?", (cycle_id, player_id),
            ).fetchone()
        if row is None:
            return None
        return self._out_guess(PrevalenceGuess(cycle_id=cycle_id, player_id=player_id, percent=row["percent"]))

    def purge_cycle(self, cycle_id: str) -> None:
        """Operator reset of a fixture cycle (Will checks it is a fixture cycle)."""
        with self._store.tx() as conn:
            conn.execute("DELETE FROM answers WHERE cycle_id = ?", (cycle_id,))
            conn.execute("DELETE FROM guesses WHERE cycle_id = ?", (cycle_id,))
            conn.execute("DELETE FROM cycle_locks WHERE cycle_id = ?", (cycle_id,))

    # ------------------------------------------------------------- lifecycle
    def mark_locked(self, cycle_id: str, locked_at: str) -> None:
        """Saturday lock: further writes for this cycle are refused and the
        14-day retention clock starts. Idempotent (first lock time wins)."""
        _parse_time(locked_at)
        with self._store.tx() as conn:
            conn.execute("INSERT OR IGNORE INTO cycle_locks (cycle_id, locked_at) VALUES (?, ?)",
                         (cycle_id, locked_at))

    def purge_expired(self) -> dict[str, int]:
        """Delete answers and guesses of cycles locked 14+ days ago."""
        cutoff = format_time(self._now() - RETENTION)
        with self._store.tx() as conn:
            expired = [r["cycle_id"] for r in conn.execute(
                "SELECT cycle_id FROM cycle_locks WHERE locked_at <= ?", (cutoff,)).fetchall()]
            counts = {"answers": 0, "guesses": 0}
            for cycle_id in expired:
                counts["answers"] += conn.execute("DELETE FROM answers WHERE cycle_id = ?", (cycle_id,)).rowcount
                counts["guesses"] += conn.execute("DELETE FROM guesses WHERE cycle_id = ?", (cycle_id,)).rowcount
        return counts

    def delete_my_data(self, player_id: str) -> dict[str, int]:
        """DELETE /me/data: every answer and guess of this player, any cycle."""
        with self._store.tx() as conn:
            counts = {
                "answers": conn.execute("DELETE FROM answers WHERE player_id = ?", (player_id,)).rowcount,
                "guesses": conn.execute("DELETE FROM guesses WHERE player_id = ?", (player_id,)).rowcount,
            }
        self._privacy.notify(ChangeNotice("data_deleted", player_id, None, None, format_time(self._now())))
        return counts

    # --------------------------------------------------------------- formation
    def eligible_answers(self, cycle_id: str, community_id: str | None = None) -> list[sqlite3.Row]:
        """Server-only formation input: answers of players who are active
        members with all three consents on and have NO flagged answer in this
        cycle (contract: eligible = consented, not flagged; week-sample
        expectedFormation excludes the distress player entirely), (in ``community_id`` when
        given, else in any community). One row per answer, never duplicated.
        Rows include ``consent_version`` (of ``community_id`` when given) for
        the publish-guard revision. Never exposed over HTTP."""
        return self._eligible(cycle_id, community_id)

    def _eligible(self, cycle_id: str, community_id: str | None) -> list[sqlite3.Row]:
        with self._store.tx() as conn:
            return conn.execute(
                """
                SELECT a.answer_id, a.player_id, a.day, a.text, a.weight, a.edited_at, p.is_synthetic,
                  (SELECT max(c.version) FROM current_consents c
                   WHERE c.player_id = a.player_id AND (:community IS NULL OR c.community_id = :community)
                  ) AS consent_version
                FROM answers a
                JOIN players p ON p.player_id = a.player_id
                WHERE a.cycle_id = :cycle AND a.safety_flag = 'none'
                  AND NOT EXISTS (  -- a player with any flagged answer this cycle sits out entirely
                    SELECT 1 FROM answers f
                    WHERE f.cycle_id = a.cycle_id AND f.player_id = a.player_id AND f.safety_flag <> 'none')
                  AND EXISTS (
                    SELECT 1 FROM memberships m
                    JOIN current_consents c ON c.player_id = m.player_id AND c.community_id = m.community_id
                    WHERE m.player_id = a.player_id AND m.left_at IS NULL
                      AND (:community IS NULL OR m.community_id = :community)
                      AND c.match_answers = 1 AND c.anonymous_chat = 1 AND c.is_adult = 1)
                ORDER BY a.player_id, a.day
                """,
                {"cycle": cycle_id, "community": community_id},
            ).fetchall()

    @staticmethod
    def new_answer_id() -> str:
        return new_id("a")
