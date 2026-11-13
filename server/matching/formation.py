"""FormationService: semantic constellation formation for one locked weekly cycle.

Pipeline: authorized snapshot -> keyword baseline -> M3 themes -> M4 constellations
(validated, one re-solve) -> deterministic "Fallback grouping" if still invalid ->
M5 names in parallel (guarded) -> Constellation objects with private ids remapped.
Muse proposes; this module decides. Nothing here persists; orchestration (Kai) commits.
"""
from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from server.matching import prompts
from server.matching.baseline import baseline_groups, same_group
from server.matching.models import (
    COLOR_IDS,
    LOOSE_MATCH_CONFIDENCE,
    SHAPES_BY_SIZE,
    Constellation,
    FormationResult,
    FormationSnapshot,
    MatchingError,
    MuseCallEvidence,
    Theme,
    ValidationError,
)
from server.matching.ports import MusePortLike, OutputGuardLike, SnapshotSource
from server.matching.validation import violations

DEFAULT_TIMEOUT_S = 45.0
M4_ATTEMPTS = 2  # first proposal + one re-solve
FALLBACK_MEANING = "Grouped by shared keywords (Fallback grouping)"
FALLBACK_CONFIDENCE = 0.0


@dataclass(frozen=True)
class _Call:
    output: Any
    evidence: MuseCallEvidence


def _fallback_name(index: int, size: int) -> tuple[str, str, str]:
    color = COLOR_IDS[index % len(COLOR_IDS)]
    shape = SHAPES_BY_SIZE[size][index % len(SHAPES_BY_SIZE[size])]
    return f"The {color.capitalize()} {shape.split('-')[0].capitalize()}", shape, color


class FormationService:
    def __init__(self, muse: MusePortLike, snapshots: SnapshotSource, guard: OutputGuardLike,
                 *, timeout_s: float = DEFAULT_TIMEOUT_S, allow_fallback: bool = True,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self._muse = muse
        self._snapshots = snapshots
        self._guard = guard
        self._timeout_s = timeout_s
        self._allow_fallback = allow_fallback
        self._clock = clock

    # ------------------------------------------------------------ Muse calls

    async def _call(self, task: str, prompt_version: str, payload: dict,
                    request_id: str) -> _Call:
        response = await asyncio.wait_for(
            self._muse.run(task=task, requestId=request_id, promptVersion=prompt_version,
                           payload=payload),
            timeout=self._timeout_s)
        if not isinstance(response, Mapping) or set(response) != {"output", "evidence"}:
            raise ValidationError("response", "expected output and evidence")
        return _Call(response["output"], MuseCallEvidence.from_dict(response["evidence"]))

    async def _try(self, attempt: Callable[[], Awaitable[Any]],
                   evidence: list[MuseCallEvidence], parse: Callable[[Any], Any],
                   attempts: int) -> Any | None:
        """Run a Muse call up to `attempts` times; return parsed output or None.

        Provider and validation failures are retried and never logged with payloads.
        """
        for _ in range(attempts):
            try:
                call = await attempt()
            except Exception:  # noqa: BLE001 - any provider failure counts as one attempt
                continue
            evidence.append(call.evidence)
            try:
                return parse(call.output)
            except ValidationError:
                continue
        return None

    # ------------------------------------------------------------ steps

    async def _themes(self, snap: FormationSnapshot, request_id: str,
                      evidence: list[MuseCallEvidence]) -> tuple[prompts.RawTheme, ...]:
        known = set(snap.refs)
        payload = prompts.build_m3_payload(snap.answers)
        parsed = await self._try(
            lambda: self._call("theme_discovery", prompts.PROMPT_VERSION_M3, payload,
                               f"{request_id}:m3"),
            evidence, lambda out: prompts.parse_m3(out, known), attempts=2)
        return parsed or ()

    async def _groups(self, snap: FormationSnapshot, themes: Sequence[prompts.RawTheme],
                      request_id: str, evidence: list[MuseCallEvidence]
                      ) -> tuple[prompts.RawConstellation, ...] | None:
        known = set(snap.refs)
        blocked = snap.blocked_ref_pairs()
        payload = prompts.build_m4_payload(themes, snap.answers, blocked)

        def parse(out: Any) -> tuple[prompts.RawConstellation, ...]:
            proposal = prompts.parse_m4(out, known)
            problems = violations([c[0] for c in proposal], known, blocked)
            if problems:
                raise ValidationError("output.constellations", ",".join(problems))
            return proposal

        return await self._try(
            lambda: self._call("constellation_formation", prompts.PROMPT_VERSION_M4,
                               payload, f"{request_id}:m4"),
            evidence, parse, attempts=M4_ATTEMPTS)

    async def _name(self, index: int, meaning: str, size: int, answer_texts: Sequence[str],
                    request_id: str, evidence: list[MuseCallEvidence]
                    ) -> tuple[str, str, str]:
        payload = prompts.build_m5_payload(meaning, size)

        def parse(out: Any) -> tuple[str, str, str]:
            name, shape, color = prompts.parse_m5(out, size)
            verdict = self._guard.check(name, answer_texts)
            if not isinstance(verdict, Mapping) or verdict.get("ok") is not True:
                raise ValidationError("output.name", "rejected by OutputGuard")
            return name, shape, color

        local: list[MuseCallEvidence] = []
        named = await self._try(
            lambda: self._call("constellation_naming", prompts.PROMPT_VERSION_M5, payload,
                               f"{request_id}:m5:{index}"),
            local, parse, attempts=2)
        evidence.extend(local)
        return named or _fallback_name(index, size)

    # ------------------------------------------------------------ public

    async def form(self, cycle_id: str, request_id: str) -> FormationResult:
        started = self._clock()
        timings: dict[str, int] = {}
        try:
            snap = FormationSnapshot.from_dict(await self._snapshots.formation_snapshot(cycle_id))
            baseline = baseline_groups(snap.answers, snap.blocked_ref_pairs())
        except ValidationError:
            return FormationResult("failed", error=MatchingError(
                "INVALID_INPUT", "Formation snapshot invalid", retryable=False))
        except MatchingError as exc:
            return FormationResult("failed", error=exc)
        timings["baselineMs"] = int((self._clock() - started) * 1000)

        evidence: list[MuseCallEvidence] = []
        themes = await self._themes(snap, request_id, evidence)
        timings["m3Ms"] = int((self._clock() - started) * 1000)
        proposal = await self._groups(snap, themes, request_id, evidence)
        timings["m4Ms"] = int((self._clock() - started) * 1000)

        used_fallback = proposal is None
        if used_fallback:
            if not self._allow_fallback:
                return FormationResult("failed", evidence=tuple(evidence), error=MatchingError(
                    "PROVIDER_UNAVAILABLE", "Formation unavailable; retry", retryable=True))
            proposal = tuple((g, FALLBACK_MEANING, FALLBACK_CONFIDENCE) for g in baseline)

        answer_texts = [a.text for a in snap.answers]
        names = await asyncio.gather(*(
            self._name(i, meaning, len(refs), answer_texts, request_id, evidence)
            for i, (refs, meaning, _) in enumerate(proposal)))
        timings["totalMs"] = int((self._clock() - started) * 1000)

        constellations = tuple(
            Constellation(
                constellation_id=f"{cycle_id}-c{i + 1}", cycle_id=cycle_id,
                member_ids=tuple(sorted(snap.id_map[r] for r in refs)),
                shared_meaning=meaning, confidence=confidence,
                is_loose_match=used_fallback or confidence < LOOSE_MATCH_CONFIDENCE,
                name=name, shape_id=shape, color_id=color,
                baseline_agrees=same_group(baseline, refs), is_fallback=used_fallback)
            for i, ((refs, meaning, confidence), (name, shape, color))
            in enumerate(zip(proposal, names, strict=False)))
        weight_by_ref: dict[str, float] = {}
        for a in snap.answers:
            weight_by_ref[a.id] = weight_by_ref.get(a.id, 0.0) + a.weight
        theme_objs = tuple(
            Theme(theme_id=f"{cycle_id}-t{i + 1}", cycle_id=cycle_id, label=label,
                  description=desc, member_ids=tuple(sorted(snap.id_map[r] for r in refs)),
                  weighted_support=round(sum(weight_by_ref.get(r, 0.0) for r in refs), 3))
            for i, (_, label, desc, refs) in enumerate(themes))
        return FormationResult("ok", constellations=constellations, themes=theme_objs,
                               evidence=tuple(evidence), used_fallback=used_fallback,
                               timings_ms=timings)
