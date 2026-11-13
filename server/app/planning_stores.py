"""Private planning persistence and staged formation results for orchestration.

Selections and follow-up decisions use the configured workflow repository; these
stores do not accept answer text, provider payloads or prompts. Formation staging
is deliberately memory-only until the caller holds cycle + privacy guards and
persists ``dump_matching_result`` in its short workflow transaction.
"""

import threading
from copy import deepcopy
from datetime import date
from typing import Annotated, Literal

from pydantic import Field, ValidationError, field_validator, model_validator

from server.app.errors import ServiceError
from server.cycle.wire import M2Out
from server.matching.models import (
    FALLBACK_LABEL,
    FormationResult,
    MatchingError,
    Theme,
)
from server.matching.models import (
    Constellation as MatchingConstellation,
)
from server.matching.models import (
    MuseCallEvidence as MatchingEvidence,
)
from server.orchestration.storage import WorkflowRepository
from server.orchestration.wire import (
    FormationFailure,
    FormationSuccess,
    MuseCallEvidence,
    NonNegative,
    Text,
    Wire,
)
from server.planning import ClarifyResult, validate_question


class _Selection(Wire):
    cycleId: Text
    communityId: Text
    weekStart: str
    questionIds: Annotated[list[Text], Field(min_length=5, max_length=5)]
    questions: Annotated[list[dict], Field(min_length=5, max_length=5)]

    @field_validator("questions")
    @classmethod
    def valid_questions(cls, questions):
        return [validate_question(question) for question in questions]

    @model_validator(mode="after")
    def week(self):
        monday = date.fromisoformat(self.weekStart)
        if monday.isoformat() != self.weekStart or monday.weekday() != 0:
            raise ValueError("invalid selected week")
        if self.questionIds != [question["questionId"] for question in self.questions]:
            raise ValueError("invalid question lineage")
        if len(set(self.questionIds)) != 5 or not all(q["active"] for q in self.questions):
            raise ValueError("invalid selected questions")
        return self


def _selection(cycle_id, value) -> dict:
    try:
        selected = _Selection.model_validate(value)
        if selected.cycleId != cycle_id:
            raise ValueError("invalid selection cycle")
        return selected.model_dump(mode="json")
    except (TypeError, ValueError):
        raise ServiceError("INVALID_INPUT") from None


class DurableSelectionStore:
    """Adam's SelectionStore; selected weeks are immutable snapshots once stored."""

    def __init__(self, repository: WorkflowRepository):
        self.repository = repository

    def get(self, cycle_id: str) -> dict | None:
        with self.repository.transaction() as state:
            value = state.records.get("questionSelections", {}).get(cycle_id)
            if value is None:
                return None
            try:
                return _selection(cycle_id, value)
            except ServiceError:
                raise ServiceError("PROVIDER_UNAVAILABLE") from None

    def put(self, cycle_id: str, record: dict) -> None:
        selected = _selection(cycle_id, record)
        with self.repository.transaction() as state:
            rows = state.records.setdefault("questionSelections", {})
            existing = rows.get(cycle_id)
            if existing is not None and not isinstance(existing, dict):
                raise ServiceError("PROVIDER_UNAVAILABLE")
            if existing is not None and existing != selected:
                code = (
                    "NOT_FOUND"
                    if existing.get("communityId") != selected["communityId"]
                    else ("STALE_REVISION")
                )
                raise ServiceError(code)
            rows[cycle_id] = selected

    def recent(self, community_id: str, limit: int, exclude_cycle_id: str) -> list[dict]:
        if type(limit) is not int or limit < 0:
            raise ServiceError("INVALID_INPUT")
        if limit == 0:
            return []
        with self.repository.transaction() as state:
            selected = []
            for cycle_id, row in state.records.get("questionSelections", {}).items():
                if not isinstance(row, dict):
                    raise ServiceError("PROVIDER_UNAVAILABLE")
                if cycle_id != exclude_cycle_id and row.get("communityId") == community_id:
                    try:
                        selected.append(_selection(cycle_id, row))
                    except ServiceError:
                        raise ServiceError("PROVIDER_UNAVAILABLE") from None
            selected.sort(key=lambda row: (row["weekStart"], row["cycleId"]))
            return selected[-limit:]


class _ClarifyDecision(Wire):
    output: M2Out
    source: Literal["muse", "fallback", "none"]
    evidence: MuseCallEvidence | None

    @model_validator(mode="after")
    def decision(self):
        if self.output.needsFollowup:
            if not self.output.question.strip() or len(self.output.question) > 140:
                raise ValueError("invalid follow-up")
            if self.source == "none":
                raise ValueError("invalid no-follow-up source")
        elif self.output.question != "":
            raise ValueError("unexpected no-follow-up text")
        if self.source == "muse":
            if self.evidence is None or self.evidence.callType != "M2":
                raise ValueError("missing M2 evidence")
        elif self.evidence is not None:
            raise ValueError("invented fallback evidence")
        return self


def _clarify_document(result: ClarifyResult) -> dict:
    try:
        if not isinstance(result, ClarifyResult):
            raise TypeError("invalid decision")
        return _ClarifyDecision.model_validate(
            {"output": result.output, "source": result.source, "evidence": result.evidence}
        ).model_dump(mode="json")
    except (TypeError, ValueError):
        raise ServiceError("INVALID_INPUT") from None


class DurableClarifyStore:
    """Adam's ClarifyStore, with one immutable decision per private answer ID."""

    def __init__(self, repository: WorkflowRepository):
        self.repository = repository

    def get(self, answer_id: str) -> ClarifyResult | None:
        with self.repository.transaction() as state:
            value = state.records.get("clarifyDecisions", {}).get(answer_id)
            if value is None:
                return None
            try:
                decision = _ClarifyDecision.model_validate(value)
                evidence = decision.evidence.model_dump(mode="json") if decision.evidence else None
                return ClarifyResult(
                    decision.output.model_dump(mode="json"), decision.source, evidence
                )
            except (TypeError, ValueError):
                raise ServiceError("PROVIDER_UNAVAILABLE") from None

    def put(self, answer_id: str, result: ClarifyResult) -> None:
        if not isinstance(answer_id, str) or not answer_id.strip():
            raise ServiceError("INVALID_INPUT")
        value = _clarify_document(result)
        with self.repository.transaction() as state:
            decisions = state.records.setdefault("clarifyDecisions", {})
            if answer_id in decisions and decisions[answer_id] != value:
                raise ServiceError("STALE_REVISION")
            decisions[answer_id] = value


class _PrivateTheme(Wire):
    themeId: Text
    cycleId: Text
    label: Text
    description: str
    memberIds: list[Text]
    weightedSupport: Annotated[float, Field(ge=0)]


class _PrivateFormation(Wire):
    wire: Annotated[FormationSuccess | FormationFailure, Field(discriminator="status")]
    themes: list[_PrivateTheme]
    evidence: list[MuseCallEvidence]
    usedFallback: bool
    repairedGroups: NonNegative
    timingsMs: dict[Text, NonNegative]
    fallbackConstellationIds: list[Text]

    @model_validator(mode="after")
    def lineage(self):
        if self.wire.status == "failed":
            if self.themes or self.fallbackConstellationIds:
                raise ValueError("private success fields on failed formation")
            return self
        if self.evidence != self.wire.evidence:
            raise ValueError("inconsistent evidence")
        constellations = self.wire.constellations
        ids = {constellation.constellationId for constellation in constellations}
        cycles = {constellation.cycleId for constellation in constellations}
        members = [player for constellation in constellations for player in constellation.memberIds]
        if len(ids) != len(constellations) or len(cycles) > 1 or len(set(members)) != len(members):
            raise ValueError("invalid private formation lineage")
        fallback = self.fallbackConstellationIds
        if len(set(fallback)) != len(fallback) or not set(fallback) <= ids:
            raise ValueError("invalid fallback references")
        for constellation in constellations:
            if constellation.constellationId in fallback and (
                not constellation.isLooseMatch or FALLBACK_LABEL not in constellation.name
            ):
                raise ValueError("missing public fallback label")
        if len({theme.themeId for theme in self.themes}) != len(self.themes):
            raise ValueError("invalid duplicate theme")
        for theme in self.themes:
            if theme.cycleId not in cycles or not set(theme.memberIds) <= set(members):
                raise ValueError("invalid private theme lineage")
            if len(set(theme.memberIds)) != len(theme.memberIds):
                raise ValueError("invalid duplicate theme member")
        return self


def dump_matching_result(result: FormationResult) -> dict:
    """Private format only. Persist it solely inside an authorized guarded commit."""
    try:
        if not isinstance(result, FormationResult):
            raise TypeError("invalid formation result")
        value = {
            "wire": result.to_wire("stored-formation"),
            "themes": [theme.to_wire() for theme in result.themes],
            "evidence": [evidence.to_wire() for evidence in result.evidence],
            "usedFallback": result.used_fallback,
            "repairedGroups": result.repaired_groups,
            "timingsMs": dict(result.timings_ms),
            "fallbackConstellationIds": [
                constellation.constellation_id
                for constellation in result.constellations
                if constellation.is_fallback
            ],
        }
        return _PrivateFormation.model_validate(value).model_dump(mode="json")
    except (AssertionError, AttributeError, TypeError, ValueError):
        raise ServiceError("INVALID_INPUT") from None


def load_matching_result(value: dict) -> FormationResult:
    """Validate a saved private format, then reconstruct Rishi's public dataclasses."""
    try:
        saved = _PrivateFormation.model_validate(value)
        evidence = tuple(
            MatchingEvidence.from_dict(e.model_dump(mode="json")) for e in saved.evidence
        )
        if saved.wire.status == "failed":
            error = saved.wire.error
            return FormationResult(
                "failed",
                evidence=evidence,
                used_fallback=saved.usedFallback,
                repaired_groups=saved.repairedGroups,
                error=MatchingError(error.code, error.message, retryable=error.retryable),
                timings_ms=dict(saved.timingsMs),
            )
        fallback = set(saved.fallbackConstellationIds)
        constellations = tuple(
            MatchingConstellation(
                constellation_id=c.constellationId,
                cycle_id=c.cycleId,
                member_ids=tuple(c.memberIds),
                shared_meaning=c.sharedMeaning,
                confidence=c.confidence,
                is_loose_match=c.isLooseMatch,
                name=c.name,
                shape_id=c.shapeId,
                color_id=c.colorId,
                baseline_agrees=c.baselineAgrees,
                is_fallback=c.constellationId in fallback,
            )
            for c in saved.wire.constellations
        )
        themes = tuple(
            Theme(
                t.themeId, t.cycleId, t.label, t.description, tuple(t.memberIds), t.weightedSupport
            )
            for t in saved.themes
        )
        return FormationResult(
            "ok",
            constellations=constellations,
            themes=themes,
            evidence=evidence,
            used_fallback=saved.usedFallback,
            repaired_groups=saved.repairedGroups,
            timings_ms=dict(saved.timingsMs),
        )
    except (TypeError, ValueError, ValidationError):
        raise ServiceError("PROVIDER_UNAVAILABLE") from None


class StagedThemeStore:
    """Rishi's ThemeStore without premature persistence/publication side effects.

    Use a fresh stage for each leased formation job. Save/load copies are isolated;
    only the root orchestration commit may copy a validated result into PostgreSQL.
    """

    def __init__(self):
        self._results: dict[str, dict] = {}
        self._lock = threading.RLock()

    def save(self, cycle_id: str, result: FormationResult) -> None:
        value = dump_matching_result(result)
        if result.status == "ok" and any(c.cycle_id != cycle_id for c in result.constellations):
            raise ServiceError("INVALID_INPUT")
        with self._lock:
            self._results[cycle_id] = value

    def load(self, cycle_id: str) -> FormationResult | None:
        with self._lock:
            value = self._results.get(cycle_id)
            return load_matching_result(deepcopy(value)) if value is not None else None
