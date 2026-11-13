"""Aggregate signal tags for M6 question generation, computed by code.

Inputs are per-player sets of allowlisted labels that another owner already
reduced from private data: D010 activity topics (Patrik's ``derive_topics``)
or theme tags. This module never sees text. It turns them into the
``aggregateSignals`` M6 accepts: ``[{tag, share}]`` where

  - only players who opted in are counted (the caller passes only them)
  - nothing is produced for a population smaller than ``min_players``
  - a tag is dropped unless at least ``min_count`` players carry it, so a tag
    can never point at one or two people
  - shares are rounded to ``share_step`` so exact counts cannot be recovered
  - at most ``max_tags`` tags, most common first, ties by tag name

What leaves here is statistics about the community, never about a person.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from typing import Iterable

_TAG = re.compile(r"^[a-z][a-z0-9_]{0,39}$")

MIN_PLAYERS = 10
MIN_COUNT = 5
SHARE_STEP = 0.05
MAX_TAGS = 20


def aggregate_signals(per_player: Iterable[Iterable[str]], *, min_players: int = MIN_PLAYERS,
                      min_count: int = MIN_COUNT, share_step: float = SHARE_STEP,
                      max_tags: int = MAX_TAGS, allowed: Iterable[str] | None = None) -> list[dict[str, float | str]]:
    """``[{tag, share}]`` for M6, thresholded and rounded. See module docstring."""
    if min_count < 3 or min_players < min_count:
        raise ValueError("thresholds too low to keep tags anonymous")
    allow = set(allowed) if allowed is not None else None
    players = 0
    counts: Counter[str] = Counter()
    for tags in per_player:
        players += 1
        unique = {t for t in tags if isinstance(t, str) and _TAG.match(t) and (allow is None or t in allow)}
        counts.update(unique)
    if players < min_players:
        return []
    rows = []
    for tag, n in counts.items():
        if n < min_count:
            continue
        share = math.floor((n / players) / share_step + 0.5) * share_step
        share = min(1.0, max(share_step, round(share, 4)))
        rows.append({"tag": tag, "share": share, "_n": n})
    rows.sort(key=lambda r: (-r["_n"], r["tag"]))
    return [{"tag": r["tag"], "share": r["share"]} for r in rows[:max_tags]]
