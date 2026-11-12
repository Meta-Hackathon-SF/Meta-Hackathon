"""Intent extraction: transcript -> private IntentDraft + missing-field questions.

Muse interprets; this module decides what survives. Every value must cite a
verbatim transcript quote, fit deterministic bounds, and (for areaId) belong to
the community's allowlist. Anything else is dropped and reported as missing so
Will's confirmation UI asks the person instead of inventing facts. Consent is
never part of the draft; Patrik's PUT /intents/me persists the confirmed copy.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Sequence
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from server.providers.errors import ProviderError
from server.providers.port import GenerateRequest, MusePort

from . import wire
from .errors import PlanningError
from .prompts import EXTRACT_PROMPT_VERSION
from .timeutil import fmt_utc, normalize, parse_utc

MAX_TRANSCRIPT_CHARS = 2000
HORIZON = timedelta(days=14)
MIN_WINDOW = timedelta(minutes=15)
MAX_WINDOW = timedelta(hours=24)
MAX_BUDGET_MINOR = 100_000  # bound for a small social activity, minor units
MIN_DURATION, MAX_DURATION = 15, 480
_INTEREST_OK = re.compile(r"^[\w][\w &'\-/+.]{0,39}$", re.UNICODE)

QUESTIONS: dict[str, str] = {
    "goal": "What would you like to get out of this? For example, meeting new people or trying something new.",
    "interests": "What are one or two things you'd enjoy doing with a small group?",
    "areaId": "Which area works for you?",
    "availability": "When are you free in the next two weeks? A day and time range works, like \"Saturday 2-5pm\".",
    "maxBudgetMinor": "What's the most you'd want to spend? Free is fine.",
    "maxDurationMinutes": "How much time can you spend on it? For example 30 minutes or an hour.",
}


@dataclass(frozen=True)
class Area:
    area_id: str
    name: str


@dataclass(frozen=True)
class CommunityContext:
    """Server-side community facts (supplied by the route, not the client)."""

    community_id: str
    areas: Sequence[Area]
    currency: str
    time_zone: str


@dataclass
class ExtractionOutcome:
    result: dict[str, Any]  # wire ExtractionResult (PROPOSED D005)
    # Sanitized diagnostics: counts of discarded model values per field.
    rejected: dict[str, int] = field(default_factory=dict)


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).lower()
    text = text.replace("’", "'").replace("–", "-").replace("—", "-")
    return re.sub(r"[^\w$€£%]+", " ", text).strip()


def _clean_transcript(transcript: Any) -> str:
    if not isinstance(transcript, str):
        raise PlanningError("INVALID_INPUT", "transcript must be a string")
    cleaned = "".join(ch for ch in transcript if ch in "\n\t" or unicodedata.category(ch)[0] != "C").strip()
    if not cleaned:
        raise PlanningError("INVALID_INPUT", "transcript is empty")
    if len(cleaned) > MAX_TRANSCRIPT_CHARS:
        raise PlanningError("INVALID_INPUT", f"transcript exceeds {MAX_TRANSCRIPT_CHARS} characters")
    return cleaned


def require_model_consent(consent: Any, community_id: str) -> None:
    """Fail closed unless model-processing consent is current for this community."""
    ok = (
        isinstance(consent, dict)
        and consent.get("communityId") == community_id
        and consent.get("modelProcessing") is True
        and consent.get("revokedAt") is None
    )
    if not ok:
        raise PlanningError("CONSENT_REQUIRED", "model processing consent is required")


class IntentExtractor:
    def __init__(self, muse: MusePort, *, now: Callable[[], datetime] | None = None) -> None:
        self._muse = muse
        self._now = now or (lambda: datetime.now(timezone.utc))

    async def extract(
        self,
        *,
        transcript: Any,
        community: CommunityContext,
        consent: Any,
        request_id: str,
    ) -> ExtractionOutcome:
        require_model_consent(consent, community.community_id)
        text = _clean_transcript(transcript)
        try:
            tz = ZoneInfo(community.time_zone)
        except (ZoneInfoNotFoundError, ValueError):
            raise PlanningError("INVALID_INPUT", "community time zone is invalid") from None
        ref = self._now().astimezone(timezone.utc).replace(microsecond=0)
        payload = {
            "transcript": text,
            "referenceTimeUtc": fmt_utc(ref),
            "referenceTimeLocal": ref.astimezone(tz).strftime("%A %Y-%m-%d %H:%M"),
            "timeZone": community.time_zone,
            "currency": community.currency,
            "areas": [{"areaId": a.area_id, "name": a.name} for a in community.areas],
        }
        try:
            generated = await self._muse.generate(GenerateRequest(
                task="extract_intent",
                request_id=request_id,
                prompt_version=EXTRACT_PROMPT_VERSION,
                payload=payload,
            ))
        except ProviderError as exc:
            raise PlanningError.from_provider(exc) from None
        return self._build(generated.output, generated.evidence, text, community, ref)

    def _build(self, out: dict[str, Any], evidence: dict, transcript: str, community: CommunityContext, ref: datetime) -> ExtractionOutcome:
        haystack = f" {_norm(transcript)} "
        rejected: dict[str, int] = {}

        def reject(name: str) -> None:
            rejected[name] = rejected.get(name, 0) + 1

        def supported(quote: Any) -> bool:
            if not isinstance(quote, str):
                return False
            q = _norm(quote)
            return len(q) >= 2 and q in haystack

        # goal
        goal = None
        g = out["goal"]
        if g["value"] is not None:
            value = " ".join(g["value"].split())
            if value and supported(g["quote"]):
                goal = value
            else:
                reject("goal")

        # interests
        interests: list[str] = []
        for item in out["interests"]:
            value = " ".join(item["value"].lower().split())
            if not _INTEREST_OK.match(value) or not supported(item["quote"]):
                reject("interests")
                continue
            if value not in interests:
                interests.append(value)

        # areaId (community allowlist)
        area_id = None
        a = out["areaId"]
        allowed = {x.area_id for x in community.areas}
        if a["value"] is not None:
            if a["value"] in allowed and supported(a["quote"]):
                area_id = a["value"]
            else:
                reject("areaId")

        # availability
        spans = []
        for w in out["availability"]:
            try:
                start, end = parse_utc(w["start"]), parse_utc(w["end"])
            except ValueError:
                reject("availability")
                continue
            start = max(start, ref)
            if (
                not supported(w["quote"])
                or end - start < MIN_WINDOW
                or end - start > MAX_WINDOW
                or start >= ref + HORIZON
            ):
                reject("availability")
                continue
            spans.append((start, end))
        availability = [{"start": fmt_utc(s), "end": fmt_utc(e)} for s, e in normalize(spans)][:6]

        # budget
        budget = None
        b = out["maxBudgetMinor"]
        if b["value"] is not None:
            if 0 <= b["value"] <= MAX_BUDGET_MINOR and supported(b["quote"]):
                budget = b["value"]
            else:
                reject("maxBudgetMinor")

        # duration
        duration = None
        d = out["maxDurationMinutes"]
        if d["value"] is not None:
            if MIN_DURATION <= d["value"] <= MAX_DURATION and supported(d["quote"]):
                duration = d["value"]
            else:
                reject("maxDurationMinutes")

        draft = {
            "communityId": community.community_id,
            "goal": goal,
            "interests": interests,
            "areaId": area_id,
            "timeZone": community.time_zone,
            "availability": availability,
            "maxBudgetMinor": budget,
            "currency": community.currency,
            "maxDurationMinutes": duration,
            "groupPreference": "small",
        }
        missing = [f for f in wire.INTENT_FIELDS if draft[f] in (None, [])]
        questions = [{"field": f, "question": _question(f, community)} for f in missing]
        result = {
            "status": "draft",
            "draft": draft,
            "missingFields": missing,
            "questions": questions,
            "evidence": dict(evidence),
        }
        wire.extraction_result(result)  # our own output must satisfy the contract
        return ExtractionOutcome(result=result, rejected=rejected)


def _question(field_name: str, community: CommunityContext) -> str:
    if field_name == "areaId" and community.areas:
        names = ", ".join(a.name for a in community.areas[:5])
        return f"Which area works for you: {names}?"
    return QUESTIONS[field_name]
