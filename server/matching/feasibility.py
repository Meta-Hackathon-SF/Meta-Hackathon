"""Hard feasibility gates for Group Quests team matching.

Pure, deterministic, stdlib only. Nothing here relaxes a constraint: a group is
returned only if every member shares one common window of at least
MIN_ACTIVITY_MINUTES. Budget and other private values stay server-side.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import reduce
from itertools import combinations
from typing import Sequence, Tuple

from server.matching.models import (
    MAX_GROUP_SIZE,
    MIN_GROUP_SIZE,
    Candidate,
    MatchInput,
    MatchingError,
    ValidationError,
    Window,
)

MIN_ACTIVITY_MINUTES = 30
MAX_POOL = 12
MAX_SHORTLIST = 8
MAX_WINDOW_SCORE_MINUTES = 240
SIZE_WEIGHT = 0.1
REQUESTER_SHARED_WEIGHT = 2


@dataclass(frozen=True)
class FeasibleGroup:
    member_ids: Tuple[str, ...]
    common_windows: Tuple[Window, ...]
    shared_interests: Tuple[str, ...]
    max_activity_minutes: int
    budget_cap_minor: int
    baseline_score: float


def intersect_windows(a: Sequence[Window], b: Sequence[Window]) -> Tuple[Window, ...]:
    """Pairwise intersection of half-open intervals; empty results dropped."""
    out = []
    for wa in a:
        for wb in b:
            start = max(wa.start, wb.start)
            end = min(wa.end, wb.end)
            if start < end:
                out.append(Window(start, end))
    return tuple(sorted(out, key=lambda w: (w.start, w.end)))


def _long_enough(windows: Sequence[Window]) -> Tuple[Window, ...]:
    return tuple(w for w in windows if w.minutes >= MIN_ACTIVITY_MINUTES)


def _interest_keys(c: Candidate) -> frozenset:
    return frozenset(i.casefold() for i in c.public_profile.public_interests)


def _check_duplicates(inp: MatchInput) -> None:
    ids = [c.participant_id for c in inp.candidates]
    if len(set(ids)) != len(ids):
        raise ValidationError("candidates", "duplicate participant")


def find_requester(inp: MatchInput) -> Candidate:
    match = next((c for c in inp.candidates if c.participant_id == inp.requester_id), None)
    if match is None:
        raise MatchingError("FORBIDDEN", "Requester is not an authorized candidate",
                            retryable=False)
    if match.intent.community_id != inp.community_id:
        raise MatchingError("FORBIDDEN", "Requester is outside the community", retryable=False)
    if match.intent.max_duration_minutes < MIN_ACTIVITY_MINUTES:
        raise MatchingError("FORBIDDEN", "Requester duration too short", retryable=False)
    return match


def _same_scope(inp: MatchInput, req: Candidate, c: Candidate) -> bool:
    return (c.intent.community_id == inp.community_id
            and c.intent.area_id == req.intent.area_id
            and c.intent.currency == req.intent.currency)


def _others_in_scope(inp: MatchInput) -> Tuple[Candidate, ...]:
    _check_duplicates(inp)
    req = find_requester(inp)
    return tuple(c for c in inp.candidates
                 if c.participant_id != req.participant_id and _same_scope(inp, req, c))


def eligible_candidates(inp: MatchInput) -> Tuple[Candidate, ...]:
    req = find_requester(inp)
    scoped = _others_in_scope(inp)
    req_keys = _interest_keys(req)
    ok = [c for c in scoped
          if c.intent.max_duration_minutes >= MIN_ACTIVITY_MINUTES
          and _long_enough(intersect_windows(req.intent.availability, c.intent.availability))]
    ok.sort(key=lambda c: (-len(req_keys & _interest_keys(c)), c.participant_id))
    return tuple(ok[:MAX_POOL])


def _shared_interests(members: Sequence[Candidate]) -> Tuple[str, ...]:
    counts: dict = {}
    first_form: dict = {}
    for m in members:
        for key in _interest_keys(m):
            counts[key] = counts.get(key, 0) + 1
        for raw in m.public_profile.public_interests:
            first_form.setdefault(raw.casefold(), raw)
    shared = [k for k, n in counts.items() if n >= 2]
    shared.sort(key=lambda k: (-counts[k], k))
    return tuple(first_form[k] for k in shared)


def _score(shared: Tuple[str, ...], req: Candidate, size: int, longest: float) -> float:
    req_keys = _interest_keys(req)
    with_req = sum(1 for s in shared if s.casefold() in req_keys)
    return (with_req * REQUESTER_SHARED_WEIGHT + len(shared) + SIZE_WEIGHT * size
            + min(longest, MAX_WINDOW_SCORE_MINUTES) / MAX_WINDOW_SCORE_MINUTES)


def _build_group(req: Candidate, others: Sequence[Candidate]):
    ordered = (req,) + tuple(sorted(others, key=lambda c: c.participant_id))
    windows = _long_enough(reduce(intersect_windows,
                                  (m.intent.availability for m in ordered)))
    if not windows:
        return None
    longest = max(w.minutes for w in windows)
    shared = _shared_interests(ordered)
    return FeasibleGroup(
        member_ids=tuple(m.participant_id for m in ordered),
        common_windows=windows,
        shared_interests=shared,
        max_activity_minutes=int(min(min(m.intent.max_duration_minutes for m in ordered),
                                     longest)),
        budget_cap_minor=min(m.intent.max_budget_minor for m in ordered),
        baseline_score=_score(shared, req, len(ordered), longest),
    )


def enumerate_groups(inp: MatchInput) -> Tuple[FeasibleGroup, ...]:
    req = find_requester(inp)
    pool = eligible_candidates(inp)
    groups = []
    for k in range(MIN_GROUP_SIZE - 1, MAX_GROUP_SIZE):
        for combo in combinations(pool, k):
            group = _build_group(req, combo)
            if group is not None:
                groups.append(group)
    groups.sort(key=lambda g: (-g.baseline_score, -len(g.member_ids), g.member_ids))
    return tuple(groups[:MAX_SHORTLIST])


def diagnose_no_match(inp: MatchInput) -> str:
    if len(_others_in_scope(inp)) < MIN_GROUP_SIZE - 1:
        return "too_few"
    if enumerate_groups(inp):
        return "constraints"
    return "no_common_time"
