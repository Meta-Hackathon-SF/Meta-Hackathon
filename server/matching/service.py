"""MatchingService: feasibility gates, Muse ranking, validated GroupProposal.

Muse proposes; code validates. No constraint is ever relaxed, provider failure is an
explicit MatchingError (never a fake success), and no payload is logged.
"""
from __future__ import annotations

import dataclasses
from datetime import datetime, timezone
from typing import Callable, Mapping, Sequence, Union
from uuid import uuid4

from server.matching.feasibility import (
    FeasibleGroup, diagnose_no_match, eligible_candidates, enumerate_groups, find_requester,
)
from server.matching.models import (
    MAX_GROUP_SIZE, MIN_GROUP_SIZE, Candidate, GroupProposal, Matched, MatchingError,
    MatchInput, MemberVersion, ModelEvidence, NoMatch, PublicParticipant, ValidationError,
)
from server.matching.ranking import (
    MusePortLike, RankDecision, build_public_rationale, rank_with_muse,
)

SUGGESTIONS = {
    "too_few": ("Invite more community members to opt in",),
    "no_common_time": ("Add another availability window",),
    "constraints": ("Try a different time or a nearby area",),
}
_PROPOSAL_ID_PREFIX = "prop_"
# fixture mode accepts the labeled test double; live/replay must match exactly.
_EVIDENCE_SOURCE_FOR_MODE = {"live": "live", "replay": "replay"}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_proposal_id() -> str:
    return _PROPOSAL_ID_PREFIX + uuid4().hex


def _parse_input(raw: Union[MatchInput, Mapping]) -> MatchInput:
    if isinstance(raw, MatchInput):
        return raw
    try:
        return MatchInput.from_dict(raw)
    except ValidationError as exc:
        raise MatchingError("INVALID_INPUT", f"Invalid match input: {exc.path}",
                            retryable=False) from exc


def _validate_selection(group: FeasibleGroup, inp: MatchInput) -> None:
    allowed = {c.participant_id for c in eligible_candidates(inp)} | {inp.requester_id}
    ids = group.member_ids
    ok = (inp.requester_id in ids and len(set(ids)) == len(ids)
          and set(ids) <= allowed and MIN_GROUP_SIZE <= len(ids) <= MAX_GROUP_SIZE)
    if not ok:
        raise MatchingError("PROVIDER_UNAVAILABLE", "Muse ranking unavailable", retryable=True)


def _check_evidence_mode(evidence: ModelEvidence, inp: MatchInput) -> None:
    """Mode is server-selected; a live request must never carry replay evidence and vice versa."""
    required = _EVIDENCE_SOURCE_FOR_MODE.get(inp.context.mode)
    if required is not None and evidence.source != required:
        raise MatchingError("PROVIDER_UNAVAILABLE", "Muse evidence does not match request mode",
                            retryable=False)


def _build_proposal(group: FeasibleGroup, decision: RankDecision, evidence: ModelEvidence,
                    inp: MatchInput, proposal_id: str) -> GroupProposal:
    by_id = {c.participant_id: c for c in inp.candidates}
    versions = tuple(MemberVersion(pid, by_id[pid].intent.intent_version,
                                   by_id[pid].intent.consent_version)
                     for pid in group.member_ids)
    shared = decision.shared_interests or group.shared_interests
    proposal = GroupProposal(
        proposal_id=proposal_id, community_id=inp.community_id, revision=1,
        member_ids=group.member_ids, member_versions=versions,
        feasible_windows=group.common_windows, shared_interests=tuple(shared),
        public_rationale=build_public_rationale(decision, group), evidence=evidence)
    return proposal


def _no_match(inp: MatchInput) -> NoMatch:
    reason = diagnose_no_match(inp)
    return NoMatch(reason=reason, suggestions=SUGGESTIONS[reason])


class MatchingService:
    """Implements the contracts MatchingPort."""

    def __init__(self, muse: MusePortLike, *,
                 id_factory: Callable[[], str] = _new_proposal_id,
                 clock: Callable[[], datetime] = utcnow) -> None:
        self._muse = muse
        self._id_factory = id_factory
        self._clock = clock

    async def match(self, raw_or_input: Union[MatchInput, Mapping]) -> Union[Matched, NoMatch]:
        inp = _parse_input(raw_or_input)
        try:
            find_requester(inp)
            groups = enumerate_groups(inp)
            if not groups:
                return _no_match(inp)
            profiles = {c.participant_id: c.public_profile for c in inp.candidates}
            decision, evidence = await rank_with_muse(
                self._muse, groups, profiles, inp.requester_id, inp.context.request_id)
            group = groups[decision.option_index]
            _validate_selection(group, inp)
            _check_evidence_mode(evidence, inp)
            proposal = _build_proposal(group, decision, evidence, inp, self._id_factory())
            GroupProposal.from_dict(proposal.to_dict())
        except ValidationError as exc:
            raise MatchingError("INVALID_INPUT", f"Invalid match input: {exc.path}",
                                retryable=False) from exc
        return Matched(proposal)

    async def recompute(self, prior: GroupProposal,
                        raw_or_input: Union[MatchInput, Mapping]) -> Union[Matched, NoMatch]:
        inp = _parse_input(raw_or_input)
        if inp.community_id != prior.community_id:
            raise MatchingError("FORBIDDEN", "Community mismatch", retryable=False)
        result = await self.match(inp)
        if isinstance(result, NoMatch):
            return result
        bumped = dataclasses.replace(result.proposal, proposal_id=prior.proposal_id,
                                     revision=prior.revision + 1)
        return Matched(bumped)


def is_stale(proposal: GroupProposal, candidates: Sequence[Candidate]) -> bool:
    current = {c.participant_id: c.intent for c in candidates}
    for mv in proposal.member_versions:
        intent = current.get(mv.participant_id)
        if intent is None or (intent.intent_version != mv.intent_version
                              or intent.consent_version != mv.consent_version):
            return True
    return False


def public_projection(result: Union[Matched, NoMatch],
                      profiles: Mapping[str, PublicParticipant]) -> dict:
    """Allowlisted public DTO (API.md Exposure): no versions, windows or constraints."""
    if isinstance(result, NoMatch):
        return {"status": "no_match", "reason": result.reason,
                "suggestions": list(result.suggestions)}
    p = result.proposal
    missing = [pid for pid in p.member_ids if pid not in profiles]
    if missing:
        raise MatchingError("INVALID_INPUT", "Missing public profile for member",
                            retryable=False)
    return {"status": "matched", "proposal": {
        "proposalId": p.proposal_id, "revision": p.revision,
        "members": [profiles[pid].to_dict() for pid in p.member_ids],
        "sharedInterests": list(p.shared_interests),
        "publicRationale": p.public_rationale,
        "evidence": p.evidence.to_dict()}}
