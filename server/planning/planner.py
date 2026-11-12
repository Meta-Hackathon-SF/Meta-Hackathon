"""PlanningPort implementation: plan / revise / continue.

Division of labor:
  code  - validates input, rejects stale member versions, computes the feasible
          option set (shared time ∩ venue hours, group caps), detects
          needs_input / no_feasible_plan, validates every model choice, and
          renders the public rationale from verified fact codes.
  Muse  - chooses venue + slot from the options and writes the collaborative
          activity, opener, next-week activity and invitation draft.
No database or external side effects happen here; Kai persists results.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Callable

from server.providers.errors import ProviderError
from server.providers.port import GenerateRequest, MusePort

from . import public_text, wire
from .errors import PlanningError
from .prompts import CONTINUE_PROMPT_VERSION, PLAN_PROMPT_VERSION, REVISE_PROMPT_VERSION
from .timeutil import Interval, covers, fmt_utc, intersect, intersect_all, minutes, parse_utc, to_intervals

MIN_ACTIVITY_MINUTES = 15
MAX_OPTIONS = 8
MAX_SLOTS_PER_OPTION = 4
MATERIAL_FIELDS = ("venueId", "start", "end", "costPerPersonMinor")
PUBLIC_PLAN_FIELDS = ("title", "activity", "collaborationTask", "opener")

NO_COMMON_TIME_QUESTION = (
    "There's no time that works for everyone in the group right now. "
    "Could you share another time you're free?"
)
NO_VENUE_REASON = "No approved public venue is open during a time that works for the whole group."
TOO_SHORT_REASON = "The group's available time is too short for a quest."

Telemetry = Callable[[dict[str, Any]], None]


def plan_changes(previous: dict, current: dict) -> list[str]:
    """Public plan fields that differ between two QuestPlans."""
    fields = ("title", "activity", "collaborationTask", "venueId", "start", "end", "costPerPersonMinor")
    return [f for f in fields if previous.get(f) != current.get(f)]


def requires_reconfirmation(previous: dict, current: dict) -> bool:
    """Time, place or cost changed: members must reconfirm (contracts/WORKFLOW.md)."""
    return any(f in MATERIAL_FIELDS for f in plan_changes(previous, current))


class QuestPlanner:
    def __init__(
        self,
        muse: MusePort,
        *,
        now: Callable[[], datetime] | None = None,
        new_id: Callable[[], str] | None = None,
        semantic_attempts: int = 2,
        telemetry: Telemetry | None = None,
    ) -> None:
        self._muse = muse
        self._now = now or (lambda: datetime.now(timezone.utc))
        self._new_id = new_id or (lambda: "plan_" + uuid.uuid4().hex)
        self._attempts = max(1, min(semantic_attempts, 3))
        self._telemetry = telemetry or (lambda _r: None)

    # ------------------------------------------------------------------ port
    async def plan(self, inp: dict) -> dict:
        return await self._plan(inp, revise=False)

    async def revise(self, inp: dict) -> dict:
        return await self._plan(inp, revise=True)

    async def continue_(self, inp: dict) -> dict:
        return await self._continue(inp)

    # ------------------------------------------------------------ plan/revise
    async def _plan(self, inp: dict, *, revise: bool) -> dict:
        try:
            wire.plan_input(inp)
        except wire.ContractError as exc:
            raise PlanningError("INVALID_INPUT", f"invalid PlanInput at {exc.path}") from None
        proposal, parts, ctx = inp["proposal"], inp["participants"], inp["context"]
        previous = inp.get("previousPlan")
        if revise and previous is None:
            raise PlanningError("INVALID_INPUT", "revise requires previousPlan")
        if previous is not None and previous["proposalId"] != proposal["proposalId"]:
            raise PlanningError("INVALID_INPUT", "previousPlan belongs to another proposal")
        self._check_membership(proposal, parts)

        now = self._now().astimezone(timezone.utc)
        shared = intersect_all(
            [[(max(s, now), e) for s, e in to_intervals(proposal["feasibleWindows"])]]
            + [to_intervals(p["intent"]["availability"]) for p in parts]
        )
        if not any(minutes(s, e) >= MIN_ACTIVITY_MINUTES for s, e in shared):
            return {"status": "needs_input", "fields": ["availability"], "question": NO_COMMON_TIME_QUESTION}

        dur_cap = min(p["intent"]["maxDurationMinutes"] for p in parts)
        if dur_cap < MIN_ACTIVITY_MINUTES:
            return {"status": "no_feasible_plan", "reason": TOO_SHORT_REASON}
        budget_cap = min(p["intent"]["maxBudgetMinor"] for p in parts)
        currency = parts[0]["intent"]["currency"]
        area = parts[0]["intent"]["areaId"]

        options: dict[str, dict[str, Any]] = {}
        for v in inp["venues"]:
            if v["areaId"] != area or v["isPublic"] is not True:
                continue
            slots = [(s, e) for s, e in intersect(shared, to_intervals(v["openingWindows"]))
                     if minutes(s, e) >= MIN_ACTIVITY_MINUTES]
            if slots:
                options[v["venueId"]] = {"venue": v, "slots": slots}
        if not options:
            return {"status": "no_feasible_plan", "reason": NO_VENUE_REASON}
        ranked = sorted(options.values(), key=lambda o: o["slots"][0][0])[:MAX_OPTIONS]
        options = {o["venue"]["venueId"]: o for o in ranked}

        payload: dict[str, Any] = {
            "group": {
                "size": len(parts),
                "sharedInterests": proposal["sharedInterests"],
                "publicInterests": sorted({i for p in parts for i in p["publicProfile"]["publicInterests"]})[:20],
            },
            "constraints": {
                "maxCostPerPersonMinor": budget_cap,
                "currency": currency,
                "minDurationMinutes": MIN_ACTIVITY_MINUTES,
                "maxDurationMinutes": dur_cap,
                "timeZone": parts[0]["intent"]["timeZone"],
            },
            "options": [
                {
                    "venueId": o["venue"]["venueId"],
                    "name": o["venue"]["name"],
                    "slots": [{"start": fmt_utc(s), "end": fmt_utc(e)} for s, e in o["slots"][:MAX_SLOTS_PER_OPTION]],
                }
                for o in ranked
            ],
        }
        if previous is not None:
            payload["previousPlan"] = {k: previous[k] for k in ("title", "activity", "collaborationTask", "venueId", "start", "end", "costPerPersonMinor")}
            payload["changeSummary"] = inp.get("changeSummary") or "Group circumstances changed."

        task = "revise" if revise else "plan"
        version = REVISE_PROMPT_VERSION if revise else PLAN_PROMPT_VERSION
        correction: str | None = None
        rejections: list[str] = []
        for attempt in range(1, self._attempts + 1):
            try:
                gen = await self._muse.generate(GenerateRequest(
                    task=task, request_id=ctx["requestId"], prompt_version=version,
                    payload=payload, correction=correction,
                ))
            except ProviderError as exc:
                raise PlanningError.from_provider(exc) from None
            errors = self._check_choice(gen.output, options, dur_cap, budget_cap)
            if not errors:
                plan = self._build_plan(gen.output, gen.evidence, proposal, parts, previous, currency)
                self._telemetry({"requestId": ctx["requestId"], "task": task, "semanticAttempts": attempt,
                                 "rejections": rejections, "outcome": "proposed"})
                return {"status": "proposed", "plan": plan}
            rejections.extend(e.split(":")[0] for e in errors)
            correction = "; ".join(errors)[:580]
        self._telemetry({"requestId": ctx["requestId"], "task": task, "semanticAttempts": self._attempts,
                         "rejections": rejections, "outcome": "invalid_model_output"})
        raise PlanningError("PROVIDER_UNAVAILABLE", "model did not produce a valid plan", retryable=True)

    @staticmethod
    def _check_membership(proposal: dict, parts: list[dict]) -> None:
        ids = [p["intent"]["participantId"] for p in parts]
        if sorted(ids) != sorted(proposal["memberIds"]):
            raise PlanningError("INVALID_INPUT", "participants must be exactly the proposal members")
        versions = {m["participantId"]: m for m in proposal["memberVersions"]}
        for p in parts:
            i = p["intent"]
            mv = versions[i["participantId"]]
            if i["intentVersion"] != mv["intentVersion"] or i["consentVersion"] != mv["consentVersion"]:
                raise PlanningError("STALE_REVISION", "participant snapshot does not match proposal versions")
            if i["communityId"] != proposal["communityId"]:
                raise PlanningError("INVALID_INPUT", "participant outside proposal community")
        if len({p["intent"]["areaId"] for p in parts}) != 1:
            raise PlanningError("INVALID_INPUT", "participants span multiple areas")
        if len({p["intent"]["currency"] for p in parts}) != 1:
            raise PlanningError("INVALID_INPUT", "participants use different currencies")

    @staticmethod
    def _check_choice(out: dict, options: dict[str, dict], dur_cap: int, budget_cap: int) -> list[str]:
        errors: list[str] = []
        option = options.get(out["venueId"])
        if option is None:
            errors.append("venueId: must be one of the provided options")
        try:
            start, end = parse_utc(out["start"]), parse_utc(out["end"])
        except ValueError:
            errors.append("time_format: start/end must be RFC3339 UTC with trailing Z")
            start = end = None
        if start is not None and end is not None:
            if end <= start:
                errors.append("time_order: end must be after start")
            else:
                length = minutes(start, end)
                if not (MIN_ACTIVITY_MINUTES <= length <= dur_cap):
                    errors.append(f"duration: must be between {MIN_ACTIVITY_MINUTES} and {dur_cap} minutes")
                if option is not None and not covers(option["slots"], start, end):
                    errors.append("slot: start/end must lie inside one slot of the chosen venue")
        if out["costPerPersonMinor"] > budget_cap:
            errors.append("cost: costPerPersonMinor exceeds constraints.maxCostPerPersonMinor")
        for field in PUBLIC_PLAN_FIELDS:
            bad = public_text.violations(out[field])
            if bad:
                errors.append(f"public_text: {field} contains disallowed content ({', '.join(bad)})")
        return errors

    def _build_plan(self, out: dict, evidence: dict, proposal: dict, parts: list[dict],
                    previous: dict | None, currency: str) -> dict:
        start, end = parse_utc(out["start"]), parse_utc(out["end"])
        rationale = public_text.render_rationale(
            out["rationaleFacts"],
            shared_interests=proposal["sharedInterests"],
            cost_per_person_minor=out["costPerPersonMinor"],
            duration_minutes=minutes(start, end),
        )
        plan = {
            "planId": self._new_id(),
            "proposalId": proposal["proposalId"],
            "revision": 1 if previous is None else previous["revision"] + 1,
            "basedOnRevision": None if previous is None else previous["revision"],
            "memberVersions": [dict(m) for m in proposal["memberVersions"]],
            "title": out["title"].strip(),
            "activity": out["activity"].strip(),
            "collaborationTask": out["collaborationTask"].strip(),
            "venueId": out["venueId"],
            "start": fmt_utc(start),
            "end": fmt_utc(end),
            "timeZone": parts[0]["intent"]["timeZone"],
            "costPerPersonMinor": out["costPerPersonMinor"],
            "currency": currency,
            "minimumSize": 3,
            "maximumSize": 5,
            "publicRationale": rationale,
            "opener": out["opener"].strip(),
            "evidence": dict(evidence),
        }
        return wire.quest_plan(plan)

    # -------------------------------------------------------------- continue
    async def _continue(self, inp: dict) -> dict:
        try:
            wire.continuation_input(inp)
        except wire.ContractError as exc:
            raise PlanningError("INVALID_INPUT", f"invalid ContinuationInput at {exc.path}") from None
        prior = inp["priorPlan"]
        members = {m["participantId"] for m in prior["memberVersions"]}
        if any(f["participantId"] not in members for f in inp["feedback"]):
            raise PlanningError("FORBIDDEN", "feedback from a non-member")
        if not inp["simulateTimeSkip"] and parse_utc(prior["end"]) > self._now():
            raise PlanningError("INVALID_INPUT", "continuation before the prior quest has ended")
        # Minimal voluntary signal only: who wants to return. Attendance is not sent.
        willing = sorted(f["participantId"] for f in inp["feedback"] if f["wantsReturn"])
        payload = {
            "priorPlan": {k: prior[k] for k in ("title", "activity", "collaborationTask")},
            "willingHostIds": willing,
            "simulatedTimeSkip": inp["simulateTimeSkip"],
        }
        correction: str | None = None
        for _ in range(self._attempts):
            try:
                gen = await self._muse.generate(GenerateRequest(
                    task="continue", request_id=inp["context"]["requestId"],
                    prompt_version=CONTINUE_PROMPT_VERSION, payload=payload, correction=correction,
                ))
            except ProviderError as exc:
                raise PlanningError.from_provider(exc) from None
            out = gen.output
            errors: list[str] = []
            host = out["proposedHostId"]
            if host is not None and host not in willing:
                errors.append("proposedHostId: must be one of willingHostIds or null")
            for field in ("nextActivity", "invitationText"):
                bad = public_text.violations(out[field], forbid_attendance_claims=True)
                if bad:
                    errors.append(f"public_text: {field} contains disallowed content ({', '.join(bad)})")
            if not errors:
                if host is None and willing:
                    host = willing[0]  # code fallback: a willing member, never an unwilling one
                result = {
                    "questId": inp["questId"],
                    "proposedHostId": host,
                    "invitationText": out["invitationText"].strip(),
                    "nextActivity": out["nextActivity"].strip(),
                    "evidence": dict(gen.evidence),
                }
                return wire.continuation(result)
            correction = "; ".join(errors)[:580]
        raise PlanningError("PROVIDER_UNAVAILABLE", "model did not produce a valid continuation", retryable=True)


# ``continue`` is a Python keyword; expose the contract method name for getattr-based callers.
setattr(QuestPlanner, "continue", QuestPlanner.continue_)
