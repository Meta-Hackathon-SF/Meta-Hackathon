"""Allowlisted public projections and the private-fact leak guard.

Peers and browsers only ever receive these DTOs. Each validator forbids extra
fields, so a private field added upstream fails loudly instead of leaking.

``find_leaks`` is a defense-in-depth check on free text (model or template
rationale, opener, titles, invitations). It catches known private facts from
the authorized snapshot: member budgets, verbatim goal fragments, interests a
member did not consent to publish, and individual-constraint phrasing. It is a
heuristic, not a proof of non-disclosure; callers must still build public text
from approved facts (PRIVACY.md).
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from typing import Annotated, Literal

from pydantic import Field, StrictInt, StringConstraints

from .errors import PrivacyError
from .wire import Candidate, Currency, Id, IsoTime, PublicParticipant, Tag, TimeZoneName, Wire

PublicText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=600)]


class ModelEvidence(Wire):
    model: Annotated[str, StringConstraints(min_length=1, max_length=120)]
    source: Literal["live", "replay"]
    generated_at: IsoTime
    latency_ms: StrictInt = Field(ge=0)


class PublicGroupProposal(Wire):
    """Peer-visible group proposal. Same shape as matching.public_projection
    (Rishi): no memberVersions, feasibleWindows or private constraints."""

    proposal_id: Id
    revision: StrictInt = Field(ge=1)
    members: list[PublicParticipant] = Field(min_length=3, max_length=5)
    shared_interests: list[Tag] = Field(max_length=10)
    public_rationale: PublicText
    evidence: ModelEvidence


class PublicPlanCard(Wire):
    """Peer-visible QuestPlan. Drops memberVersions/basedOnRevision."""

    plan_id: Id
    proposal_id: Id
    revision: StrictInt = Field(ge=1)
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
    activity: PublicText
    collaboration_task: PublicText
    venue_id: Id
    start: IsoTime
    end: IsoTime
    time_zone: TimeZoneName
    cost_per_person_minor: StrictInt = Field(ge=0)
    currency: Currency
    minimum_size: Literal[3]
    maximum_size: Literal[5]
    public_rationale: PublicText
    opener: PublicText
    evidence: ModelEvidence


PROPOSAL_TEXT_FIELDS = ("publicRationale",)
PLAN_TEXT_FIELDS = ("title", "activity", "collaborationTask", "publicRationale", "opener")

# Phrasing that discloses an individual's constraint rather than a group fact.
_INDIVIDUAL_CONSTRAINT = re.compile(
    r"\b(can(?:no|')?t|cannot|unable to|could ?n[o']t) afford\b"
    r"|\b(his|her|my) (max(?:imum)?|budget|limit|cap)\b"
    r"|\bbudget (?:is|of|cap|limit)\b"
    r"|\bonly (?:has|have|got) \$"
    r"|\b(?:is|isn'?t|are|aren'?t|not|only) (?:free|available) (?:after|before|until|on)\b",
    re.IGNORECASE,
)
_WORD = re.compile(r"[a-z0-9']+")
GOAL_NGRAM = 5


def _amount_patterns(minor: int) -> list[re.Pattern[str]]:
    major, cents = divmod(minor, 100)
    forms = [rf"{major}\.{cents:02d}"] if cents else [rf"{major}(?:\.00)?"]
    pats = [re.compile(rf"[$€£]\s?{f}\b") for f in forms]
    pats.append(re.compile(rf"\b{forms[0]}\s?(?:dollars?|usd|eur|gbp|bucks)\b", re.IGNORECASE))
    if minor >= 100:
        pats.append(re.compile(rf"\b{minor}\b"))  # raw minor units
    return pats


def _ngrams(text: str, n: int) -> set[tuple[str, ...]]:
    words = _WORD.findall(text.lower())
    return {tuple(words[i:i + n]) for i in range(len(words) - n + 1)}


def find_leaks(
    texts: Mapping[str, str],
    candidates: Sequence[Candidate],
    *,
    allowed_amounts_minor: Iterable[int] = (),
) -> list[str]:
    """Return sorted ``field:reason`` codes. Never includes the private value."""
    allowed = set(allowed_amounts_minor)
    public_interests = {
        i.lower() for c in candidates for i in c.public_profile.public_interests
    }
    found: set[str] = set()
    for field, text in texts.items():
        if not text:
            continue
        lower = text.lower()
        if _INDIVIDUAL_CONSTRAINT.search(text):
            found.add(f"{field}:individual_constraint")
        text_ngrams = _ngrams(text, GOAL_NGRAM)
        for c in candidates:
            name = c.public_profile.display_name.split(" ")[0]
            if len(name) >= 2 and re.search(
                rf"\b{re.escape(name)}(?:'s (?:budget|max(?:imum)?|limit|cap|availability|schedule)"
                rf"| (?:can(?:no|')?t|cannot|isn'?t|is not|is only|only has|has only)\b)",
                text, re.IGNORECASE,
            ):
                found.add(f"{field}:individual_constraint")
            budget = c.intent.max_budget_minor
            if budget not in allowed and budget > 0 and any(p.search(text) for p in _amount_patterns(budget)):
                found.add(f"{field}:budget")
            if text_ngrams & _ngrams(c.intent.goal, GOAL_NGRAM):
                found.add(f"{field}:goal")
            for interest in c.intent.interests:
                key = interest.lower()
                if key not in public_interests and re.search(rf"\b{re.escape(key)}\b", lower):
                    found.add(f"{field}:unconsented_interest")
    return sorted(found)


def _members(member_ids: Sequence[str], candidates: Sequence[Candidate]) -> list[PublicParticipant]:
    by_id = {c.public_profile.participant_id: c.public_profile for c in candidates}
    if len(set(member_ids)) != len(member_ids):
        raise PrivacyError("INVALID_INPUT", "Duplicate member in proposal.")
    missing = [m for m in member_ids if m not in by_id]
    if missing:
        # A member outside the authorized snapshot cannot be shown to peers.
        raise PrivacyError("FORBIDDEN", "Proposal references a participant outside the authorized snapshot.")
    return [by_id[m] for m in member_ids]


def _reject_leaks(texts: Mapping[str, str], candidates: Sequence[Candidate], **kw) -> None:
    leaks = find_leaks(texts, candidates, **kw)
    if leaks:
        raise PrivacyError(
            "INVALID_INPUT",
            "Public text failed the privacy check (" + ", ".join(leaks) + ").",
        )


def project_proposal(proposal: Mapping, candidates: Sequence[Candidate]) -> PublicGroupProposal:
    """GroupProposal wire dict -> PublicGroupProposal, with members re-derived
    from the authorized snapshot and rationale leak-checked."""
    dto = PublicGroupProposal.model_validate({
        "proposalId": proposal["proposalId"],
        "revision": proposal["revision"],
        "members": [m.wire() for m in _members(proposal["memberIds"], candidates)],
        "sharedInterests": list(proposal["sharedInterests"]),
        "publicRationale": proposal["publicRationale"],
        "evidence": proposal["evidence"],
    })
    member_set = set(proposal["memberIds"])
    in_group = [c for c in candidates if c.public_profile.participant_id in member_set]
    _reject_leaks({"publicRationale": dto.public_rationale}, in_group)
    return dto


def validate_public_proposal(dto: Mapping, candidates: Sequence[Candidate]) -> PublicGroupProposal:
    """Gate for an already-projected proposal (e.g. matching.public_projection
    output) before it reaches a peer: strict shape + member/leak checks."""
    parsed = PublicGroupProposal.model_validate(dict(dto))
    ids = [m.participant_id for m in parsed.members]
    expected = _members(ids, candidates)
    if [m.wire() for m in expected] != [m.wire() for m in parsed.members]:
        raise PrivacyError("INVALID_INPUT", "Member profiles differ from the authorized public profiles.")
    in_group = [c for c in candidates if c.public_profile.participant_id in set(ids)]
    _reject_leaks({"publicRationale": parsed.public_rationale}, in_group)
    return parsed


def project_plan(plan: Mapping, candidates: Sequence[Candidate]) -> PublicPlanCard:
    """QuestPlan wire dict -> PublicPlanCard, leak-checking every text field.
    The plan's own cost is a public group fact, so it is an allowed amount."""
    allow = {k: plan[k] for k in (
        "planId", "proposalId", "revision", "title", "activity", "collaborationTask",
        "venueId", "start", "end", "timeZone", "costPerPersonMinor", "currency",
        "minimumSize", "maximumSize", "publicRationale", "opener", "evidence")}
    dto = PublicPlanCard.model_validate(allow)
    member_ids = {m["participantId"] for m in plan["memberVersions"]}
    in_group = [c for c in candidates if c.public_profile.participant_id in member_ids]
    if len(in_group) != len(member_ids):
        raise PrivacyError("FORBIDDEN", "Plan references a participant outside the authorized snapshot.")
    _reject_leaks({f: allow[f] for f in PLAN_TEXT_FIELDS}, in_group,
                  allowed_amounts_minor=[dto.cost_per_person_minor])
    return dto
