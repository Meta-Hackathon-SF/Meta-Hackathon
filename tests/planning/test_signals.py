"""Aggregate signals for M6: thresholded, rounded, never about one person."""
from __future__ import annotations

import unittest

from server.planning.signals import aggregate_signals


class AggregateSignalsTests(unittest.TestCase):
    def test_small_population_yields_nothing(self):
        self.assertEqual(aggregate_signals([["music"]] * 9), [])

    def test_rare_tags_dropped_and_shares_rounded(self):
        players = [["music", "coffee"]] * 7 + [["music"]] * 5 + [["film"]] * 4  # 16 players
        out = aggregate_signals(players)
        self.assertEqual(out, [{"tag": "music", "share": 0.75}, {"tag": "coffee", "share": 0.45}])
        self.assertNotIn("film", {r["tag"] for r in out})  # 4 < min_count 5

    def test_one_player_counts_once_and_free_text_is_ignored(self):
        players = [["music", "music", "I eat alone in my room", "Music"]] * 10
        self.assertEqual(aggregate_signals(players), [{"tag": "music", "share": 1.0}])

    def test_allowlist_and_cap(self):
        players = [["music", "coffee", "secret_tag"]] * 10
        self.assertEqual([r["tag"] for r in aggregate_signals(players, allowed={"music", "coffee"})],
                         ["coffee", "music"])
        many = [[f"t{i}" for i in range(30)]] * 10
        self.assertEqual(len(aggregate_signals(many)), 20)

    def test_thresholds_cannot_be_weakened(self):
        with self.assertRaises(ValueError):
            aggregate_signals([["music"]] * 10, min_count=1)
        with self.assertRaises(ValueError):
            aggregate_signals([["music"]] * 10, min_players=2, min_count=3)

    def test_output_is_valid_m6_aggregate_signals(self):
        from server.providers.contract import M6_IN
        from server.providers.schema import validate

        out = aggregate_signals([["music", "outdoors"]] * 12)
        validate({"recentQuestionIds": [], "categoryMix": {c: 1 for c in M6_IN["properties"]["categoryMix"]["properties"]},
                  "aggregateSignals": out, "count": 3}, M6_IN)


if __name__ == "__main__":
    unittest.main()
