"""Privacy service: identity, membership, consent, private intents, snapshots.

Ports exposed to other owners (import from ``privacy``; never query privacy
tables directly):

* ``PrivacyService.resolve(token) -> Actor``           every route (Kai/all)
* ``PrivacyService.authorized_candidates(actor, communityId) -> list[Candidate]``
                                                        matching/planning jobs (Rishi/Adam via Kai)
* ``PrivacyService.check_member_versions(actor, communityId, memberVersions)``
                                                        recheck before publish (Kai)
* ``PrivacyService.require_eligible(actor, communityId)``  guard before enqueueing model jobs
* ``PrivacyService.add_listener(fn)``                   invalidation notices (Kai)

Identity is always an ``Actor`` produced by ``resolve`` from a session token,
never a participantId taken from a request body.
"""

from __future__ import annotations

import hashlib
import logging
import secrets
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Literal

import psycopg
from psycopg.types.json import Jsonb

from . import errors
from .db import Database
from .errors import PrivacyError
from .wire import (
    Candidate,
    Consent,
    ConsentToggles,
    JoinCommunityRequest,
    MembershipView,
    MemberVersion,
    PrivateIntent,
    PublicParticipant,
    PutIntentRequest,
    SessionView,
    UpdateAvailabilityRequest,
    UpdateConsentRequest,
    format_time,
)

log = logging.getLogger("gq.privacy")

SESSION_TTL = timedelta(days=7)
_ACTOR_KEY = object()


@dataclass(frozen=True)
class Actor:
    """A participant proven by a server-verified session. Construct only via
    ``PrivacyService.resolve`` (or the labeled test helper in fixtures.py)."""

    participant_id: str
    session_id: str
    _key: object

    def __post_init__(self) -> None:
        if self._key is not _ACTOR_KEY:
            raise TypeError("Actor must come from PrivacyService.resolve")


ChangeKind = Literal["consent_granted", "consent_revoked", "intent_updated", "left_community"]


@dataclass(frozen=True)
class ChangeNotice:
    """Invalidation notice. Ids and versions only; never private content."""

    kind: ChangeKind
    participant_id: str
    community_id: str
    consent_version: int | None
    intent_version: int | None
    occurred_at: str


@dataclass(frozen=True)
class VersionCheck:
    current: bool
    stale_participant_ids: tuple[str, ...]
    ineligible_participant_ids: tuple[str, ...]


Listener = Callable[[ChangeNotice], None]


def hash_token(token: str) -> bytes:
    return hashlib.sha256(token.encode("utf-8")).digest()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _db_error(exc: psycopg.Error) -> PrivacyError:
    if exc.sqlstate == "GQ401":
        return errors.unauthenticated()
    if exc.sqlstate == "GQ403":
        return errors.consent_required()
    raise exc


class PrivacyService:
    def __init__(self, db: Database):
        self._db = db
        self._listeners: list[Listener] = []

    def ready(self) -> bool:
        return self._db.ping()

    # ------------------------------------------------------------------ notices
    def add_listener(self, listener: Listener) -> None:
        self._listeners.append(listener)

    def _notify(self, notice: ChangeNotice) -> None:
        for listener in self._listeners:
            try:
                listener(notice)
            except Exception:  # listener failure must not undo a committed revocation
                log.exception("privacy listener failed kind=%s", notice.kind)

    # ----------------------------------------------------------------- sessions
    def create_guest_session(self) -> tuple[str, Actor, datetime]:
        """New pseudonymous participant + session. Returns the raw token once;
        only its SHA-256 hash is stored."""
        token = secrets.token_urlsafe(32)
        with self._db.as_actor(None) as conn:
            row = conn.execute(
                "SELECT * FROM privacy.create_guest_session(%s, %s)",
                (hash_token(token), SESSION_TTL),
            ).fetchone()
        actor = Actor(row["participant_id"], row["session_id"], _ACTOR_KEY)
        return token, actor, row["expires_at"]

    def resolve(self, token: str | None) -> Actor:
        if not token or len(token) > 256:
            raise errors.unauthenticated()
        with self._db.as_actor(None) as conn:
            row = conn.execute(
                "SELECT * FROM privacy.resolve_session(%s)", (hash_token(token),)
            ).fetchone()
        if row is None:
            raise errors.unauthenticated()
        return Actor(row["participant_id"], row["session_id"], _ACTOR_KEY)

    def session_expiry(self, token: str) -> datetime:
        with self._db.as_actor(None) as conn:
            row = conn.execute(
                "SELECT expires_at FROM privacy.resolve_session(%s)", (hash_token(token),)
            ).fetchone()
        if row is None:
            raise errors.unauthenticated()
        return row["expires_at"]

    def revoke_session(self, token: str) -> None:
        with self._db.as_actor(None) as conn:
            conn.execute("SELECT privacy.revoke_session(%s)", (hash_token(token),))

    def session_view(self, actor: Actor, token: str) -> SessionView:
        expires_at = self.session_expiry(token)
        with self._db.as_actor(actor.participant_id) as conn:
            rows = conn.execute(
                """
                SELECT m.community_id, m.display_name, c.version, c.matching,
                       c.model_processing, c.public_interests, c.revoked_at,
                       i.intent_version
                FROM privacy.memberships m
                JOIN privacy.current_consents c
                  ON c.community_id = m.community_id AND c.participant_id = m.participant_id
                LEFT JOIN privacy.private_intents i
                  ON i.community_id = m.community_id AND i.participant_id = m.participant_id
                WHERE m.left_at IS NULL AND m.participant_id = privacy.actor()
                ORDER BY m.joined_at
                """
            ).fetchall()
        return SessionView(
            participant_id=actor.participant_id,
            expires_at=format_time(expires_at),
            memberships=[self._membership_view(actor, r) for r in rows],
        )

    @staticmethod
    def _membership_view(actor: Actor, r: dict) -> MembershipView:
        return MembershipView(
            community_id=r["community_id"],
            display_name=r["display_name"],
            consent=_consent(actor.participant_id, r["community_id"], r),
            has_intent=r["intent_version"] is not None,
            intent_version=r["intent_version"],
        )

    # --------------------------------------------------------------- membership
    def join(self, actor: Actor, community_id: str, req: JoinCommunityRequest) -> MembershipView:
        toggles = req.consent
        with self._db.as_actor(actor.participant_id) as conn:
            if not conn.execute(
                "SELECT 1 FROM privacy.communities WHERE community_id = %s", (community_id,)
            ).fetchone():
                raise errors.not_found()
            existing = conn.execute(
                "SELECT left_at FROM privacy.memberships WHERE community_id = %s AND participant_id = privacy.actor() FOR UPDATE",
                (community_id,),
            ).fetchone()
            if existing is not None and existing["left_at"] is None:
                pass  # already an active member: idempotent, consent changes go through PATCH
            else:
                if existing is None:
                    conn.execute(
                        "INSERT INTO privacy.memberships (community_id, participant_id, display_name)"
                        " VALUES (%s, %s, %s)",
                        (community_id, actor.participant_id, req.display_name),
                    )
                else:
                    conn.execute(
                        "UPDATE privacy.memberships SET left_at = NULL, joined_at = now(),"
                        " display_name = %s WHERE community_id = %s AND participant_id = privacy.actor()",
                        (req.display_name, community_id),
                    )
                conn.execute(
                    """
                    INSERT INTO privacy.consents
                      (participant_id, community_id, version, matching, model_processing, public_interests)
                    SELECT %s, %s, coalesce(max(version), 0) + 1, %s, %s, %s
                    FROM privacy.consents WHERE community_id = %s AND participant_id = privacy.actor()
                    """,
                    (actor.participant_id, community_id, toggles.matching,
                     toggles.model_processing, toggles.public_interests, community_id),
                )
            row = self._own_membership_row(conn, community_id)
        view = self._membership_view(actor, row)
        if existing is None or existing["left_at"] is not None:
            self._notify(ChangeNotice(
                "consent_granted", actor.participant_id, community_id,
                view.consent.version, None, format_time(_now()),
            ))
        return view

    @staticmethod
    def _own_membership_row(conn: psycopg.Connection, community_id: str) -> dict:
        row = conn.execute(
            """
            SELECT m.community_id, m.display_name, c.version, c.matching,
                   c.model_processing, c.public_interests, c.revoked_at, i.intent_version
            FROM privacy.memberships m
            JOIN privacy.current_consents c
              ON c.community_id = m.community_id AND c.participant_id = m.participant_id
            LEFT JOIN privacy.private_intents i
              ON i.community_id = m.community_id AND i.participant_id = m.participant_id
            WHERE m.community_id = %s AND m.left_at IS NULL AND m.participant_id = privacy.actor()
            """,
            (community_id,),
        ).fetchone()
        if row is None:
            raise errors.not_found()
        return row

    def leave_community(self, actor: Actor, community_id: str) -> Consent:
        """Leave: membership ends, all consent withdrawn, private intent deleted."""
        with self._db.as_actor(actor.participant_id) as conn:
            updated = conn.execute(
                "UPDATE privacy.memberships SET left_at = now()"
                " WHERE community_id = %s AND left_at IS NULL AND participant_id = privacy.actor() RETURNING 1",
                (community_id,),
            ).fetchone()
            if updated is None:
                raise errors.not_found()
            conn.execute(
                "DELETE FROM privacy.private_intents WHERE community_id = %s AND participant_id = privacy.actor()", (community_id,)
            )
            row = conn.execute(
                """
                INSERT INTO privacy.consents
                  (participant_id, community_id, version, matching, model_processing,
                   public_interests, revoked_at)
                SELECT %s, %s, max(version) + 1, false, false, false, now()
                FROM privacy.consents WHERE community_id = %s AND participant_id = privacy.actor()
                RETURNING *
                """,
                (actor.participant_id, community_id, community_id),
            ).fetchone()
        consent = _consent(actor.participant_id, community_id, row)
        self._notify(ChangeNotice(
            "left_community", actor.participant_id, community_id,
            consent.version, None, format_time(_now()),
        ))
        return consent

    # ------------------------------------------------------------------ consent
    def get_consent(self, actor: Actor, community_id: str) -> Consent:
        with self._db.as_actor(actor.participant_id) as conn:
            row = self._own_membership_row(conn, community_id)
        return _consent(actor.participant_id, community_id, row)

    def update_consent(self, actor: Actor, community_id: str, req: UpdateConsentRequest) -> Consent:
        wanted: ConsentToggles = req
        try:
            with self._db.as_actor(actor.participant_id) as conn:
                current = self._own_membership_row(conn, community_id)
                if current["version"] != req.expected_version:
                    if current["version"] == req.expected_version + 1 and _same_toggles(current, wanted):
                        return _consent(actor.participant_id, community_id, current)  # retried request
                    raise errors.stale()
                # revokedAt marks withdrawal of participation (matching or model
                # processing). Hiding public interests is a withdrawal too, so it
                # still emits consent_revoked, but it does not set revokedAt.
                participation_revoked = (
                    (current["matching"] and not wanted.matching)
                    or (current["model_processing"] and not wanted.model_processing)
                )
                revoked = participation_revoked or (current["public_interests"] and not wanted.public_interests)
                row = conn.execute(
                    """
                    INSERT INTO privacy.consents
                      (participant_id, community_id, version, matching, model_processing,
                       public_interests, revoked_at)
                    VALUES (%s, %s, %s, %s, %s, %s, CASE WHEN %s THEN now() END)
                    RETURNING *
                    """,
                    (actor.participant_id, community_id, req.expected_version + 1,
                     wanted.matching, wanted.model_processing, wanted.public_interests,
                     participation_revoked),
                ).fetchone()
        except psycopg.errors.UniqueViolation:
            raise errors.stale() from None  # concurrent revision won the race
        consent = _consent(actor.participant_id, community_id, row)
        self._notify(ChangeNotice(
            "consent_revoked" if revoked else "consent_granted",
            actor.participant_id, community_id, consent.version, None, format_time(_now()),
        ))
        return consent

    # ------------------------------------------------------------------ intents
    def get_intent(self, actor: Actor, community_id: str) -> PrivateIntent:
        with self._db.as_actor(actor.participant_id) as conn:
            row = conn.execute(
                "SELECT * FROM privacy.private_intents WHERE community_id = %s AND participant_id = privacy.actor()", (community_id,)
            ).fetchone()
        if row is None:
            raise errors.not_found()
        return _intent(row)

    def put_intent(self, actor: Actor, req: PutIntentRequest) -> PrivateIntent:
        fields = {
            "goal": req.goal,
            "interests": list(req.interests),
            "area_id": req.area_id,
            "time_zone": req.time_zone,
            "availability": [w.wire() for w in req.availability],
            "max_budget_minor": req.max_budget_minor,
            "currency": req.currency,
            "max_duration_minutes": req.max_duration_minutes,
        }
        with self._db.as_actor(actor.participant_id) as conn:
            membership = self._own_membership_row(conn, req.community_id)
            community = conn.execute(
                "SELECT area_ids, currency FROM privacy.communities WHERE community_id = %s",
                (req.community_id,),
            ).fetchone()
            if req.area_id not in community["area_ids"]:
                raise PrivacyError("INVALID_INPUT", "areaId is not part of this community.")
            if req.currency != community["currency"]:
                raise PrivacyError("INVALID_INPUT", "currency must match the community currency.")
            current = conn.execute(
                "SELECT * FROM privacy.private_intents WHERE community_id = %s AND participant_id = privacy.actor() FOR UPDATE",
                (req.community_id,),
            ).fetchone()
            current_version = current["intent_version"] if current else 0
            if current_version != req.expected_version:
                if current and current_version == req.expected_version + 1 and _same_intent(current, fields):
                    return _intent(current)  # retried request
                raise errors.stale()
            params = {**fields, "availability": Jsonb(fields["availability"]),
                      "community_id": req.community_id, "participant_id": actor.participant_id,
                      "consent_version": membership["version"], "expected": req.expected_version}
            if current is None:
                row = conn.execute(
                    """
                    INSERT INTO privacy.private_intents
                      (participant_id, community_id, intent_version, goal, interests, area_id,
                       time_zone, availability, max_budget_minor, currency,
                       max_duration_minutes, consent_version, confirmed_at)
                    VALUES (%(participant_id)s, %(community_id)s, 1, %(goal)s, %(interests)s,
                            %(area_id)s, %(time_zone)s, %(availability)s, %(max_budget_minor)s,
                            %(currency)s, %(max_duration_minutes)s, %(consent_version)s, now())
                    RETURNING *
                    """,
                    params,
                ).fetchone()
            else:
                row = conn.execute(
                    """
                    UPDATE privacy.private_intents SET
                      intent_version = intent_version + 1, goal = %(goal)s,
                      interests = %(interests)s, area_id = %(area_id)s,
                      time_zone = %(time_zone)s, availability = %(availability)s,
                      max_budget_minor = %(max_budget_minor)s, currency = %(currency)s,
                      max_duration_minutes = %(max_duration_minutes)s,
                      consent_version = %(consent_version)s, confirmed_at = now()
                    WHERE community_id = %(community_id)s AND intent_version = %(expected)s
                      AND participant_id = privacy.actor()
                    RETURNING *
                    """,
                    params,
                ).fetchone()
                if row is None:
                    raise errors.stale()
        intent = _intent(row)
        self._notify(ChangeNotice(
            "intent_updated", actor.participant_id, req.community_id,
            intent.consent_version, intent.intent_version, format_time(_now()),
        ))
        return intent

    def update_availability(self, actor: Actor, req: UpdateAvailabilityRequest) -> PrivateIntent:
        windows = [w.wire() for w in req.availability]
        with self._db.as_actor(actor.participant_id) as conn:
            membership = self._own_membership_row(conn, req.community_id)
            current = conn.execute(
                "SELECT * FROM privacy.private_intents WHERE community_id = %s AND participant_id = privacy.actor() FOR UPDATE",
                (req.community_id,),
            ).fetchone()
            if current is None:
                raise errors.not_found()
            if current["intent_version"] != req.expected_version:
                if (current["intent_version"] == req.expected_version + 1
                        and current["availability"] == windows):
                    return _intent(current)
                raise errors.stale()
            row = conn.execute(
                """
                UPDATE privacy.private_intents
                SET intent_version = intent_version + 1, availability = %s,
                    consent_version = %s, confirmed_at = now()
                WHERE community_id = %s AND intent_version = %s AND participant_id = privacy.actor()
                RETURNING *
                """,
                (Jsonb(windows), membership["version"], req.community_id, req.expected_version),
            ).fetchone()
        intent = _intent(row)
        self._notify(ChangeNotice(
            "intent_updated", actor.participant_id, req.community_id,
            intent.consent_version, intent.intent_version, format_time(_now()),
        ))
        return intent

    # ------------------------------------------------------- authorized snapshots
    def reauthorize_for_job(self, enqueued_by: str, community_id: str) -> Actor:
        """WORKER-ONLY. Re-derive an Actor for a queued job.

        ``enqueued_by`` must be the participantId of the verified Actor that
        enqueued the job (stored by the workflow layer at enqueue time), never a
        value from a request body. Membership and consent are rechecked now, so
        a participant who left or revoked consent after enqueueing cannot have
        work executed on their behalf (AGENTS.md: recheck before queued action).
        """
        probe = Actor(enqueued_by, "job", _ACTOR_KEY)
        self.require_eligible(probe, community_id)
        return probe

    def require_eligible(self, actor: Actor, community_id: str) -> None:
        """Guard before enqueueing matching/model work for this actor."""
        with self._db.as_actor(actor.participant_id) as conn:
            row = conn.execute(
                """
                SELECT c.matching AND c.model_processing AS ok
                FROM privacy.memberships m
                JOIN privacy.current_consents c
                  ON c.community_id = m.community_id AND c.participant_id = m.participant_id
                JOIN privacy.private_intents i
                  ON i.community_id = m.community_id AND i.participant_id = m.participant_id
                WHERE m.community_id = %s AND m.left_at IS NULL AND m.participant_id = privacy.actor()
                """,
                (community_id,),
            ).fetchone()
        if row is None or not row["ok"]:
            raise errors.consent_required()

    def authorized_candidates(self, actor: Actor, community_id: str) -> list[Candidate]:
        """Minimized, consent-filtered snapshot for MatchInput.candidates.

        Includes the requester. Excludes anyone who left, lacks matching or
        model-processing consent, or has no confirmed intent. publicInterests is
        empty unless that participant consented to public interests.
        ``intent.consentVersion`` is the consent revision that authorizes this
        snapshot (the current one), so memberVersions can be rechecked later.
        """
        try:
            with self._db.as_actor(actor.participant_id) as conn:
                rows = conn.execute(
                    "SELECT * FROM privacy.authorized_candidates(%s)", (community_id,)
                ).fetchall()
        except psycopg.Error as exc:
            raise _db_error(exc) from None
        return [_candidate(community_id, r) for r in rows]

    def check_member_versions(
        self, actor: Actor, community_id: str, member_versions: Sequence[MemberVersion]
    ) -> VersionCheck:
        """Recheck at write/publish time (WORKFLOW.md step 7). ``current`` is
        False if any member changed intent/consent or is no longer eligible."""
        ids = [m.participant_id for m in member_versions]
        if len(set(ids)) != len(ids):
            raise PrivacyError("INVALID_INPUT", "duplicate participant in memberVersions.")
        try:
            with self._db.as_actor(actor.participant_id) as conn:
                rows = conn.execute(
                    "SELECT * FROM privacy.member_versions(%s, %s)", (community_id, ids)
                ).fetchall()
        except psycopg.Error as exc:
            if exc.sqlstate == "GQ403":
                raise PrivacyError("FORBIDDEN", "Not allowed.") from None
            raise _db_error(exc) from None
        by_id = {r["participant_id"]: r for r in rows}
        stale, ineligible = [], []
        for mv in member_versions:
            r = by_id[mv.participant_id]
            if not r["eligible"]:
                ineligible.append(mv.participant_id)
            elif (r["intent_version"], r["consent_version"]) != (mv.intent_version, mv.consent_version):
                stale.append(mv.participant_id)
        return VersionCheck(not stale and not ineligible, tuple(stale), tuple(ineligible))


# ---------------------------------------------------------------- row mappers
def _consent(participant_id: str, community_id: str, r: dict) -> Consent:
    return Consent(
        participant_id=participant_id,
        community_id=community_id,
        version=r["version"],
        matching=r["matching"],
        model_processing=r["model_processing"],
        public_interests=r["public_interests"],
        revoked_at=format_time(r["revoked_at"]) if r["revoked_at"] else None,
    )


def _same_toggles(row: dict, toggles: ConsentToggles) -> bool:
    return (row["matching"], row["model_processing"], row["public_interests"]) == (
        toggles.matching, toggles.model_processing, toggles.public_interests)


def _same_intent(row: dict, fields: dict) -> bool:
    return all(row[k] == v for k, v in fields.items())


def _intent(r: dict, *, consent_version: int | None = None) -> PrivateIntent:
    return PrivateIntent(
        participant_id=r["participant_id"],
        community_id=r["community_id"],
        intent_version=r["intent_version"],
        goal=r["goal"],
        interests=list(r["interests"]),
        area_id=r["area_id"],
        time_zone=r["time_zone"],
        availability=r["availability"],
        max_budget_minor=int(r["max_budget_minor"]),
        currency=r["currency"],
        max_duration_minutes=r["max_duration_minutes"],
        group_preference="small",
        consent_version=consent_version if consent_version is not None else r["consent_version"],
        confirmed_at=format_time(r["confirmed_at"]),
    )


def _candidate(community_id: str, r: dict) -> Candidate:
    intent = _intent({**r, "community_id": community_id}, consent_version=r["consent_version"])
    profile = PublicParticipant(
        participant_id=r["participant_id"],
        display_name=r["display_name"],
        public_interests=list(r["interests"]) if r["public_interests_consent"] else [],
        is_synthetic=r["is_synthetic"],
    )
    return Candidate(intent=intent, public_profile=profile)
