"""Offline lifecycle evidence using synthetic IDs and fixture-labeled plans only."""

import copy
import re
from pathlib import Path

import pytest

from server.orchestration.domain import (
    decide_acceptance,
    decide_publication,
    requires_reconfirmation,
)
from server.orchestration.wire import (
    GroupProposal,
    MemberVersion,
    ModelEvidence,
    QuestPlan,
    Window,
    WorkflowError,
    validate_acceptance,
    validate_acceptance_record,
    validate_message,
    validate_plan,
    validate_plan_for_proposal,
    validate_proposal,
    validate_snapshot,
)

MEMBERS = ["synthetic-a", "synthetic-b", "synthetic-c"]


def proposal() -> dict:
    return {
        "proposalId": "proposal-synthetic",
        "communityId": "community-synthetic",
        "revision": 1,
        "memberIds": list(MEMBERS),
        "memberVersions": [
            {"participantId": participant, "intentVersion": 1, "consentVersion": 1}
            for participant in MEMBERS
        ],
        "feasibleWindows": [{"start": "2026-11-14T18:00:00Z", "end": "2026-11-14T20:00:00Z"}],
        "sharedInterests": ["photography"],
        "publicRationale": "Shared interest in photography.",
        "evidence": {
            "model": "fixture:lifecycle",
            "source": "replay",
            "generatedAt": "2026-11-12T21:00:00Z",
            "latencyMs": 0,
        },
    }


def plan() -> dict:
    fixture = proposal()
    return {
        "planId": "plan-synthetic",
        "proposalId": fixture["proposalId"],
        "revision": 1,
        "basedOnRevision": None,
        "memberVersions": fixture["memberVersions"],
        "title": "A shared photo walk",
        "activity": "Walk around the public plaza together.",
        "collaborationTask": "Create a three-photo story together.",
        "venueId": "venue-synthetic",
        "start": "2026-11-14T18:30:00Z",
        "end": "2026-11-14T19:00:00Z",
        "timeZone": "UTC",
        "costPerPersonMinor": 0,
        "currency": "USD",
        "minimumSize": 3,
        "maximumSize": 5,
        "publicRationale": "A free shared activity fits the group.",
        "opener": "What would you each like to photograph?",
        "evidence": fixture["evidence"],
    }


def decision(*, status="proposed", accepted=None, participant=MEMBERS[0], choice="accept", **kw):
    return decide_acceptance(status, 1, 1, list(MEMBERS), accepted or [], participant, choice, **kw)


def assert_code(code: str, operation) -> None:
    with pytest.raises(WorkflowError) as caught:
        operation()
    assert caught.value.code == code
    assert str(caught.value) == code


def test_first_two_acceptances_do_not_finalize_third_freezes_once():
    accepted = []
    for index, participant in enumerate(MEMBERS):
        outcome = decision(accepted=accepted, participant=participant)
        assert outcome["status"] == ("planning" if index == 2 else "proposed")
        assert outcome["enqueueFinalization"] is (index == 2)
        accepted = outcome["acceptedIds"]
    retry = decision(status="planning", accepted=accepted)
    assert retry == {
        "status": "planning",
        "acceptedIds": sorted(MEMBERS),
        "declinedIds": [],
        "enqueueFinalization": False,
    }


def test_duplicate_accept_before_quorum_does_not_change_count_or_enqueue():
    accepted = [MEMBERS[0]]
    outcome = decision(accepted=accepted)
    assert outcome["acceptedIds"] == accepted
    assert outcome["enqueueFinalization"] is False


def test_decline_removes_acceptance_and_is_sticky_until_a_new_revision():
    outcome = decision(accepted=[MEMBERS[0], MEMBERS[1]], choice="decline")
    assert outcome["acceptedIds"] == [MEMBERS[1]]
    assert outcome["declinedIds"] == [MEMBERS[0]]
    assert outcome["status"] == "proposed"
    assert_code("STALE_REVISION", lambda: decision(declined_ids=outcome["declinedIds"]))
    retry = decision(accepted=[MEMBERS[1]], choice="decline", declined_ids=[MEMBERS[0]])
    assert retry["acceptedIds"] == [MEMBERS[1]]
    assert retry["declinedIds"] == [MEMBERS[0]]
    # The new proposed revision starts a new explicit vote.
    fresh = decide_acceptance("proposed", 2, 2, MEMBERS, [], MEMBERS[0], "accept")
    assert fresh["acceptedIds"] == [MEMBERS[0]]


@pytest.mark.parametrize("status", ["planning", "scheduled"])
def test_frozen_quorum_cannot_gain_late_acceptance_or_change_votes(status):
    members = MEMBERS + ["synthetic-d", "synthetic-e"]
    assert_code(
        "STALE_REVISION",
        lambda: decide_acceptance(status, 1, 1, members, MEMBERS, "synthetic-d", "accept"),
    )
    assert_code(
        "STALE_REVISION",
        lambda: decide_acceptance(status, 1, 1, members, MEMBERS, MEMBERS[0], "decline"),
    )


def test_scheduled_repeat_accept_is_idempotent_and_never_requeues():
    outcome = decision(status="scheduled", accepted=MEMBERS)
    assert outcome["status"] == "scheduled"
    assert outcome["enqueueFinalization"] is False


@pytest.mark.parametrize("status", ["forming", "revision_pending", "cancelled", "completed"])
def test_non_voting_states_require_a_fresh_proposal(status):
    assert_code("STALE_REVISION", lambda: decision(status=status))


def test_outsiders_and_stale_revision_cannot_accept():
    assert_code("FORBIDDEN", lambda: decision(participant="synthetic-outsider"))
    assert_code(
        "STALE_REVISION",
        lambda: decide_acceptance("proposed", 2, 1, MEMBERS, [], MEMBERS[0], "accept"),
    )


@pytest.mark.parametrize(
    "args",
    [
        ("proposed", True, 1, MEMBERS, [], MEMBERS[0], "accept"),
        ("proposed", 1, True, MEMBERS, [], MEMBERS[0], "accept"),
        ("proposed", 1, 1, MEMBERS + [MEMBERS[0]], [], MEMBERS[0], "accept"),
        ("proposed", 1, 1, MEMBERS, ["synthetic-outsider"], MEMBERS[0], "accept"),
        ("proposed", 1, 1, MEMBERS, MEMBERS, MEMBERS[0], "accept"),
        ("planning", 1, 1, MEMBERS, [], MEMBERS[0], "accept"),
    ],
)
def test_invalid_state_facts_fail_closed(args):
    assert_code("INVALID_INPUT", lambda: decide_acceptance(*args))


def test_decisions_do_not_mutate_input_collections():
    members, accepted, declined = list(MEMBERS), [MEMBERS[0]], [MEMBERS[2]]
    before = copy.deepcopy((members, accepted, declined))
    decide_acceptance(
        "proposed", 1, 1, members, accepted, MEMBERS[1], "accept", declined_ids=declined
    )
    assert (members, accepted, declined) == before


@pytest.mark.parametrize(
    "raw",
    [
        {"revision": True, "choice": "accept"},
        {"revision": "1", "choice": "accept"},
        {"revision": 0, "choice": "accept"},
        {"revision": 1, "choice": "approve"},
        {"revision": 1, "choice": "accept", "participantId": "synthetic-outsider"},
        {"revision": 1, "choice": "accept", "mode": "fixture"},
    ],
)
def test_acceptance_wire_rejects_coercion_identity_and_mode_escalation(raw):
    assert_code("INVALID_INPUT", lambda: validate_acceptance(raw))


def test_valid_acceptance_has_exact_public_command_fields():
    assert validate_acceptance({"revision": 1, "choice": "accept"}) == {
        "revision": 1,
        "choice": "accept",
    }


def snapshot() -> dict:
    return {
        "questId": "quest-synthetic",
        "communityId": "community-synthetic",
        "revision": 1,
        "status": "scheduled",
        "acceptedCount": 3,
        "capacity": 5,
        "minimumSize": 3,
        "members": [
            {
                "participantId": participant,
                "displayName": "Synthetic demo person",
                "publicInterests": ["photography"],
                "isSynthetic": True,
            }
            for participant in MEMBERS
        ],
        "event": {
            "eventId": "event-synthetic",
            "questId": "quest-synthetic",
            "planId": "plan-synthetic",
            "revision": 1,
            "status": "scheduled",
            "title": "A shared photo walk",
            "venueId": "venue-synthetic",
            "start": "2026-11-14T18:30:00Z",
            "end": "2026-11-14T19:00:00Z",
            "acceptedMemberIds": list(MEMBERS),
            "conversationId": "conversation-synthetic",
        },
    }


def test_snapshot_has_exact_public_fields_and_preserves_synthetic_flags():
    fixture = snapshot()
    assert validate_snapshot(fixture) == fixture
    for member in validate_snapshot(fixture)["members"]:
        assert member["isSynthetic"] is True


@pytest.mark.parametrize(
    "mutation",
    [
        lambda raw: raw.update(memberVersions=proposal()["memberVersions"]),
        lambda raw: raw["members"][0].update(maxBudgetMinor=1000),
        lambda raw: raw["members"][0].update(isSynthetic="false"),
        lambda raw: raw["event"].update(opener="synthetic-private-value"),
        lambda raw: raw["event"].update(questId="another-quest"),
        lambda raw: raw.update(acceptedCount=True),
        lambda raw: raw.update(acceptedCount=4),
        lambda raw: raw.update(capacity=5.0),
        lambda raw: raw["event"].update(acceptedMemberIds=MEMBERS[:2]),
    ],
)
def test_snapshot_rejects_private_fields_and_invalid_public_state(mutation):
    raw = snapshot()
    mutation(raw)
    assert_code("INVALID_INPUT", lambda: validate_snapshot(raw))


def test_revision_pending_may_retain_prior_event_for_visible_history():
    raw = snapshot()
    raw.update(status="revision_pending", revision=2, acceptedCount=0)
    assert validate_snapshot(raw)["event"]["revision"] == 1


def test_acceptance_record_rejects_extra_private_fields():
    raw = {
        "questId": "quest-synthetic",
        "participantId": MEMBERS[0],
        "revision": 1,
        "choice": "accept",
        "recordedAt": "2026-11-12T21:00:00Z",
    }
    assert validate_acceptance_record(raw) == raw
    raw["consentVersion"] = 1
    assert_code("INVALID_INPUT", lambda: validate_acceptance_record(raw))


def test_messages_distinguish_assistant_and_participant_without_extra_identity():
    raw = {
        "messageId": "message-synthetic",
        "conversationId": "conversation-synthetic",
        "createdAt": "2026-11-12T21:00:00Z",
        "sender": {"kind": "assistant"},
        "text": "Welcome to the demo quest.",
    }
    assert validate_message(raw) == raw
    raw["sender"]["participantId"] = MEMBERS[0]
    assert_code("INVALID_INPUT", lambda: validate_message(raw))
    raw["sender"] = {"kind": "participant", "participantId": MEMBERS[0]}
    assert validate_message(raw)["sender"]["kind"] == "participant"
    raw["privateTranscript"] = "synthetic-private-value"
    assert_code("INVALID_INPUT", lambda: validate_message(raw))


def test_valid_internal_shapes_round_trip_without_mutating_input():
    fixture_proposal, fixture_plan = proposal(), plan()
    before = copy.deepcopy((fixture_proposal, fixture_plan))
    assert validate_proposal(fixture_proposal) == fixture_proposal
    assert validate_plan_for_proposal(fixture_plan, fixture_proposal) == fixture_plan
    assert (fixture_proposal, fixture_plan) == before


@pytest.mark.parametrize(
    "mutation",
    [
        lambda raw: raw.update(revision=True),
        lambda raw: raw["memberIds"].append(raw["memberIds"][0]),
        lambda raw: raw["memberVersions"][0].update(participantId="synthetic-outsider"),
        lambda raw: raw["memberVersions"][0].update(consentVersion=0),
        lambda raw: raw["feasibleWindows"][0].update(start="2026-11-14T18:00:00-08:00"),
        lambda raw: raw["feasibleWindows"][0].update(end="2026-11-14T17:00:00Z"),
        lambda raw: raw["evidence"].update(source="fixture"),
        lambda raw: raw.update(privateIntent={"goal": "synthetic-private-value"}),
    ],
)
def test_invalid_proposals_are_rejected_without_echoing_values(mutation):
    raw = proposal()
    mutation(raw)
    assert_code("INVALID_INPUT", lambda: validate_proposal(raw))


@pytest.mark.parametrize(
    "mutation",
    [
        lambda raw: raw.update(costPerPersonMinor=True),
        lambda raw: raw.update(costPerPersonMinor=-1),
        lambda raw: raw.update(maximumSize=5.0),
        lambda raw: raw.update(currency="USD\n"),
        lambda raw: raw.update(currency="usd"),
        lambda raw: raw.update(timeZone="Not/AZone"),
        lambda raw: raw.update(start="2026-11-14 18:30:00Z"),
        lambda raw: raw.update(end="2026-11-14T18:00:00Z"),
        lambda raw: raw.update(basedOnRevision=1),
        lambda raw: raw["memberVersions"].append(raw["memberVersions"][0]),
        lambda raw: raw.update(privateBudget="synthetic-private-value"),
    ],
)
def test_invalid_plan_wire_is_rejected(mutation):
    raw = plan()
    mutation(raw)
    assert_code("INVALID_INPUT", lambda: validate_plan(raw))


def test_plan_lineage_and_feasible_interval_are_checked_against_proposal():
    raw = plan()
    raw["memberVersions"][0]["intentVersion"] = 2
    assert_code("STALE_REVISION", lambda: validate_plan_for_proposal(raw, proposal()))
    raw = plan()
    raw.update(start="2026-11-14T20:00:00Z", end="2026-11-14T20:30:00Z")
    assert_code("INVALID_INPUT", lambda: validate_plan_for_proposal(raw, proposal()))
    raw = plan()
    raw["proposalId"] = "unrelated-proposal"
    assert_code("INVALID_INPUT", lambda: validate_plan_for_proposal(raw, proposal()))


@pytest.mark.parametrize(
    "field,value",
    [
        ("title", "A different activity"),
        ("activity", "Another activity"),
        ("collaborationTask", "Work separately"),
        ("venueId", "another-venue"),
        ("start", "2026-11-14T18:45:00Z"),
        ("end", "2026-11-14T19:15:00Z"),
        ("costPerPersonMinor", 500),
        ("currency", "EUR"),
    ],
)
def test_material_final_changes_require_fresh_acceptances(field, value):
    old, new = plan(), plan()
    new[field] = value
    assert requires_reconfirmation(old, new) is True
    result = decide_publication(
        old, new, current_revision=1, accepted_ids=MEMBERS, member_ids=MEMBERS
    )
    assert result == {
        "status": "proposed",
        "revision": 2,
        "requiresReconfirmation": True,
        "acceptedIds": [],
    }


def test_member_versions_are_material_but_order_and_nonmaterial_metadata_are_not():
    old, new = plan(), plan()
    new["planId"] = "new-server-plan-id"
    new["opener"] = "Another welcome message."
    new["publicRationale"] = "Another public rationale."
    new["memberVersions"].reverse()
    new["evidence"]["latencyMs"] = 17
    assert requires_reconfirmation(old, new) is False
    new["memberVersions"][0]["consentVersion"] = 2
    assert requires_reconfirmation(old, new) is True


def test_unchanged_final_plan_schedules_the_frozen_quorum_without_new_vote():
    result = decide_publication(
        plan(), plan(), current_revision=1, accepted_ids=MEMBERS, member_ids=MEMBERS
    )
    assert result == {
        "status": "scheduled",
        "revision": 1,
        "requiresReconfirmation": False,
        "acceptedIds": sorted(MEMBERS),
    }


def test_publication_rejects_stale_lineage_insufficient_quorum_and_intruders():
    assert_code(
        "STALE_REVISION",
        lambda: decide_publication(
            plan(), plan(), current_revision=2, accepted_ids=MEMBERS, member_ids=MEMBERS
        ),
    )
    assert_code(
        "INVALID_INPUT",
        lambda: decide_publication(
            plan(), plan(), current_revision=1, accepted_ids=MEMBERS[:2], member_ids=MEMBERS
        ),
    )
    raw = plan()
    raw["memberVersions"][0]["participantId"] = "synthetic-outsider"
    assert_code(
        "INVALID_INPUT",
        lambda: decide_publication(
            plan(), raw, current_revision=1, accepted_ids=MEMBERS, member_ids=MEMBERS
        ),
    )


def test_new_final_revision_never_uses_votes_for_an_older_revision():
    raw = plan()
    raw.update(revision=2, basedOnRevision=1)
    outcome = decide_publication(
        plan(), raw, current_revision=1, accepted_ids=MEMBERS, member_ids=MEMBERS
    )
    assert outcome["status"] == "proposed"
    assert outcome["acceptedIds"] == []


@pytest.mark.parametrize("model", [Window, ModelEvidence, MemberVersion, GroupProposal, QuestPlan])
def test_workflow_runtime_field_names_match_the_shared_wire_contract(model):
    protocol = (Path(__file__).parents[2] / "contracts" / "protocol.ts").read_text()
    body = re.search(rf"export interface {model.__name__}\s*\{{([^}}]+)\}}", protocol).group(1)
    shared_fields = set(re.findall(r"\b([A-Za-z]\w*)\s*\??\s*:", body))
    assert set(model.model_fields) == shared_fields
