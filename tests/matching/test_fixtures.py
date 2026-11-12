"""Checks that the synthetic fixtures are valid wire data and that FakeMusePort behaves as scripted."""
import asyncio

import pytest

from server.matching.models import Candidate, MatchInput, ValidationError
from tests.matching.fixtures import (
    DEFAULT_MUSE_OUTPUT,
    DEMO_POOL,
    FakeMusePort,
    make_candidate,
    make_intent,
    make_match_input,
)

REQUESTER_ID = "p_ava"
POOL_SIZE = 8
EXPECTED_FAKE_MODEL = "fake-muse"


def _run(coro):
    return asyncio.run(coro)


def _generate(port: FakeMusePort, **overrides):
    kwargs = {
        "task": "rank_group",
        "requestId": "req_test",
        "promptVersion": "rank_group.v1",
        "payload": {"requester": "m0", "options": []},
    }
    kwargs.update(overrides)
    return _run(port.generate(**kwargs))


# ---------------------------------------------------------------- DEMO_POOL


def test_demo_pool_has_eight_candidates_including_requester():
    ids = [c["publicProfile"]["participantId"] for c in DEMO_POOL]

    assert len(DEMO_POOL) == POOL_SIZE
    assert REQUESTER_ID in ids
    assert len(set(ids)) == POOL_SIZE


@pytest.mark.parametrize("index", range(POOL_SIZE))
def test_every_demo_pool_entry_parses_as_candidate(index):
    candidate = Candidate.from_dict(DEMO_POOL[index])

    assert candidate.participant_id == DEMO_POOL[index]["publicProfile"]["participantId"]
    assert candidate.public_profile.is_synthetic is True
    assert candidate.public_profile.display_name.startswith("Synthetic ")


def test_demo_pool_has_two_candidates_without_time_overlap_with_requester():
    requester = Candidate.from_dict(_find(REQUESTER_ID))
    no_overlap = [
        c for c in map(Candidate.from_dict, DEMO_POOL)
        if c.participant_id != REQUESTER_ID
        and not _overlaps(requester.intent.availability, c.intent.availability)
    ]

    assert len(no_overlap) == 2


def test_demo_pool_has_exactly_one_candidate_in_a_different_area():
    requester = Candidate.from_dict(_find(REQUESTER_ID))
    other_area = [
        c for c in map(Candidate.from_dict, DEMO_POOL)
        if c.intent.area_id != requester.intent.area_id
    ]

    assert len(other_area) == 1
    assert other_area[0].intent.area_id == "area_downtown"


def test_demo_pool_entries_are_independent_copies():
    first = make_candidate("p_x", "X", ["coffee"])
    second = make_candidate("p_x", "X", ["coffee"])
    first["intent"]["interests"].append("mutated")

    assert second["intent"]["interests"] == ["coffee"]


def test_make_intent_returns_fresh_availability_list_each_call():
    first = make_intent("p_a")
    second = make_intent("p_a")
    first["availability"].append({"start": "x", "end": "y"})

    assert len(second["availability"]) == 1


def test_candidate_with_mismatched_participant_ids_fails_closed():
    bad = make_candidate("p_a", "A", ["coffee"])
    bad["publicProfile"]["participantId"] = "p_other"

    with pytest.raises(ValidationError):
        Candidate.from_dict(bad)


# ---------------------------------------------------------------- make_match_input


def test_make_match_input_output_parses_as_match_input():
    wire = make_match_input(DEMO_POOL, REQUESTER_ID)

    parsed = MatchInput.from_dict(wire)

    assert parsed.requester_id == REQUESTER_ID
    assert parsed.community_id == "comm_demo"
    assert len(parsed.candidates) == POOL_SIZE
    assert parsed.context.mode == "fixture"
    assert parsed.context.request_id == "req_test"


def test_make_match_input_respects_mode_and_request_id():
    wire = make_match_input(DEMO_POOL[:3], REQUESTER_ID, mode="replay", request_id="req_9")

    parsed = MatchInput.from_dict(wire)

    assert parsed.context.mode == "replay"
    assert parsed.context.request_id == "req_9"


def test_make_match_input_does_not_alias_candidates():
    wire = make_match_input(DEMO_POOL, REQUESTER_ID)
    wire["candidates"][0]["intent"]["interests"].append("mutated")

    assert "mutated" not in DEMO_POOL[0]["intent"]["interests"]


def test_make_match_input_with_no_candidates_parses_to_empty_tuple():
    wire = make_match_input([], REQUESTER_ID)

    parsed = MatchInput.from_dict(wire)

    assert parsed.candidates == ()


# ---------------------------------------------------------------- FakeMusePort


def test_fake_muse_records_each_call_in_order():
    port = FakeMusePort()

    _generate(port, requestId="req_1", task="rank_group")
    _generate(port, requestId="req_2", task="plan", promptVersion="plan.v1")

    assert len(port.calls) == 2
    assert port.calls[0]["requestId"] == "req_1"
    assert port.calls[0]["task"] == "rank_group"
    assert port.calls[0]["promptVersion"] == "rank_group.v1"
    assert port.calls[1]["requestId"] == "req_2"
    assert port.calls[1]["task"] == "plan"
    assert port.calls[1]["promptVersion"] == "plan.v1"


def test_fake_muse_records_payload_without_aliasing_caller_data():
    port = FakeMusePort()
    payload = {"requester": "m0", "options": [{"optionId": "g0"}]}

    _generate(port, payload=payload)
    payload["options"].append({"optionId": "mutated"})

    assert port.calls[0]["payload"] == {"requester": "m0", "options": [{"optionId": "g0"}]}


def test_fake_muse_default_output_picks_g0_with_strong_shared_interest():
    port = FakeMusePort()

    result = _generate(port)

    assert result["output"] == DEFAULT_MUSE_OUTPUT
    assert result["output"]["optionId"] == "g0"
    assert result["output"]["sharedInterests"] == []
    assert result["output"]["reasonCodes"] == ["strong_shared_interest"]


def test_fake_muse_evidence_is_labeled_replay_never_live():
    port = FakeMusePort()

    evidence = _generate(port)["evidence"]

    assert evidence == {
        "model": EXPECTED_FAKE_MODEL,
        "source": "replay",
        "generatedAt": "2026-11-12T20:00:00Z",
        "latencyMs": 1,
    }


def test_fake_muse_returns_scripted_mapping_then_falls_back_to_default():
    scripted = {"optionId": "g1", "sharedInterests": ["coffee"], "reasonCodes": []}
    port = FakeMusePort([scripted])

    first = _generate(port)
    second = _generate(port)

    assert first["output"] == scripted
    assert second["output"] == DEFAULT_MUSE_OUTPUT


def test_fake_muse_returns_raw_string_output_unchanged():
    port = FakeMusePort(["not json at all"])

    assert _generate(port)["output"] == "not json at all"


def test_fake_muse_raises_scripted_exception_and_still_records_call():
    port = FakeMusePort([TimeoutError("scripted timeout")])

    with pytest.raises(TimeoutError, match="scripted timeout"):
        _generate(port)

    assert len(port.calls) == 1


def test_fake_muse_hang_blocks_until_cancelled():
    port = FakeMusePort(["hang"])

    async def _hang_then_cancel() -> bool:
        task = asyncio.ensure_future(port.generate(
            task="rank_group", requestId="req_h", promptVersion="rank_group.v1", payload={},
        ))
        await asyncio.sleep(0)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            return True
        return False

    assert _run(_hang_then_cancel()) is True
    assert len(port.calls) == 1


def test_fake_muse_calls_property_returns_copy_not_internal_list():
    port = FakeMusePort()
    _generate(port)

    snapshot = port.calls
    snapshot[0]["task"] = "mutated"

    assert port.calls[0]["task"] == "rank_group"


def test_fake_muse_instances_do_not_share_state():
    first = FakeMusePort()
    second = FakeMusePort()

    _generate(first)

    assert len(first.calls) == 1
    assert second.calls == ()


# ---------------------------------------------------------------- helpers


def _find(pid: str) -> dict:
    for entry in DEMO_POOL:
        if entry["publicProfile"]["participantId"] == pid:
            return entry
    raise AssertionError(f"fixture {pid} missing from DEMO_POOL")


def _overlaps(left, right) -> bool:
    return any(
        a.start < b.end and b.start < a.end
        for a in left
        for b in right
    )
