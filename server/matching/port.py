"""MatchingPort: the one object orchestration (Kai) wires for formation and Sky.

    port = build_matching_port(muse=KeywordMusePort(adapter), snapshots=privacy,
                               guesses=privacy, guard=output_guard)
    raw = await port.form(cycle_id)             # FormationPort.form -> wire dict
    sky = await port.computeSky(cycle_id, 3)    # FormationPort.computeSky -> SkyStats wire

`form` returns exactly the FormationSuccess / FormationFailure wire shapes (protocol.ts
2.0.0), never raises for model or provider trouble, and never exposes internal fields
(isFallback, repairedGroups, timings). Themes are private and stay inside matching:
they go to a ThemeStore keyed by cycle so computeSky can run after a restart when a
durable store is supplied. The default in-memory store is per process.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol

from server.matching.formation import FormationService
from server.matching.models import (
    DEMO_SKY_THRESHOLD,
    FormationResult,
    MatchingError,
    ValidationError,
)
from server.matching.ports import MusePortLike, OutputGuardLike, SnapshotSource
from server.matching.sky import (
    SkyService,
    SkyStats,
    SyntheticSignal,
    synthetic_signals_from_population,
)


class GuessSource(Protocol):
    async def prevalence_guesses(self, cycle_id: str) -> Mapping[str, int]:
        """{playerId: percent 0-100} for consenting, unflagged players (Patrik)."""
        ...


class ThemeStore(Protocol):
    def save(self, cycle_id: str, result: FormationResult) -> None: ...
    def load(self, cycle_id: str) -> FormationResult | None: ...


class InMemoryThemeStore:
    """Per-process store. Replace with a durable store for multi-process deploys."""

    def __init__(self) -> None:
        self._results: dict[str, FormationResult] = {}

    def save(self, cycle_id: str, result: FormationResult) -> None:
        self._results = {**self._results, cycle_id: result}

    def load(self, cycle_id: str) -> FormationResult | None:
        return self._results.get(cycle_id)


class MatchingPort:
    def __init__(self, formation: FormationService, sky: SkyService, guesses: GuessSource,
                 *, themes: ThemeStore | None = None,
                 synthetic_tags: tuple[str, ...] = (), synthetic_seed: int = 0,
                 synthetic_size: int = 500,
                 precompute_threshold: int | None = DEMO_SKY_THRESHOLD) -> None:
        self._formation = formation
        self._sky = sky
        self._guesses = guesses
        self._themes = themes or InMemoryThemeStore()
        self._synthetic_tags = synthetic_tags
        self._synthetic_seed = synthetic_seed
        self._synthetic_size = synthetic_size
        self._precompute_threshold = precompute_threshold
        self._sky_cache: dict[tuple[str, int], SkyStats] = {}

    async def form(self, cycleId: str) -> dict:  # noqa: N803 - protocol.ts parameter name
        """Formation, with Sky (M8) precomputed alongside M5 naming when enabled."""
        hook = None
        if self._precompute_threshold is not None:
            threshold = self._precompute_threshold

            async def hook(themes, eligible, constellations):  # type: ignore[no-untyped-def]
                guesses = await self._guesses.prevalence_guesses(cycleId)
                stats = await self._sky.compute_from(
                    cycleId, themes, eligible, constellations, guesses, threshold,
                    synthetic_signals=self._synthetic())
                self._sky_cache = {**self._sky_cache, (cycleId, threshold): stats}

        result = await self._formation.form(cycleId, on_grouped=hook)
        if result.status == "ok":
            self._themes.save(cycleId, result)
        return result.to_wire(f"form-{cycleId}")

    def _synthetic(self) -> tuple[SyntheticSignal, ...]:
        if not self._synthetic_tags:
            return ()
        return synthetic_signals_from_population(self._synthetic_seed, self._synthetic_size,
                                                 self._synthetic_tags)

    async def compute_sky(self, cycle_id: str, threshold: int = DEMO_SKY_THRESHOLD,
                          *, mutual_reveals: int = 0) -> dict:
        """SkyStats wire dict. Raises MatchingError NOT_FOUND if the cycle was not formed here,
        INVALID_INPUT on bad guesses or threshold."""
        cached = self._sky_cache.get((cycle_id, threshold))
        if cached is not None and mutual_reveals == cached.mutual_reveals:
            return cached.to_wire()
        result = self._themes.load(cycle_id)
        if result is None:
            raise MatchingError("NOT_FOUND", "No formation for this cycle", retryable=False)
        try:
            guesses = await self._guesses.prevalence_guesses(cycle_id)
            stats = await self._sky.compute(cycle_id, result, guesses, threshold,
                                            mutual_reveals=mutual_reveals,
                                            synthetic_signals=self._synthetic())
        except ValidationError as exc:
            raise MatchingError("INVALID_INPUT", "Sky inputs invalid", retryable=False) from exc
        return stats.to_wire()

    async def computeSky(self, cycleId: str, threshold: int) -> dict:  # noqa: N802,N803
        """protocol.ts FormationPort.computeSky(cycleId, threshold)."""
        return await self.compute_sky(cycleId, threshold)


def build_matching_port(*, muse: MusePortLike, snapshots: SnapshotSource,
                        guesses: GuessSource, guard: OutputGuardLike,
                        themes: ThemeStore | None = None, allow_fallback: bool = True,
                        synthetic_tags: tuple[str, ...] = (), parallel_themes: bool = True,
                        precompute_threshold: int | None = DEMO_SKY_THRESHOLD,
                        **sky_kwargs: Any) -> MatchingPort:
    """Public factory. Register Muse specs separately with register_formation_specs."""
    formation = FormationService(muse, snapshots, guard, allow_fallback=allow_fallback,
                                 parallel_themes=parallel_themes)
    return MatchingPort(formation, SkyService(muse, guard, **sky_kwargs), guesses,
                        themes=themes, synthetic_tags=synthetic_tags,
                        precompute_threshold=precompute_threshold)
