# ruff: noqa: E501
"""Input-adaptive signal weights for the code-side parts of matching (brightness and tie-breaks).

Muse decides grouping by meaning; its internal weighting is not inspectable. These weights are the
ones code controls, and they move with the input:

* keyword reliability: short answers ("nobody", "every day") share almost no words, so keyword cosine
  is noisy; its weight rises from 0.5 to 1.0 as the median answer reaches ~5 meaningful words.
* activity trust: Group/Event/topic boosts only mean something when enough people opted in. The scale
  rises from 0 to 1 as opt-in coverage goes from 0% to 50%.

Everything is bounded, deterministic and computed from counts only (no text, no ids leave).
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass

from server.matching.baseline import tokens
from server.matching.models import FormationSnapshot

KEYWORD_MIN, KEYWORD_FULL_AT_TOKENS = 0.5, 5.0
ACTIVITY_FULL_AT_COVERAGE = 0.5


@dataclass(frozen=True)
class Weights:
    keyword: float  # multiplier on keyword cosine, 0.5..1.0
    activity: float  # multiplier on Group/Event/topic boosts, 0..1
    players: int
    median_tokens: float
    optin_coverage: float  # 0..1

    def to_dict(self) -> dict:
        return {
            "keyword": round(self.keyword, 2),
            "activity": round(self.activity, 2),
            "players": self.players,
            "medianTokens": round(self.median_tokens, 1),
            "optinCoverage": round(self.optin_coverage, 2),
        }


NEUTRAL = Weights(1.0, 1.0, 0, 0.0, 0.0)


def adaptive_weights(snap: FormationSnapshot) -> Weights:
    refs = set(snap.refs)
    if not refs:
        return NEUTRAL
    per_player: dict[str, int] = {}
    for a in snap.answers:
        per_player[a.id] = per_player.get(a.id, 0) + len(tokens(a.text))
    median = statistics.median(per_player.values()) if per_player else 0.0
    keyword = KEYWORD_MIN + (1 - KEYWORD_MIN) * min(1.0, median / KEYWORD_FULL_AT_TOKENS)
    coverage = len(refs & set(snap.activity)) / len(refs)
    activity = min(1.0, coverage / ACTIVITY_FULL_AT_COVERAGE)
    return Weights(keyword, activity, len(refs), float(median), coverage)


# --- cold start: how much to trust ONE player's evidence ------------------------------------------
#
# adaptive_weights() above looks at the whole population. A brand-new player is thinner evidence than
# the population median: one short answer, no history, no opt-in. user_weights() scales the same two
# code-side levers per player and reports how much weight is left for Muse's meaning-based judgement.
# Bounded, deterministic, counts only. For a pair, use min() of the two players' weights.

KEYWORD_COLD_FLOOR = 0.3  # never trust keywords less than this, even for one 1-word answer
EVIDENCE_FULL_AT_ANSWERS = 5  # 5 answers this cycle = fully established
ACTIVITY_PER_ANSWER = 0.1  # opted-in activity earns trust gradually: 0.5 + 0.1 per answer, max 1.0


@dataclass(frozen=True)
class UserWeights:
    keyword: float  # multiplier on keyword cosine, KEYWORD_COLD_FLOOR..1.0
    activity: float  # multiplier on Group/Event/topic boosts, 0..1
    muse: float  # share left to Muse meaning = 1 - keyword/2, 0.5..0.85
    answers: int
    median_tokens: float
    has_activity: bool

    def to_dict(self) -> dict:
        return {
            "keyword": round(self.keyword, 2),
            "activity": round(self.activity, 2),
            "muse": round(self.muse, 2),
            "answers": self.answers,
            "medianTokens": round(self.median_tokens, 1),
            "hasActivity": self.has_activity,
        }


def user_weights(answers: int, median_tokens: float, has_activity: bool) -> UserWeights:
    """Per-player weights: thin evidence -> low keyword, zero activity, more weight on Muse."""
    answers = max(0, answers)
    fill = min(1.0, max(0.0, median_tokens) / KEYWORD_FULL_AT_TOKENS)
    base = KEYWORD_MIN + (1 - KEYWORD_MIN) * fill
    evidence = 0.6 + 0.4 * min(1.0, max(0, answers - 1) / (EVIDENCE_FULL_AT_ANSWERS - 1))
    keyword = max(KEYWORD_COLD_FLOOR, base * evidence)
    activity = min(1.0, 0.5 + ACTIVITY_PER_ANSWER * answers) if has_activity else 0.0
    return UserWeights(keyword, activity, 1 - keyword / 2, answers, median_tokens, has_activity)


def pair_user_weights(a: UserWeights, b: UserWeights) -> UserWeights:
    """A pair is only as well-evidenced as its thinner side."""
    keyword, activity = min(a.keyword, b.keyword), min(a.activity, b.activity)
    return UserWeights(
        keyword, activity, 1 - keyword / 2, min(a.answers, b.answers),
        min(a.median_tokens, b.median_tokens), a.has_activity and b.has_activity,
    )
