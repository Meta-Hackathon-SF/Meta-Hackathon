"""Privacy service: join + 18+ consent, sessions, operator role (Facebook Space 2.0.0).

Ports for other owners (import from ``server.privacy``; never open the store):

* ``require_session(token) -> Actor``  every authenticated route. Mirrors
  ``PrivacyPort.requireSession``: player, community and operator flag come from
  the server-side session, never from a request body.
* ``require_consent(actor)``           guard before storing an answer, joining a
  room or enqueueing a model job (raises CONSENT_REQUIRED).
* ``require_operator(actor)``          guard for operator routes (FORBIDDEN).
* ``add_listener(fn)``                 ``ChangeNotice`` on consent changes (ids
  and versions only) so Kai/Will can drop queued work and leave rooms.

Every private query is keyed to ``actor.player_id`` from a verified session.
"""

from __future__ import annotations

import hashlib
import logging
import secrets
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Literal

from . import errors
from .store import PrivacyStore
from .wire import Consent, ConsentToggles, JoinRequest, Player, SessionView, UpdateConsentRequest, format_time

log = logging.getLogger("constellations.privacy")

SESSION_TTL = timedelta(days=7)
MAX_TOKEN_LENGTH = 256
# Fixed palette; colors are assigned by the server, never chosen from input.
AVATAR_COLORS = ("#7c9cff", "#ffb86b", "#6be3c1", "#ff7ab6", "#c9a7ff", "#ffd36b", "#8be36b", "#6bc7ff")
_ACTOR_KEY = object()

Clock = Callable[[], datetime]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def new_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(12)}"


def hash_token(token: str) -> bytes:
    return hashlib.sha256(token.encode("utf-8")).digest()


@dataclass(frozen=True)
class Actor:
    """A player proven by a server-verified session. Only ``PrivacyService``
    can construct one; a forged playerId can never become an Actor."""

    player_id: str
    session_id: str
    community_id: str
    is_operator: bool
    _key: object

    def __post_init__(self) -> None:
        if self._key is not _ACTOR_KEY:
            raise TypeError("Actor must come from PrivacyService.require_session")


ChangeKind = Literal["consent_granted", "consent_revoked", "answer_deleted", "data_deleted"]


@dataclass(frozen=True)
class ChangeNotice:
    """Invalidation notice. Ids and versions only; never private content.
    ``consent_version`` is set for consent kinds; ``cycle_id`` for answer_deleted."""

    kind: ChangeKind
    player_id: str
    community_id: str | None
    consent_version: int | None
    occurred_at: str
    cycle_id: str | None = None


Listener = Callable[[ChangeNotice], None]


@dataclass(frozen=True)
class JoinResult:
    view: SessionView
    token: str | None  # set only when a new session was issued
    created: bool


def _consent(row: sqlite3.Row) -> Consent:
    return Consent(
        player_id=row["player_id"],
        community_id=row["community_id"],
        match_answers=bool(row["match_answers"]),
        anonymous_chat=bool(row["anonymous_chat"]),
        is_adult=bool(row["is_adult"]),
        version=row["version"],
        revoked_at=row["revoked_at"],
    )


def _same_toggles(row: sqlite3.Row, toggles: ConsentToggles) -> bool:
    return (
        bool(row["match_answers"]) == toggles.match_answers
        and bool(row["anonymous_chat"]) == toggles.anonymous_chat
        and bool(row["is_adult"]) == toggles.is_adult
    )


def _grants_all(toggles: ConsentToggles) -> bool:
    return toggles.match_answers and toggles.anonymous_chat and toggles.is_adult


class PrivacyService:
    def __init__(self, store: PrivacyStore, *, clock: Clock = _utc_now, session_ttl: timedelta = SESSION_TTL):
        self._store = store
        self._clock = clock
        self._session_ttl = session_ttl
        self._listeners: list[Listener] = []

    @property
    def session_ttl(self) -> timedelta:
        return self._session_ttl

    def now(self) -> datetime:
        return self._clock()

    def _now(self) -> str:
        return format_time(self._clock())

    def ready(self) -> bool:
        return self._store.ping()

    # ------------------------------------------------------------------ notices
    def add_listener(self, listener: Listener) -> None:
        self._listeners.append(listener)

    def notify(self, notice: ChangeNotice) -> None:
        """Used by privacy's own answer store; other owners only subscribe."""
        self._notify(notice)

    def _notify(self, notice: ChangeNotice) -> None:
        for listener in self._listeners:
            try:
                listener(notice)
            except Exception:  # a listener failure must not undo a committed revocation
                log.exception("privacy listener failed kind=%s", notice.kind)

    # ----------------------------------------------------------------- sessions
    def _resolve_row(self, conn: sqlite3.Connection, token: str | None) -> sqlite3.Row | None:
        if not token or len(token) > MAX_TOKEN_LENGTH:
            return None
        return conn.execute(
            """
            SELECT s.session_id, s.player_id, s.community_id, m.is_operator
            FROM sessions s
            JOIN players p ON p.player_id = s.player_id
            JOIN memberships m ON m.player_id = s.player_id AND m.community_id = s.community_id
            WHERE s.token_hash = ? AND s.revoked_at IS NULL AND s.expires_at > ?
              AND p.is_synthetic = 0 AND m.left_at IS NULL
            """,
            (hash_token(token), self._now()),
        ).fetchone()

    def require_session(self, token: str | None) -> Actor:
        with self._store.tx() as conn:
            row = self._resolve_row(conn, token)
        if row is None:
            raise errors.unauthenticated()
        return Actor(row["player_id"], row["session_id"], row["community_id"], bool(row["is_operator"]), _ACTOR_KEY)

    def end_session(self, actor: Actor) -> None:
        with self._store.tx() as conn:
            conn.execute(
                "UPDATE sessions SET revoked_at = ? WHERE session_id = ? AND player_id = ? AND revoked_at IS NULL",
                (self._now(), actor.session_id, actor.player_id),
            )

    def _issue_session(self, conn: sqlite3.Connection, player_id: str, community_id: str) -> str:
        token = secrets.token_urlsafe(32)
        now = self._clock()
        conn.execute(
            "INSERT INTO sessions (session_id, token_hash, player_id, community_id, created_at, expires_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (new_id("s"), hash_token(token), player_id, community_id,
             format_time(now), format_time(now + self._session_ttl)),
        )
        return token

    # --------------------------------------------------------------------- join
    def join(self, community_id: str, req: JoinRequest, existing_token: str | None = None) -> JoinResult:
        """Join with all three toggles on (match me, anonymous chat, 18+).

        With a valid session for this community the call is idempotent and
        returns the current state. Otherwise a new pseudonymous player and
        session are created. Nothing is written when consent is incomplete.
        """
        if not _grants_all(req):
            raise errors.consent_required()
        with self._store.tx() as conn:
            if conn.execute("SELECT 1 FROM communities WHERE community_id = ?", (community_id,)).fetchone() is None:
                raise errors.not_found()
            current = self._resolve_row(conn, existing_token)
            if current is not None and current["community_id"] == community_id:
                actor = Actor(current["player_id"], current["session_id"], community_id,
                              bool(current["is_operator"]), _ACTOR_KEY)
                return JoinResult(self._view(conn, actor), None, False)
            now = self._now()
            player_id = new_id("p")
            conn.execute(
                "INSERT INTO players (player_id, display_name, avatar_color, is_synthetic, created_at)"
                " VALUES (?, ?, ?, 0, ?)",
                (player_id, req.display_name, secrets.choice(AVATAR_COLORS), now),
            )
            conn.execute(
                "INSERT INTO memberships (community_id, player_id, joined_at) VALUES (?, ?, ?)",
                (community_id, player_id, now),
            )
            conn.execute(
                "INSERT INTO consents (player_id, community_id, version, match_answers, anonymous_chat,"
                " is_adult, created_at) VALUES (?, ?, 1, 1, 1, 1, ?)",
                (player_id, community_id, now),
            )
            token = self._issue_session(conn, player_id, community_id)
            row = self._resolve_row(conn, token)
            actor = Actor(player_id, row["session_id"], community_id, False, _ACTOR_KEY)
            view = self._view(conn, actor)
        self._notify(ChangeNotice("consent_granted", player_id, community_id, 1, now))
        return JoinResult(view, token, True)

    # ------------------------------------------------------------------ reading
    @staticmethod
    def _own_consent_row(conn: sqlite3.Connection, actor: Actor) -> sqlite3.Row:
        row = conn.execute(
            "SELECT * FROM current_consents WHERE player_id = ? AND community_id = ?",
            (actor.player_id, actor.community_id),
        ).fetchone()
        if row is None:
            raise errors.unauthenticated()
        return row

    def _view(self, conn: sqlite3.Connection, actor: Actor) -> SessionView:
        p = conn.execute(
            "SELECT player_id, display_name, avatar_color, is_synthetic FROM players WHERE player_id = ?",
            (actor.player_id,),
        ).fetchone()
        player = Player(
            player_id=p["player_id"], display_name=p["display_name"],
            avatar_color=p["avatar_color"], is_synthetic=bool(p["is_synthetic"]),
        )
        return SessionView(player=player, consent=_consent(self._own_consent_row(conn, actor)),
                           is_operator=actor.is_operator)

    def session_view(self, actor: Actor) -> SessionView:
        with self._store.tx() as conn:
            return self._view(conn, actor)

    def get_consent(self, actor: Actor) -> Consent:
        with self._store.tx() as conn:
            return _consent(self._own_consent_row(conn, actor))

    # ------------------------------------------------------------------ consent
    def update_consent(self, actor: Actor, req: UpdateConsentRequest) -> Consent:
        """Compare-and-set on ``expectedVersion``. Withdrawing any toggle sets
        ``revokedAt`` and emits ``consent_revoked``; re-granting all three
        clears it. Retrying the same body after success returns the stored row."""
        with self._store.tx() as conn:
            current = self._own_consent_row(conn, actor)
            if current["version"] != req.expected_version:
                if current["version"] == req.expected_version + 1 and _same_toggles(current, req):
                    return _consent(current)  # retried request
                raise errors.stale()
            if _same_toggles(current, req):
                return _consent(current)  # no-op: no new revision
            withdrawn = (
                (current["match_answers"] and not req.match_answers)
                or (current["anonymous_chat"] and not req.anonymous_chat)
                or (current["is_adult"] and not req.is_adult)
            )
            now = self._now()
            revoked_at = None if _grants_all(req) else (now if withdrawn else current["revoked_at"])
            conn.execute(
                "INSERT INTO consents (player_id, community_id, version, match_answers, anonymous_chat,"
                " is_adult, revoked_at, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (actor.player_id, actor.community_id, req.expected_version + 1, int(req.match_answers),
                 int(req.anonymous_chat), int(req.is_adult), revoked_at, now),
            )
            consent = _consent(self._own_consent_row(conn, actor))
        # granted = playable again; anything short of all three is a revocation.
        kind: ChangeKind = "consent_granted" if consent.grants_play else "consent_revoked"
        self._notify(ChangeNotice(kind, actor.player_id, actor.community_id, consent.version, now))
        return consent

    def require_consent(self, actor: Actor) -> Consent:
        """Current consent, or CONSENT_REQUIRED unless all three toggles are on.
        Call it again at commit time for queued work: consent may have changed."""
        consent = self.get_consent(actor)
        if not consent.grants_play:
            raise errors.consent_required()
        return consent

    @staticmethod
    def require_operator(actor: Actor) -> None:
        if not actor.is_operator:
            raise errors.forbidden()
