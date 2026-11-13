"""FormationService: semantic constellation formation for one locked weekly cycle.

Pipeline: authorized snapshot -> keyword baseline -> M3 themes -> M4 constellations
(validated, one re-solve) -> deterministic "Fallback grouping" if still invalid ->
M5 names in parallel (guarded) -> Constellation objects with private ids remapped.
Muse proposes; this module decides. Nothing here persists; orchestration (Kai) commits.
"""
from __future__ import annotations

import asyncio
import contextvars
import inspect
import time
import uuid
from collections.abc import Awaitable, Callable, Collection, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from server.matching import prompts
from server.matching.baseline import (
    Similarity,
    baseline_groups,
    same_group,
    similarity_matrix,
)
from server.matching.closeness import affinity_pairs, member_context, pair_closeness
from server.matching.models import (
    COLOR_IDS,
    FALLBACK_LABEL,
    LOOSE_MATCH_CONFIDENCE,
    MAX_NAME_CHARS,
    shapes_for,
    Constellation,
    FormationResult,
    FormationSnapshot,
    MatchingError,
    MuseCallEvidence,
    Theme,
    ValidationError,
)
from server.matching.ports import MusePortLike, OutputGuardLike, SnapshotSource
from server.matching.repair import repair_proposal
from server.matching.sampling import sample_for_muse
from server.matching.sky import formation_debug
from server.matching.validation import violations

# Live muse-spark-1.3 (Adam, 2026-11-13, 30 players): M3 21.5 s, M4 38.8 s, M5 10-25 s with
# intermittent hangs. Timeouts sit above observed latency; naming has a safe fixed fallback,
# so it gets one short attempt instead of a retry.
DEFAULT_TIMEOUT_S = 75.0
NAME_TIMEOUT_S = 20.0
NAME_ATTEMPTS = 1
M3_ATTEMPTS = 1  # themes feed Sky only when run in parallel; never worth a second wait
M4_ATTEMPTS = 2  # first proposal + one re-solve
FALLBACK_MEANING = "Grouped by shared keywords (Fallback grouping)"
FALLBACK_CONFIDENCE = 0.0
FALLBACK_SUFFIX = f" ({FALLBACK_LABEL})"
# sharedMeaning is private but feeds M5 naming and M7 nudges, so a meaning that quotes an
# answer or carries a sensitive term is replaced by this fixed text before it goes anywhere.
NEUTRAL_MEANING = "Answers that share a similar feeling this week"


GroupedHook = Callable[[tuple[Theme, ...], int, int], Awaitable[Any]]


async def _run_hook(hook: GroupedHook | None, themes: tuple[Theme, ...], eligible: int,
                    constellations: int) -> None:
    """Sky precompute; isolated so its failure never fails formation."""
    if hook is None:
        return
    try:
        await hook(themes, eligible, constellations)
    except Exception:  # noqa: BLE001 - Sky is recomputed on demand if precompute failed
        return


@dataclass(frozen=True)
class _Call:
    output: Any
    evidence: MuseCallEvidence


# Absolute clock time by which this formation must finish (None = no budget). Set in form(); read
# by _call so every Muse call gets the REMAINING time as deadline_s (audit #72), keeping a reserve
# for the code-only keyword fallback. A ContextVar keeps gather() tasks and forms apart.
_FORMATION_DEADLINE: contextvars.ContextVar[float | None] = contextvars.ContextVar(
    "formation_deadline", default=None)
FALLBACK_RESERVE_S = 3.0
MIN_CALL_BUDGET_S = 1.0


def _accepts_kwarg(muse: Any, name: str) -> bool:
    try:
        params = inspect.signature(muse.run).parameters
    except (TypeError, ValueError, AttributeError):
        return False
    return name in params or any(p.kind is inspect.Parameter.VAR_KEYWORD for p in params.values())


def _accepts_correction(muse: Any) -> bool:
    """True when muse.run takes `correction=` (KeywordMusePort does; older fakes do not)."""
    try:
        params = inspect.signature(muse.run).parameters
    except (TypeError, ValueError, AttributeError):
        return False
    return "correction" in params or any(
        p.kind is inspect.Parameter.VAR_KEYWORD for p in params.values())


def _fallback_name(index: int, size: int) -> tuple[str, str, str]:
    color = COLOR_IDS[index % len(COLOR_IDS)]
    shape = shapes_for(size)[index % len(shapes_for(size))]
    return f"The {color.capitalize()} {shape.split('-')[0].capitalize()}", shape, color


def _fallback_grouping_name(index: int, size: int) -> tuple[str, str, str]:
    """Name for a Fallback grouping constellation: '<Color> <Shape> (Fallback grouping)'.

    isFallback is not a wire field (protocol.ts 2.0.0), so the label rides in the name.
    """
    color = COLOR_IDS[index % len(COLOR_IDS)]
    shape = shapes_for(size)[index % len(shapes_for(size))]
    base = f"{color.capitalize()} {shape.split('-')[0].capitalize()}"
    base = base[:MAX_NAME_CHARS - len(FALLBACK_SUFFIX)].rstrip()
    return f"{base}{FALLBACK_SUFFIX}", shape, color


class FormationService:
    def __init__(self, muse: MusePortLike, snapshots: SnapshotSource, guard: OutputGuardLike,
                 *, timeout_s: float = DEFAULT_TIMEOUT_S, allow_fallback: bool = True,
                 parallel_themes: bool = True, name_timeout_s: float = NAME_TIMEOUT_S,
                 approved_event_ids: Collection[str] = (), budget_s: float | None = None,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self._muse = muse
        self._sends_correction = _accepts_correction(muse)
        self._sends_deadline = _accepts_kwarg(muse, "deadline_s")
        # Adam's venue catalog event ids; only these count toward M4 affinity.
        self._approved_event_ids = frozenset(approved_event_ids)
        self._snapshots = snapshots
        self._guard = guard
        self._timeout_s = timeout_s
        self._allow_fallback = allow_fallback
        self._parallel_themes = parallel_themes
        self._name_timeout_s = name_timeout_s
        self._clock = clock
        self._budget_s = budget_s

    # ------------------------------------------------------------ Muse calls

    async def _call(self, task: str, prompt_version: str, payload: dict,
                    request_id: str, timeout_s: float | None = None,
                    correction: str | None = None) -> _Call:
        extra: dict[str, Any] = (
            {"correction": correction} if correction and self._sends_correction else {})
        cap = timeout_s or self._timeout_s
        absolute = _FORMATION_DEADLINE.get()
        if absolute is not None:
            remaining = absolute - self._clock() - FALLBACK_RESERVE_S
            if remaining < MIN_CALL_BUDGET_S:
                raise TimeoutError  # out of budget: caller falls back to keyword grouping
            cap = min(cap, remaining)
        if self._sends_deadline:
            extra["deadline_s"] = cap
        response = await asyncio.wait_for(
            self._muse.run(task=task, requestId=request_id, promptVersion=prompt_version,
                           payload=payload, **extra),
            timeout=cap)
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
        payload = prompts.build_m3_payload(snap.answers, snap.questions)
        parsed = await self._try(
            lambda: self._call("theme_discovery", prompts.PROMPT_VERSION_M3, payload,
                               f"{request_id}:m3"),
            evidence, lambda out: prompts.parse_m3(out, known), attempts=M3_ATTEMPTS)
        return parsed or ()

    async def _groups(self, snap: FormationSnapshot, themes: Sequence[prompts.RawTheme],
                      request_id: str, evidence: list[MuseCallEvidence], sim: Similarity
                      ) -> tuple[tuple[prompts.RawConstellation, ...], int] | None:
        """M4 with repair. Returns (proposal, repairedGroups) or None.

        Order per attempt: strict parse -> valid? accept -> near-valid? repair and accept ->
        otherwise spend the re-solve attempt, which carries a code-generated `correction`
        (violation kinds, counts and random refs only). Repair keeps Muse's grouping and
        marks touched groups loose (confidence capped).
        """
        known = set(snap.refs)
        blocked = snap.blocked_ref_pairs()
        payload = prompts.build_m4_payload(
            themes, snap.answers, blocked, snap.questions,
            affinity_pairs(snap, self._approved_event_ids))
        correction: str | None = None

        def parse(out: Any) -> tuple[tuple[prompts.RawConstellation, ...], int]:
            nonlocal correction
            try:
                proposal = prompts.parse_m4(out, known, allow_unknown_refs=True)
            except ValidationError:
                correction = prompts.m4_correction((), parse_failed=True)
                raise
            groups = [c[0] for c in proposal]
            codes = violations(groups, known, blocked)
            if not codes:
                return proposal, 0
            fixed = repair_proposal(proposal, sorted(known), blocked, sim)
            if fixed is None:
                placed = {r for g in groups for r in g}
                correction = prompts.m4_correction(
                    codes, unplaced=sorted(known - placed), unknown=len(placed - known))
                raise ValidationError("output.constellations", "not repairable")
            return (tuple(zip(fixed.groups, fixed.meanings, fixed.confidences, strict=False)),
                    sum(fixed.touched))

        return await self._try(
            lambda: self._call("constellation_formation", prompts.PROMPT_VERSION_M4,
                               payload, f"{request_id}:m4", correction=correction),
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
                               f"{request_id}:m5:{index}", self._name_timeout_s),
            local, parse, attempts=NAME_ATTEMPTS)
        evidence.extend(local)
        return named or _fallback_name(index, size)

    def _guarded_fallback_name(self, index: int, size: int,
                               answer_texts: Sequence[str]) -> tuple[str, str, str]:
        name, shape, color = _fallback_grouping_name(index, size)
        verdict = self._guard.check(name, answer_texts)
        if not isinstance(verdict, Mapping) or verdict.get("ok") is not True:
            name = FALLBACK_LABEL  # fixed text; still labeled
        return name, shape, color

    def _guarded_meanings(self, proposal: Sequence[prompts.RawConstellation],
                          answer_texts: Sequence[str]) -> tuple[prompts.RawConstellation, ...]:
        """Replace any sharedMeaning that fails OutputGuard against the answers with fixed
        neutral text. sharedMeaning feeds M5 naming and M7 nudges after this point."""
        out = []
        for refs, meaning, confidence in proposal:
            verdict = self._guard.check(meaning, answer_texts)
            if not isinstance(verdict, Mapping) or verdict.get("ok") is not True:
                meaning = NEUTRAL_MEANING
            out.append((refs, meaning, confidence))
        return tuple(out)

    def _guarded_themes(self, themes: Sequence[prompts.RawTheme],
                        answer_texts: Sequence[str]) -> tuple[prompts.RawTheme, ...]:
        """Drop any M3 theme whose label or description fails OutputGuard against the
        answers. Theme labels reach the public Sky, and Sky runs later without the
        answers, so the no-quote check has to happen here, while they are in hand."""
        kept = []
        for theme in themes:
            _, label, desc, _ = theme
            verdicts = (self._guard.check(label, answer_texts), self._guard.check(desc, answer_texts))
            if all(isinstance(v, Mapping) and v.get("ok") is True for v in verdicts):
                kept.append(theme)
        return tuple(kept)

    @staticmethod
    def _theme_objects(cycle_id: str, snap: FormationSnapshot,
                       themes: Sequence[prompts.RawTheme]) -> tuple[Theme, ...]:
        weight_by_ref: dict[str, float] = {}
        for a in snap.answers:
            weight_by_ref[a.id] = weight_by_ref.get(a.id, 0.0) + a.weight
        return tuple(
            Theme(theme_id=f"{cycle_id}-t{i + 1}", cycle_id=cycle_id, label=label,
                  description=desc, member_ids=tuple(sorted(snap.id_map[r] for r in refs)),
                  weighted_support=round(sum(weight_by_ref.get(r, 0.0) for r in refs), 3))
            for i, (_, label, desc, refs) in enumerate(themes))

    # ------------------------------------------------------------ public

    async def form(self, cycle_id: str, request_id: str | None = None, *,
                   on_grouped: GroupedHook | None = None) -> FormationResult:
        """FormationPort.form(cycleId). request_id is optional (generated when omitted).

        Schedule: M3 and M4 run concurrently (M4 gets no themes; themes feed Sky only) when
        parallel_themes is on, else M3 then M4 with themes. After grouping validates, M5
        naming runs in parallel with `on_grouped` (Sky precompute); a hook failure never
        fails formation.
        """
        request_id = request_id or f"form-{cycle_id}-{uuid.uuid4().hex[:8]}"
        started = self._clock()
        _FORMATION_DEADLINE.set(None if self._budget_s is None else started + self._budget_s)
        timings: dict[str, int] = {}
        try:
            snap = FormationSnapshot.from_dict(await self._snapshots.formation_snapshot(cycle_id))
            sim = similarity_matrix(snap.answers)
            baseline = baseline_groups(snap.answers, snap.blocked_ref_pairs())
        except ValidationError:
            return FormationResult("failed", error=MatchingError(
                "INVALID_INPUT", "Formation snapshot invalid", retryable=False))
        except MatchingError as exc:
            return FormationResult("failed", error=exc)
        timings["baselineMs"] = int((self._clock() - started) * 1000)
        full_snap = snap
        snap, sample_reason = sample_for_muse(full_snap)  # Muse sees a bounded sample; code uses all

        evidence: list[MuseCallEvidence] = []
        if self._parallel_themes:
            m3_evidence: list[MuseCallEvidence] = []
            themes, grouped = await asyncio.gather(
                self._themes(snap, request_id, m3_evidence),
                self._groups(snap, (), request_id, evidence, sim))
            evidence = m3_evidence + evidence
            timings["m3m4Ms"] = int((self._clock() - started) * 1000)
        else:
            themes = await self._themes(snap, request_id, evidence)
            timings["m3Ms"] = int((self._clock() - started) * 1000)
            grouped = await self._groups(snap, themes, request_id, evidence, sim)
            timings["m4Ms"] = int((self._clock() - started) * 1000)

        used_fallback = grouped is None
        proposal, repaired = grouped if grouped is not None else ((), 0)
        if used_fallback:
            if not self._allow_fallback:
                return FormationResult("failed", evidence=tuple(evidence), error=MatchingError(
                    "PROVIDER_UNAVAILABLE", "Formation unavailable; retry", retryable=True))
            proposal = tuple((g, FALLBACK_MEANING, FALLBACK_CONFIDENCE) for g in baseline)

        snap = full_snap  # guards, closeness and context use every answer
        answer_texts = [a.text for a in snap.answers]
        proposal = self._guarded_meanings(proposal, answer_texts)
        themes = self._guarded_themes(themes, answer_texts)
        theme_objs = self._theme_objects(cycle_id, snap, themes)
        hook = asyncio.ensure_future(_run_hook(on_grouped, theme_objs, len(snap.refs),
                                               len(proposal)))
        if used_fallback:
            names = [self._guarded_fallback_name(i, len(refs), answer_texts)
                     for i, (refs, _, _) in enumerate(proposal)]
        else:
            names = await asyncio.gather(*(
                self._name(i, meaning, len(refs), answer_texts, request_id, evidence)
                for i, (refs, meaning, _) in enumerate(proposal)))
        timings["namesMs"] = int((self._clock() - started) * 1000)
        await hook
        timings["totalMs"] = int((self._clock() - started) * 1000)

        constellations = tuple(
            Constellation(
                constellation_id=f"{cycle_id}-c{i + 1}", cycle_id=cycle_id,
                member_ids=tuple(sorted(snap.id_map[r] for r in refs)),
                shared_meaning=meaning, confidence=confidence,
                is_loose_match=used_fallback or confidence < LOOSE_MATCH_CONFIDENCE,
                name=name, shape_id=shape, color_id=color,
                baseline_agrees=same_group(baseline, refs), is_fallback=used_fallback,
                closeness=pair_closeness(snap, refs), member_context=member_context(snap, refs))
            for i, ((refs, meaning, confidence), (name, shape, color))
            in enumerate(zip(proposal, names, strict=False)))
        debug = formation_debug([tuple(refs) for refs, _, _ in proposal], baseline)
        if sample_reason:
            debug = {**debug, "reason": sample_reason}  # operator-only, no ids or text
        return FormationResult("ok", constellations=constellations, themes=theme_objs,
                               evidence=tuple(evidence), used_fallback=used_fallback,
                               repaired_groups=repaired, debug=debug,
                               timings_ms=timings)
