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
