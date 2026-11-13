"""D009 brightness + D010 context (proposed by Will; forced in ahead of the
owners' ACKs, see docs/DECISIONS.md). Code only, no model call.

* ``pair_closeness``: per member pair, keyword-baseline cosine of their answers
  plus small capped boosts for shared Groups, shared Events and shared
  allowlisted topics (only for players who opted in to activity signals).
  Answers dominate: boosts add at most ``MAX_BOOST`` in total.
* ``bands_for_viewer``: turns the viewer's scores into "bright" | "mid" |
  "faint" by rank inside the constellation. The raw score never leaves the
  server, and the viewer's own handle gets no band.
* ``member_context``: per viewer, counts only (how many other members share a
  Group, are already friends, share an event). Never which member.
"""
from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from itertools import combinations

from .baseline import cosine, player_vectors
from .models import ActivitySignals, FormationSnapshot, pair

GROUP_BOOST, GROUP_CAP = 0.08, 0.16
EVENT_BOOST, EVENT_CAP = 0.08, 0.16
TOPIC_BOOST, TOPIC_CAP = 0.04, 0.12
MAX_BOOST = 0.3
FAINT_FLOOR = 0.05  # below this a member is always "faint"
BANDS = ("bright", "mid", "faint")


def activity_boost(a: ActivitySignals | None, b: ActivitySignals | None) -> float:
    if a is None or b is None:
        return 0.0
    groups = len(set(a.group_ids) & set(b.group_ids))
    events = len(set(a.event_ids) & set(b.event_ids))
    topics = len(set(a.topics) & set(b.topics))
    boost = (min(GROUP_CAP, groups * GROUP_BOOST) + min(EVENT_CAP, events * EVENT_BOOST)
             + min(TOPIC_CAP, topics * TOPIC_BOOST))
    return min(MAX_BOOST, boost)


def pair_closeness(snap: FormationSnapshot, refs: Sequence[str]) -> tuple[tuple[str, str, float], ...]:
    """(playerA, playerB, score) for each pair of refs, sorted, scores in [0, 1]."""
    vectors = player_vectors(a for a in snap.answers if a.id in set(refs))
    out = []
    for ra, rb in combinations(sorted(refs), 2):
        base = cosine(vectors.get(ra, {}), vectors.get(rb, {}))  # type: ignore[arg-type]
        score = min(1.0, max(0.0, base + activity_boost(snap.activity.get(ra), snap.activity.get(rb))))
        a, b = pair(snap.id_map[ra], snap.id_map[rb])
        out.append((a, b, round(score, 4)))
    return tuple(sorted(out))


def _score(closeness: Sequence[tuple[str, str, float]], x: str, y: str) -> float:
    a, b = pair(x, y)
    for p, q, s in closeness:
        if (p, q) == (a, b):
            return s
    return 0.0


def bands_for_viewer(viewer: str, member_ids: Sequence[str],
                     closeness: Sequence[tuple[str, str, float]]) -> dict[str, str]:
    """Other members -> band, by rank of closeness to the viewer. Ties share a band."""
    others = [m for m in member_ids if m != viewer]
    if not others:
        return {}
    scored = sorted(others, key=lambda m: (-_score(closeness, viewer, m), m))
    n = len(scored)
    n_bright = max(1, math.ceil(n / 3))
    n_faint = n // 3
    bands: dict[str, str] = {}
    for i, member in enumerate(scored):
        band = "bright" if i < n_bright else "faint" if i >= n - n_faint else "mid"
        if i and _score(closeness, viewer, member) == _score(closeness, viewer, scored[i - 1]):
            band = bands[scored[i - 1]]  # equal closeness never gets a dimmer band
        if _score(closeness, viewer, member) < FAINT_FLOOR:
            band = "faint"
        bands[member] = band
    return bands


def member_context(snap: FormationSnapshot, refs: Sequence[str]) -> dict[str, dict[str, int]]:
    """playerId -> counts for that viewer. Players without activity get zeros."""
    by_ref: Mapping[str, ActivitySignals] = snap.activity
    out: dict[str, dict[str, int]] = {}
    for viewer in refs:
        mine = by_ref.get(viewer)
        shared_group = friends = same_event = 0
        if mine is not None:
            for other in refs:
                if other == viewer:
                    continue
                theirs = by_ref.get(other)
                if theirs is None:
                    continue
                shared_group += bool(set(mine.group_ids) & set(theirs.group_ids))
                same_event += bool(set(mine.event_ids) & set(theirs.event_ids))
                friends += bool(theirs.profile_id and theirs.profile_id in mine.friend_ids)
        out[snap.id_map[viewer]] = {"sharedGroupStars": shared_group, "alreadyFriends": friends,
                                    "sameEventStars": same_event}
    return out


SIMILAR_FLOOR = 0.15  # closeness at or above this counts as "people like you"
HEAT_THRESHOLD = 3


def heat_bucket(count: int) -> str | None:
    """Bucketed, thresholded count. None means the event is never shown."""
    if count < HEAT_THRESHOLD:
        return None
    return "10+" if count >= 10 else "6-9" if count >= 6 else "3-5"


def event_heat(snap: FormationSnapshot, viewer_ref: str) -> list[dict[str, str]]:
    """D010 "Where people like you are going": per event id, how many players
    similar to the viewer are interested, bucketed and thresholded by code.
    Only players who opted in to activity are counted; never who they are."""
    if viewer_ref not in snap.id_map:
        return []
    others = [r for r in snap.refs if r != viewer_ref and r in snap.activity]
    scores = {(a, b): s for a, b, s in pair_closeness(snap, [viewer_ref, *others])}
    viewer = snap.id_map[viewer_ref]
    counts: dict[str, int] = {}
    for ref in others:
        if scores.get(pair(viewer, snap.id_map[ref]), 0.0) < SIMILAR_FLOOR:
            continue
        for event in snap.activity[ref].event_ids:
            counts[event] = counts.get(event, 0) + 1
    rows = [{"eventId": e, "bucket": b} for e, n in counts.items() if (b := heat_bucket(n))]
    return sorted(rows, key=lambda r: (-counts[r["eventId"]], r["eventId"]))
