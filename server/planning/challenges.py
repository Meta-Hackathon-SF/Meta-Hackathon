"""Post-meetup group challenges (PROPOSED D008, retention).

Muse writes a personalized challenge that gives the group a reason to meet
again. Code keeps it honest and countable:
  - the goal metric is ``sessions_together`` (future completed events of this
    quest, which Kai can count), target 2..6, due 7..60 days out;
  - a reward can only be one of the server's approved, simulated reward
    options, and a venue-sponsored reward must come from the event's own venue;
  - text may not claim attendance (unknown), money amounts, links or contacts;
  - only voluntary signals reach the model: how many members want to return.
Progress starts at zero; Kai owns progress updates and persistence.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Callable

from server.providers.errors import ProviderError
from server.providers.port import GenerateRequest, MusePort

from . import public_text, wire
from .errors import PlanningError
from .prompts_v11 import CHALLENGE_PROMPT_VERSION
from .timeutil import fmt_utc, parse_utc


class ChallengeGenerator:
    def __init__(self, muse: MusePort, *, now: Callable[[], datetime] | None = None,
                 new_id: Callable[[str], str] | None = None, semantic_attempts: int = 2) -> None:
        self._muse = muse
        self._now = now or (lambda: datetime.now(timezone.utc))
        self._new_id = new_id or (lambda prefix: f"{prefix}_{uuid.uuid4().hex}")
        self._attempts = max(1, min(semantic_attempts, 3))

    async def challenge(self, inp: dict) -> dict:
        try:
            wire.challenge_input(inp)
        except wire.ContractError as exc:
            raise PlanningError("INVALID_INPUT", f"invalid ChallengeInput at {exc.path}") from None
        event, plan = inp["event"], inp["priorPlan"]
        if event["planId"] != plan["planId"]:
            raise PlanningError("INVALID_INPUT", "event does not belong to priorPlan")
        if event["status"] == "cancelled":
            raise PlanningError("INVALID_INPUT", "no challenge for a cancelled event")
        members = set(event["acceptedMemberIds"])
        if any(f["participantId"] not in members for f in inp["feedback"]):
            raise PlanningError("FORBIDDEN", "feedback from a non-member")
        now = self._now().astimezone(timezone.utc)
        if not inp["simulateTimeSkip"] and parse_utc(event["end"]) > now:
            raise PlanningError("INVALID_INPUT", "challenge before the meetup has ended")

        options = {r["rewardOptionId"]: r for r in inp["rewardOptions"]
                   if r["sponsor"] == "group_quests" or r["venueId"] == event["venueId"]}
        payload = {
            "priorPlan": {k: plan[k] for k in ("title", "activity", "collaborationTask")},
            "returningCount": sum(1 for f in inp["feedback"] if f["wantsReturn"]),
            "rewardOptions": [{"rewardOptionId": r["rewardOptionId"], "label": r["label"], "sponsor": r["sponsor"]}
                              for r in options.values()],
            "simulatedTimeSkip": inp["simulateTimeSkip"],
        }
        correction: str | None = None
        for _ in range(self._attempts):
            try:
                gen = await self._muse.generate(GenerateRequest(
                    task="challenge", request_id=inp["context"]["requestId"],
                    prompt_version=CHALLENGE_PROMPT_VERSION, payload=payload, correction=correction,
                ))
            except ProviderError as exc:
                raise PlanningError.from_provider(exc) from None
            out = gen.output
            errors = []
            if out["rewardOptionId"] is not None and out["rewardOptionId"] not in options:
                errors.append("rewardOptionId: must be one of rewardOptions or null")
            for f in ("title", "description"):
                bad = public_text.violations(out[f], forbid_attendance_claims=True)
                if bad:
                    errors.append(f"public_text: {f} contains disallowed content ({', '.join(bad)})")
            if not errors:
                return self._build(inp, out, gen.evidence, options, now)
            correction = "; ".join(errors)[:580]
        raise PlanningError("PROVIDER_UNAVAILABLE", "model did not produce a valid challenge", retryable=True)

    def _build(self, inp: dict, out: dict, evidence: dict, options: dict, now: datetime) -> dict:
        start_from = max(now, parse_utc(inp["event"]["end"]))
        reward = None
        if out["rewardOptionId"] is not None:
            r = options[out["rewardOptionId"]]
            reward = {"rewardId": self._new_id("reward"), "rewardOptionId": r["rewardOptionId"], "label": r["label"],
                      "sponsor": r["sponsor"], "venueId": r["venueId"], "isSimulated": True}
        return wire.challenge({
            "challengeId": self._new_id("challenge"),
            "questId": inp["questId"],
            "basedOnEventId": inp["event"]["eventId"],
            "title": out["title"].strip(),
            "description": out["description"].strip(),
            "goal": {"metric": "sessions_together", "target": out["target"]},
            "dueBy": fmt_utc(start_from + timedelta(days=out["dueInDays"])),
            "progress": {"completed": 0, "target": out["target"]},
            "reward": reward,
            "evidence": dict(evidence),
        })


__all__ = ["ChallengeGenerator"]
