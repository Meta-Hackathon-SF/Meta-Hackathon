"""Formation pipeline tests against synthetic fixtures with TEST-ONLY adapters.

Passing proves mechanics, validation and guards, not live Muse grouping quality.
"""
from __future__ import annotations

import asyncio
import json

import pytest

from server.matching import prompts
from server.matching.baseline import baseline_groups, group_sizes, partition
from server.matching.formation import FALLBACK_MEANING, FormationService
from server.matching.models import FormationSnapshot, MatchingError, ValidationError
from server.matching.validation import violations
from tests.matching.adapters import FakeMuse, FixtureGuard, FixtureSnapshotSource, load_week

GOOD = [["p-maya", "p-dev", "p-omar", "p-lee"], ["p-jordan", "p-sam", "p-ren"]]
CONTRACT_PAYLOAD_KEYS = {  # M3In / M4In / M5In in contracts/protocol.ts 2.0.0
    "theme_discovery": {"answers", "questions"},
    "constellation_formation": {"themes", "answers", "blockedPairs"},
    "constellation_naming": {"sharedMeaning", "size"},
}
CONSTELLATION_WIRE_KEYS = {"constellationId", "cycleId", "memberIds", "sharedMeaning",
                           "confidence", "isLooseMatch", "name", "shapeId", "colorId",
                           "baselineAgrees"}
OPTIONAL_WIRE_KEYS = {"closeness", "memberContext"}  # D009/D010, private, present when computed
BLOCKED = [["p-maya", "p-dev", "p-jordan", "p-lee"], ["p-omar", "p-sam", "p-ren"]]


def run(coro):
    return asyncio.run(coro)


def build(m4_script=("good",), m3_mode="good", m5_name="Quiet Lanterns", **kw):
    source = FixtureSnapshotSource()
    source.snapshot()  # populate ref_of
    muse = FakeMuse(source.ref_of, GOOD, m4_script=m4_script, m3_mode=m3_mode,
                    m5_name=m5_name, blocked_groups=BLOCKED)
    service = FormationService(muse, source, FixtureGuard(), **kw)
    return service, muse, source


def groups_by_player(result):
    return [set(c.member_ids) for c in result.constellations]


# ---------------------------------------------------------------- baseline

def test_group_sizes_cover_three_to_five():
    for n in range(3, 40):
        sizes = group_sizes(n)
        assert sum(sizes) == n and all(3 <= s <= 5 for s in sizes)


def test_group_sizes_rejects_fewer_than_three():
    with pytest.raises(MatchingError):
        group_sizes(2)


def test_keyword_baseline_splits_maya_and_dev():
    source = FixtureSnapshotSource()
    snap = FormationSnapshot.from_dict(source.snapshot())
    groups = baseline_groups(snap.answers, snap.blocked_ref_pairs())
    maya, dev = source.ref_of["p-maya"], source.ref_of["p-dev"]
    assert not any({maya, dev} <= set(g) for g in groups)
    assert violations(groups, snap.refs, snap.blocked_ref_pairs()) == []


def test_partition_respects_blocks_and_is_deterministic():
    refs = [f"r{i}" for i in range(9)]
    sim = {("r0", "r1"): 0.9, ("r0", "r2"): 0.9, ("r1", "r2"): 0.9}
    blocked = [("r0", "r1")]
    first = partition(refs, sim, blocked)
    assert first == partition(list(reversed(refs)), sim, blocked)
    assert violations(first, refs, blocked) == []


# ---------------------------------------------------------------- validation

@pytest.mark.parametrize("groups,code", [
    ([["a", "b"], ["c", "d", "e"]], "size"),
    ([["a", "b", "c"], ["c", "d", "e"]], "placed_twice"),
    ([["a", "b", "c"]], "unplaced"),
    ([["a", "b", "c", "x"], ["d", "e", "f"]], "unknown_refs"),
    ([["a", "b", "c"], ["d", "e", "f"]], "blocked_pair"),
])
def test_violations_detected(groups, code):
    eligible = ["a", "b", "c", "d", "e"] if code != "blocked_pair" else list("abcdef")
    if code in ("unknown_refs",):
        eligible = list("abcdef")
    problems = violations(groups, eligible, [("a", "c")] if code == "blocked_pair" else [])
    assert any(p.startswith(code) for p in problems)


# ---------------------------------------------------------------- parsers

def test_m4_parser_rejects_unknown_keys_and_refs():
    with pytest.raises(ValidationError):
        prompts.parse_m4({"constellations": [], "extra": 1}, {"r1"})
    with pytest.raises(ValidationError):
        prompts.parse_m4({"constellations": [{"memberIds": ["zz"], "sharedMeaning": "x",
                                              "confidence": 0.5}]}, {"r1"})
    with pytest.raises(ValidationError):
        prompts.parse_m4({"constellations": [{"memberIds": ["r1"], "sharedMeaning": "x",
                                              "confidence": 1.5}]}, {"r1"})


def test_m5_parser_enforces_fixed_sets():
    with pytest.raises(ValidationError):
        prompts.parse_m5({"name": "A", "shapeId": "pentagon", "colorId": "dusk"}, 3)
    with pytest.raises(ValidationError):
        prompts.parse_m5({"name": "A", "shapeId": "triangle", "colorId": "neon"}, 3)
    assert prompts.parse_m5('{"name":"A","shapeId":"triangle","colorId":"dusk"}', 3)


# ---------------------------------------------------------------- formation

def test_meaning_formation_meets_fixture_constraints():
    service, muse, _ = build()
    result = run(service.form("cycle-demo-w1", "req-1"))
    week = load_week()
    expected = week["expectedFormation"]
    assert result.status == "ok" and not result.used_fallback
    groups = groups_by_player(result)
    for together in expected["mustBeTogether"]:
        assert any(set(together) <= g for g in groups)
    for apart in expected["mustBeApart"]:
        assert not any(set(apart) <= g for g in groups)
    placed = set().union(*groups)
    assert not placed & set(expected["excluded"])
    assert all(3 <= len(g) <= 5 for g in groups)
    maya_c = next(c for c in result.constellations if "p-maya" in c.member_ids)
    assert maya_c.baseline_agrees is False  # keywords split Maya and Dev; meaning joins them
    assert [e.call_type for e in result.evidence].count("M5") == len(result.constellations)


def test_blocked_pair_proposal_is_resolved_once():
    service, muse, _ = build(m4_script=("blocked", "good"))
    result = run(service.form("c", "r"))
    assert result.status == "ok" and not result.used_fallback
    assert [c["task"] for c in muse.calls].count("constellation_formation") == 2
    assert not any({"p-omar", "p-ren"} <= g for g in groups_by_player(result))


@pytest.mark.parametrize("mode", ["invalid_json", "raise", "blocked"])
def test_fallback_grouping_after_two_bad_proposals(mode):
    service, _, source = build(m4_script=(mode,))
    result = run(service.form("c", "r"))
    assert result.status == "ok" and result.used_fallback
    assert all(c.is_fallback and c.is_loose_match for c in result.constellations)
    assert all("Fallback grouping" in c.name and len(c.name) <= 40
               for c in result.constellations)
    assert all(c.to_wire()["isLooseMatch"] for c in result.constellations)
    assert all(c.shared_meaning == FALLBACK_MEANING for c in result.constellations)
    snap = FormationSnapshot.from_dict(source.snapshot())
    refs = [[source.ref_of[p] for p in c.member_ids] for c in result.constellations]
    assert violations(refs, snap.refs, snap.blocked_ref_pairs()) == []


def test_fallback_disabled_returns_retryable_error():
    service, _, _ = build(m4_script=("raise",), allow_fallback=False)
    result = run(service.form("c", "r"))
    assert result.status == "failed"
    assert result.error.code == "PROVIDER_UNAVAILABLE" and result.error.retryable
    assert result.to_wire("r")["error"]["requestId"] == "r"


def test_m3_outage_still_forms():
    service, _, _ = build(m3_mode="raise")
    result = run(service.form("c", "r"))
    assert result.status == "ok" and result.themes == ()


def test_quoting_name_is_replaced_by_fixed_fallback_name():
    service, _, _ = build(m5_name="eat in my room so no one")
    result = run(service.form("c", "r"))
    for c in result.constellations:
        assert c.name != "eat in my room so no one"
        assert FixtureGuard().check(c.name, [])["ok"]


def test_prompts_carry_refs_and_text_only():
    service, muse, _ = build()
    run(service.form("c", "r"))
    blob = json.dumps([c["payload"] for c in muse.calls])
    for player in load_week()["players"]:
        assert player["playerId"] not in blob
        assert player["displayName"] not in blob
    for call in muse.calls:
        assert set(call["payload"]) == CONTRACT_PAYLOAD_KEYS[call["task"]]
        for answer in call["payload"].get("answers", []):
            assert set(answer) == {"id", "text", "weight"}


def test_distress_answer_never_reaches_muse():
    service, muse, _ = build()
    run(service.form("c", "r"))
    blob = json.dumps([c["payload"] for c in muse.calls])
    assert load_week()["distressFixture"]["text"] not in blob


def test_injection_text_is_data_and_constraints_hold():
    service, muse, _ = build()
    result = run(service.form("c", "r"))
    m4 = next(c for c in muse.calls if c["task"] == "constellation_formation")
    assert set(m4["payload"]) == CONTRACT_PAYLOAD_KEYS["constellation_formation"]
    assert all("instructions" not in c["payload"] for c in muse.calls)
    assert result.status == "ok"
    assert not any({"p-omar", "p-ren"} <= g for g in groups_by_player(result))


def test_invalid_snapshot_fails_closed():
    class Bad:
        async def formation_snapshot(self, cycle_id):
            return {"answers": [{"id": "r1", "text": "x"}], "idMap": {}}
    service = FormationService(FakeMuse({}, []), Bad(), FixtureGuard())
    result = run(service.form("c", "r"))
    assert result.status == "failed" and result.error.code == "INVALID_INPUT"


def test_weights_out_of_range_rejected():
    with pytest.raises(ValidationError):
        FormationSnapshot.from_dict({"answers": [{"id": "r1", "text": "x", "weight": 3}],
                                     "idMap": {"r1": "p"}})


def test_thirty_synthetic_players_form_with_fallback_quickly():
    answers, id_map = [], {}
    topics = ["eat alone dorm", "miss home city", "pickup soccer games", "late night coding",
              "new transfer student", "quiet library study"]
    for i in range(30):
        ref = f"r{i}"
        id_map[ref] = f"p{i}"
        answers.append({"id": ref, "text": f"{topics[i % 6]} week {i}", "weight": 1.0})

    class Src:
        async def formation_snapshot(self, cycle_id):
            return {"answers": answers, "idMap": id_map, "blockedPairs": [["p0", "p6"]]}

    service = FormationService(FakeMuse({}, [], m4_script=("raise",), m3_mode="raise"),
                               Src(), FixtureGuard())
    result = run(service.form("c", "r"))
    assert result.status == "ok" and len(result.constellations) == 6
    assert result.timings_ms["totalMs"] < 60_000


@pytest.mark.parametrize("m4_script", [("good",), ("raise",)])
def test_constellation_wire_keys_match_contract(m4_script):
    service, _, _ = build(m4_script=m4_script)
    result = run(service.form("cycle-demo-w1"))  # request id optional per FormationPort
    assert result.status == "ok"
    for c in result.constellations:
        keys = set(c.to_wire())
        assert CONSTELLATION_WIRE_KEYS <= keys <= CONSTELLATION_WIRE_KEYS | OPTIONAL_WIRE_KEYS
    wire = result.to_wire("r")
    assert set(wire) == {"status", "constellations", "evidence"}


def test_prompt_text_lives_outside_payloads():
    assert set(prompts.PROMPT_TEXT) == {prompts.PROMPT_VERSION_M3, prompts.PROMPT_VERSION_M4,
                                        prompts.PROMPT_VERSION_M5}
    assert "triangle" in prompts.PROMPT_TEXT[prompts.PROMPT_VERSION_M5]
