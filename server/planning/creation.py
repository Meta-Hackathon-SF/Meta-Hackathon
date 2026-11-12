"""Muse-created events (PROPOSED D008): when no existing opportunity fits.

Code computes every feasible (approved venue, time slot) option from the
authorized candidate pool: the venue is public, in the members' area and open;
at least three members are free for the whole slot; and the option carries the
cost and duration caps that keep at least three of them eligible. Muse picks one
option and writes the activity. Code then re-derives exactly who could join at
the chosen time and price and rejects the choice unless at least three can.

The model sees aggregates only: counts of public interests, an unattributed
union of avoid terms, energy/comfort mixes and per-option counts. No ids, names,
individual budgets or schedules.
"""
from __future__ import annotations

import uuid
from collections import Counter
from datetime import datetime, timezone
from typing import Callable

from server.providers.errors import ProviderError
from server.providers.port import GenerateRequest, MusePort

from . import public_text, wire
from .errors import PlanningError
from .planner import MIN_ACTIVITY_MINUTES, PUBLIC_PLAN_FIELDS
from .prompts_v11 import CREATE_EVENT_PROMPT_VERSION
from .timeutil import Interval, covers, fmt_utc, minutes, normalize, parse_utc, to_intervals

MAX_OPTIONS = 8
MAX_INTERESTS = 12
MIN_GROUP = 3


class _Member:
    __slots__ = ("pid", "area", "free", "budget", "duration", "interests", "avoid", "energy", "comfort", "tz", "currency")

    def __init__(self, c: dict, now: datetime) -> None:
        i = c["intent"]
        prefs = c.get("preferences") or {}
        self.pid = i["participantId"]
        self.area = i["areaId"]
        self.free = normalize((max(s, now), e) for s, e in to_intervals(i["availability"]) if e > now)
        self.budget = i["maxBudgetMinor"]
        self.duration = i["maxDurationMinutes"]
        self.interests = list(c["publicProfile"]["publicInterests"])
        self.avoid = list(prefs.get("avoid", []))
        self.energy = prefs.get("energy")
        self.comfort = prefs.get("socialComfort")
        self.tz = i["timeZone"]
        self.currency = i["currency"]


def _third_highest(values: list[int]) -> int:
    return sorted(values, reverse=True)[MIN_GROUP - 1]


def eligible_members(members: list[_Member], area: str, start: datetime, end: datetime, cost: int) -> list[_Member]:
    length = minutes(start, end)
    return [m for m in members
            if m.area == area and covers(m.free, start, end) and m.budget >= cost and m.duration >= length]


def compute_options(members: list[_Member], venues: list[dict]) -> list[dict]:
    """Elementary slots where >=3 members in the venue's area are free and the venue is open."""
    options: list[dict] = []
    for v in venues:
        if v["isPublic"] is not True:
            continue
        local = [m for m in members if m.area == v["areaId"]]
        if len(local) < MIN_GROUP:
            continue
        opening = normalize(to_intervals(v["openingWindows"]))
        cuts = sorted({t for m in local for s, e in m.free for t in (s, e)} | {t for s, e in opening for t in (s, e)})
        pieces: list[tuple[Interval, frozenset[str]]] = []
        for s, e in zip(cuts, cuts[1:]):
            if not covers(opening, s, e):
                continue
            free = frozenset(m.pid for m in local if covers(m.free, s, e))
            if len(free) >= MIN_GROUP:
                if pieces and pieces[-1][0][1] == s and pieces[-1][1] == free:
                    pieces[-1] = ((pieces[-1][0][0], e), free)  # merge contiguous, same people
                else:
                    pieces.append(((s, e), free))
        by_id = {m.pid: m for m in local}
        for (s, e), free in pieces:
            group = [by_id[p] for p in free]
            max_dur = min(_third_highest([m.duration for m in group]), int(minutes(s, e)))
            if max_dur < MIN_ACTIVITY_MINUTES:
                continue
            options.append({
                "venue": v, "start": s, "end": e, "free": len(free),
                "maxCost": _third_highest([m.budget for m in group]), "maxDuration": max_dur,
            })
    options.sort(key=lambda o: (-o["free"], o["start"]))
    return options[:MAX_OPTIONS]


class EventCreator:
    def __init__(self, muse: MusePort, *, now: Callable[[], datetime] | None = None,
                 new_id: Callable[[], str] | None = None, semantic_attempts: int = 2) -> None:
        self._muse = muse
        self._now = now or (lambda: datetime.now(timezone.utc))
        self._new_id = new_id or (lambda: "opp_" + uuid.uuid4().hex)
        self._attempts = max(1, min(semantic_attempts, 3))

    async def create(self, inp: dict) -> dict:
        try:
            wire.create_event_input(inp)
        except wire.ContractError as exc:
            raise PlanningError("INVALID_INPUT", f"invalid CreateEventInput at {exc.path}") from None
        now = self._now().astimezone(timezone.utc)
        members = [_Member(c, now) for c in inp["candidates"]]
        if len({m.currency for m in members}) != 1:
            raise PlanningError("INVALID_INPUT", "candidates use different currencies")
        venues = [v for v in inp["venues"] if v["isPublic"] is True]
        if not any(sum(m.area == v["areaId"] for m in members) >= MIN_GROUP for v in venues):
            return wire.create_event_result({"status": "no_fit", "reason": "no_open_venue" if not venues else "too_few_overlap"})
        options = compute_options(members, venues)
        if not options:
            return wire.create_event_result({"status": "no_fit", "reason": "too_few_overlap"})

        avoid = sorted({a for m in members for a in m.avoid})
        interest_counts = Counter(i for m in members for i in m.interests).most_common(MAX_INTERESTS)
        ids = {f"o{n}": o for n, o in enumerate(options)}
        payload = {
            "pool": {
                "eligibleMembers": len(members),
                "interestCounts": [{"interest": i, "count": c} for i, c in interest_counts],
                "avoid": avoid,
                "energyMix": dict(Counter(m.energy for m in members if m.energy)),
                "comfortMix": dict(Counter(m.comfort for m in members if m.comfort)),
            },
            "constraints": {"currency": members[0].currency, "minDurationMinutes": MIN_ACTIVITY_MINUTES,
                            "timeZone": members[0].tz, "groupSize": "3-5"},
            "options": [
                {"optionId": oid, "venueId": o["venue"]["venueId"], "name": o["venue"]["name"],
                 "slot": {"start": fmt_utc(o["start"]), "end": fmt_utc(o["end"])},
                 "freeCount": o["free"], "maxCostPerPersonMinor": o["maxCost"],
                 "maxDurationMinutes": o["maxDuration"]}
                for oid, o in ids.items()
            ],
        }
        interest_names = {i for i, _ in interest_counts}
        correction: str | None = None
        for _ in range(self._attempts):
            try:
                gen = await self._muse.generate(GenerateRequest(
                    task="create_event", request_id=inp["context"]["requestId"],
                    prompt_version=CREATE_EVENT_PROMPT_VERSION, payload=payload, correction=correction,
                ))
            except ProviderError as exc:
                raise PlanningError.from_provider(exc) from None
            out = gen.output
            errors, chosen = self._check(out, ids, avoid, interest_names, members)
            if not errors:
                return self._build(inp, out, gen.evidence, chosen)
            correction = "; ".join(errors)[:580]
        raise PlanningError("PROVIDER_UNAVAILABLE", "model did not produce a valid event", retryable=True)

    @staticmethod
    def _check(out: dict, ids: dict[str, dict], avoid: list[str], interests: set[str],
               members: list[_Member]) -> tuple[list[str], dict | None]:
        errors: list[str] = []
        option = ids.get(out["optionId"])
        if option is None:
            return ["optionId: must be one of options[].optionId"], None
        try:
            start, end = parse_utc(out["start"]), parse_utc(out["end"])
        except ValueError:
            return ["time_format: start/end must be RFC3339 UTC with trailing Z"], None
        if end <= start:
            return ["time_order: end must be after start"], None
        length = minutes(start, end)
        if not (MIN_ACTIVITY_MINUTES <= length <= option["maxDuration"]):
            errors.append(f"duration: must be between {MIN_ACTIVITY_MINUTES} and {option['maxDuration']} minutes")
        if not covers([(option["start"], option["end"])], start, end):
            errors.append("slot: start/end must lie inside the option's slot")
        if out["costPerPersonMinor"] > option["maxCost"]:
            errors.append("cost: costPerPersonMinor exceeds the option's maxCostPerPersonMinor")
        for i in out["interestsUsed"]:
            if i not in interests:
                errors.append("interestsUsed: must be copied from pool.interestCounts")
                break
        for f in PUBLIC_PLAN_FIELDS[:3]:
            bad = public_text.violations(out[f], extra_terms=avoid)
            if bad:
                kinds = ["avoid_term" if b == "names_individual" else b for b in bad]
                errors.append(f"public_text: {f} contains disallowed content ({', '.join(kinds)})")
        eligible = []
        if not errors:
            eligible = eligible_members(members, option["venue"]["areaId"], start, end, out["costPerPersonMinor"])
            if len(eligible) < MIN_GROUP:
                errors.append("eligibility: fewer than 3 members can join at that time and cost")
        return errors, (None if errors else {"option": option, "start": start, "end": end, "eligible": len(eligible)})

    def _build(self, inp: dict, out: dict, evidence: dict, chosen: dict) -> dict:
        start, end = chosen["start"], chosen["end"]
        tz = inp["candidates"][0]["intent"]["timeZone"]
        currency = inp["candidates"][0]["intent"]["currency"]
        rationale = public_text.render_rationale(
            out["rationaleFacts"], shared_interests=out["interestsUsed"],
            cost_per_person_minor=out["costPerPersonMinor"], duration_minutes=minutes(start, end),
        ).replace("fits a time that works for everyone", "fits a time when enough members are free").replace(
            "builds on the group's shared interest in", "draws on interests members listed, like")
        opportunity = {
            "opportunityId": self._new_id(),
            "communityId": inp["communityId"],
            "source": "muse_created",
            "title": out["title"].strip(),
            "activity": out["activity"].strip(),
            "collaborationTask": out["collaborationTask"].strip(),
            "venueId": chosen["option"]["venue"]["venueId"],
            "window": {"start": fmt_utc(start), "end": fmt_utc(end)},
            "timeZone": tz,
            "costPerPersonMinor": out["costPerPersonMinor"],
            "currency": currency,
            "minimumSize": 3,
            "maximumSize": 5,
            "publicRationale": rationale,
            "isSimulated": False,
            "evidence": dict(evidence),
        }
        return wire.create_event_result({"status": "created", "opportunity": opportunity,
                                         "eligibleMemberCount": min(chosen["eligible"], 50)})


__all__ = ["EventCreator", "compute_options", "eligible_members"]
