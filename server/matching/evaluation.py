"""Grouping quality against a labeled synthetic gold set.

Pairwise metrics: a "gold pair" is two players whose answers mean the same thing (same gold
feeling) even when they share no keywords. Precision = share of grouped pairs that are gold;
recall = share of gold pairs grouped together. Baseline vs Muse on the same snapshot gives the
"keywords split, meaning joins" number. Synthetic only; never computed on real answers.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from itertools import combinations

from server.matching.models import pair

SYNTHETIC_LABEL = "Synthetic player"

# Each feeling has paraphrases with deliberately little word overlap.
GOLD_FEELINGS: Mapping[str, tuple[str, ...]] = {
    "eating_alone": (
        "I eat in my room so no one sees me alone",
        "cooking for one is honestly depressing",
        "I grab food and leave before anyone sits down",
        "lunch is the worst part, I never know where to sit",
        "dinner at my desk with a show on, every night",
    ),
    "faking_fine": (
        "I tell everyone I'm good even when I'm not",
        "pretending to have weekend plans so it doesn't look weird",
        "my texts home are way more upbeat than my week",
        "I laugh along in group chats but feel far away",
        "smiling through class then crashing in my dorm",
    ),
    "behind_everyone": (
        "everyone else seems to already get the material",
        "I feel like I showed up late to every friendship",
        "people here had their whole lives figured out at orientation",
        "my classmates talk about internships and I panic",
        "transferring in feels like joining a party at midnight",
    ),
    "missing_home": (
        "I miss my mom's cooking more than I expected",
        "nobody here knows the version of me from back home",
        "I call my little brother just to hear the noise",
        "the weather here makes me homesick every morning",
        "I still keep my old town's time on my phone",
    ),
    "small_joys": (
        "pickup soccer at the rec is the best part of my week",
        "found a quiet corner in the library with a window",
        "the cafe barista remembers my order now",
        "late night walks around the quad clear my head",
        "I started sketching people on the bus",
    ),
    "overwhelmed": (
        "three deadlines on the same day and no sleep",
        "my calendar has no gaps until Thanksgiving",
        "I keep saying yes to things and drowning",
        "work shifts plus labs plus club stuff, it's a lot",
        "I haven't had a slow morning since August",
    ),
}


@dataclass(frozen=True)
class PairMetrics:
    precision: float
    recall: float
    gold_pairs: int
    grouped_pairs: int
    gold_pairs_grouped: int

    def to_wire(self) -> dict:
        return {"precision": self.precision, "recall": self.recall, "goldPairs": self.gold_pairs,
                "groupedPairs": self.grouped_pairs, "goldPairsGrouped": self.gold_pairs_grouped}


def gold_snapshot(players: int, seed_offset: int = 0) -> tuple[dict, dict[str, str]]:
    """Snapshot-shaped dict plus playerId -> gold feeling. One answer per synthetic player."""
    feelings = list(GOLD_FEELINGS)
    answers, id_map, gold = [], {}, {}
    for i in range(players):
        feeling = feelings[(i + seed_offset) % len(feelings)]
        texts = GOLD_FEELINGS[feeling]
        ref, player = f"g{i + 1}", f"syn-gold-{i + 1}"
        id_map[ref] = player
        gold[player] = feeling
        answers.append({"id": ref, "text": texts[(i // len(feelings)) % len(texts)],
                        "weight": 1.0})
    return {"answers": answers, "idMap": id_map, "blockedPairs": []}, gold


def pair_metrics(groups: Sequence[Sequence[str]], gold: Mapping[str, str]) -> PairMetrics:
    grouped = {pair(a, b) for g in groups for a, b in combinations(sorted(set(g)), 2)}
    members = sorted({m for g in groups for m in g})
    gold_pairs = {pair(a, b) for a, b in combinations(members, 2) if gold.get(a) == gold.get(b)}
    hit = grouped & gold_pairs
    return PairMetrics(
        precision=round(len(hit) / len(grouped), 3) if grouped else 0.0,
        recall=round(len(hit) / len(gold_pairs), 3) if gold_pairs else 0.0,
        gold_pairs=len(gold_pairs), grouped_pairs=len(grouped), gold_pairs_grouped=len(hit))
