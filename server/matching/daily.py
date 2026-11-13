"""v3 daily producers, code only: tag-based daily constellations, week co-membership graph,
Sunday main constellation, week-seeded sky layout. No Muse call, no network, deterministic.

Daily method (PRD-v3): tags name a shared meaning. Muse may propose tags at day close
(see `Tag`); with none, tags are the shared keywords. Each answer goes to its best 1-2 tags.
A tag with 3+ players becomes a constellation. Blocks are respected: a blocked pair never
shares a group.
"""

from __future__ import annotations

import random
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from itertools import combinations

from server.matching.baseline import partition, player_vectors, similarity_matrix
from server.matching.models import MatchingError, PromptText, pair

MIN_VISIBLE = 3  # protocol V3.minVisibleConstellation (R2)
MAX_DAILY_PER_PLAYER = 3  # V3.maxDailyConstellations
MAX_DAILY_STARS = 12  # V3.dailyConstellationMaxStars
MAIN_MIN, MAIN_MAX = 3, 5
SECOND_DEGREE_MIN_ELIGIBLE = 30
SECOND_DEGREE_MAX_PER_STAR = 2
TAGS_PER_ANSWER = 2
SKY_STARS = 10_000

Group = tuple[str, ...]


@dataclass(frozen=True)
class Tag:
    """A meaning tag: a name that is never shown, plus the keywords that evidence it."""

    tag_id: str
    keywords: frozenset[str]


def keyword_tags(
    answers: Sequence[PromptText], min_players: int = MIN_VISIBLE, limit: int = 40
) -> tuple[Tag, ...]:
    """Fallback tags: shared keywords that at least `min_players` players used."""
    vectors = player_vectors(answers)
    users = Counter(tok for vec in vectors.values() for tok in vec)
    kept = sorted((t for t, n in users.items() if n >= min_players), key=lambda t: (-users[t], t))[
        :limit
    ]
    return tuple(Tag(f"kw-{t}", frozenset({t})) for t in kept)


def _score(vec: Mapping[str, float], tag: Tag) -> float:
    return sum(vec.get(k, 0.0) for k in tag.keywords)


def _drop_blocked(
    members: Iterable[str], blocked: set[tuple[str, str]], strength: Mapping[str, float]
) -> list[str]:
    """Greedy: keep strongest members first, skip anyone blocked with a kept member."""
    kept: list[str] = []
    for ref in sorted(members, key=lambda r: (-strength.get(r, 0.0), r)):
        if not any(pair(ref, k) in blocked for k in kept):
            kept.append(ref)
    return kept


def daily_groups(
    answers: Sequence[PromptText],
    blocked_ref_pairs: Iterable[tuple[str, str]] = (),
    tags: Sequence[Tag] | None = None,
) -> tuple[tuple[Group, ...], tuple[str, ...]]:
    """Return (constellations, unplaced refs). Each constellation has 3..12 refs."""
    blocked = {pair(a, b) for a, b in blocked_ref_pairs}
    vectors = player_vectors(answers)
    use = tuple(tags) if tags is not None else keyword_tags(answers)
    members: dict[str, list[tuple[float, str]]] = {t.tag_id: [] for t in use}
    for ref, vec in vectors.items():
        ranked = sorted(((_score(vec, t), t.tag_id) for t in use), key=lambda x: (-x[0], x[1]))
        for score, tag_id in ranked[:TAGS_PER_ANSWER]:
            if score > 0:
                members[tag_id].append((score, ref))
    seen: set[Group] = set()
    out: list[Group] = []
    for tag_id in sorted(members):
        strength = {r: s for s, r in members[tag_id]}
        kept = _drop_blocked(strength, blocked, strength)[:MAX_DAILY_STARS]
        group = tuple(sorted(kept))
        if len(group) >= MIN_VISIBLE and group not in seen:
            seen.add(group)
            out.append(group)
    out.sort(key=lambda g: (-len(g), g))
    per_player: Counter = Counter()
    final: list[Group] = []
    for g in out:
        if all(per_player[r] < MAX_DAILY_PER_PLAYER for r in g):
            final.append(g)
            per_player.update(g)
    placed = {r for g in final for r in g}
    return tuple(final), tuple(sorted(set(vectors) - placed))


def groups_from_themes(
    themes: Iterable[Sequence[str]],
    known_refs: Iterable[str],
    blocked_ref_pairs: Iterable[tuple[str, str]] = (),
) -> tuple[tuple[Group, ...], tuple[str, ...]]:
    """Use Muse (M3) theme memberships directly as daily constellations. Code only enforces:
    known refs, no blocked pair, 3..12 stars, at most MAX_DAILY_PER_PLAYER per player."""
    known = set(known_refs)
    blocked = {pair(a, b) for a, b in blocked_ref_pairs}
    cands: list[Group] = []
    for members in themes:
        uniq = [r for r in dict.fromkeys(members) if r in known]
        kept = _drop_blocked(uniq, blocked, {})[:MAX_DAILY_STARS]
        group = tuple(sorted(kept))
        if len(group) >= MIN_VISIBLE and group not in cands:
            cands.append(group)
    cands.sort(key=lambda g: (-len(g), g))
    per_player: Counter = Counter()
    final: list[Group] = []
    for g in cands:
        if all(per_player[r] < MAX_DAILY_PER_PLAYER for r in g):
            final.append(g)
            per_player.update(g)
    placed = {r for g in final for r in g}
    return tuple(final), tuple(sorted(known - placed))


def week_graph(days: Iterable[Iterable[Sequence[str]]]) -> dict[tuple[str, str], int]:
    """Co-membership weight per pair: number of constellations they shared across the week.
    Reproducible from the day results alone."""
    weights: Counter = Counter()
    for day in days:
        for group in day:
            for a, b in combinations(sorted(set(group)), 2):
                weights[(a, b)] += 1
    return dict(weights)


def main_groups(
    players: Sequence[str],
    graph: Mapping[tuple[str, str], int],
    answers: Sequence[PromptText] = (),
    blocked_pairs: Iterable[tuple[str, str]] = (),
) -> tuple[tuple[Group, ...], tuple[str, ...]]:
    """Sunday main constellations: 3-5, one per player. Candidates are players who share 2+
    constellations or have similar answers. Players with no qualifying match are unplaced."""
    sim = dict(similarity_matrix(answers)) if answers else {}
    closeness = {
        pair(a, b): graph.get(pair(a, b), 0) + sim.get(pair(a, b), 0.0)
        for a, b in combinations(sorted(set(players)), 2)
    }
    qualified = {r for (a, b), w in graph.items() if w >= 2 for r in (a, b)}
    qualified |= {r for (a, b), s in sim.items() if s >= 0.35 for r in (a, b)}
    pool = sorted(qualified & set(players))
    if len(pool) < MAIN_MIN:
        return (), tuple(sorted(set(players)))
    try:
        groups = partition(pool, closeness, blocked_pairs)
    except MatchingError:
        return (), tuple(sorted(set(players)))
    placed = {r for g in groups for r in g}
    return groups, tuple(sorted(set(players) - placed))


def sky_positions(week_seed: str, count: int = SKY_STARS) -> tuple[tuple[int, int], ...]:
    """Week-seeded (x, y) on a 0..32767 grid. Positions reveal nothing about membership."""
    rng = random.Random(f"sky:{week_seed}")
    return tuple((rng.randrange(32768), rng.randrange(32768)) for _ in range(count))


def star_indices(week_seed: str, refs: Sequence[str], count: int = SKY_STARS) -> dict[str, int]:
    """Distinct week-randomized star index per player; changes every week."""
    if len(refs) > count:
        raise MatchingError("INVALID_INPUT", "More players than stars", retryable=False)
    rng = random.Random(f"stars:{week_seed}")
    slots = rng.sample(range(count), len(refs))
    return dict(zip(sorted(refs), slots, strict=True))


def second_degree(
    mine: Sequence[Group], all_groups: Sequence[Group], eligible: int
) -> tuple[tuple[str, Group], ...]:
    """(via_ref, group) pairs: for each star in my groups, its 2 biggest other groups.
    Empty below SECOND_DEGREE_MIN_ELIGIBLE (R2). Groups under 3 are never returned."""
    if eligible < SECOND_DEGREE_MIN_ELIGIBLE:
        return ()
    mine_set = set(mine)
    out: list[tuple[str, Group]] = []
    for ref in sorted({r for g in mine for r in g}):
        others = sorted(
            (g for g in all_groups if ref in g and g not in mine_set and len(g) >= MIN_VISIBLE),
            key=lambda g: (-len(g), g),
        )
        out.extend((ref, g) for g in others[:SECOND_DEGREE_MAX_PER_STAR])
    return tuple(out)
