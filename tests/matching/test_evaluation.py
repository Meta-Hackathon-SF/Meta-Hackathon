from server.matching.evaluation import GOLD_FEELINGS, gold_snapshot, pair_metrics


def test_oracle_grouping_scores_perfect():
    _, gold = gold_snapshot(30)
    by_feeling: dict[str, list[str]] = {}
    for player, feeling in gold.items():
        by_feeling.setdefault(feeling, []).append(player)
    m = pair_metrics(list(by_feeling.values()), gold)
    assert (m.precision, m.recall) == (1.0, 1.0)


def test_gold_snapshot_is_synthetic_and_balanced():
    snap, gold = gold_snapshot(30)
    assert all(p.startswith("syn-gold-") for p in snap["idMap"].values())
    counts = {f: list(gold.values()).count(f) for f in GOLD_FEELINGS}
    assert set(counts.values()) == {5}


def test_mixed_grouping_partial_scores():
    gold = {"a": "x", "b": "x", "c": "y", "d": "y"}
    m = pair_metrics([["a", "b", "c"], ["d"]], gold)
    assert m.gold_pairs_grouped == 1 and m.grouped_pairs == 3 and m.gold_pairs == 2
