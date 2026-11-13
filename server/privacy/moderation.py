"""Block and report storage (role tasks 6 and chat moderation support).

Kai's chat owns rooms and the private handle -> player mapping. It resolves a
handle server-side, then calls these methods with player ids taken from
verified sessions. Nothing here is returned to another player.

* Blocks: a blocked pair never shares a constellation (``blocked_pairs`` feeds
  ``formationSnapshot``), and the blocker stops seeing the blocked player's
  messages (``blocked_by``). Blocking never reveals whether the other player
  exists, and you cannot block yourself.
* Reports: stored privately; ``distinct_reporters`` drives Kai's "2 distinct
  reports auto-hide" rule; ``reported_message_ids`` lets Kai hide a reported
  message for the reporter at once; ``report_queue`` is operator-only.
"""

from __future__ import annotations

from collections.abc import Callable

from . import errors
from .service import Actor, PrivacyService, new_id
from .store import PrivacyStore
from .wire import Report, ReportReason, format_time

_REASONS = ("harassment", "self_harm", "spam", "personal_info", "other")

# Kai: (actor, roomId, handle) -> playerId of that handle in a room the actor
# belongs to, or None. Must never return a player outside the actor's room.
HandleResolver = Callable[[Actor, str, str], "str | None"]


class ModerationStore:
    def __init__(self, store: PrivacyStore, privacy: PrivacyService):
        self._store = store
        self._privacy = privacy

    # ----------------------------------------------------------------- blocks
    def block(self, actor: Actor, blocked_player_id: str | None) -> None:
        """Idempotent. Silently does nothing for an unknown player, a player
        outside the actor's community, or the actor themself (no existence leak)."""
        if not blocked_player_id or blocked_player_id == actor.player_id:
            return
        with self._store.tx() as conn:
            member = conn.execute(
                "SELECT 1 FROM memberships WHERE player_id = ? AND community_id = ?",
                (blocked_player_id, actor.community_id),
            ).fetchone()
            if member is None:
                return
            conn.execute(
                "INSERT OR IGNORE INTO blocks (community_id, blocker_id, blocked_id, created_at) VALUES (?, ?, ?, ?)",
                (actor.community_id, actor.player_id, blocked_player_id, format_time(self._privacy.now())),
            )

    def blocked_by(self, player_id: str, community_id: str) -> frozenset[str]:
        """Players whose messages ``player_id`` must not see."""
        with self._store.tx() as conn:
            rows = conn.execute(
                "SELECT blocked_id FROM blocks WHERE blocker_id = ? AND community_id = ?",
                (player_id, community_id),
            ).fetchall()
        return frozenset(r["blocked_id"] for r in rows)

    def blocked_pairs(self, community_id: str, player_ids: set[str] | None = None) -> list[list[str]]:
        """[blockerId, blockedId] pairs, optionally limited to pairs inside ``player_ids``."""
        with self._store.tx() as conn:
            rows = conn.execute(
                "SELECT blocker_id, blocked_id FROM blocks WHERE community_id = ? ORDER BY blocker_id, blocked_id",
                (community_id,),
            ).fetchall()
        pairs = [[r["blocker_id"], r["blocked_id"]] for r in rows]
        if player_ids is not None:
            pairs = [p for p in pairs if p[0] in player_ids and p[1] in player_ids]
        return pairs

    # ---------------------------------------------------------------- reports
    def report(self, actor: Actor, room_id: str, message_id: str | None, reported_handle: str,
               reason: ReportReason) -> Report:
        """Store a report from the actor. Repeat reports of the same message by
        the same reporter return the first one (idempotent)."""
        if reason not in _REASONS:
            raise errors.invalid_input("Unknown report reason.")
        if not isinstance(reported_handle, str) or not 1 <= len(reported_handle) <= 40:
            raise errors.invalid_input("Invalid handle.")
        if not isinstance(room_id, str) or not room_id or (message_id is not None and not isinstance(message_id, str)):
            raise errors.invalid_input("Invalid room or message.")
        with self._store.tx() as conn:
            existing = conn.execute(
                "SELECT * FROM reports WHERE reporter_id = ? AND room_id = ? AND coalesce(message_id, '') = ?"
                " AND reported_handle = ?",
                (actor.player_id, room_id, message_id or "", reported_handle),
            ).fetchone()
            if existing is None:
                conn.execute(
                    "INSERT INTO reports (report_id, community_id, room_id, message_id, reporter_id,"
                    " reported_handle, reason, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (new_id("r"), actor.community_id, room_id, message_id, actor.player_id, reported_handle,
                     reason, format_time(self._privacy.now())),
                )
                existing = conn.execute(
                    "SELECT * FROM reports WHERE reporter_id = ? AND room_id = ? AND coalesce(message_id, '') = ?"
                    " AND reported_handle = ?",
                    (actor.player_id, room_id, message_id or "", reported_handle),
                ).fetchone()
        return _report(existing)

    def distinct_reporters(self, room_id: str, message_id: str) -> int:
        with self._store.tx() as conn:
            return conn.execute(
                "SELECT count(DISTINCT reporter_id) FROM reports WHERE room_id = ? AND message_id = ?",
                (room_id, message_id),
            ).fetchone()[0]

    def reported_message_ids(self, reporter_id: str, room_id: str) -> frozenset[str]:
        with self._store.tx() as conn:
            rows = conn.execute(
                "SELECT message_id FROM reports WHERE reporter_id = ? AND room_id = ? AND message_id IS NOT NULL",
                (reporter_id, room_id),
            ).fetchall()
        return frozenset(r["message_id"] for r in rows)

    def report_queue(self, operator: Actor) -> list[Report]:
        """GET /operator/reports (Kai's route): operator of this community only."""
        self._privacy.require_operator(operator)
        with self._store.tx() as conn:
            rows = conn.execute(
                "SELECT * FROM reports WHERE community_id = ? ORDER BY created_at, rowid",
                (operator.community_id,),
            ).fetchall()
        return [_report(r) for r in rows]


def _report(row) -> Report:
    return Report(
        report_id=row["report_id"], room_id=row["room_id"], message_id=row["message_id"],
        reporter_id=row["reporter_id"], reported_handle=row["reported_handle"], reason=row["reason"],
        created_at=row["created_at"],
    )
