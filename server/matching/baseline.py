"""Keyword baseline grouper and constrained partitioner.

The baseline groups players by shared keywords only (weighted bag of words, cosine
similarity). It exists to (1) show where meaning-based formation beats keywords and
(2) provide a deterministic, always-valid "Fallback grouping" when Muse output fails
validation twice. Stdlib only, deterministic.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from itertools import combinations

from server.matching.models import (
    MIN_CONSTELLATION_SIZE,
    MatchingError,
    PromptText,
    pair,
)

_TOKEN_RE = re.compile(r"[a-z']+")
_STOPWORDS = frozenset("""
a about after again all already am an and any are as at be because been but by can could
did do does doing don't for from get gets got had has have having he her here hers him his
how i i'm if in into is it it's its just like lot me more most my no nor not now of off on
one only or other our out over own really same she should so some such than that the their
them then there these they this those through to too under until up very was we were what
when where which while who why will with would you your yours honestly mostly usually
""".split())

Similarity = Mapping[tuple[str, str], float]
Group = tuple[str, ...]
MAX_SEARCH_STEPS = 50_000


def _stem(token: str) -> str:
    for suffix in ("ing", "ed", "es", "s"):
        if len(token) > len(suffix) + 2 and token.endswith(suffix):
            return token[: -len(suffix)]
    return token


def tokens(text: str) -> tuple[str, ...]:
    words = _TOKEN_RE.findall(text.lower())
    return tuple(_stem(w) for w in words if w not in _STOPWORDS and len(w) > 2)


def player_vectors(answers: Iterable[PromptText]) -> dict[str, Counter]:
    """One weighted keyword vector per player ref."""
    vectors: dict[str, Counter] = {}
    for answer in answers:
        bag = vectors.setdefault(answer.id, Counter())
        for tok in tokens(answer.text):
            bag[tok] += answer.weight
    return vectors


def cosine(a: Counter, b: Counter) -> float:
    dot = sum(v * b.get(k, 0.0) for k, v in a.items())
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    return dot / (na * nb) if na and nb else 0.0


def similarity_matrix(answers: Iterable[PromptText]) -> dict[tuple[str, str], float]:
    vectors = player_vectors(answers)
    return {pair(a, b): cosine(vectors[a], vectors[b])
            for a, b in combinations(sorted(vectors), 2)}


def group_sizes(n: int) -> tuple[int, ...]:
    """Split n players into as many groups as possible with at least MIN_CONSTELLATION_SIZE
    each, as even as possible. There is no maximum: sizes land in [5, 9]."""
    if n < MIN_CONSTELLATION_SIZE:
        raise MatchingError("INVALID_INPUT", "Not enough eligible players to form",
                            retryable=False)
    k = n // MIN_CONSTELLATION_SIZE
    base, extra = divmod(n, k)
    return tuple(base + 1 if i < extra else base for i in range(k))


def _group_affinity(ref: str, members: Sequence[str], sim: Similarity) -> float:
    if not members:
        return 0.0
    return sum(sim.get(pair(ref, m), 0.0) for m in members) / len(members)


def _pick_seeds(refs: Sequence[str], k: int, sim: Similarity,
                blocked: set[tuple[str, str]]) -> tuple[str, ...]:
    """Most-connected ref first, then refs least similar to existing seeds."""
    def degree(r: str) -> float:
        return sum(sim.get(pair(r, o), 0.0) for o in refs if o != r)

    seeds = [max(refs, key=lambda r: (degree(r), r))]
    while len(seeds) < k:
        remaining = [r for r in refs if r not in seeds]
        seeds.append(min(remaining, key=lambda r: (max(sim.get(pair(r, s), 0.0)
                                                       for s in seeds), r)))
    return tuple(seeds)


def partition(refs: Sequence[str], sim: Similarity,
              blocked_pairs: Iterable[tuple[str, str]] = ()) -> tuple[Group, ...]:
    """Constrained partition: sizes 5+, everyone once, no blocked pair together.

    Seeds one ref per group, then places the most constrained refs first into the group
    with the highest keyword affinity, backtracking when a block leaves no legal group.
    Deterministic for the same input. Raises MatchingError if no legal partition is found
    within MAX_SEARCH_STEPS.
    """
    ordered = sorted(set(refs))
    blocked = {pair(a, b) for a, b in blocked_pairs}
    sizes = group_sizes(len(ordered))
    seeds = _pick_seeds(ordered, len(sizes), sim, blocked)
    groups: list[list[str]] = [[s] for s in seeds]
    blocked_degree = Counter(r for p in blocked for r in p)
    pending = sorted((r for r in ordered if r not in seeds),
                     key=lambda r: (-blocked_degree[r], r))
    steps = [0]

    def legal(ref: str, gi: int) -> bool:
        return len(groups[gi]) < sizes[gi] and not any(
            pair(ref, m) in blocked for m in groups[gi])

    def place(index: int) -> bool:
        if index == len(pending):
            return True
        steps[0] += 1
        if steps[0] > MAX_SEARCH_STEPS:
            return False
        ref = pending[index]
        options = sorted((gi for gi in range(len(groups)) if legal(ref, gi)),
                         key=lambda gi: (-_group_affinity(ref, groups[gi], sim), gi))
        for gi in options:
            groups[gi].append(ref)
            if place(index + 1):
                return True
            groups[gi].pop()
        return False

    if place(0):
        return tuple(tuple(sorted(g)) for g in groups)
    raise MatchingError("INVALID_INPUT", "Blocks make grouping infeasible", retryable=False)


def baseline_groups(answers: Sequence[PromptText],
                    blocked_ref_pairs: Iterable[tuple[str, str]] = ()) -> tuple[Group, ...]:
    sim = similarity_matrix(answers)
    refs = sorted({a.id for a in answers})
    return partition(refs, sim, blocked_ref_pairs)


def same_group(groups: Sequence[Group], members: Sequence[str]) -> bool:
    wanted = set(members)
    return any(wanted <= set(g) for g in groups)
