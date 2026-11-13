"""FormationV3: the v3 FormationPort (protocol.ts 3.0.0) over the code-only producers in daily.py.

    port = FormationV3(muse=..., snapshots=privacy_day_source, store=InMemoryDayStore())
    await port.dailyPlace(cycle, 2, player_id)   # instant, no Muse
    await port.closeDay(cycle, 2)  # M3 proposes tags; code assigns; fallback on failure
    await port.weekGraph(cycle); await port.mainConstellation(cycle); await port.skyLayout(cycle)

Results are counts and opaque ids. Views (`daily_view`, `my_sky`, `main_view`) return star or room
indices only (R1): room indices are drawn per room and never equal the sky star index. Private
player ids live in the DayStore and never leave this module. Nothing here calls the network except
the optional M3 tag proposal, which is validated and falls back to keyword tags.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import random
import struct
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from server.matching import prompts
from server.matching.baseline import tokens
from server.matching.adaptive import adaptive_weights
from server.matching.closeness import bands_for_viewer, pair_closeness
from server.matching.daily import (
    SECOND_DEGREE_MIN_ELIGIBLE,
    SKY_STARS,
    Tag,
    daily_groups,
    main_groups,
    second_degree,
    sky_positions,
    star_indices,
    week_graph,
)
from server.matching.models import (
    FormationSnapshot,
    MatchingError,
    MuseCallEvidence,
    PromptText,
    ValidationError,
)
from server.matching.ports import MusePortLike

M3_TIMEOUT_S = 45.0
BAND_ORDER = {"bright": 0, "mid": 1, "faint": 2}


class DaySnapshotSource(Protocol):
    async def day_snapshot(self, cycle_id: str, day: int) -> Mapping[str, Any]:
        """Consent- and safety-filtered snapshot of that day's accepted answers (Patrik)."""
        ...


@dataclass(frozen=True)
class DayGroup:
    group_id: str
    members: tuple[str, ...]  # private player ids
    brightness: Mapping[str, str]  # viewer player id -> band


@dataclass(frozen=True)
class DayRecord:
    final: bool
    groups: tuple[DayGroup, ...]
    players: tuple[str, ...]  # everyone placed or not, private ids


class InMemoryDayStore:
    """Per-process. A durable store replaces it for multi-process deploys (Kai/Patrik)."""

    def __init__(self) -> None:
        self.days: dict[tuple[str, int], DayRecord] = {}
        self.mains: dict[str, tuple[tuple[str, ...], ...]] = {}

    def save_day(self, cycle: str, day: int, record: DayRecord) -> None:
        self.days = {**self.days, (cycle, day): record}

    def load_days(self, cycle: str) -> dict[int, DayRecord]:
        return {d: r for (c, d), r in self.days.items() if c == cycle}

    def save_main(self, cycle: str, groups: tuple[tuple[str, ...], ...]) -> None:
        self.mains = {**self.mains, cycle: groups}

    def load_main(self, cycle: str) -> tuple[tuple[str, ...], ...] | None:
        return self.mains.get(cycle)

    def purge_cycle(self, cycle: str) -> None:
        """Called from the 14-day retention sweep (AnswerStore.expired_cycles)."""
        self.days = {k: v for k, v in self.days.items() if k[0] != cycle}
        self.mains = {k: v for k, v in self.mains.items() if k != cycle}


def _gid(cycle: str, day: int, members: tuple[str, ...]) -> str:
    return "c-" + hashlib.sha256(f"{cycle}:{day}:{'|'.join(members)}".encode()).hexdigest()[:12]


def _failure(code: str, message: str, retryable: bool = False) -> dict:
    return {"status": "failed", "error": {"code": code, "message": message, "retryable": retryable}}


def _best_band(bands: Mapping[str, str]) -> str:
    return min(bands.values(), key=BAND_ORDER.__getitem__) if bands else "mid"


def tags_from_themes(themes: tuple[tuple, ...], answers: tuple[PromptText, ...]) -> tuple[Tag, ...]:
    """Turn M3 themes into keyword tags (keywords members share). Never trusts members."""
    by_ref: dict[str, set[str]] = {}
    for a in answers:
        by_ref.setdefault(a.id, set()).update(tokens(a.text))
    tags = []
    for theme_id, _label, _desc, members in themes:
        counts = Counter(t for r in members for t in by_ref.get(r, ()))
        shared = frozenset(t for t, n in counts.items() if n >= max(2, len(members) // 2))
        if shared:
            tags.append(Tag(f"m3-{theme_id}", shared))
    return tuple(tags)


class FormationV3:
    def __init__(
        self,
        muse: MusePortLike | None,
        snapshots: DaySnapshotSource,
        store: InMemoryDayStore | None = None,
        *,
        m3_timeout_s: float = M3_TIMEOUT_S,
    ) -> None:
        self._muse, self._snapshots = muse, snapshots
        self.store = store or InMemoryDayStore()
        self._m3_timeout_s = m3_timeout_s

    async def _snap(self, cycle: str, day: int) -> FormationSnapshot:
        return FormationSnapshot.from_dict(await self._snapshots.day_snapshot(cycle, day))

    def _record(
        self, cycle: str, day: int, snap: FormationSnapshot, tags, final: bool
    ) -> DayRecord:
        groups, _unplaced = daily_groups(snap.answers, _ref_blocks(snap), tags)
        close = pair_closeness(snap, snap.refs, adaptive_weights(snap))
        out = []
        for g in groups:
            ids = tuple(sorted(snap.id_map[r] for r in g))
            bright = {
                snap.id_map[r]: _best_band(
                    bands_for_viewer(snap.id_map[r], [snap.id_map[m] for m in g], close)
                )
                for r in g
            }
            out.append(DayGroup(_gid(cycle, day, ids), ids, bright))
        return DayRecord(final, tuple(out), tuple(sorted(snap.id_map[r] for r in snap.refs)))

    # ---- FormationPort ----------------------------------------------------

    async def dailyPlace(self, cycleId: str, day: int, playerRef: str) -> dict:  # noqa: N802,N803
        try:
            snap = await self._snap(cycleId, day)
        except ValidationError:
            return _failure("INVALID_INPUT", "Bad snapshot")
        rec = self._record(cycleId, day, snap, None, final=False)
        self.store.save_day(cycleId, day, rec)
        ids = [
            g.group_id
            for g in rec.groups
            if playerRef in g.members
            or playerRef in {r for r in snap.id_map if snap.id_map[r] in g.members}
        ]
        return {"status": "ok", "placement": "ready" if ids else "pending", "constellationIds": ids}

    async def closeDay(self, cycleId: str, day: int) -> dict:  # noqa: N802,N803
        try:
            snap = await self._snap(cycleId, day)
        except ValidationError:
            return _failure("INVALID_INPUT", "Bad snapshot")
        tags, evidence = await self._propose_tags(cycleId, day, snap)
        rec = self._record(cycleId, day, snap, tags, final=True)
        self.store.save_day(cycleId, day, rec)
        placed = {p for g in rec.groups for p in g.members}
        return {
            "status": "ok",
            "constellations": len(rec.groups),
            "unplaced": len(set(rec.players) - placed),
            "evidence": evidence,
        }

    async def _propose_tags(self, cycle: str, day: int, snap: FormationSnapshot):
        """M3 tags if Muse answers validly; else None (daily_groups falls back to keyword tags)."""
        if self._muse is None or not snap.answers:
            return None, []
        try:
            resp = await asyncio.wait_for(
                self._muse.run(
                    task="theme_discovery",
                    requestId=f"day-{cycle}-{day}",
                    promptVersion=prompts.PROMPT_VERSION_M3,
                    payload=prompts.build_m3_payload(snap.answers),
                ),
                timeout=self._m3_timeout_s,
            )
            themes = prompts.parse_m3(resp["output"], set(snap.refs))
            tags = tags_from_themes(themes, snap.answers)
            return (tags or None), [MuseCallEvidence.from_dict(resp["evidence"]).to_wire()]
        except (TimeoutError, Exception):  # noqa: BLE001 - keyword fallback, never fails the day
            return None, []

    async def weekGraph(self, cycleId: str) -> dict:  # noqa: N802,N803
        days = self.store.load_days(cycleId)
        graph = self._graph(cycleId)
        return {
            "status": "ok",
            "players": len({p for r in days.values() for p in r.players}),
            "edges": len(graph),
        }

    def _graph(self, cycle: str) -> dict[tuple[str, str], int]:
        return week_graph(
            [[g.members for g in r.groups] for _, r in sorted(self.store.load_days(cycle).items())]
        )

    async def mainConstellation(self, cycleId: str) -> dict:  # noqa: N802,N803
        days = self.store.load_days(cycleId)
        if not days:
            return _failure("NOT_FOUND", "No days formed for this cycle")
        players = sorted({p for r in days.values() for p in r.players})
        groups, unplaced = main_groups(players, self._graph(cycleId))
        self.store.save_main(cycleId, groups)
        return {"status": "ok", "groups": len(groups), "unplaced": len(unplaced), "evidence": []}

    async def skyLayout(self, cycleId: str) -> dict:  # noqa: N802,N803
        days = self.store.load_days(cycleId)
        if not days:
            return _failure("NOT_FOUND", "No days formed for this cycle")
        eligible = len({p for r in days.values() for p in r.players})
        pos = sky_positions(cycleId)
        raw = struct.pack(f"<{2 * len(pos)}h", *(v for xy in pos for v in xy))
        return {
            "status": "ok",
            "eligiblePlayers": eligible,
            "secondDegree": eligible >= SECOND_DEGREE_MIN_ELIGIBLE,
            "stars": {
                "weekSeed": cycleId,
                "count": len(pos),
                "positions": base64.b64encode(raw).decode(),
            },
        }

    # ---- views (indices only) --------------------------------------------

    def _stars(self, cycle: str) -> dict[str, int]:
        players = sorted({p for r in self.store.load_days(cycle).values() for p in r.players})
        return star_indices(cycle, players, SKY_STARS)

    def daily_view(
        self, cycle: str, day: int, player: str, color_id: str, answered_today: int
    ) -> dict:
        rec, stars = self.store.load_days(cycle).get(day), self._stars(cycle)
        if rec is None or player not in stars:
            raise MatchingError("NOT_FOUND", "No placement for this player", retryable=False)
        pos = sky_positions(cycle)
        mine = [g for g in rec.groups if player in g.members]
        return {
            "day": day,
            "colorId": color_id,
            "answeredToday": answered_today,
            "placement": "final" if rec.final else ("ready" if mine else "pending"),
            "myStarIndex": stars[player],
            "constellations": [
                {
                    "constellationId": g.group_id,
                    "starIndices": sorted(stars[m] for m in g.members),
                    "brightness": g.brightness.get(player, "mid"),
                    "anchors": [
                        {
                            "index": stars[m],
                            "x": pos[stars[m]][0] / 32767,
                            "y": pos[stars[m]][1] / 32767,
                        }
                        for m in g.members
                    ],
                }
                for g in mine
            ],
        }

    def my_sky(self, cycle: str, player: str, day_colors: Mapping[int, str]) -> dict:
        days, stars = self.store.load_days(cycle), self._stars(cycle)
        if player not in stars:
            raise MatchingError("NOT_FOUND", "No placement for this player", retryable=False)
        by_player = lambda g: tuple(sorted(g.members))  # noqa: E731
        every = [(d, g) for d, r in sorted(days.items()) for g in r.groups]
        mine = [(d, g) for d, g in every if player in g.members]
        eligible = len({p for r in days.values() for p in r.players})
        second = second_degree(
            [by_player(g) for _, g in mine], [by_player(g) for _, g in every], eligible
        )
        ids = {by_player(g): g.group_id for _, g in every}
        return {
            "myStarIndex": stars[player],
            "mine": [
                {
                    "constellationId": g.group_id,
                    "day": d,
                    "colorId": day_colors[d],
                    "starIndices": sorted(stars[m] for m in g.members),
                }
                for d, g in mine
            ],
            "secondDegree": [
                {
                    "constellationId": ids[grp],
                    "viaStarIndex": stars[via],
                    "starIndices": sorted(stars[m] for m in grp),
                }
                for via, grp in second
            ],
        }

    def main_view(
        self, cycle: str, player: str, room_id: str, revealed_at: str, expires_at: str
    ) -> dict:
        """R1: room indices are shuffled per room and never the sky star index."""
        groups = self.store.load_main(cycle)
        if groups is None:
            return {"main": None, "reason": "no_match"}
        group = next((g for g in groups if player in g), None)
        if group is None:
            return {"main": None, "reason": "no_match"}
        order = list(range(len(group)))
        random.Random(f"room:{room_id}").shuffle(order)
        idx = dict(zip(group, order, strict=True))
        n = max(len(group) - 1, 1)
        return {
            "main": {
                "constellationId": _gid(cycle, 0, group),
                "roomId": room_id,
                "myRoomIndex": idx[player],
                "roomIndices": sorted(idx.values()),
                "anchors": [{"index": idx[m], "t": round(idx[m] / n, 3)} for m in group],
                "brightness": {idx[m]: "mid" for m in group if m != player},
                "revealedAt": revealed_at,
                "roomExpiresAt": expires_at,
            },
            "reason": None,
        }


def _ref_blocks(snap: FormationSnapshot) -> list[tuple[str, str]]:
    by_id = {v: k for k, v in snap.id_map.items()}
    return [(by_id[a], by_id[b]) for a, b in snap.blocked_pairs if a in by_id and b in by_id]
