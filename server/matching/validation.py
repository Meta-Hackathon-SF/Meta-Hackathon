"""Deterministic validation of proposed constellations. Muse proposes, this decides."""
from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Sequence

from server.matching.models import MAX_CONSTELLATION_SIZE, MIN_CONSTELLATION_SIZE, pair


def violations(groups: Sequence[Sequence[str]], eligible: Iterable[str],
               blocked_pairs: Iterable[tuple[str, str]]) -> list[str]:
    """Return human-readable violation codes; empty list means valid.

    Rules: size 3-5, every eligible ref exactly once, no unknown refs, no blocked pair.
    Codes never include answer text.
    """
    eligible_set = set(eligible)
    blocked = {pair(a, b) for a, b in blocked_pairs}
    problems: list[str] = []
    counts = Counter(ref for g in groups for ref in g)
    for i, group in enumerate(groups):
        if not MIN_CONSTELLATION_SIZE <= len(set(group)) <= MAX_CONSTELLATION_SIZE:
            problems.append(f"size:{i}")
        if len(set(group)) != len(group):
            problems.append(f"duplicate_in_group:{i}")
        members = sorted(set(group))
        for a_idx, a in enumerate(members):
            for b in members[a_idx + 1:]:
                if pair(a, b) in blocked:
                    problems.append(f"blocked_pair:{i}")
    unknown = sorted(set(counts) - eligible_set)
    if unknown:
        problems.append(f"unknown_refs:{len(unknown)}")
    missing = sorted(eligible_set - set(counts))
    if missing:
        problems.append(f"unplaced:{len(missing)}")
    repeated = sorted(r for r, c in counts.items() if c > 1)
    if repeated:
        problems.append(f"placed_twice:{len(repeated)}")
    return problems
