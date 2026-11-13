"""Formation wire models mirroring contracts/protocol.ts 2.1.0 (camelCase on the wire).

Stdlib only. Every constructor path that accepts external data validates it; dataclasses are
frozen so nothing is mutated after validation.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

CONTRACT_VERSION = "2.1.0"
MIN_CONSTELLATION_SIZE = 3
MAX_CONSTELLATION_SIZE = 5
LOOSE_MATCH_CONFIDENCE = 0.5
DEMO_SKY_THRESHOLD = 3
PRODUCTION_SKY_THRESHOLD = 25
MAX_ANSWER_CHARS = 400
MAX_LABEL_CHARS = 80
MAX_NAME_CHARS = 40
MAX_MEANING_CHARS = 300

# Fixed visual sets. shapeId is chosen per size; Muse may only pick from these.
SHAPES_BY_SIZE: Mapping[int, tuple[str, ...]] = {
    3: ("triangle", "arrow", "crown"),
    4: ("kite", "square", "dipper-4", "cross"),
    5: ("w-cass", "house", "pentagon", "dipper-5"),
}
COLOR_IDS: tuple[str, ...] = ("ember", "tide", "moss", "dusk", "gold", "rose", "frost", "violet")
MUSE_CALL_TYPES = frozenset({"M1", "M2", "M3", "M4", "M5", "M6", "M7", "M8"})
EVIDENCE_SOURCES = frozenset({"live", "replay"})
FALLBACK_LABEL = "Fallback grouping"


class MatchingError(Exception):
    """Error surfaced to orchestration as ApiError['error']. Message is safe to show."""

    def __init__(self, code: str, message: str, *, retryable: bool) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable

    def to_wire(self, request_id: str) -> dict:
        return {"code": self.code, "message": self.message,
                "requestId": request_id, "retryable": self.retryable}


class ValidationError(ValueError):
    def __init__(self, path: str, reason: str) -> None:
        super().__init__(f"{path}: {reason}")
        self.path = path
        self.reason = reason


def _require_str(data: Mapping[str, Any], key: str, path: str, *, max_len: int) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{path}.{key}", "expected non-empty string")
    if len(value) > max_len:
        raise ValidationError(f"{path}.{key}", f"longer than {max_len}")
    return value.strip()


@dataclass(frozen=True)
class PromptText:
    """Random per-call ref + text. `id` is a player ref shared by that player's answers."""
    id: str
    text: str
    weight: float = 1.0

    @staticmethod
    def from_dict(data: Any, path: str = "answer") -> PromptText:
        if not isinstance(data, Mapping):
            raise ValidationError(path, "expected object")
        ref = _require_str(data, "id", path, max_len=64)
        text = _require_str(data, "text", path, max_len=MAX_ANSWER_CHARS)
        weight = data.get("weight", 1.0)
        is_number = isinstance(weight, (int, float)) and not isinstance(weight, bool)
        if not is_number or not 0 < weight <= 1.1:
            raise ValidationError(f"{path}.weight", "expected number in (0, 1.1]")
        return PromptText(ref, text, float(weight))

    def to_wire(self) -> dict:
        return {"id": self.id, "text": self.text, "weight": self.weight}


def _id_list(data: Mapping[str, Any], key: str, path: str) -> tuple[str, ...]:
    value = data.get(key, [])
    if not isinstance(value, list) or len(value) > 50 or not all(
            isinstance(v, str) and 0 < len(v) <= 128 for v in value):
        raise ValidationError(f"{path}.{key}", "expected up to 50 ids")
    return tuple(sorted(set(value)))


@dataclass(frozen=True)
class ActivitySignals:
    """D010 (PRIVATE): opaque ids and allowlisted topic labels; never free text."""
    profile_id: str | None = None
    group_ids: tuple[str, ...] = ()
    event_ids: tuple[str, ...] = ()
    friend_ids: tuple[str, ...] = ()
    topics: tuple[str, ...] = ()

    @staticmethod
    def from_dict(data: Any, path: str) -> ActivitySignals:
        if not isinstance(data, Mapping):
            raise ValidationError(path, "expected object")
        profile = data.get("profileId")
        if profile is not None and not (isinstance(profile, str) and 0 < len(profile) <= 128):
            raise ValidationError(f"{path}.profileId", "expected id or null")
        topics = _id_list(data, "topics", path)
        if any(len(t) > 40 for t in topics):
            raise ValidationError(f"{path}.topics", "topic label too long")
        return ActivitySignals(profile, _id_list(data, "groupIds", path), _id_list(data, "eventIds", path),
                               _id_list(data, "friendIds", path), topics)


@dataclass(frozen=True)
class FormationSnapshot:
    """PrivacyPort.formationSnapshot output. Already consent-filtered and safety-filtered."""
    answers: tuple[PromptText, ...]
    id_map: Mapping[str, str]  # ref -> playerId (private, never sent to Muse)
    blocked_pairs: tuple[tuple[str, str], ...]  # playerIds
    activity: Mapping[str, ActivitySignals] = field(default_factory=dict)  # D010: by ref, opt-in only

    @staticmethod
    def from_dict(data: Any) -> FormationSnapshot:
        if not isinstance(data, Mapping):
            raise ValidationError("snapshot", "expected object")
        raw_answers = data.get("answers")
        if not isinstance(raw_answers, list):
            raise ValidationError("snapshot.answers", "expected array")
        answers = tuple(PromptText.from_dict(a, f"snapshot.answers[{i}]")
                        for i, a in enumerate(raw_answers))
        id_map = data.get("idMap")
        if not isinstance(id_map, Mapping) or not all(
                isinstance(k, str) and isinstance(v, str) for k, v in id_map.items()):
            raise ValidationError("snapshot.idMap", "expected string map")
        missing = sorted({a.id for a in answers} - set(id_map))
        if missing:
            raise ValidationError("snapshot.idMap", "answer ref without player")
        pairs = data.get("blockedPairs", [])
        if not isinstance(pairs, list) or not all(
                isinstance(p, (list, tuple)) and len(p) == 2 and all(isinstance(x, str) for x in p)
                for p in pairs):
            raise ValidationError("snapshot.blockedPairs", "expected [id, id] pairs")
        raw_activity = data.get("activity", {})
        if not isinstance(raw_activity, Mapping):
            raise ValidationError("snapshot.activity", "expected object")
        if set(raw_activity) - set(id_map):
            raise ValidationError("snapshot.activity", "activity for unknown ref")
        activity = {ref: ActivitySignals.from_dict(v, f"snapshot.activity.{ref}")
                    for ref, v in raw_activity.items()}
        return FormationSnapshot(answers, dict(id_map), tuple((a, b) for a, b in pairs), activity)

    @property
    def refs(self) -> tuple[str, ...]:
        return tuple(sorted({a.id for a in self.answers}))

    def blocked_ref_pairs(self) -> tuple[tuple[str, str], ...]:
        player_to_ref = {p: r for r, p in self.id_map.items()}
        out = []
        for a, b in self.blocked_pairs:
            if a in player_to_ref and b in player_to_ref:
                out.append(tuple(sorted((player_to_ref[a], player_to_ref[b]))))
        return tuple(sorted(set(out)))


@dataclass(frozen=True)
class MuseCallEvidence:
    call_type: str
    model: str
    source: str
    generated_at: str
    latency_ms: int

    @staticmethod
    def from_dict(data: Any) -> MuseCallEvidence:
        if not isinstance(data, Mapping):
            raise ValidationError("evidence", "expected object")
        call_type = data.get("callType")
        source = data.get("source")
        latency = data.get("latencyMs")
        if call_type not in MUSE_CALL_TYPES:
            raise ValidationError("evidence.callType", "unknown call type")
        if source not in EVIDENCE_SOURCES:
            raise ValidationError("evidence.source", "expected live or replay")
        if isinstance(latency, bool) or not isinstance(latency, (int, float)) or latency < 0:
            raise ValidationError("evidence.latencyMs", "expected non-negative number")
        return MuseCallEvidence(call_type, _require_str(data, "model", "evidence", max_len=80),
                                source, _require_str(data, "generatedAt", "evidence", max_len=40),
                                int(latency))

    def to_wire(self) -> dict:
        return {"callType": self.call_type, "model": self.model, "source": self.source,
                "generatedAt": self.generated_at, "latencyMs": self.latency_ms}


@dataclass(frozen=True)
class Theme:
    theme_id: str
    cycle_id: str
    label: str
    description: str
    member_ids: tuple[str, ...]  # playerIds, PRIVATE
    weighted_support: float

    def to_wire(self) -> dict:
        return {"themeId": self.theme_id, "cycleId": self.cycle_id, "label": self.label,
                "description": self.description, "memberIds": list(self.member_ids),
                "weightedSupport": self.weighted_support}


@dataclass(frozen=True)
class Constellation:
    constellation_id: str
    cycle_id: str
    member_ids: tuple[str, ...]  # playerIds, PRIVATE
    shared_meaning: str  # PRIVATE
    confidence: float
    is_loose_match: bool
    name: str
    shape_id: str
    color_id: str
    baseline_agrees: bool
    is_fallback: bool = False  # UI label FALLBACK_LABEL when true
    # D009, PRIVATE: (playerA, playerB, score 0..1) for every member pair; banded before output.
    closeness: tuple[tuple[str, str, float], ...] = ()
    # D010, PRIVATE: playerId -> {sharedGroupStars, alreadyFriends, sameEventStars}; served only to that member.
    member_context: Mapping[str, Mapping[str, int]] = field(default_factory=dict)

    def to_wire(self) -> dict:
        out = {"constellationId": self.constellation_id, "cycleId": self.cycle_id,
               "memberIds": list(self.member_ids), "sharedMeaning": self.shared_meaning,
               "confidence": self.confidence, "isLooseMatch": self.is_loose_match,
               "name": self.name, "shapeId": self.shape_id, "colorId": self.color_id,
               "baselineAgrees": self.baseline_agrees}
        if self.closeness:
            out["closeness"] = [{"a": a, "b": b, "score": s} for a, b, s in self.closeness]
        if self.member_context:
            out["memberContext"] = {k: dict(v) for k, v in self.member_context.items()}
        return out


@dataclass(frozen=True)
class FormationResult:
    status: str  # "ok" | "failed"
    constellations: tuple[Constellation, ...] = ()
    themes: tuple[Theme, ...] = ()
    evidence: tuple[MuseCallEvidence, ...] = ()
    used_fallback: bool = False
    repaired_groups: int = 0  # internal: groups code fixed after a near-valid M4 proposal
    debug: Mapping[str, Any] | None = None  # internal, operator only: ids-only baseline vs Muse
    error: MatchingError | None = None
    timings_ms: Mapping[str, int] = field(default_factory=dict)

    def to_wire(self, request_id: str) -> dict:
        if self.status == "ok":
            return {"status": "ok",
                    "constellations": [c.to_wire() for c in self.constellations],
                    "evidence": [e.to_wire() for e in self.evidence]}
        assert self.error is not None
        return {"status": "failed", "error": self.error.to_wire(request_id)}


def pair(a: str, b: str) -> tuple[str, str]:
    return (a, b) if a <= b else (b, a)


def unique_sorted(items: Sequence[str]) -> tuple[str, ...]:
    return tuple(sorted(set(items)))
