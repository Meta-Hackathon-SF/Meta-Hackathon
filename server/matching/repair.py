"""Deterministic repair of near-valid M4 proposals.

Live models often return a grouping that is right in meaning but breaks one rule: a missing
or duplicated ref, a group of 6, a group of 2, or one blocked pair. Rejecting the whole
proposal throws away Muse's judgment and costs another 20 s call. Repair keeps every
Muse group that is already legal, evicts the minimum number of refs from the rest, and
re-places them by keyword affinity. A repaired group is marked loose so the UI stays honest.
Repair never invents a grouping from scratch: if fewer than half the refs survive in their
Muse group, it gives up and the caller falls back.
"""
from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from server.matching.baseline import Similarity, partition
from server.matching.models import (
    MIN_CONSTELLATION_SIZE,
    MatchingError,
    pair,
)
from server.matching.validation import violations

MIN_KEPT_SHARE = 0.5
REPAIRED_CONFIDENCE_CAP = 0.49  # below LOOSE_MATCH_CONFIDENCE, so repaired groups read loose


@dataclass(frozen=True)
class Repair:
    groups: tuple[tuple[str, ...], ...]
    meanings: tuple[str, ...]
    confidences: tuple[float, ...]
    touched: tuple[bool, ...]  # group differs from Muse's proposal
    moved_refs: int


def _affinity(ref: str, members: Sequence[str], sim: Similarity) -> float:
    return sum(sim.get(pair(ref, m), 0.0) for m in members) / len(members) if members else 0.0


def _sanitize(proposal: Sequence[tuple[Sequence[str], str, float]], eligible: set[str],
              blocked: set[tuple[str, str]], sim: Similarity
              ) -> tuple[list[list[str]], list[int], set[str]]:
    """Drop unknown/duplicate refs, evict blocked and oversize members. Returns kept groups,
    their source index, and the evicted pool."""
    seen: set[str] = set()
    kept: list[list[str]] = []
    source: list[int] = []
    pool: set[str] = set()
    for idx, (refs, _, _) in enumerate(proposal):
        group: list[str] = []
        for ref in refs:
            if ref not in eligible or ref in seen:
                continue
            seen.add(ref)
            if any(pair(ref, m) in blocked for m in group):
                pool.add(ref)
                continue
            group.append(ref)
        if len(group) < MIN_CONSTELLATION_SIZE:
            pool.update(group)
            continue
        kept.append(group)
        source.append(idx)
    pool.update(eligible - seen)
    return kept, source, pool


def _place(pool: Iterable[str], groups: list[list[str]], blocked: set[tuple[str, str]],
           sim: Similarity) -> list[str]:
    """Put pool refs into groups with room, best affinity first. Returns leftovers."""
    leftovers = []
    for ref in sorted(pool):
        options = [i for i, g in enumerate(groups)
                   if not any(pair(ref, m) in blocked for m in g)]
        if not options:
            leftovers.append(ref)
            continue
        best = max(options, key=lambda i: (_affinity(ref, groups[i], sim), -i))
        groups[best] = groups[best] + [ref]
    return leftovers


def _swap_in(ref: str, groups: list[list[str]], blocked: set[tuple[str, str]],
             sim: Similarity) -> bool:
    """Place ref into a full group by moving one of its members to a group with room."""
    def legal(r: str, g: Sequence[str]) -> bool:
        return not any(pair(r, m) in blocked for m in g)

    moves = []
    for gi, group in enumerate(groups):
        if not legal(ref, group):
            continue
        for member in group:
            rest = [m for m in group if m != member]
            if not legal(ref, rest):
                continue
            for hi, host in enumerate(groups):
                if hi != gi and legal(member, host):
                    score = _affinity(ref, rest, sim) + _affinity(member, host, sim)
                    moves.append((score, gi, member, hi))
    if not moves:
        return False
    _, gi, member, hi = max(moves, key=lambda m: (m[0], -m[1], m[2], -m[3]))
    groups[gi] = [m for m in groups[gi] if m != member] + [ref]
    groups[hi] = groups[hi] + [member]
    return True


def repair_proposal(proposal: Sequence[tuple[Sequence[str], str, float]],
                    eligible: Sequence[str], blocked_pairs: Iterable[tuple[str, str]],
                    sim: Similarity) -> Repair | None:
    """Return a valid repaired grouping, or None when repair would not preserve Muse's
    grouping (caller then uses Fallback grouping)."""
    eligible_set = set(eligible)
    blocked = {pair(a, b) for a, b in blocked_pairs}
    kept, source, pool = _sanitize(proposal, eligible_set, blocked, sim)
    kept_refs = sum(len(g) for g in kept)
    if not eligible_set or kept_refs < MIN_KEPT_SHARE * len(eligible_set):
        return None
    originals = [tuple(sorted(g)) for g in kept]
    leftovers = [r for r in _place(pool, kept, blocked, sim)
                 if not _swap_in(r, kept, blocked, sim)]
    extra_groups: list[tuple[str, ...]] = []
    if leftovers:
        if len(leftovers) < MIN_CONSTELLATION_SIZE:
            return None
        try:
            extra_groups = list(partition(leftovers, sim, blocked))
        except MatchingError:
            return None
    groups = tuple(tuple(sorted(g)) for g in kept) + tuple(extra_groups)
    if violations(groups, eligible_set, blocked):
        return None
    meanings, confidences, touched = [], [], []
    for i, group in enumerate(groups):
        if i < len(kept):
            _, meaning, confidence = proposal[source[i]]
            changed = group != originals[i] or tuple(sorted(
                r for r in proposal[source[i]][0])) != group
            meanings.append(meaning)
            confidences.append(min(confidence, REPAIRED_CONFIDENCE_CAP) if changed
                               else confidence)
            touched.append(changed)
        else:
            meanings.append("Grouped by code after Muse's proposal left these apart")
            confidences.append(0.0)
            touched.append(True)
    return Repair(groups, tuple(meanings), tuple(confidences), tuple(touched),
                  moved_refs=len(eligible_set) - sum(
                      len(set(g) & set(proposal[source[i]][0]))
                      for i, g in enumerate(groups[:len(kept)])))
