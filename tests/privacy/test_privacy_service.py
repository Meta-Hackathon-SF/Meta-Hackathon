"""Privacy service behavior against real Postgres with non-bypass credentials."""

from __future__ import annotations

import threading

import pytest

from privacy_helpers import COMMUNITY, consent_req, eligible_member, intent_req, join_req, window
from server.privacy.errors import PrivacyError
from server.privacy.fixtures import seed_synthetic_profiles
from server.privacy.service import Actor, hash_token
from server.privacy.wire import MemberVersion, UpdateAvailabilityRequest


def code(exc_info) -> str:
    return exc_info.value.code


# ------------------------------------------------------------------ sessions
def test_session_round_trip_and_revoke(service):
    token, actor, _ = service.create_guest_session()
    assert service.resolve(token).participant_id == actor.participant_id
    service.revoke_session(token)
    with pytest.raises(PrivacyError) as exc:
        service.resolve(token)
    assert code(exc) == "UNAUTHENTICATED"


@pytest.mark.parametrize("token", [None, "", "not-a-token", "x" * 300])
def test_unknown_tokens_rejected(service, token):
    with pytest.raises(PrivacyError) as exc:
        service.resolve(token)
    assert code(exc) == "UNAUTHENTICATED"


def test_raw_token_not_stored(service, admin):
    token, _, _ = service.create_guest_session()
    stored = admin.execute("SELECT token_hash FROM privacy.sessions").fetchone()[0]
    assert bytes(stored) == hash_token(token) and token.encode() not in bytes(stored)


def test_expired_session_rejected(service, admin):
    token, _, _ = service.create_guest_session()
    admin.execute("UPDATE privacy.sessions SET created_at = now() - interval '9 days',"
                  " expires_at = now() - interval '1 second'")
    with pytest.raises(PrivacyError):
        service.resolve(token)


def test_synthetic_profile_cannot_be_impersonated(service, admin):
    [synthetic_id, *_] = seed_synthetic_profiles(admin)
    token = "fixture-impersonation-attempt"
    admin.execute(
        "INSERT INTO privacy.sessions (token_hash, participant_id, expires_at)"
        " VALUES (%s, %s, now() + interval '1 day')",
        (hash_token(token), synthetic_id),
    )
    with pytest.raises(PrivacyError) as exc:
        service.resolve(token)
    assert code(exc) == "UNAUTHENTICATED"


def test_actor_cannot_be_constructed_from_a_claimed_id():
    with pytest.raises(TypeError):
        Actor("p_forged", "s_forged", object())


# ---------------------------------------------------------- membership/consent
def test_join_creates_consent_v1_and_is_idempotent(service):
    _, actor, _ = service.create_guest_session()
    first = service.join(actor, COMMUNITY, join_req("A", model=False))
    again = service.join(actor, COMMUNITY, join_req("A2"))
    assert first.consent.version == again.consent.version == 1
    assert again.consent.model_processing is False  # join does not silently grant consent
    assert again.display_name == "A"


def test_join_unknown_community(service):
    _, actor, _ = service.create_guest_session()
    with pytest.raises(PrivacyError) as exc:
        service.join(actor, "nope", join_req())
    assert code(exc) == "NOT_FOUND"


def test_consent_versioning_stale_and_retry(service):
    _, actor = eligible_member(service, "A")
    notices = []
    service.add_listener(notices.append)
    v2 = service.update_consent(actor, COMMUNITY, consent_req(1, model=False))
    assert v2.version == 2 and v2.revoked_at is not None
    assert service.update_consent(actor, COMMUNITY, consent_req(1, model=False)) == v2  # retry
    with pytest.raises(PrivacyError) as exc:
        service.update_consent(actor, COMMUNITY, consent_req(1, model=True))
    assert code(exc) == "STALE_REVISION"
    v3 = service.update_consent(actor, COMMUNITY, consent_req(2, model=True))
    assert v3.version == 3 and v3.revoked_at is None
    assert [n.kind for n in notices] == ["consent_revoked", "consent_granted"]
    assert all(not hasattr(n, "goal") for n in notices)


def test_concurrent_consent_updates_single_winner(service):
    _, actor = eligible_member(service, "A")
    results = []

    def attempt(model: bool):
        try:
            results.append(service.update_consent(actor, COMMUNITY, consent_req(1, model=model)).version)
        except PrivacyError as exc:
            results.append(exc.code)

    threads = [threading.Thread(target=attempt, args=(i % 2 == 0,)) for i in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert service.get_consent(actor, COMMUNITY).version == 2
    assert results.count("STALE_REVISION") >= 3


def test_consent_requires_membership(service):
    _, actor, _ = service.create_guest_session()
    with pytest.raises(PrivacyError) as exc:
        service.update_consent(actor, COMMUNITY, consent_req(1))
    assert code(exc) == "NOT_FOUND"


# ------------------------------------------------------------------- intents
def test_intent_create_update_stale_and_retry(service):
    _, actor, _ = service.create_guest_session()
    service.join(actor, COMMUNITY, join_req())
    v1 = service.put_intent(actor, intent_req(0))
    assert v1.intent_version == 1 and v1.participant_id == actor.participant_id
    assert service.put_intent(actor, intent_req(0)) == v1  # retried create
    with pytest.raises(PrivacyError) as exc:
        service.put_intent(actor, intent_req(0, maxBudgetMinor=0))
    assert code(exc) == "STALE_REVISION"
    v2 = service.put_intent(actor, intent_req(1, maxBudgetMinor=0))
    assert v2.intent_version == 2 and v2.max_budget_minor == 0
    assert service.get_intent(actor, COMMUNITY) == v2


def test_intent_requires_membership(service):
    _, actor, _ = service.create_guest_session()
    with pytest.raises(PrivacyError) as exc:
        service.put_intent(actor, intent_req())
    assert code(exc) == "NOT_FOUND"


@pytest.mark.parametrize("override", [{"areaId": "elsewhere"}, {"currency": "EUR"}])
def test_intent_must_fit_community(service, override):
    _, actor, _ = service.create_guest_session()
    service.join(actor, COMMUNITY, join_req())
    with pytest.raises(PrivacyError) as exc:
        service.put_intent(actor, intent_req(**override))
    assert code(exc) == "INVALID_INPUT"


def test_other_member_intent_invisible(service):
    _, a = eligible_member(service, "A")
    _, b, _ = service.create_guest_session()
    service.join(b, COMMUNITY, join_req("B"))
    with pytest.raises(PrivacyError) as exc:
        service.get_intent(b, COMMUNITY)
    assert code(exc) == "NOT_FOUND"  # B sees only B's (absent) intent, never A's


def test_availability_update_bumps_version_and_notifies(service):
    _, actor = eligible_member(service, "A")
    notices = []
    service.add_listener(notices.append)
    req = UpdateAvailabilityRequest.model_validate(
        {"communityId": COMMUNITY, "expectedVersion": 1, "availability": [window(2)]})
    updated = service.update_availability(actor, req)
    assert updated.intent_version == 2 and updated.availability[0].start == window(2)["start"]
    assert service.update_availability(actor, req) == updated  # retry
    assert notices[-1].kind == "intent_updated" and notices[-1].intent_version == 2


# ------------------------------------------------------- candidate snapshots
def test_snapshot_filters_consent_and_minimizes(service, admin):
    synthetic = seed_synthetic_profiles(admin)
    _, requester = eligible_member(service, "Req")
    _, no_model = eligible_member(service, "NoModel", model=False)
    _, no_match = eligible_member(service, "NoMatch", matching=False)
    _, private = eligible_member(service, "Private", public=False)
    _, leaver = eligible_member(service, "Leaver")
    service.leave_community(leaver, COMMUNITY)
    _, no_intent, _ = service.create_guest_session()
    service.join(no_intent, COMMUNITY, join_req("NoIntent"))

    candidates = service.authorized_candidates(requester, COMMUNITY)
    ids = {c.public_profile.participant_id for c in candidates}
    assert ids == {requester.participant_id, private.participant_id, *synthetic}
    by_id = {c.public_profile.participant_id: c for c in candidates}
    assert by_id[private.participant_id].public_profile.public_interests == []
    assert by_id[requester.participant_id].public_profile.public_interests == ["board games", "coffee"]
    assert all(by_id[s].public_profile.is_synthetic for s in synthetic)
    assert not by_id[requester.participant_id].public_profile.is_synthetic
    assert all(c.intent.community_id == COMMUNITY for c in candidates)


def test_snapshot_denied_to_ineligible_requester(service):
    eligible_member(service, "A")
    _, opted_out = eligible_member(service, "B", model=False)
    with pytest.raises(PrivacyError) as exc:
        service.authorized_candidates(opted_out, COMMUNITY)
    assert code(exc) == "CONSENT_REQUIRED"
    with pytest.raises(PrivacyError):
        service.require_eligible(opted_out, COMMUNITY)


def test_snapshot_is_community_scoped(service):
    _, a = eligible_member(service, "A")
    with pytest.raises(PrivacyError) as exc:
        service.authorized_candidates(a, "other-campus")
    assert code(exc) == "CONSENT_REQUIRED"


def test_revocation_removes_candidate_immediately(service):
    _, a = eligible_member(service, "A")
    _, b = eligible_member(service, "B")
    assert len(service.authorized_candidates(a, COMMUNITY)) == 2
    service.update_consent(b, COMMUNITY, consent_req(1, matching=False))
    assert [c.public_profile.participant_id for c in service.authorized_candidates(a, COMMUNITY)] == [
        a.participant_id]


# --------------------------------------------------------- publication recheck
def _versions(candidates):
    return [MemberVersion(participant_id=c.intent.participant_id,
                          intent_version=c.intent.intent_version,
                          consent_version=c.intent.consent_version) for c in candidates]


def test_member_versions_detect_stale_and_revoked(service):
    _, a = eligible_member(service, "A")
    _, b = eligible_member(service, "B")
    _, c = eligible_member(service, "C")
    versions = _versions(service.authorized_candidates(a, COMMUNITY))
    assert service.check_member_versions(a, COMMUNITY, versions).current

    service.put_intent(b, intent_req(1, maxDurationMinutes=60))
    service.update_consent(c, COMMUNITY, consent_req(1, model=False))
    check = service.check_member_versions(a, COMMUNITY, versions)
    assert not check.current
    assert check.stale_participant_ids == (b.participant_id,)
    assert check.ineligible_participant_ids == (c.participant_id,)


def test_member_versions_require_actor_in_group(service):
    _, a = eligible_member(service, "A")
    _, b = eligible_member(service, "B")
    _, outsider = eligible_member(service, "Outsider")
    versions = _versions(service.authorized_candidates(a, COMMUNITY))
    versions = [v for v in versions if v.participant_id != outsider.participant_id]
    with pytest.raises(PrivacyError) as exc:
        service.check_member_versions(outsider, COMMUNITY, versions)
    assert code(exc) == "FORBIDDEN"


def test_leave_deletes_private_intent(service, admin):
    _, a = eligible_member(service, "A")
    consent = service.leave_community(a, COMMUNITY)
    assert not (consent.matching or consent.model_processing or consent.public_interests)
    assert consent.revoked_at is not None
    assert admin.execute("SELECT count(*) FROM privacy.private_intents WHERE participant_id = %s",
                         (a.participant_id,)).fetchone()[0] == 0
    with pytest.raises(PrivacyError):
        service.get_consent(a, COMMUNITY)
    rejoined = service.join(a, COMMUNITY, join_req("A", matching=False))
    assert rejoined.consent.version == 3 and rejoined.has_intent is False


# ------------------------------------------------------------- queued jobs
def test_job_reauthorization_rechecks_consent(service):
    _, a = eligible_member(service, "A")
    job_actor = service.reauthorize_for_job(a.participant_id, COMMUNITY)
    assert service.authorized_candidates(job_actor, COMMUNITY)
    service.update_consent(a, COMMUNITY, consent_req(1, model=False))
    with pytest.raises(PrivacyError) as exc:
        service.reauthorize_for_job(a.participant_id, COMMUNITY)
    assert code(exc) == "CONSENT_REQUIRED"


def test_job_reauthorization_rejects_left_or_unknown(service):
    _, a = eligible_member(service, "A")
    service.leave_community(a, COMMUNITY)
    for pid in (a.participant_id, "p_does_not_exist"):
        with pytest.raises(PrivacyError):
            service.reauthorize_for_job(pid, COMMUNITY)


def test_revoked_at_marks_participation_withdrawal_only(service):
    _, actor = eligible_member(service, "A")
    notices = []
    service.add_listener(notices.append)
    hidden = service.update_consent(actor, COMMUNITY, consent_req(1, public=False))
    assert hidden.revoked_at is None and hidden.matching and hidden.model_processing
    assert notices[-1].kind == "consent_revoked"  # profile visibility changed: projections must refresh
    stopped = service.update_consent(actor, COMMUNITY, consent_req(2, public=False, matching=False))
    assert stopped.revoked_at is not None


def test_ready_reports_database(service):
    assert service.ready() is True
