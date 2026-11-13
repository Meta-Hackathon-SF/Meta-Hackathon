"""v3 daily producers: offline, deterministic, synthetic."""

from __future__ import annotations

import time

from server.matching.daily import (
    daily_groups,
    main_groups,
    second_degree,
    sky_positions,
    star_indices,
    week_graph,
)
from server.matching.models import PromptText

GAMES = [PromptText(f"g{i}", "board games with my floor in the dining hall") for i in range(4)]
HIKE = [PromptText(f"h{i}", "long quiet hikes with music outdoors") for i in range(3)]
LONE = [PromptText("z", "competitive chess tournaments")]


def test_daily_groups_form_by_shared_meaning_and_place_everyone_possible():
    groups, unplaced = daily_groups(GAMES + HIKE + LONE)
    assert {tuple(g) for g in groups} >= {tuple(sorted(f"g{i}" for i in range(4)))}
    assert all(len(g) >= 3 for g in groups) and unplaced == ("z",)


def test_blocked_pair_never_shares_a_group_and_group_stays_at_3():
    groups, _ = daily_groups(GAMES, blocked_ref_pairs=[("g0", "g1")])
    assert all(not {"g0", "g1"} <= set(g) for g in groups)
    assert all(len(g) >= 3 for g in groups)


def test_under_three_never_becomes_a_constellation():
    groups, unplaced = daily_groups(GAMES[:2] + LONE)
    assert groups == () and len(unplaced) == 3


def test_instant_placement_is_fast_for_a_thousand_players():
    answers = [
        PromptText(f"p{i}", f"topic{i % 40} shared words about thing{i % 7}") for i in range(1000)
    ]
    start = time.perf_counter()
    daily_groups(answers)
    assert time.perf_counter() - start < 1.0


def test_week_graph_is_reproducible_from_day_results():
    days = [[("a", "b", "c")], [("a", "b", "d")], [("c", "d", "e")]]
    assert week_graph(days) == week_graph(list(days))
    assert week_graph(days)[("a", "b")] == 2 and week_graph(days)[("c", "d")] == 1


def test_main_groups_size_blocks_and_unplaced():
    graph = week_graph([[("a", "b", "c", "d")], [("a", "b", "c", "d")], [("x", "y", "w")]] * 1)
    players = ["a", "b", "c", "d", "x", "y", "w", "q"]
    groups, unplaced = main_groups(players, graph, blocked_pairs=[("a", "b")])
    assert all(len(g) >= 5 for g in groups)
    assert all(not {"a", "b"} <= set(g) for g in groups)
    assert "q" in unplaced
    assert len({r for g in groups for r in g}) == sum(len(g) for g in groups)  # exactly once


def test_star_indices_distinct_and_change_by_week():
    refs = [f"p{i}" for i in range(500)]
    w1, w2 = star_indices("2026-W46", refs), star_indices("2026-W47", refs)
    assert len(set(w1.values())) == 500 and w1 != w2
    assert sky_positions("2026-W46", 50) == sky_positions("2026-W46", 50)


def test_second_degree_caps_and_small_population_gate():
    mine = [("a", "b", "c")]
    allg = mine + [("a", f"x{i}", f"y{i}") for i in range(6)] + [("a", "m")]
    assert second_degree(mine, allg, eligible=29) == ()
    out = second_degree(mine, allg, eligible=30)
    assert len([v for v in out if v[0] == "a"]) == 2 and all(len(g) >= 3 for _, g in out)


def test_second_degree_cap_holds_on_a_10k_fixture():
    groups = [tuple(f"s{(i + j) % 3000}" for j in range(3)) for i in range(3000)]
    out = second_degree([groups[0]], groups, eligible=10000)
    per_star = {}
    for via, _ in out:
        per_star[via] = per_star.get(via, 0) + 1
    assert per_star and max(per_star.values()) <= 2
