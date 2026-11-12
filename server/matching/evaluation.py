"""Offline evaluation harness for Group Quests matching.

Measures mechanics and constraint safety of MatchingService against synthetic pools, and
compares the Muse-chosen group with the shared-interest baseline (top of enumerate_groups,
same hard constraints). Results are only as meaningful as the port supplied: runs with a
fake port prove harness mechanics, not ranking quality, and must be labeled accordingly.
Stdlib only; no network; aggregate output contains no participant data.
"""
from __future__ import annotations

import random
import time
from datetime import datetime, timedelta, timezone
from functools import reduce
from typing import Any, Mapping, Optional, Sequence

from server.matching.feasibility import MIN_ACTIVITY_MINUTES, enumerate_groups
from server.matching.models import (
    MAX_GROUP_SIZE, MIN_GROUP_SIZE, EVIDENCE_SOURCES, NO_MATCH_REASONS, MatchInput,
    MatchingError, Matched, NoMatch, Window,
)
from server.matching.ranking import MusePortLike
from server.matching.service import MatchingService

COMMUNITY_ID = "comm_eval"
AREAS = ("area_campus", "area_downtown")
CURRENCIES = ("USD", "EUR")
INTEREST_POOL = ("photography", "coffee", "hiking", "board games", "climbing", "cooking",
                 "film", "running", "music", "pottery")
EVENT_DAY = datetime(2026, 11, 14, tzinfo=timezone.utc)
CONFIRMED_AT = "2026-11-12T20:00:00Z"
CONTRACT_VERSION = "1.0.0"
MODE = "fixture"
REQUESTER_WINDOW = (18 * 60, 22 * 60)      # minutes after midnight UTC
EARLY_WINDOW = (2 * 60, 3 * 60)            # never overlaps the requester
OFF_AREA_RATE = 0.10
OFF_CURRENCY_RATE = 0.08
NON_OVERLAP_RATE = 0.15
MIN_INTERESTS, MAX_INTERESTS = 2, 4
P50, P95 = 0.50, 0.95


def _iso(minutes: int) -> str:
    return (EVENT_DAY + timedelta(minutes=minutes)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _candidate(pid: str, number: int, interests: Sequence[str], area: str, currency: str,
               window: tuple) -> dict:
    return {
        "intent": {
            "participantId": pid, "communityId": COMMUNITY_ID, "intentVersion": 1,
            "goal": "meet people", "interests": list(interests), "areaId": area,
            "timeZone": "America/Los_Angeles",
            "availability": [{"start": _iso(window[0]), "end": _iso(window[1])}],
            "maxBudgetMinor": 1500, "currency": currency, "maxDurationMinutes": 120,
            "groupPreference": "small", "consentVersion": 1, "confirmedAt": CONFIRMED_AT,
        },
        "publicProfile": {"participantId": pid, "displayName": f"Synthetic {number}",
                          "publicInterests": list(interests), "isSynthetic": True},
    }


def _member_window(rng: random.Random) -> tuple:
    if rng.random() < NON_OVERLAP_RATE:
        return EARLY_WINDOW
    start = rng.randrange(REQUESTER_WINDOW[0], REQUESTER_WINDOW[1] - 60 + 1, 30)
    end = min(REQUESTER_WINDOW[1] + 60, start + rng.randrange(60, 241, 30))
    return (start, end)


def generate_synthetic_pools(seed: int, n_pools: int, pool_size: int = 8) -> list:
    """Deterministic MatchInput wire dicts. Requester is always the first candidate."""
    rng = random.Random(seed)
    counter = 0
    pools = []
    for pool_index in range(n_pools):
        candidates = []
        for slot in range(pool_size):
            counter += 1
            pid = f"syn_{pool_index}_{slot}"
            interests = rng.sample(INTEREST_POOL, rng.randint(MIN_INTERESTS, MAX_INTERESTS))
            if slot == 0:  # requester stays in the default scope so pools are exercised
                area, currency, window = AREAS[0], CURRENCIES[0], REQUESTER_WINDOW
            else:
                area = AREAS[1] if rng.random() < OFF_AREA_RATE else AREAS[0]
                currency = CURRENCIES[1] if rng.random() < OFF_CURRENCY_RATE else CURRENCIES[0]
                window = _member_window(rng)
            candidates.append(_candidate(pid, counter, interests, area, currency, window))
        pools.append({
            "context": {"requestId": f"eval_{seed}_{pool_index}",
                        "contractVersion": CONTRACT_VERSION, "mode": MODE},
            "communityId": COMMUNITY_ID,
            "requesterId": candidates[0]["intent"]["participantId"],
            "candidates": candidates, "minimumSize": MIN_GROUP_SIZE,
            "maximumSize": MAX_GROUP_SIZE,
        })
    return pools


# ---------------------------------------------------------------- independent re-check

def _overlap(a: Sequence[Window], b: Sequence[Window]) -> list:
    out = []
    for x in a:
        for y in b:
            lo, hi = max(x.start, y.start), min(x.end, y.end)
            if lo < hi:
                out.append(Window(lo, hi))
    return out


def count_violations(inp: MatchInput, member_ids: Sequence[str]) -> list:
    """Return the list of violated rule names for a proposed group (empty means valid)."""
    problems = []
    if inp.requester_id not in member_ids:
        problems.append("requester_missing")
    if len(set(member_ids)) != len(member_ids):
        problems.append("duplicate_member")
    if not MIN_GROUP_SIZE <= len(member_ids) <= MAX_GROUP_SIZE:
        problems.append("size")
    by_id = {c.participant_id: c for c in inp.candidates}
    if any(pid not in by_id for pid in member_ids):
        return problems + ["unknown_member"]
    intents = [by_id[pid].intent for pid in member_ids]
    if any(i.community_id != inp.community_id for i in intents):
        problems.append("community")
    if len({i.area_id for i in intents}) > 1:
        problems.append("area")
    if len({i.currency for i in intents}) > 1:
        problems.append("currency")
    if intents:
        common = reduce(_overlap, (i.availability for i in intents))
        if not any(w.minutes >= MIN_ACTIVITY_MINUTES for w in common):
            problems.append("no_common_window")
    return problems


# ---------------------------------------------------------------- metrics

def _percentile(sorted_values: Sequence[float], q: float) -> float:
    if not sorted_values:
        return 0.0
    index = min(len(sorted_values) - 1, max(0, int(round(q * len(sorted_values) + 0.5)) - 1))
    return round(sorted_values[index], 3)


def _mean(values: Sequence[float]) -> Optional[float]:
    return round(sum(values) / len(values), 4) if values else None


async def evaluate(pools: Sequence[Mapping[str, Any]], muse_port: MusePortLike, *,
                   label: str) -> dict:
    service = MatchingService(muse_port)
    no_match = {reason: 0 for reason in NO_MATCH_REASONS}
    sources = {source: 0 for source in EVIDENCE_SOURCES}
    latencies, muse_shared, base_shared = [], [], []
    matched = violations = provider_errors = other_errors = agree = 0
    for raw in pools:
        inp = MatchInput.from_dict(raw)
        started = time.perf_counter()
        try:
            result: Any = await service.match(raw)
        except MatchingError as exc:
            latencies.append((time.perf_counter() - started) * 1000)
            if exc.code == "PROVIDER_UNAVAILABLE":
                provider_errors += 1
            else:
                other_errors += 1
            continue
        latencies.append((time.perf_counter() - started) * 1000)
        if isinstance(result, NoMatch):
            no_match[result.reason] += 1
            continue
        assert isinstance(result, Matched)
        proposal = result.proposal
        matched += 1
        sources[proposal.evidence.source] += 1
        if count_violations(inp, proposal.member_ids):
            violations += 1
        groups = enumerate_groups(inp)
        chosen = next((g for g in groups if g.member_ids == proposal.member_ids), None)
        if groups:
            base_shared.append(len(groups[0].shared_interests))
            agree += int(set(groups[0].member_ids) == set(proposal.member_ids))
        if chosen is not None:
            muse_shared.append(len(chosen.shared_interests))
    ordered = sorted(latencies)
    return {
        "label": label,
        "pools": len(pools),
        "matched": matched,
        "no_match_by_reason": no_match,
        "hard_constraint_violations": violations,
        "muse_vs_baseline_agreement": round(agree / matched, 4) if matched else None,
        "mean_shared_interests": {"muse": _mean(muse_shared), "baseline": _mean(base_shared)},
        "latency_ms": {"p50": _percentile(ordered, P50), "p95": _percentile(ordered, P95)},
        "provider_errors": provider_errors,
        "other_errors": other_errors,
        "evidence_sources": sources,
    }
