"""Preference extraction (PROPOSED D008): voice/text -> private PreferenceProfile.

Members describe what they are comfortable with (time, budget ceiling, area,
energy, social comfort, interests, dislikes), not an activity to organize.

Muse interprets; code decides what survives:
  - every value cites a verbatim quote from the member's own words;
  - deterministic bounds and the community area allowlist apply;
  - code, not Muse, picks the follow-up: at most ONE, for the most important
    missing hard-constraint field, worded by a fixed server question;
  - a request that already carries a follow-up answer never gets another
    question back, so the "one follow-up" rule is structural, not a prompt hope.
Consent is checked before any model call; the profile has no identity fields.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from server.providers.errors import ProviderError
from server.providers.port import GenerateRequest, MusePort

from . import wire
from .errors import PlanningError
from .extraction import (
    _INTEREST_OK, HORIZON, MAX_BUDGET_MINOR, MAX_WINDOW, MIN_WINDOW,
    CommunityContext, _clean_transcript, _norm, require_model_consent,
)
from .prompts_v11 import PREFERENCES_PROMPT_VERSION
from .timeutil import fmt_utc, normalize, parse_utc

# Hard constraints first: matching cannot run without them.
FOLLOW_UP_PRIORITY = ("availability", "maxBudgetMinor", "areaId", "interests")
FOLLOW_UP_QUESTIONS: dict[str, str] = {
    "availability": "When are you free in the next two weeks? A day and time range works, like \"Saturday 2-5pm\".",
    "maxBudgetMinor": "What's the most you'd want to spend on one meetup? Free is fine.",
    "areaId": "Which area works for you?",
    "interests": "What's something you enjoy, or would like to try with a small group?",
}
MAX_ANSWER_CHARS = 500


@dataclass
class PreferenceOutcome:
    result: dict[str, Any]  # wire PreferenceExtractionResult (PROPOSED D008)
    rejected: dict[str, int] = field(default_factory=dict)  # sanitized counts only


def empty_profile(community: CommunityContext) -> dict[str, Any]:
    return {
        "communityId": community.community_id, "availability": [], "timeZone": community.time_zone,
        "maxBudgetMinor": None, "currency": community.currency, "areaId": None,
        "interests": [], "avoid": [], "energy": None, "socialComfort": None, "openToNew": None,
    }


class PreferenceExtractor:
    def __init__(self, muse: MusePort, *, now: Callable[[], datetime] | None = None) -> None:
        self._muse = muse
        self._now = now or (lambda: datetime.now(timezone.utc))

    async def extract(self, *, request: Any, community: CommunityContext, consent: Any,
                      request_id: str) -> PreferenceOutcome:
        require_model_consent(consent, community.community_id)
        try:
            wire.preference_extraction_request(request)
        except wire.ContractError as exc:
            raise PlanningError("INVALID_INPUT", f"invalid preference request at {exc.path}") from None
        if request["communityId"] != community.community_id:
            raise PlanningError("INVALID_INPUT", "communityId does not match the route community")
        transcript = _clean_transcript(request["transcript"])
        try:
            tz = ZoneInfo(community.time_zone)
        except (ZoneInfoNotFoundError, ValueError):
            raise PlanningError("INVALID_INPUT", "community time zone is invalid") from None
        ref = self._now().astimezone(timezone.utc).replace(microsecond=0)

        follow = request.get("followUp")
        source_text = transcript
        payload: dict[str, Any] = {
            "mode": "initial",
            "transcript": transcript,
            "referenceTimeUtc": fmt_utc(ref),
            "referenceTimeLocal": ref.astimezone(tz).strftime("%A %Y-%m-%d %H:%M"),
            "timeZone": community.time_zone,
            "currency": community.currency,
            "areas": [{"areaId": a.area_id, "name": a.name} for a in community.areas],
        }
        if follow is not None:
            answer = _clean_transcript(follow["answer"])[:MAX_ANSWER_CHARS]
            source_text = answer
            payload.update(mode="follow_up", transcript=answer, field=follow["field"],
                           question=FOLLOW_UP_QUESTIONS.get(follow["field"], ""))
        try:
            gen = await self._muse.generate(GenerateRequest(
                task="extract_preferences", request_id=request_id,
                prompt_version=PREFERENCES_PROMPT_VERSION, payload=payload,
            ))
        except ProviderError as exc:
            raise PlanningError.from_provider(exc) from None

        rejected: dict[str, int] = {}
        extracted = _sanitize(gen.output, source_text, community, ref, rejected)
        if follow is None:
            profile = extracted
        else:
            profile = _bounded_previous(follow["previous"], community, ref, rejected)
            name = follow["field"]
            if extracted[name] not in (None, []):
                profile[name] = extracted[name]
        return PreferenceOutcome(result=_result(profile, gen.evidence, allow_follow_up=follow is None),
                                 rejected=rejected)


def _result(profile: dict, evidence: dict, *, allow_follow_up: bool) -> dict:
    missing = [f for f in wire.PREFERENCE_FIELDS if profile[f] in (None, [])]
    ask = next((f for f in FOLLOW_UP_PRIORITY if f in missing), None) if allow_follow_up else None
    result = {
        "status": "needs_follow_up" if ask else "ready_to_confirm",
        "profile": profile,
        "missingFields": missing,
        "followUp": {"field": ask, "question": FOLLOW_UP_QUESTIONS[ask]} if ask else None,
        "evidence": dict(evidence),
    }
    return wire.preference_extraction_result(result)


def _sanitize(out: dict, source_text: str, community: CommunityContext, ref: datetime,
              rejected: dict[str, int]) -> dict:
    haystack = f" {_norm(source_text)} "

    def reject(name: str) -> None:
        rejected[name] = rejected.get(name, 0) + 1

    def supported(quote: Any) -> bool:
        if not isinstance(quote, str):
            return False
        q = _norm(quote)
        return len(q) >= 2 and q in haystack

    profile = empty_profile(community)

    spans = []
    for w in out["availability"]:
        try:
            start, end = parse_utc(w["start"]), parse_utc(w["end"])
        except ValueError:
            reject("availability")
            continue
        start = max(start, ref)
        if not supported(w["quote"]) or not _window_ok(start, end, ref):
            reject("availability")
            continue
        spans.append((start, end))
    profile["availability"] = [{"start": fmt_utc(s), "end": fmt_utc(e)} for s, e in normalize(spans)][:6]

    b = out["maxBudgetMinor"]
    if b["value"] is not None:
        if 0 <= b["value"] <= MAX_BUDGET_MINOR and supported(b["quote"]):
            profile["maxBudgetMinor"] = b["value"]
        else:
            reject("maxBudgetMinor")

    a = out["areaId"]
    if a["value"] is not None:
        if a["value"] in {x.area_id for x in community.areas} and supported(a["quote"]):
            profile["areaId"] = a["value"]
        else:
            reject("areaId")

    for key, limit in (("interests", 8), ("avoid", 5)):
        values: list[str] = []
        for item in out[key]:
            value = " ".join(item["value"].lower().split())
            if not _INTEREST_OK.match(value) or not supported(item["quote"]):
                reject(key)
                continue
            if value not in values:
                values.append(value)
        profile[key] = values[:limit]

    for key, allowed in (("energy", wire.ENERGY), ("socialComfort", wire.SOCIAL_COMFORT)):
        item = out[key]
        if item["value"] is not None:
            if item["value"] in allowed and supported(item["quote"]):
                profile[key] = item["value"]
            else:
                reject(key)

    o = out["openToNew"]
    if o["value"] is not None:
        if isinstance(o["value"], bool) and supported(o["quote"]):
            profile["openToNew"] = o["value"]
        else:
            reject("openToNew")
    return wire.preference_profile(profile)


def _window_ok(start: datetime, end: datetime, ref: datetime) -> bool:
    return MIN_WINDOW <= end - start <= MAX_WINDOW and start < ref + HORIZON


def _bounded_previous(prev: dict, community: CommunityContext, ref: datetime, rejected: dict[str, int]) -> dict:
    """The client echoes its own draft; re-apply server bounds (not quotes) before merging."""
    profile = {**prev, "communityId": community.community_id, "timeZone": community.time_zone,
               "currency": community.currency}
    kept = []
    for w in prev["availability"]:
        s, e = parse_utc(w["start"]), parse_utc(w["end"])
        if _window_ok(max(s, ref), e, ref):
            kept.append(w)
        else:
            rejected["availability"] = rejected.get("availability", 0) + 1
    profile["availability"] = kept
    if profile["areaId"] is not None and profile["areaId"] not in {a.area_id for a in community.areas}:
        profile["areaId"] = None
        rejected["areaId"] = rejected.get("areaId", 0) + 1
    if profile["maxBudgetMinor"] is not None and profile["maxBudgetMinor"] > MAX_BUDGET_MINOR:
        profile["maxBudgetMinor"] = None
        rejected["maxBudgetMinor"] = rejected.get("maxBudgetMinor", 0) + 1
    profile["interests"] = [i for i in profile["interests"] if _INTEREST_OK.match(i)]
    profile["avoid"] = [i for i in profile["avoid"] if _INTEREST_OK.match(i)]
    return wire.preference_profile(profile)


__all__ = ["PreferenceExtractor", "PreferenceOutcome", "FOLLOW_UP_PRIORITY", "FOLLOW_UP_QUESTIONS", "empty_profile"]
