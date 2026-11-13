from server.matching.extras import (
    HourlyInterest,
    cluster_aggregate,
    constellation_interest,
    find_clusters,
    nudge_eligible,
    progress_events,
)


def test_progress_uses_only_real_scored_pairs_and_viewer_neighbourhood():
    scored = [("a", "b", 0.9), ("a", "c", 0.1), ("x", "y", 0.8)]
    stars = {"a": 1, "b": 2, "c": 3, "x": 8, "y": 9}
    ev = progress_events(scored, stars, {"a", "b", "c"})
    seen = [t for e in ev for t in e["attempts"]]
    assert [(t["fromStarIndex"], t["outcome"]) for t in seen] == [(1, "kept"), (1, "dropped")]
    assert all(e["source"] == "trace" and e["isVisualization"] is False for e in ev)
    assert ev[0]["phase"] == "queued" and ev[-1]["phase"] == "done"
    assert {8, 9}.isdisjoint({i for t in seen for i in (t["fromStarIndex"], t["toStarIndex"])})


def test_progress_visualization_is_labeled():
    ev = progress_events([], {}, set(), visualization=True)
    assert all(e["isVisualization"] and e["source"] == "visualization" for e in ev)


def test_interest_threshold_buckets_and_allowlist():
    interested = {
        f"p{i}": ["e-games", "e-rare"] if i < 2 else ["e-games", "e-fake"] for i in range(4)
    }
    rows = constellation_interest(
        "v", [f"p{i}" for i in range(4)] + ["v"], interested, {"e-games", "e-rare"}
    )
    assert rows == [{"eventId": "e-games", "bucket": "3-5"}]  # e-rare has 2, e-fake not approved
    assert constellation_interest("v", ["p0", "p1"], interested, {"e-games"}) == []
    assert nudge_eligible(rows, {"e-games"}) == ["e-games"] and nudge_eligible(rows, set()) == []


def test_interest_recomputed_hourly_only():
    calls, now = [], [0]
    h = HourlyInterest(
        lambda v: calls.append(v) or [{"eventId": "e", "bucket": "3-5"}], lambda: now[0]
    )
    h.get("v")
    h.get("v")
    now[0] = 3599
    h.get("v")
    assert len(calls) == 1
    now[0] = 3600
    h.get("v")
    assert len(calls) == 2


def test_cluster_finder_finds_repeats_not_one_offs():
    group = [f"p{i}" for i in range(7)]
    week = {(a, b): 1 for i, a in enumerate(group) for b in group[i + 1 :]}
    one_off = {
        ("x1", "x2"): 5,
        ("x2", "x3"): 5,
        ("x1", "x3"): 5,
        ("x3", "x4"): 5,
        ("x4", "x5"): 5,
        ("x5", "x6"): 5,
    }
    found = find_clusters([week, week, {**week, **one_off}][:3])
    assert found == [tuple(sorted(group))]
    assert find_clusters([week, week]) == []  # fewer than 3 weeks
    agg = cluster_aggregate(found[0], {"p0": ["food"], "p1": ["food", "music"]})
    assert agg["clusterSize"] == 7 and agg["tags"][0] == "food" and "p0" not in str(agg)
