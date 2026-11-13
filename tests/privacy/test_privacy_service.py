"""Join, sessions, consent and operator role, including adversarial cases. Offline."""

from __future__ import annotations

import pytest

from privacy_helpers import COMMUNITY, consent_req, join_req, joined
from server.privacy.errors import PrivacyError
from server.privacy.fixtures import grant_operator, seed_community, seed_synthetic_players
from server.privacy.service import Actor, hash_token


def code(exc_info) -> str:
    return exc_info.value.code


# ---------------------------------------------------------------- join
def test_join_creates_player_consent_and_session(service):
    result = service.join(COMMUNITY, join_req("Maya"))
    assert result.created and result.token
    view = result.view
    assert view.player.display_name == "Maya" and not view.player.is_synthetic
    assert view.player.avatar_color.startswith("#")
    c = view.consent
    assert (c.match_answers, c.anonymous_chat, c.is_adult, c.version, c.revoked_at) == (True, True, True, 1, None)
    assert view.is_operator is False
    actor = service.require_session(result.token)
    assert (actor.player_id, actor.community_id) == (view.player.player_id, COMMUNITY)


@pytest.mark.parametrize("toggles", [
    {"match": False}, {"chat": False}, {"adult": False}, {"match": False, "chat": False, "adult": False},
])
def test_join_requires_all_three_consents_and_writes_nothing(service, store, toggles):
    with pytest.raises(PrivacyError) as e:
        service.join(COMMUNITY, join_req(**toggles))
    assert code(e) == "CONSENT_REQUIRED"
    with store.tx() as conn:
        assert conn.execute("SELECT count(*) FROM players").fetchone()[0] == 0
        assert conn.execute("SELECT count(*) FROM sessions").fetchone()[0] == 0


def test_join_unknown_community_is_not_found(service):
    with pytest.raises(PrivacyError) as e:
        service.join("no-such-group", join_req())
    assert code(e) == "NOT_FOUND"


def test_join_with_valid_session_is_idempotent(service):
    token, actor = joined(service)
    again = service.join(COMMUNITY, join_req("Different name"), token)
    assert not again.created and again.token is None
    assert again.view.player.player_id == actor.player_id
    assert again.view.player.display_name == "Tester (synthetic)"


def test_join_other_community_issues_separate_scoped_session(service, store):
    seed_community(store, "community-other", "Other Group (synthetic)")
    token, actor = joined(service)
    other = service.join("community-other", join_req(), token)
    assert other.created and other.token != token
    assert service.require_session(other.token).community_id == "community-other"
    assert service.require_session(token).community_id == COMMUNITY


# ------------------------------------------------------------- sessions
@pytest.mark.parametrize("token", [None, "", "x" * 257, "not-a-real-token"])
def test_bad_tokens_are_unauthenticated(service, token):
    joined(service)
    with pytest.raises(PrivacyError) as e:
        service.require_session(token)
    assert code(e) == "UNAUTHENTICATED"


def test_only_token_hash_is_stored(service, store):
    token, _ = joined(service)
    with store.tx() as conn:
        rows = conn.execute("SELECT token_hash FROM sessions").fetchall()
    assert [bytes(r[0]) for r in rows] == [hash_token(token)]
    assert token.encode() not in bytes(rows[0][0])


def test_session_expires(service, clock):
    token, _ = joined(service)
    clock.advance(days=7)
    with pytest.raises(PrivacyError):
        service.require_session(token)


def test_end_session_revokes_only_that_session(service):
    token, actor = joined(service)
    other_token, _ = joined(service, "Other")
    service.end_session(actor)
    with pytest.raises(PrivacyError):
        service.require_session(token)
    assert service.require_session(other_token)


def test_actor_cannot_be_forged():
    with pytest.raises(TypeError):
        Actor("p-maya", "s_x", COMMUNITY, True, object())


def test_synthetic_players_never_hold_sessions(service, store, clock):
    ids = seed_synthetic_players(store)
    assert "p-maya" in ids
    # Even if a session row were planted for a synthetic player, it never resolves.
    token = "planted-token-for-synthetic"
    with store.tx() as conn:
        conn.execute(
            "INSERT INTO sessions (session_id, token_hash, player_id, community_id, created_at, expires_at)"
            " VALUES ('s_planted', ?, 'p-maya', ?, '2026-11-01T00:00:00Z', '2099-01-01T00:00:00Z')",
            (hash_token(token), COMMUNITY),
        )
    with pytest.raises(PrivacyError):
        service.require_session(token)


def test_synthetic_seed_is_idempotent_and_labeled(store):
    seed_synthetic_players(store)
    seed_synthetic_players(store)
    with store.tx() as conn:
        rows = conn.execute("SELECT display_name, is_synthetic FROM players").fetchall()
    assert len(rows) == 8 and all(r["is_synthetic"] == 1 for r in rows)
    assert all("(synthetic)" in r["display_name"] for r in rows)


# --------------------------------------------------------------- consent
def test_withdraw_sets_revoked_and_regrant_clears(service, clock):
    _, actor = joined(service)
    clock.advance(minutes=5)
    c2 = service.update_consent(actor, consent_req(1, chat=False))
    assert c2.version == 2 and not c2.anonymous_chat and c2.revoked_at == "2026-11-11T17:05:00Z"
    with pytest.raises(PrivacyError) as e:
        service.require_consent(actor)
    assert code(e) == "CONSENT_REQUIRED"
    c3 = service.update_consent(actor, consent_req(2))
    assert c3.version == 3 and c3.revoked_at is None
    assert service.require_consent(actor).version == 3


def test_partial_regrant_stays_revoked(service):
    _, actor = joined(service)
    c2 = service.update_consent(actor, consent_req(1, match=False, adult=False))
    c3 = service.update_consent(actor, consent_req(2, adult=False))
    assert c3.revoked_at == c2.revoked_at is not None


def test_stale_version_rejected(service):
    _, actor = joined(service)
    service.update_consent(actor, consent_req(1, chat=False))
    with pytest.raises(PrivacyError) as e:
        service.update_consent(actor, consent_req(1, match=False))
    assert code(e) == "STALE_REVISION"


def test_retried_request_returns_stored_row(service):
    _, actor = joined(service)
    first = service.update_consent(actor, consent_req(1, chat=False))
    assert service.update_consent(actor, consent_req(1, chat=False)) == first


def test_noop_update_creates_no_revision(service):
    _, actor = joined(service)
    assert service.update_consent(actor, consent_req(1)).version == 1


def test_consent_is_scoped_to_the_session_player(service):
    _, maya = joined(service, "Maya")
    _, dev = joined(service, "Dev")
    service.update_consent(dev, consent_req(1, match=False))
    assert service.get_consent(maya).match_answers is True
    assert service.get_consent(maya).player_id == maya.player_id


def test_listeners_get_ids_and_versions_only(service):
    notices = []
    service.add_listener(notices.append)
    service.add_listener(lambda n: (_ for _ in ()).throw(RuntimeError("listener down")))
    _, actor = joined(service)
    service.update_consent(actor, consent_req(1, adult=False))
    service.update_consent(actor, consent_req(2))
    assert [(n.kind, n.consent_version) for n in notices] == [
        ("consent_granted", 1), ("consent_revoked", 2), ("consent_granted", 3),
    ]
    assert set(vars(notices[0])) == {"kind", "player_id", "community_id", "consent_version", "occurred_at"}
    assert service.get_consent(actor).version == 3  # failing listener did not undo the commit


# -------------------------------------------------------------- operator
def test_operator_role_only_via_local_grant(service, store):
    token, actor = joined(service)
    assert actor.is_operator is False
    with pytest.raises(PrivacyError) as e:
        service.require_operator(actor)
    assert code(e) == "FORBIDDEN"
    grant_operator(store, actor.player_id, COMMUNITY)
    promoted = service.require_session(token)
    assert promoted.is_operator
    service.require_operator(promoted)
    assert service.session_view(promoted).is_operator is True


def test_grant_operator_requires_membership(store):
    with pytest.raises(LookupError):
        grant_operator(store, "p_nobody", COMMUNITY)
