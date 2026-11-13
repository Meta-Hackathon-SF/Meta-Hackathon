"""SkyStats: thresholded prevalence (guessed vs actual) plus checked M8 narration.

Code computes every number. Muse (M8) only writes headlines from counts, and every number
in a headline must equal a number the server sent. Themes below threshold never leave this
module except as a count. Synthetic signals are labeled and never merged into real counts.
"""
from __future__ import annotations

import asyncio
import random
import re
import statistics
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from server.matching.models import (
    FormationResult,
    MatchingError,
    MuseCallEvidence,
    Theme,
    ValidationError,
)
from server.matching.ports import MusePortLike, OutputGuardLike
from server.matching.prompts import load_object

PROMPT_VERSION_M8 = "sky_narration.v1"
M8_INSTRUCTIONS = (
    "You are Muse. Write 1-3 short headlines (max 140 chars each) for a community's weekly "
    "Sky from these counts only. Contrast what people guessed with what was true, warmly. "
    "Use only numbers given; never invent or round numbers. Return strict JSON {headlines}."
)
MAX_HEADLINES = 3
MAX_HEADLINE_CHARS = 140
M8_ATTEMPTS = 2
DEFAULT_TIMEOUT_S = 45.0
SYNTHETIC_LABEL = "Synthetic signal"
_NUMBER_RE = re.compile(r"\d+(?:\.\d+)?")


@dataclass(frozen=True)
class SkyTheme:
    theme_id: str
    label: str
    count: int
    actual_percent: int
    guessed_percent_median: int

    def to_wire(self) -> dict:
        return {"themeId": self.theme_id, "label": self.label, "count": self.count,
                "actualPercent": self.actual_percent,
                "guessedPercentMedian": self.guessed_percent_median}


@dataclass(frozen=True)
class SyntheticSignal:
    signal_id: str
    label: str
    percent: int
    sample_size: int

    def to_wire(self) -> dict:
        return {"signalId": self.signal_id, "label": self.label, "percent": self.percent,
                "sampleSize": self.sample_size, "source": "synthetic"}


@dataclass(frozen=True)
class SkyStats:
    cycle_id: str
    threshold: int
    eligible_players: int
    constellations: int
    mutual_reveals: int
    themes: tuple[SkyTheme, ...]
    suppressed_themes: int
    headlines: tuple[str, ...]
    synthetic_signals: tuple[SyntheticSignal, ...]
    evidence: tuple[MuseCallEvidence, ...]

    def to_wire(self) -> dict:
        return {"cycleId": self.cycle_id, "threshold": self.threshold,
                "eligiblePlayers": self.eligible_players,
                "constellations": self.constellations, "mutualReveals": self.mutual_reveals,
                "themes": [t.to_wire() for t in self.themes],
                "suppressedThemes": self.suppressed_themes,
                "headlines": list(self.headlines),
                "syntheticSignals": [s.to_wire() for s in self.synthetic_signals],
                "evidence": [e.to_wire() for e in self.evidence]}


# ---------------------------------------------------------------- pure computation

def validate_guesses(guesses: Mapping[str, Any]) -> dict[str, int]:
    out: dict[str, int] = {}
    for player_id, value in guesses.items():
        if not isinstance(player_id, str) or isinstance(value, bool) \
                or not isinstance(value, int) or not 0 <= value <= 100:
            raise ValidationError("guesses", "expected integer percent 0-100 per player")
        out[player_id] = value
    return out


def _guard_ok(guard: OutputGuardLike, text: str, answers: Sequence[str]) -> bool:
    verdict = guard.check(text, answers)
    return isinstance(verdict, Mapping) and verdict.get("ok") is True


def compute_themes(themes: Sequence[Theme], guesses: Mapping[str, int], eligible: int,
                   threshold: int, guard: OutputGuardLike,
                   answer_texts: Sequence[str] = ()) -> tuple[tuple[SkyTheme, ...], int]:
    """Return (visible themes, suppressed count). Suppressed = below threshold, no member
    guesses, or label rejected by OutputGuard. Labels of suppressed themes never escape."""
    if threshold < 1:
        raise ValidationError("threshold", "expected >= 1")
    if eligible < 1:
        raise ValidationError("eligiblePlayers", "expected >= 1")
    visible: list[SkyTheme] = []
    suppressed = 0
    for theme in themes:
        count = len(set(theme.member_ids))
        member_guesses = [guesses[p] for p in theme.member_ids if p in guesses]
        if count < threshold or not member_guesses or count > eligible \
                or not _guard_ok(guard, theme.label, answer_texts):
            suppressed += 1
            continue
        visible.append(SkyTheme(
            theme_id=theme.theme_id, label=theme.label, count=count,
            actual_percent=round(100 * count / eligible),
            guessed_percent_median=round(statistics.median(member_guesses))))
    visible.sort(key=lambda t: (-t.count, t.theme_id))
    return tuple(visible), suppressed


def synthetic_signals_from_population(seed: int, size: int,
                                      tags: Sequence[str]) -> tuple[SyntheticSignal, ...]:
    """Deterministic labeled aggregate from a simulated population. Never real data."""
    if size < 1:
        raise ValidationError("size", "expected >= 1")
    rng = random.Random(seed)
    signals = []
    for i, tag in enumerate(tags):
        share = rng.betavariate(2, 4)
        hits = sum(1 for _ in range(size) if rng.random() < share)
        signals.append(SyntheticSignal(
            signal_id=f"syn-{seed}-{i}", label=f"{SYNTHETIC_LABEL}: {tag}",
            percent=round(100 * hits / size), sample_size=size))
    return tuple(signals)


# ---------------------------------------------------------------- M8

def build_m8_payload(eligible: int, constellations: int,
                     themes: Sequence[SkyTheme]) -> dict:
    """Exactly M8In: counts only, visible themes only."""
    return {"eligiblePlayers": eligible, "constellations": constellations,
            "themes": [{"label": t.label, "count": t.count, "actualPercent": t.actual_percent,
                        "guessedPercentMedian": t.guessed_percent_median} for t in themes]}


def allowed_numbers(payload: Mapping[str, Any]) -> set[int]:
    nums = {payload["eligiblePlayers"], payload["constellations"]}
    for t in payload["themes"]:
        nums |= {t["count"], t["actualPercent"], t["guessedPercentMedian"]}
    return nums


def parse_m8(output: Any, allowed: set[int]) -> tuple[str, ...]:
    data = load_object(output)
    if set(data) != {"headlines"}:
        raise ValidationError("output", "expected exactly {headlines}")
    items = data["headlines"]
    if not isinstance(items, list) or not 1 <= len(items) <= MAX_HEADLINES:
        raise ValidationError("output.headlines", f"expected 1-{MAX_HEADLINES} items")
    out = []
    for i, line in enumerate(items):
        if not isinstance(line, str) or not line.strip() or len(line) > MAX_HEADLINE_CHARS:
            raise ValidationError(f"output.headlines[{i}]", "bad headline")
        for token in _NUMBER_RE.findall(line):
            if "." in token or int(token) not in allowed:
                raise ValidationError(f"output.headlines[{i}]", "number not from server")
        out.append(line.strip())
    return tuple(out)


def template_headlines(eligible: int, themes: Sequence[SkyTheme]) -> tuple[str, ...]:
    if not themes:
        return (f"{eligible} people shared their week. Not enough overlap to show a theme yet.",)
    return tuple(
        f"{t.count} of {eligible} people here share this: {t.label.lower()}. "
        f"They guessed {t.guessed_percent_median}%."[:MAX_HEADLINE_CHARS]
        for t in themes[:MAX_HEADLINES])


class SkyService:
    """Builds SkyStats for a formed cycle. Kai calls compute() after formation commits."""

    def __init__(self, muse: MusePortLike, guard: OutputGuardLike, *,
                 timeout_s: float = DEFAULT_TIMEOUT_S) -> None:
        self._muse = muse
        self._guard = guard
        self._timeout_s = timeout_s

    async def _narrate(self, payload: dict, answers: Sequence[str], request_id: str,
                       evidence: list[MuseCallEvidence]) -> tuple[str, ...] | None:
        allowed = allowed_numbers(payload)
        for _ in range(M8_ATTEMPTS):
            try:
                response = await asyncio.wait_for(self._muse.run(
                    task="sky_narration", requestId=request_id,
                    promptVersion=PROMPT_VERSION_M8, payload=payload), timeout=self._timeout_s)
                if not isinstance(response, Mapping) or set(response) != {"output", "evidence"}:
                    continue
                evidence.append(MuseCallEvidence.from_dict(response["evidence"]))
                lines = parse_m8(response["output"], allowed)
            except (Exception, asyncio.TimeoutError):  # noqa: BLE001 - counts as an attempt
                continue
            if all(_guard_ok(self._guard, line, answers) for line in lines):
                return lines
        return None

    async def compute(self, cycle_id: str, formation: FormationResult,
                      guesses: Mapping[str, Any], threshold: int, *,
                      answer_texts: Sequence[str] = (), mutual_reveals: int = 0,
                      synthetic_signals: Sequence[SyntheticSignal] = (),
                      request_id: str | None = None) -> SkyStats:
        if formation.status != "ok":
            raise MatchingError("INVALID_INPUT", "Sky needs a formed cycle", retryable=False)
        eligible = len({p for c in formation.constellations for p in c.member_ids})
        themes, suppressed = compute_themes(formation.themes, validate_guesses(guesses),
                                            eligible, threshold, self._guard, answer_texts)
        payload = build_m8_payload(eligible, len(formation.constellations), themes)
        evidence: list[MuseCallEvidence] = []
        headlines = await self._narrate(payload, answer_texts,
                                        request_id or f"sky-{cycle_id}", evidence)
        return SkyStats(
            cycle_id=cycle_id, threshold=threshold, eligible_players=eligible,
            constellations=len(formation.constellations), mutual_reveals=mutual_reveals,
            themes=themes, suppressed_themes=suppressed,
            headlines=headlines or template_headlines(eligible, themes),
            synthetic_signals=tuple(synthetic_signals), evidence=tuple(evidence))


def formation_debug(constellations_refs: Sequence[Sequence[str]],
                    baseline: Sequence[Sequence[str]]) -> dict:
    """Operator-only, ids only (no answer text): where baseline and Muse disagree."""
    base_of = {r: i for i, g in enumerate(baseline) for r in g}
    split = sorted({tuple(sorted((a, b)))
                    for g in constellations_refs for a in g for b in g
                    if a < b and base_of.get(a) != base_of.get(b)})
    agree = sum(1 for g in constellations_refs if len({base_of.get(r) for r in g}) == 1)
    return {"baselineGroups": [sorted(g) for g in baseline],
            "museGroups": [sorted(g) for g in constellations_refs],
            "agreements": agree, "splitByBaseline": [list(p) for p in split]}
