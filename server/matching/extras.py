"""v3 progress trace, event interest counts, custom-event cluster finder. Code only.

Progress: attempts are pairs the matcher really scored (pair_closeness), restricted to the
viewer's own stars and second-degree neighbours, paced into steps. R1: star indices only.
Interest: bucketed, 3+ only, approved events only, one snapshot per hour (R3), never per change.
Clusters: players with repeated co-membership across weeks; aggregate output, never ids to Muse.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Collection, Iterable, Mapping, Sequence

from server.matching.closeness import heat_bucket

STEP_SIZE = 5
CLUSTER_MIN, CLUSTER_MAX = 6, 30
CLUSTER_PAIR_WEIGHT = 3
HOUR_S = 3600


def progress_events(
    scored: Sequence[tuple[str, str, float]],
    stars: Mapping[str, int],
    viewer_and_neighbours: Collection[str],
    kept_floor: float = 0.35,
    *,
    visualization: bool = False,
) -> list[dict]:
    """ProgressEvent wire dicts from real scored pairs. Pairs outside the viewer's own
    stars/neighbours are never shown. With no trace, pass visualization=True for a labeled one."""
    allowed = set(viewer_and_neighbours)
    rows = [
        (a, b, s)
        for a, b, s in scored
        if a in allowed and b in allowed and a in stars and b in stars
    ]
    rows.sort(key=lambda r: (r[0], r[1]))
    attempts = [
        {
            "seq": i,
            "fromStarIndex": stars[a],
            "toStarIndex": stars[b],
            "outcome": "kept" if s >= kept_floor else "dropped",
        }
        for i, (a, b, s) in enumerate(rows)
    ]
    source = "visualization" if visualization else "trace"
    total = max(1, -(-len(attempts) // STEP_SIZE))
    events = [_ev("queued", 0, total, [], source)]
    for step in range(1, total + 1):
        chunk = attempts[(step - 1) * STEP_SIZE : step * STEP_SIZE]
        events.append(_ev("running" if step < total else "done", step, total, chunk, source))
    return events


def _ev(phase: str, step: int, total: int, attempts: list[dict], source: str) -> dict:
    return {
        "phase": phase,
        "step": step,
        "totalSteps": total,
        "attempts": attempts,
        "source": source,
        "isVisualization": source == "visualization",
    }


class HourlyInterest:
    """Per-viewer interest buckets, recomputed at most once per hour (R3 differencing fix)."""

    def __init__(self, compute, clock) -> None:
        self._compute, self._clock = compute, clock
        self._cache: dict[str, tuple[int, list[dict]]] = {}

    def get(self, viewer: str) -> list[dict]:
        hour = int(self._clock() // HOUR_S)
        hit = self._cache.get(viewer)
        if hit and hit[0] == hour:
            return hit[1]
        rows = self._compute(viewer)
        self._cache = {**self._cache, viewer: (hour, rows)}
        return rows


def constellation_interest(
    viewer: str,
    peers: Iterable[str],
    interested: Mapping[str, Collection[str]],
    approved: Collection[str],
) -> list[dict]:
    """Per approved event: how many distinct opted-in peers (sharing a constellation with the
    viewer) are interested. Bucketed and thresholded at 3; nothing under 3, no ids, no counts."""
    ok = frozenset(approved)
    counts: Counter = Counter()
    for peer in set(peers) - {viewer}:
        counts.update(e for e in set(interested.get(peer, ())) if e in ok)
    rows = [(e, b) for e, n in counts.items() if (b := heat_bucket(n))]
    rows.sort(key=lambda r: (-counts[r[0]], r[0]))
    return [{"eventId": e, "bucket": b} for e, b in rows]


def nudge_eligible(rows: Sequence[dict], approved: Collection[str]) -> list[str]:
    """Event ids a nudge may mention: approved and with a visible bucket."""
    ok = frozenset(approved)
    return [r["eventId"] for r in rows if r["eventId"] in ok and r.get("bucket")]


def find_clusters(
    weekly_graphs: Sequence[Mapping[tuple[str, str], int]],
    min_weeks: int = 3,
    pair_weight: int = CLUSTER_PAIR_WEIGHT,
) -> list[tuple[str, ...]]:
    """Groups of 6-30 players with repeated co-membership across the last weeks. A pair counts
    when its summed weight over `min_weeks` weeks reaches `pair_weight` and it recurred in more
    than one week (a one-off match never counts). Connected components, size-bounded."""
    weeks = list(weekly_graphs)[-min_weeks:]
    if len(weeks) < min_weeks:
        return []
    total: Counter = Counter()
    seen_weeks: Counter = Counter()
    for graph in weeks:
        for p, w in graph.items():
            total[p] += w
            seen_weeks[p] += 1
    strong = {p for p, w in total.items() if w >= pair_weight and seen_weeks[p] >= 2}
    adj: dict[str, set[str]] = {}
    for a, b in strong:
        adj.setdefault(a, set()).add(b)
        adj.setdefault(b, set()).add(a)
    out, done = [], set()
    for start in sorted(adj):
        if start in done:
            continue
        comp, stack = set(), [start]
        while stack:
            n = stack.pop()
            if n in comp:
                continue
            comp.add(n)
            stack.extend(adj[n] - comp)
        done |= comp
        if CLUSTER_MIN <= len(comp) <= CLUSTER_MAX:
            out.append(tuple(sorted(comp)))
    return out


def cluster_aggregate(cluster: Sequence[str], interest_tags: Mapping[str, Collection[str]]) -> dict:
    """What Muse may see: size and allowlisted tag counts. Never player ids."""
    tags = Counter(t for p in cluster for t in set(interest_tags.get(p, ())))
    return {"clusterSize": len(cluster), "tags": [t for t, _ in tags.most_common(5)]}
