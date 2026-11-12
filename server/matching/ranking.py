"""Muse ranking layer: opaque payload out, strictly validated decision in.

Muse only proposes. Code validates the answer, and the public rationale is built from an
allowlisted template, never from model free text. Payloads are never logged.
"""
from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass
from typing import Any, Mapping, Optional, Protocol, Sequence, Tuple

from server.matching.feasibility import FeasibleGroup
from server.matching.models import (
    MatchingError, ModelEvidence, PublicParticipant, ValidationError,
)

PROMPT_VERSION = "rank_group.v1"
TASK_RANK_GROUP = "rank_group"
REASON_CODES = frozenset({
    "strong_shared_interest", "complementary_interests", "ample_common_time",
    "balanced_size", "newcomer_friendly",
})
MIN_REASON_CODES = 1
MAX_REASON_CODES = 3
MAX_RATIONALE_CHARS = 200
MAX_RATIONALE_INTERESTS = 2
MAX_INTEREST_CHARS = 30
DEFAULT_ATTEMPTS = 2
DEFAULT_TIMEOUT_S = 20.0
INSTRUCTIONS = (
    "Pick the option most likely to form an interactive small team. "
    "Return JSON {optionId, sharedInterests, reasonCodes}."
)
_OUTPUT_KEYS = frozenset({"optionId", "sharedInterests", "reasonCodes"})
_OPTION_ID_RE = re.compile(r"^g(0|[1-9][0-9]*)$")
# Letters (any script), spaces, hyphen, apostrophe, ampersand; no digits or currency.
_SAFE_INTEREST_RE = re.compile(r"^[^\W\d_]+(?:[ '&-][^\W\d_]+)*$")
_FAILURE_MESSAGE = "Muse ranking unavailable"


class MusePortLike(Protocol):
    async def generate(self, *, task: str, requestId: str, promptVersion: str,
                       payload: Any, signal: Optional[Any] = None) -> dict: ...


@dataclass(frozen=True)
class RankDecision:
    option_index: int
    shared_interests: Tuple[str, ...]
    reason_codes: Tuple[str, ...]


# ---------------------------------------------------------------- payload

def _assign_refs(groups: Sequence[FeasibleGroup], requester_id: str) -> dict:
    others = sorted({m for g in groups for m in g.member_ids if m != requester_id})
    refs = {requester_id: "m0"}
    refs.update({pid: f"m{i}" for i, pid in enumerate(others, start=1)})
    return refs


def _common_minutes(group: FeasibleGroup) -> int:
    return int(max((w.minutes for w in group.common_windows), default=0))


def build_rank_payload(groups: Sequence[FeasibleGroup],
                       profiles: Mapping[str, PublicParticipant],
                       requester_id: str) -> dict:
    """Opaque payload: refs instead of ids, public interests only, no names/budget/times."""
    refs = _assign_refs(groups, requester_id)
    options = []
    for i, group in enumerate(groups):
        members = []
        for pid in sorted(group.member_ids, key=lambda p: int(refs[p][1:])):
            profile = profiles.get(pid)
            interests = list(profile.public_interests) if profile else []
            members.append({"ref": refs[pid], "publicInterests": interests})
        options.append({
            "optionId": f"g{i}", "members": members,
            "sharedInterests": list(group.shared_interests),
            "size": len(group.member_ids), "commonMinutes": _common_minutes(group),
        })
    return {"requester": "m0", "options": options, "instructions": INSTRUCTIONS}


# ---------------------------------------------------------------- parsing

def _load_output(output: Any) -> Mapping[str, Any]:
    if isinstance(output, str):
        try:
            output = json.loads(output)
        except ValueError as exc:
            raise ValidationError("output", "expected JSON") from exc
    if not isinstance(output, Mapping):
        raise ValidationError("output", "expected object")
    return output


def _parse_option_index(value: Any, group_count: int) -> int:
    if not isinstance(value, str) or not _OPTION_ID_RE.match(value):
        raise ValidationError("output.optionId", "unknown option")
    index = int(value[1:])
    if index >= group_count:
        raise ValidationError("output.optionId", "option out of range")
    return index


def _parse_interests(value: Any, group: FeasibleGroup) -> Tuple[str, ...]:
    if not isinstance(value, list):
        raise ValidationError("output.sharedInterests", "expected array")
    allowed = {s.casefold(): s for s in group.shared_interests}
    chosen: dict = {}
    for item in value:
        if not isinstance(item, str) or item.casefold() not in allowed:
            raise ValidationError("output.sharedInterests", "interest not in group")
        chosen.setdefault(item.casefold(), allowed[item.casefold()])
    return tuple(chosen.values())


def _parse_reason_codes(value: Any) -> Tuple[str, ...]:
    if not isinstance(value, list):
        raise ValidationError("output.reasonCodes", "expected array")
    if not MIN_REASON_CODES <= len(value) <= MAX_REASON_CODES:
        raise ValidationError("output.reasonCodes", "expected 1-3 codes")
    for code in value:
        if not isinstance(code, str) or code not in REASON_CODES:
            raise ValidationError("output.reasonCodes", "unknown reason code")
    return tuple(dict.fromkeys(value))


def parse_rank_output(output: Any, groups: Sequence[FeasibleGroup]) -> RankDecision:
    data = _load_output(output)
    unknown = sorted(k for k in data if k not in _OUTPUT_KEYS)
    if unknown:
        raise ValidationError("output", f"unknown fields {unknown}")
    missing = sorted(_OUTPUT_KEYS - set(data))
    if missing:
        raise ValidationError("output", f"missing fields {missing}")
    index = _parse_option_index(data["optionId"], len(groups))
    return RankDecision(
        option_index=index,
        shared_interests=_parse_interests(data["sharedInterests"], groups[index]),
        reason_codes=_parse_reason_codes(data["reasonCodes"]),
    )


# ---------------------------------------------------------------- rationale

def _is_safe_interest(text: str) -> bool:
    return len(text) <= MAX_INTEREST_CHARS and bool(_SAFE_INTEREST_RE.match(text))


def _join_interests(items: Sequence[str]) -> str:
    return items[0] if len(items) == 1 else " and ".join(items)


def build_public_rationale(decision: RankDecision, group: FeasibleGroup) -> str:
    """Allowlisted template. Interests are included only if they look like plain words."""
    source = decision.shared_interests or group.shared_interests[:MAX_RATIONALE_INTERESTS]
    safe = [s for s in source if _is_safe_interest(s)][:MAX_RATIONALE_INTERESTS]
    if safe:
        text = (f"Matched on shared interest in {_join_interests(safe)}; "
                "everyone has time in common.")
    else:
        text = "Matched as a balanced small group; everyone has time in common."
    return text[:MAX_RATIONALE_CHARS]


# ---------------------------------------------------------------- orchestration

async def _attempt(port: MusePortLike, groups: Sequence[FeasibleGroup], payload: dict,
                   request_id: str, timeout_s: float) -> Tuple[RankDecision, ModelEvidence]:
    response = await asyncio.wait_for(
        port.generate(task=TASK_RANK_GROUP, requestId=request_id,
                      promptVersion=PROMPT_VERSION, payload=payload),
        timeout=timeout_s)
    if not isinstance(response, Mapping) or set(response) != {"output", "evidence"}:
        raise ValidationError("response", "expected output and evidence")
    decision = parse_rank_output(response["output"], groups)
    return decision, ModelEvidence.from_dict(response["evidence"])


async def rank_with_muse(port: MusePortLike, groups: Sequence[FeasibleGroup],
                         profiles: Mapping[str, PublicParticipant], requester_id: str,
                         request_id: str, *, attempts: int = DEFAULT_ATTEMPTS,
                         timeout_s: float = DEFAULT_TIMEOUT_S
                         ) -> Tuple[RankDecision, ModelEvidence]:
    if not groups:
        raise MatchingError("INVALID_INPUT", "No groups to rank", retryable=False)
    payload = build_rank_payload(groups, profiles, requester_id)
    for _ in range(max(1, attempts)):
        try:
            return await _attempt(port, groups, payload, request_id, timeout_s)
        except Exception:  # noqa: BLE001 - provider failure of any kind is retried; never logged
            continue
    raise MatchingError("PROVIDER_UNAVAILABLE", _FAILURE_MESSAGE, retryable=True)
