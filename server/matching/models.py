"""Runtime-validated mirror of the matching slice of contracts/protocol.ts v1.0.0.

Only the shapes the matching service consumes or produces live here. JSON keys stay
camelCase on the wire; Python attributes are snake_case. Every ``from_dict`` rejects
unknown keys, wrong types and contract-violating values (fail closed). Instances are
frozen: build new objects instead of mutating.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal, Mapping, Optional, Sequence, Tuple, Union

CONTRACT_VERSION = "1.0.0"
MODES = ("live", "fixture", "replay")
EVIDENCE_SOURCES = ("live", "replay")
NO_MATCH_REASONS = ("too_few", "no_common_time", "constraints")
MIN_GROUP_SIZE = 3
MAX_GROUP_SIZE = 5


class ValidationError(ValueError):
    """Raised when wire data violates the shared contract. Message never echoes values."""

    def __init__(self, path: str, problem: str) -> None:
        super().__init__(f"{path}: {problem}")
        self.path = path
        self.problem = problem


# ---------------------------------------------------------------- primitives

def _require_mapping(value: Any, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(path, "expected object")
    return value


def _check_keys(data: Mapping[str, Any], path: str, required: Sequence[str],
                optional: Sequence[str] = ()) -> None:
    allowed = set(required) | set(optional)
    unknown = sorted(k for k in data if k not in allowed)
    if unknown:
        raise ValidationError(path, f"unknown fields {unknown}")
    missing = sorted(k for k in required if k not in data)
    if missing:
        raise ValidationError(path, f"missing fields {missing}")


def _str(value: Any, path: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or (not allow_empty and not value.strip()):
        raise ValidationError(path, "expected non-empty string")
    return value


def _int(value: Any, path: str, *, minimum: Optional[int] = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValidationError(path, "expected integer")
    if minimum is not None and value < minimum:
        raise ValidationError(path, f"must be >= {minimum}")
    return value


def _bool(value: Any, path: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(path, "expected boolean")
    return value


def _literal(value: Any, path: str, options: Sequence[str]) -> str:
    if value not in options:
        raise ValidationError(path, f"expected one of {list(options)}")
    return value


def _str_list(value: Any, path: str) -> Tuple[str, ...]:
    if not isinstance(value, list):
        raise ValidationError(path, "expected array")
    return tuple(_str(v, f"{path}[{i}]") for i, v in enumerate(value))


def parse_time(value: Any, path: str) -> datetime:
    """Parse RFC3339 UTC (``Z`` or ``+00:00``). Naive or non-UTC offsets are rejected."""
    raw = _str(value, path)
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValidationError(path, "expected RFC3339 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(None):
        raise ValidationError(path, "expected UTC timestamp")
    return parsed.astimezone(timezone.utc)


def format_time(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------- types

@dataclass(frozen=True)
class Window:
    """Half-open interval [start, end) with start < end."""
    start: datetime
    end: datetime

    @property
    def minutes(self) -> float:
        return (self.end - self.start).total_seconds() / 60

    @staticmethod
    def from_dict(data: Any, path: str = "window") -> "Window":
        d = _require_mapping(data, path)
        _check_keys(d, path, ("start", "end"))
        start = parse_time(d["start"], f"{path}.start")
        end = parse_time(d["end"], f"{path}.end")
        if not start < end:
            raise ValidationError(path, "start must be before end")
        return Window(start, end)

    def to_dict(self) -> dict:
        return {"start": format_time(self.start), "end": format_time(self.end)}


@dataclass(frozen=True)
class Context:
    request_id: str
    mode: str
    contract_version: str = CONTRACT_VERSION

    @staticmethod
    def from_dict(data: Any, path: str = "context") -> "Context":
        d = _require_mapping(data, path)
        _check_keys(d, path, ("requestId", "contractVersion", "mode"))
        if d["contractVersion"] != CONTRACT_VERSION:
            raise ValidationError(f"{path}.contractVersion", f"expected {CONTRACT_VERSION}")
        return Context(_str(d["requestId"], f"{path}.requestId"),
                       _literal(d["mode"], f"{path}.mode", MODES))

    def to_dict(self) -> dict:
        return {"requestId": self.request_id, "contractVersion": self.contract_version,
                "mode": self.mode}


@dataclass(frozen=True)
class ModelEvidence:
    model: str
    source: str
    generated_at: datetime
    latency_ms: int

    @staticmethod
    def from_dict(data: Any, path: str = "evidence") -> "ModelEvidence":
        d = _require_mapping(data, path)
        _check_keys(d, path, ("model", "source", "generatedAt", "latencyMs"))
        return ModelEvidence(
            _str(d["model"], f"{path}.model"),
            _literal(d["source"], f"{path}.source", EVIDENCE_SOURCES),
            parse_time(d["generatedAt"], f"{path}.generatedAt"),
            _int(d["latencyMs"], f"{path}.latencyMs", minimum=0),
        )

    def to_dict(self) -> dict:
        return {"model": self.model, "source": self.source,
                "generatedAt": format_time(self.generated_at), "latencyMs": self.latency_ms}


_INTENT_KEYS = ("participantId", "communityId", "intentVersion", "goal", "interests",
                "areaId", "timeZone", "availability", "maxBudgetMinor", "currency",
                "maxDurationMinutes", "groupPreference", "consentVersion", "confirmedAt")


@dataclass(frozen=True)
class PrivateIntent:
    participant_id: str
    community_id: str
    intent_version: int
    goal: str
    interests: Tuple[str, ...]
    area_id: str
    time_zone: str
    availability: Tuple[Window, ...]
    max_budget_minor: int
    currency: str
    max_duration_minutes: int
    consent_version: int
    confirmed_at: datetime
    group_preference: Literal["small"] = "small"

    @staticmethod
    def from_dict(data: Any, path: str = "intent") -> "PrivateIntent":
        d = _require_mapping(data, path)
        _check_keys(d, path, _INTENT_KEYS)
        avail_raw = d["availability"]
        if not isinstance(avail_raw, list):
            raise ValidationError(f"{path}.availability", "expected array")
        currency = _str(d["currency"], f"{path}.currency")
        if len(currency) != 3 or not currency.isalpha() or not currency.isupper():
            raise ValidationError(f"{path}.currency", "expected ISO-4217 code")
        _literal(d["groupPreference"], f"{path}.groupPreference", ("small",))
        return PrivateIntent(
            participant_id=_str(d["participantId"], f"{path}.participantId"),
            community_id=_str(d["communityId"], f"{path}.communityId"),
            intent_version=_int(d["intentVersion"], f"{path}.intentVersion", minimum=1),
            goal=_str(d["goal"], f"{path}.goal", allow_empty=True),
            interests=_str_list(d["interests"], f"{path}.interests"),
            area_id=_str(d["areaId"], f"{path}.areaId"),
            time_zone=_str(d["timeZone"], f"{path}.timeZone"),
            availability=tuple(Window.from_dict(w, f"{path}.availability[{i}]")
                               for i, w in enumerate(avail_raw)),
            max_budget_minor=_int(d["maxBudgetMinor"], f"{path}.maxBudgetMinor", minimum=0),
            currency=currency,
            max_duration_minutes=_int(d["maxDurationMinutes"], f"{path}.maxDurationMinutes",
                                      minimum=1),
            consent_version=_int(d["consentVersion"], f"{path}.consentVersion", minimum=1),
            confirmed_at=parse_time(d["confirmedAt"], f"{path}.confirmedAt"),
        )


@dataclass(frozen=True)
class PublicParticipant:
    participant_id: str
    display_name: str
    public_interests: Tuple[str, ...]
    is_synthetic: bool

    @staticmethod
    def from_dict(data: Any, path: str = "publicProfile") -> "PublicParticipant":
        d = _require_mapping(data, path)
        _check_keys(d, path, ("participantId", "displayName", "publicInterests", "isSynthetic"))
        return PublicParticipant(
            _str(d["participantId"], f"{path}.participantId"),
            _str(d["displayName"], f"{path}.displayName"),
            _str_list(d["publicInterests"], f"{path}.publicInterests"),
            _bool(d["isSynthetic"], f"{path}.isSynthetic"),
        )

    def to_dict(self) -> dict:
        return {"participantId": self.participant_id, "displayName": self.display_name,
                "publicInterests": list(self.public_interests), "isSynthetic": self.is_synthetic}


@dataclass(frozen=True)
class Candidate:
    """Internal only: the privacy layer has already authorized/minimized this snapshot."""
    intent: PrivateIntent
    public_profile: PublicParticipant

    @property
    def participant_id(self) -> str:
        return self.intent.participant_id

    @staticmethod
    def from_dict(data: Any, path: str = "candidate") -> "Candidate":
        d = _require_mapping(data, path)
        _check_keys(d, path, ("intent", "publicProfile"))
        intent = PrivateIntent.from_dict(d["intent"], f"{path}.intent")
        profile = PublicParticipant.from_dict(d["publicProfile"], f"{path}.publicProfile")
        if intent.participant_id != profile.participant_id:
            raise ValidationError(path, "intent and publicProfile participantId differ")
        return Candidate(intent, profile)


@dataclass(frozen=True)
class MatchInput:
    context: Context
    community_id: str
    requester_id: str
    candidates: Tuple[Candidate, ...]
    minimum_size: int = MIN_GROUP_SIZE
    maximum_size: int = MAX_GROUP_SIZE

    @staticmethod
    def from_dict(data: Any, path: str = "matchInput") -> "MatchInput":
        d = _require_mapping(data, path)
        _check_keys(d, path, ("context", "communityId", "requesterId", "candidates",
                              "minimumSize", "maximumSize"))
        if d["minimumSize"] != MIN_GROUP_SIZE or isinstance(d["minimumSize"], bool):
            raise ValidationError(f"{path}.minimumSize", f"must be {MIN_GROUP_SIZE}")
        if d["maximumSize"] != MAX_GROUP_SIZE or isinstance(d["maximumSize"], bool):
            raise ValidationError(f"{path}.maximumSize", f"must be {MAX_GROUP_SIZE}")
        raw = d["candidates"]
        if not isinstance(raw, list):
            raise ValidationError(f"{path}.candidates", "expected array")
        return MatchInput(
            context=Context.from_dict(d["context"], f"{path}.context"),
            community_id=_str(d["communityId"], f"{path}.communityId"),
            requester_id=_str(d["requesterId"], f"{path}.requesterId"),
            candidates=tuple(Candidate.from_dict(c, f"{path}.candidates[{i}]")
                             for i, c in enumerate(raw)),
        )


@dataclass(frozen=True)
class MemberVersion:
    participant_id: str
    intent_version: int
    consent_version: int

    def to_dict(self) -> dict:
        return {"participantId": self.participant_id, "intentVersion": self.intent_version,
                "consentVersion": self.consent_version}

    @staticmethod
    def from_dict(data: Any, path: str = "memberVersion") -> "MemberVersion":
        d = _require_mapping(data, path)
        _check_keys(d, path, ("participantId", "intentVersion", "consentVersion"))
        return MemberVersion(_str(d["participantId"], f"{path}.participantId"),
                             _int(d["intentVersion"], f"{path}.intentVersion", minimum=1),
                             _int(d["consentVersion"], f"{path}.consentVersion", minimum=1))


@dataclass(frozen=True)
class GroupProposal:
    proposal_id: str
    community_id: str
    revision: int
    member_ids: Tuple[str, ...]
    member_versions: Tuple[MemberVersion, ...]
    feasible_windows: Tuple[Window, ...]
    shared_interests: Tuple[str, ...]
    public_rationale: str
    evidence: ModelEvidence

    def to_dict(self) -> dict:
        return {
            "proposalId": self.proposal_id, "communityId": self.community_id,
            "revision": self.revision, "memberIds": list(self.member_ids),
            "memberVersions": [m.to_dict() for m in self.member_versions],
            "feasibleWindows": [w.to_dict() for w in self.feasible_windows],
            "sharedInterests": list(self.shared_interests),
            "publicRationale": self.public_rationale, "evidence": self.evidence.to_dict(),
        }

    @staticmethod
    def from_dict(data: Any, path: str = "proposal") -> "GroupProposal":
        d = _require_mapping(data, path)
        _check_keys(d, path, ("proposalId", "communityId", "revision", "memberIds",
                              "memberVersions", "feasibleWindows", "sharedInterests",
                              "publicRationale", "evidence"))
        member_ids = _str_list(d["memberIds"], f"{path}.memberIds")
        if len(set(member_ids)) != len(member_ids):
            raise ValidationError(f"{path}.memberIds", "duplicate participant")
        if not MIN_GROUP_SIZE <= len(member_ids) <= MAX_GROUP_SIZE:
            raise ValidationError(f"{path}.memberIds", "group size must be 3-5")
        for key in ("memberVersions", "feasibleWindows"):
            if not isinstance(d[key], list):
                raise ValidationError(f"{path}.{key}", "expected array")
        versions = tuple(MemberVersion.from_dict(v, f"{path}.memberVersions[{i}]")
                         for i, v in enumerate(d["memberVersions"]))
        if sorted(v.participant_id for v in versions) != sorted(member_ids):
            raise ValidationError(f"{path}.memberVersions", "must cover exactly memberIds")
        return GroupProposal(
            proposal_id=_str(d["proposalId"], f"{path}.proposalId"),
            community_id=_str(d["communityId"], f"{path}.communityId"),
            revision=_int(d["revision"], f"{path}.revision", minimum=1),
            member_ids=member_ids,
            member_versions=versions,
            feasible_windows=tuple(Window.from_dict(w, f"{path}.feasibleWindows[{i}]")
                                   for i, w in enumerate(d["feasibleWindows"])),
            shared_interests=_str_list(d["sharedInterests"], f"{path}.sharedInterests"),
            public_rationale=_str(d["publicRationale"], f"{path}.publicRationale"),
            evidence=ModelEvidence.from_dict(d["evidence"], f"{path}.evidence"),
        )


@dataclass(frozen=True)
class Matched:
    proposal: GroupProposal
    status: Literal["matched"] = "matched"

    def to_dict(self) -> dict:
        return {"status": "matched", "proposal": self.proposal.to_dict()}


@dataclass(frozen=True)
class NoMatch:
    reason: str  # one of NO_MATCH_REASONS
    suggestions: Tuple[str, ...] = field(default_factory=tuple)
    status: Literal["no_match"] = "no_match"

    def __post_init__(self) -> None:
        if self.reason not in NO_MATCH_REASONS:
            raise ValidationError("noMatch.reason", f"expected one of {list(NO_MATCH_REASONS)}")

    def to_dict(self) -> dict:
        return {"status": "no_match", "reason": self.reason,
                "suggestions": list(self.suggestions)}


MatchResult = Union[Matched, NoMatch]


class MatchingError(Exception):
    """Service failure mapped to a contract ErrorCode. Never carries private values."""

    def __init__(self, code: str, message: str, *, retryable: bool) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable
