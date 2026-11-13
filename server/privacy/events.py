"""Private event interest and RSVP storage (D012 v3: S2, S13, S14; owner: Patrik).

Players opt in with the ``eventSignals`` consent toggle (off by default).
Without it nothing is stored: every write raises CONSENT_REQUIRED, and
turning it off deletes the player's interests and RSVPs.

What leaves this module:
* to the player themself: their own interest flag and their own invite state
  (RSVP + status), never a count or another player;
* to other owners (server-side only): ``interest_bucket`` returns
  "none" | "3-5" | "6-10" | "11+" (never a count, never under 3) and
  ``invite_has_quorum`` returns a yes/no for the 3-going rule. No player ids,
  no attendee lists.

Event ids must be in the approved catalog (Adam's allowlist, injected as
``is_approved_event``); unknown ids are NOT_FOUND. RSVPs are accepted only on
invites issued to the caller; anyone else gets FORBIDDEN.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable, Iterable

from . import errors
from .service import Actor, PrivacyService
from .store import PrivacyStore
from .wire import InterestBucket, InviteState, InviteStatus, RsvpChoice, format_time

MIN_VISIBLE = 3  # a count under 3 never leaves the module


def bucket(count: int) -> InterestBucket:
    if count < MIN_VISIBLE:
        return "none"
    if count <= 5:
        return "3-5"
    if count <= 10:
        return "6-10"
    return "11+"


class EventStore:
    def __init__(self, store: PrivacyStore, privacy: PrivacyService,
                 is_approved_event: Callable[[str], bool]):
        self._store = store
        self._privacy = privacy
        self._approved = is_approved_event

    # ----------------------------------------------------------------- guards
    @staticmethod
    def _require_opt_in(conn: sqlite3.Connection, actor: Actor) -> None:
        playable = conn.execute(
            """
            SELECT 1 FROM memberships m
            JOIN current_consents c ON c.player_id = m.player_id AND c.community_id = m.community_id
            JOIN event_signal_optins e ON e.player_id = m.player_id AND e.community_id = m.community_id
            WHERE m.player_id = ? AND m.community_id = ? AND m.left_at IS NULL
              AND c.match_answers = 1 AND c.anonymous_chat = 1 AND c.is_adult = 1
            """,
            (actor.player_id, actor.community_id),
        ).fetchone()
        if playable is None:
            raise errors.consent_required()

    def _require_approved(self, event_id: str) -> None:
        if not isinstance(event_id, str) or not event_id or not self._approved(event_id):
            raise errors.not_found()

    # --------------------------------------------------------------- interest
    def set_interest(self, actor: Actor, cycle_id: str, event_id: str, interested: bool) -> bool:
        """PUT /events/:eventId/interest (Adam's route calls this). Returns my flag."""
        self._require_approved(event_id)
        with self._store.tx() as conn:
            self._require_opt_in(conn, actor)
            if interested:
                conn.execute(
                    "INSERT INTO event_interests (player_id, community_id, event_id, cycle_id, created_at)"
                    " VALUES (?, ?, ?, ?, ?) ON CONFLICT (player_id, community_id, event_id) DO NOTHING",
                    (actor.player_id, actor.community_id, event_id, cycle_id, format_time(self._privacy.now())),
                )
            else:
                conn.execute(
                    "DELETE FROM event_interests WHERE player_id = ? AND community_id = ? AND event_id = ?",
                    (actor.player_id, actor.community_id, event_id),
                )
        return interested

    def replace_interests(self, actor: Actor, cycle_id: str, event_ids: Iterable[str]) -> int:
        """PUT /me/event-signals: my full set of interested events. Returns how many stored."""
        wanted = sorted(set(event_ids))
        for event_id in wanted:
            self._require_approved(event_id)
        with self._store.tx() as conn:
            self._require_opt_in(conn, actor)
            conn.execute("DELETE FROM event_interests WHERE player_id = ? AND community_id = ?",
                         (actor.player_id, actor.community_id))
            now = format_time(self._privacy.now())
            conn.executemany(
                "INSERT INTO event_interests (player_id, community_id, event_id, cycle_id, created_at)"
                " VALUES (?, ?, ?, ?, ?)",
                [(actor.player_id, actor.community_id, e, cycle_id, now) for e in wanted],
            )
        return len(wanted)

    def my_interest(self, actor: Actor, event_id: str) -> bool:
        with self._store.tx() as conn:
            return conn.execute(
                "SELECT 1 FROM event_interests WHERE player_id = ? AND community_id = ? AND event_id = ?",
                (actor.player_id, actor.community_id, event_id),
            ).fetchone() is not None

    def interest_bucket(self, community_id: str, event_id: str, among: Iterable[str]) -> InterestBucket:
        """Server-only (Rishi's per-viewer counts): how many of ``among`` (the
        viewer's constellation peers, computed by matching) are interested and
        still opted in, as a bucket. Never returns a count or who."""
        peers = sorted(set(among))
        if not peers:
            return "none"
        marks = ",".join("?" for _ in peers)
        with self._store.tx() as conn:
            n = conn.execute(
                f"""
                SELECT count(DISTINCT i.player_id) FROM event_interests i
                JOIN event_signal_optins e ON e.player_id = i.player_id AND e.community_id = i.community_id
                WHERE i.community_id = ? AND i.event_id = ? AND i.player_id IN ({marks})
                """,
                (community_id, event_id, *peers),
            ).fetchone()[0]
        return bucket(n)

    # ----------------------------------------------------------------- invites
    def issue_invite(self, invite_id: str, community_id: str, cycle_id: str, event_id: str,
                     player_ids: Iterable[str]) -> None:
        """Server-only (Kai's job after operator approval). Invites only opted-in,
        fully consenting adults; others are skipped silently. Idempotent."""
        self._require_approved(event_id)
        now = format_time(self._privacy.now())
        with self._store.tx() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO event_invites (invite_id, community_id, cycle_id, event_id, created_at)"
                " VALUES (?, ?, ?, ?, ?)",
                (invite_id, community_id, cycle_id, event_id, now),
            )
            for player_id in sorted(set(player_ids)):
                ok = conn.execute(
                    """
                    SELECT 1 FROM memberships m
                    JOIN current_consents c ON c.player_id = m.player_id AND c.community_id = m.community_id
                    JOIN event_signal_optins e ON e.player_id = m.player_id AND e.community_id = m.community_id
                    WHERE m.player_id = ? AND m.community_id = ? AND m.left_at IS NULL
                      AND c.match_answers = 1 AND c.anonymous_chat = 1 AND c.is_adult = 1
                    """,
                    (player_id, community_id),
                ).fetchone()
                if ok:
                    conn.execute(
                        "INSERT OR IGNORE INTO event_invite_recipients (invite_id, player_id, updated_at)"
                        " VALUES (?, ?, ?)", (invite_id, player_id, now))

    @staticmethod
    def _state(row: sqlite3.Row) -> InviteState:
        return InviteState(invite_id=row["invite_id"], event_id=row["event_id"],
                           rsvp=row["rsvp"], status=row["status"])

    def rsvp(self, actor: Actor, invite_id: str, choice: RsvpChoice) -> InviteState:
        """PUT /invites/:inviteId/rsvp (Kai's route calls this)."""
        if choice not in ("going", "not_going"):
            raise errors.invalid_input("Unknown RSVP.")
        with self._store.tx() as conn:
            self._require_opt_in(conn, actor)
            row = conn.execute(
                "SELECT i.invite_id, i.event_id, i.status, r.rsvp FROM event_invites i"
                " JOIN event_invite_recipients r ON r.invite_id = i.invite_id"
                " WHERE i.invite_id = ? AND r.player_id = ? AND i.community_id = ?",
                (invite_id, actor.player_id, actor.community_id),
            ).fetchone()
            if row is None:
                raise errors.forbidden()  # not my invite (or none): no further detail
            if row["status"] == "cancelled":
                raise errors.stale()
            conn.execute(
                "UPDATE event_invite_recipients SET rsvp = ?, updated_at = ? WHERE invite_id = ? AND player_id = ?",
                (choice, format_time(self._privacy.now()), invite_id, actor.player_id),
            )
            row = conn.execute(
                "SELECT i.invite_id, i.event_id, i.status, r.rsvp FROM event_invites i"
                " JOIN event_invite_recipients r ON r.invite_id = i.invite_id"
                " WHERE i.invite_id = ? AND r.player_id = ?", (invite_id, actor.player_id)).fetchone()
        return self._state(row)

    def my_invites(self, actor: Actor) -> list[InviteState]:
        """GET /me/invites (own only)."""
        with self._store.tx() as conn:
            rows = conn.execute(
                "SELECT i.invite_id, i.event_id, i.status, r.rsvp FROM event_invites i"
                " JOIN event_invite_recipients r ON r.invite_id = i.invite_id"
                " WHERE r.player_id = ? AND i.community_id = ? ORDER BY i.created_at, i.invite_id",
                (actor.player_id, actor.community_id),
            ).fetchall()
        return [self._state(r) for r in rows]

    def invite_has_quorum(self, invite_id: str) -> bool:
        """Server-only (Kai's confirmation job): at least 3 opted-in players going."""
        with self._store.tx() as conn:
            n = conn.execute(
                """
                SELECT count(*) FROM event_invite_recipients r
                JOIN event_invites i ON i.invite_id = r.invite_id
                JOIN event_signal_optins e ON e.player_id = r.player_id AND e.community_id = i.community_id
                WHERE r.invite_id = ? AND r.rsvp = 'going'
                """,
                (invite_id,),
            ).fetchone()[0]
        return n >= MIN_VISIBLE

    def set_invite_status(self, invite_id: str, status: InviteStatus) -> None:
        """Server-only (Kai's job): confirmed at quorum, cancelled 24 h before start if under."""
        if status not in ("pending", "confirmed", "cancelled"):
            raise errors.invalid_input("Unknown status.")
        with self._store.tx() as conn:
            if conn.execute("UPDATE event_invites SET status = ? WHERE invite_id = ?",
                            (status, invite_id)).rowcount != 1:
                raise errors.not_found()

    def delete_player(self, player_id: str) -> None:
        """DELETE /me/data: every interest and RSVP of this player. The
        eventSignals opt-in itself is consent, not data, so it stays."""
        with self._store.tx() as conn:
            conn.execute("DELETE FROM event_interests WHERE player_id = ?", (player_id,))
            conn.execute("DELETE FROM event_invite_recipients WHERE player_id = ?", (player_id,))
