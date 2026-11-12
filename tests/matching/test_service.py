"""Tests for MatchingService using the synthetic fixtures and a fake Muse port."""
import asyncio
import copy
import json

import pytest

from server.matching.models import GroupProposal, Matched, MatchingError, NoMatch
from server.matching.service import MatchingService, is_stale, public_projection
from server.matching.models import Candidate
from tests.matching.fixtures import (
    DEMO_POOL, FakeMusePort, make_candidate, make_match_input,
)

REQ = "p_ava"
PRIVATE_KEYS = ("maxBudgetMinor", "availability", "areaId", "goal", "memberVersions",
                "feasibleWindows")


def run(coro):
    return asyncio.run(coro)


def service(responses=None):
    port = FakeMusePort(responses)
    return MatchingService(port, id_factory=lambda: "prop_fixed"), port


def demo_input(pool=None):
    return make_match_input(pool if pool is not None else DEMO_POOL, REQ)


def matched():
    svc, _ = service()
    return svc, run(svc.match(demo_input()))


def test_happy_path_matches_demo_pool():
    svc, result = matched()
    assert isinstance(result, Matched)
    p = result.proposal
    assert 3 <= len(p.member_ids) <= 5
    assert REQ in p.member_ids
    assert p.revision == 1 and p.proposal_id == "prop_fixed"
    assert not {"p_fay", "p_gus", "p_hal"} & set(p.member_ids)
    assert GroupProposal.from_dict(p.to_dict()) == p


def test_member_versions_match_intents():
    pool = [copy.deepcopy(c) for c in DEMO_POOL]
    pool[1]["intent"]["intentVersion"] = 4
    pool[1]["intent"]["consentVersion"] = 2
    svc, _ = service()
    result = run(svc.match(demo_input(pool)))
    versions = {v.participant_id: (v.intent_version, v.consent_version)
                for v in result.proposal.member_versions}
    assert set(versions) == set(result.proposal.member_ids)
    for c in pool:
        pid = c["intent"]["participantId"]
        if pid in versions:
            assert versions[pid] == (c["intent"]["intentVersion"],
                                     c["intent"]["consentVersion"])


def test_muse_receives_no_private_data():
    svc, port = service()
    run(svc.match(demo_input()))
    blob = json.dumps(port.calls[0]["payload"])
    for key in ("maxBudgetMinor", "areaId", "availability", "p_ava", "Synthetic"):
        assert key not in blob


@pytest.mark.parametrize("bad", [{}, {"context": {}}, None, "x", [1]])
def test_malformed_input_is_invalid_input(bad):
    svc, _ = service()
    with pytest.raises(MatchingError) as exc:
        run(svc.match(bad))
    assert exc.value.code == "INVALID_INPUT" and exc.value.retryable is False


def test_unknown_field_is_invalid_input():
    raw = demo_input()
    raw["extra"] = 1
    svc, _ = service()
    with pytest.raises(MatchingError) as exc:
        run(svc.match(raw))
    assert exc.value.code == "INVALID_INPUT"


def test_requester_absent_is_forbidden():
    svc, port = service()
    with pytest.raises(MatchingError) as exc:
        run(svc.match(make_match_input(DEMO_POOL, "p_nobody")))
    assert exc.value.code == "FORBIDDEN" and exc.value.retryable is False
    assert port.calls == ()


def test_no_match_too_few():
    pool = [make_candidate("p_ava", "Ava", ["coffee"]),
            make_candidate("p_ben", "Ben", ["coffee"])]
    svc, port = service()
    result = run(svc.match(demo_input(pool)))
    assert isinstance(result, NoMatch) and result.reason == "too_few"
    assert result.suggestions and port.calls == ()
    assert "Ben" not in json.dumps(result.to_dict())


def test_no_match_no_common_time():
    other = {"availability": [{"start": "2026-11-15T18:00:00Z",
                               "end": "2026-11-15T21:00:00Z"}]}
    pool = [make_candidate("p_ava", "Ava", ["coffee"]),
            make_candidate("p_ben", "Ben", ["coffee"], **other),
            make_candidate("p_cy", "Cy", ["coffee"], **other)]
    svc, _ = service()
    result = run(svc.match(demo_input(pool)))
    assert isinstance(result, NoMatch) and result.reason == "no_common_time"
    text = json.dumps(result.to_dict())
    assert all(n not in text for n in ("Ben", "Cy", "p_ben", "p_cy"))


def test_provider_down_is_retryable_provider_unavailable():
    svc, _ = service([RuntimeError("boom"), RuntimeError("boom")])
    with pytest.raises(MatchingError) as exc:
        run(svc.match(demo_input()))
    assert exc.value.code == "PROVIDER_UNAVAILABLE" and exc.value.retryable is True


def test_invalid_muse_output_is_provider_unavailable():
    bad = {"optionId": "g99", "sharedInterests": [], "reasonCodes": ["strong_shared_interest"]}
    svc, _ = service([bad, bad])
    with pytest.raises(MatchingError) as exc:
        run(svc.match(demo_input()))
    assert exc.value.code == "PROVIDER_UNAVAILABLE"


def test_recompute_bumps_revision_and_drops_removed_member():
    svc, first = matched()
    prior = first.proposal
    removed = next(m for m in prior.member_ids if m != REQ)
    pool = [c for c in DEMO_POOL if c["intent"]["participantId"] != removed]
    result = run(svc.recompute(prior, demo_input(pool)))
    assert isinstance(result, Matched)
    assert result.proposal.revision == prior.revision + 1
    assert result.proposal.proposal_id == prior.proposal_id
    assert removed not in result.proposal.member_ids


def test_recompute_can_return_no_match():
    svc, first = matched()
    pool = [c for c in DEMO_POOL if c["intent"]["participantId"] in (REQ, "p_ben")]
    result = run(svc.recompute(first.proposal, demo_input(pool)))
    assert isinstance(result, NoMatch)


def _candidates(pool):
    return [Candidate.from_dict(c) for c in pool]


def test_is_stale_false_when_unchanged():
    _, first = matched()
    assert is_stale(first.proposal, _candidates(DEMO_POOL)) is False


def test_is_stale_on_version_bump_and_removal():
    _, first = matched()
    member = next(m for m in first.proposal.member_ids if m != REQ)
    bumped = copy.deepcopy(DEMO_POOL)
    consent = copy.deepcopy(DEMO_POOL)
    for c in bumped:
        if c["intent"]["participantId"] == member:
            c["intent"]["intentVersion"] = 2
    for c in consent:
        if c["intent"]["participantId"] == member:
            c["intent"]["consentVersion"] = 2
    removed = [c for c in DEMO_POOL if c["intent"]["participantId"] != member]
    for pool in (bumped, consent, removed):
        assert is_stale(first.proposal, _candidates(pool)) is True


def test_public_projection_matched_omits_private_data():
    _, first = matched()
    profiles = {c.participant_id: c.public_profile for c in _candidates(DEMO_POOL)}
    out = public_projection(first, profiles)
    text = json.dumps(out)
    for key in PRIVATE_KEYS:
        assert key not in text
    assert out["status"] == "matched"
    members = out["proposal"]["members"]
    assert len(members) == len(first.proposal.member_ids)
    assert all(m["isSynthetic"] is True for m in members)


def test_public_projection_missing_profile_fails_closed():
    _, first = matched()
    with pytest.raises(MatchingError):
        public_projection(first, {})


def test_public_projection_no_match():
    out = public_projection(NoMatch("too_few", ("Invite more community members to opt in",)), {})
    assert out == {"status": "no_match", "reason": "too_few",
                   "suggestions": ["Invite more community members to opt in"]}


def test_live_mode_rejects_replay_evidence():
    from server.matching.models import MatchingError
    from server.matching.service import MatchingService
    from tests.matching.fixtures import DEMO_POOL, FakeMusePort, make_match_input

    inp = make_match_input(DEMO_POOL, "p_ava", mode="live")
    service = MatchingService(FakeMusePort())  # fake port labels evidence "replay"
    with pytest.raises(MatchingError) as exc:
        asyncio.run(service.match(inp))
    assert exc.value.code == "PROVIDER_UNAVAILABLE"
    assert exc.value.retryable is False
