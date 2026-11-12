"""Guards and allowlisted rendering for text shown to other group members.

Model-written public strings (title, activity, task, opener, invitation) are
checked for private-constraint vocabulary, money amounts, contact details and
links. The plan's publicRationale is never model free text: Muse selects fact
codes and code renders only the facts it can verify.
"""
from __future__ import annotations

import re
from typing import Iterable, Sequence

_PRIVATE_TERMS = re.compile(
    r"\b(afford\w*|budget\w*|broke|income|salary|money\s+is\s+tight|can'?t\s+pay|cannot\s+pay|"
    r"private|transcript|constraint\w*|disabilit\w*|medical|diagnos\w*|home\s+address|"
    r"lives?\s+(at|on|near)|schedule\s+conflict|only\s+free\s+(at|on|after|before))\b",
    re.IGNORECASE,
)
_MONEY = re.compile(r"([$€£¥]\s?\d)|(\b\d+(\.\d+)?\s?(dollars?|usd|bucks|cents|eur|euros?|gbp)\b)", re.IGNORECASE)
_LINK = re.compile(r"(https?://|www\.|\b[\w.-]+\.(com|net|org|io|app|dev|ly)\b)", re.IGNORECASE)
_CONTACT = re.compile(r"(\S+@\S+\.\S+)|(\+?\d[\d\s().-]{7,}\d)")
_ATTENDANCE_CLAIMS = re.compile(
    r"\b(last\s+week\s+(we|you|everyone)|after\s+(our|last)\s+(walk|meetup|quest|session)|"
    r"(we|you\s+all|everyone)\s+(had|met|came|showed\s+up|attended|enjoyed)|"
    r"great\s+to\s+see\s+(you|everyone)|thanks\s+for\s+coming|since\s+we\s+met)\b",
    re.IGNORECASE,
)


def violations(text: str, *, forbid_attendance_claims: bool = False, extra_terms: Iterable[str] = ()) -> list[str]:
    found: list[str] = []
    if _PRIVATE_TERMS.search(text):
        found.append("private_constraint_language")
    if _MONEY.search(text):
        found.append("money_amount")
    if _LINK.search(text):
        found.append("link")
    if _CONTACT.search(text):
        found.append("contact_detail")
    if forbid_attendance_claims and _ATTENDANCE_CLAIMS.search(text):
        found.append("attendance_claim")
    lowered = text.lower()
    for term in extra_terms:
        if term and len(term) >= 3 and re.search(rf"\b{re.escape(term.lower())}\b", lowered):
            found.append("names_individual")
            break
    return found


RATIONALE_FACTS = (
    "shared_interest",
    "fits_shared_time",
    "free_activity",
    "low_cost",
    "public_venue",
    "short_activity",
    "creates_shared_output",
    "easy_first_meeting",
)


def render_rationale(
    facts: Sequence[str],
    *,
    shared_interests: Sequence[str],
    cost_per_person_minor: int,
    duration_minutes: float,
) -> str:
    """Compose publicRationale from verifiable, group-level facts only."""
    chosen = [f for f in dict.fromkeys(facts) if f in RATIONALE_FACTS]
    # Facts code can always verify after validation; added so the rationale is never empty.
    for always in ("fits_shared_time", "public_venue"):
        if always not in chosen:
            chosen.append(always)
    parts: list[str] = []
    if "shared_interest" in chosen and shared_interests:
        names = list(shared_interests[:2])
        parts.append("builds on the group's shared interest in " + " and ".join(names))
    parts.append("fits a time that works for everyone")
    if cost_per_person_minor == 0 and ("free_activity" in chosen or "low_cost" in chosen):
        parts.append("is free")
    elif cost_per_person_minor > 0 and "low_cost" in chosen:
        parts.append("keeps costs low for the whole group")
    if "short_activity" in chosen and duration_minutes <= 60:
        parts.append("takes about an hour or less")
    parts.append("happens at an approved public venue")
    sentence = "This quest " + ", ".join(parts[:-1]) + (", and " if len(parts) > 1 else "") + parts[-1] + "."
    if "creates_shared_output" in chosen:
        sentence += " The group makes something together rather than doing it side by side."
    elif "easy_first_meeting" in chosen:
        sentence += " It is an easy way for new people to start talking."
    return sentence
