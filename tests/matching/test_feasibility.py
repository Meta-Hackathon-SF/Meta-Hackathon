"""Tests for hard feasibility gates (synthetic data only)."""
import dataclasses

import pytest

from server.matching.feasibility import (
    MAX_POOL,
    MAX_SHORTLIST,
    MIN_ACTIVITY_MINUTES,
    FeasibleGroup,
    diagnose_no_match,
    eligible_candidates,
    enumerate_groups,
    find_requester,
    intersect_windows,
)
from server.matching.models import (
    Candidate,
    MatchingError,
    MatchInput,
    ValidationError,
    Window,
)

DAY = "2026-11-14T"


def win(start: str, end: str) -> dict:
    return {"start": f"{DAY}{start}:00Z", "end": f"{DAY}{end}:00Z"}


def W(start: str, end: str) -> Window:
    return Window.from_dict(win(start, end))


def cand(pid, interests=(), windows=None, **over) -> dict:
    intent = {
        "participantId": pid, "communityId": "comm_demo", "intentVersion": 1,
        "goal": "meet people", "interests": list(interests), "areaId": "area_campus",
        "timeZone": "America/Los_Angeles",
        "availability": windows if windows is not None else [win("18:00", "21:00")],
        "maxBudgetMinor": 1500, "currency": "USD", "maxDurationMinutes": 120,
        "groupPreference": "small", "consentVersion": 1,
        "confirmedAt": "2026-11-12T20:00:00Z",
    }
    intent.update(over)
    return {"intent": intent,
            "publicProfile": {"participantId": pid, "displayName": f"Synthetic {pid}",
                              "publicInterests": list(interests), "isSynthetic": True}}


def match_input(cands, requester="p0") -> MatchInput:
    return MatchInput.from_dict({
        "context": {"requestId": "req_test", "contractVersion": "1.0.0", "mode": "fixture"},
        "communityId": "comm_demo", "requesterId": requester, "candidates": cands,
        "minimumSize": 3, "maximumSize": 5})


# ------------------------------------------------------------ intersect_windows

def test_touching_windows_do_not_overlap():
    assert intersect_windows([W("18:00", "19:00")], [W("19:00", "20:00")]) == ()


def test_overlap_is_intersection_sorted():
    out = intersect_windows([W("18:00", "19:00"), W("10:00", "12:00")],
                            [W("10:30", "11:00"), W("18:30", "20:00")])
    assert out == (W("10:30", "11:00"), W("18:30", "19:00"))


def test_empty_inputs_yield_empty():
    assert intersect_windows([], [W("18:00", "19:00")]) == ()


# ------------------------------------------------------------ find_requester

def test_requester_missing_is_forbidden():
    inp = match_input([cand("p1"), cand("p2")], requester="p0")
    with pytest.raises(MatchingError) as exc:
        find_requester(inp)
    assert exc.value.code == "FORBIDDEN" and exc.value.retryable is False


def test_requester_wrong_community_forbidden():
    inp = match_input([cand("p0", communityId="comm_other"), cand("p1")])
    with pytest.raises(MatchingError) as exc:
        find_requester(inp)
    assert exc.value.code == "FORBIDDEN"


def test_requester_short_duration_forbidden():
    inp = match_input([cand("p0", maxDurationMinutes=MIN_ACTIVITY_MINUTES - 1)])
    with pytest.raises(MatchingError):
        find_requester(inp)


# ------------------------------------------------------------ eligible_candidates

def ids(cands):
    return [c.participant_id for c in cands]


def test_gates_exclude_mismatches():
    inp = match_input([
        cand("p0"), cand("ok"),
        cand("area", areaId="area_other"),
        cand("comm", communityId="comm_other"),
        cand("cur", currency="EUR"),
        cand("short", maxDurationMinutes=29),
        cand("touch", windows=[win("21:00", "22:00")]),
        cand("brief", windows=[win("20:40", "22:00")]),  # 20 min overlap
    ])
    assert ids(eligible_candidates(inp)) == ["ok"]


def test_exact_minimum_overlap_is_eligible():
    inp = match_input([cand("p0"), cand("edge", windows=[win("20:30", "22:00")])])
    assert ids(eligible_candidates(inp)) == ["edge"]


def test_duplicate_participant_raises():
    inp = match_input([cand("p0"), cand("p1"), cand("p1")])
    with pytest.raises(ValidationError):
        eligible_candidates(inp)


def test_pool_capped_and_ordered_by_interest_then_id():
    others = [cand(f"q{i:02d}", ["chess"]) for i in range(MAX_POOL + 3)]
    others.append(cand("zz", ["Photo"]))
    inp = match_input([cand("p0", ["photo"])] + others)
    pool = ids(eligible_candidates(inp))
    assert len(pool) == MAX_POOL
    assert pool[0] == "zz"
    assert pool[1:] == sorted(pool[1:])


# ------------------------------------------------------------ enumerate_groups

def test_sizes_three_to_five_only_and_requester_first():
    inp = match_input([cand(f"p{i}") for i in range(7)])
    groups = enumerate_groups(inp)
    assert groups and all(3 <= len(g.member_ids) <= 5 for g in groups)
    for g in groups:
        assert g.member_ids[0] == "p0"
        assert list(g.member_ids[1:]) == sorted(g.member_ids[1:])
        assert len(set(g.member_ids)) == len(g.member_ids)


def test_all_members_share_every_returned_window():
    cands = [cand("p0", windows=[win("17:00", "20:00")]),
             cand("p1", windows=[win("18:00", "21:00")]),
             cand("p2", windows=[win("18:30", "22:00")]),
             cand("p3", windows=[win("19:55", "23:00")])]  # only 5 min overlap with p0..p2
    inp = match_input(cands)
    by_id = {c.participant_id: c for c in inp.candidates}
    groups = enumerate_groups(inp)
    assert [g.member_ids for g in groups] == [("p0", "p1", "p2")]
    for g in groups:
        for w in g.common_windows:
            assert w.minutes >= MIN_ACTIVITY_MINUTES
            for pid in g.member_ids:
                assert any(a.start <= w.start and w.end <= a.end
                           for a in by_id[pid].intent.availability)
    assert groups[0].common_windows == (W("18:30", "20:00"),)


def test_no_group_without_three_members():
    assert enumerate_groups(match_input([cand("p0"), cand("p1")])) == ()


def test_pairwise_overlap_without_triple_overlap_excluded():
    cands = [cand("p0", windows=[win("10:00", "12:00")]),
             cand("p1", windows=[win("10:00", "11:00")]),
             cand("p2", windows=[win("11:00", "12:00")])]
    assert enumerate_groups(match_input(cands)) == ()


def test_shared_interests_public_only_casefold_ordered():
    cands = [cand("p0", ["Coffee", "Hiking"]),
             cand("p1", ["coffee", "Chess"]),
             cand("p2", ["COFFEE", "hiking"])]
    # private-only interest must never count
    cands[0]["intent"]["interests"] = ["secret"]
    cands[1]["intent"]["interests"] = ["secret"]
    g = enumerate_groups(match_input(cands))[0]
    assert g.shared_interests == ("Coffee", "Hiking")


def test_budget_cap_is_min_and_activity_minutes():
    cands = [cand("p0", maxBudgetMinor=900, maxDurationMinutes=90),
             cand("p1", maxBudgetMinor=500),
             cand("p2", maxBudgetMinor=2000, maxDurationMinutes=45)]
    g = enumerate_groups(match_input(cands))[0]
    assert g.budget_cap_minor == 500
    assert g.max_activity_minutes == 45


def test_max_activity_limited_by_common_window():
    cands = [cand("p0", windows=[win("18:00", "18:40")]), cand("p1"), cand("p2")]
    assert enumerate_groups(match_input(cands))[0].max_activity_minutes == 40


def test_shortlist_capped_sorted_and_deterministic():
    cands = [cand("p0", ["a"])] + [cand(f"p{i}", ["a"] if i % 2 else ["b"])
                                  for i in range(1, 9)]
    first = enumerate_groups(match_input(cands))
    second = enumerate_groups(match_input(list(cands)))
    assert len(first) == MAX_SHORTLIST
    assert first == second
    scores = [g.baseline_score for g in first]
    assert scores == sorted(scores, reverse=True)


def test_higher_shared_interest_ranks_first():
    cands = [cand("p0", ["a", "b"]), cand("p1", ["a", "b"]),
             cand("p2", ["z"]), cand("p3", ["y"])]
    groups = enumerate_groups(match_input(cands))
    by_members = {g.member_ids: g for g in groups}
    assert groups[0].shared_interests == ("a", "b")
    assert "p1" in groups[0].member_ids
    assert (by_members[("p0", "p1", "p2")].baseline_score
            > by_members[("p0", "p2", "p3")].baseline_score)


def test_group_is_frozen():
    g = enumerate_groups(match_input([cand("p0"), cand("p1"), cand("p2")]))[0]
    assert isinstance(g, FeasibleGroup)
    with pytest.raises(dataclasses.FrozenInstanceError):
        g.budget_cap_minor = 1  # type: ignore[misc]


# ------------------------------------------------------------ diagnose_no_match

def test_diagnose_too_few():
    inp = match_input([cand("p0"), cand("p1"), cand("far", areaId="area_other")])
    assert diagnose_no_match(inp) == "too_few"


def test_diagnose_no_common_time():
    cands = [cand("p0", windows=[win("10:00", "11:00")]),
             cand("p1", windows=[win("12:00", "13:00")]),
             cand("p2", windows=[win("14:00", "15:00")])]
    assert diagnose_no_match(match_input(cands)) == "no_common_time"


def test_diagnose_constraints_when_groups_exist():
    inp = match_input([cand("p0"), cand("p1"), cand("p2")])
    assert diagnose_no_match(inp) == "constraints"
