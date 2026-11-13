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
from server.matching.adaptive import adaptive_weights
from server.matching.baseline import tokens
from server.matching.closeness import bands_for_viewer, pair_closeness
from server.matching.daily import (
    SECOND_DEGREE_MIN_ELIGIBLE,
    SKY_STARS,
    Tag,
    daily_groups,
    groups_from_themes,
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
    pair,
)
from server.matching.ports import MusePortLike
from server.matching.validation import violations

M3_TIMEOUT_S = 45.0
MIN_MEANING_MEMBERS = 3
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
    meaning: str | None = None  # Muse line, guarded; only set for 3+ members
    is_fallback: bool = False  # keyword grouping, labeled as such
    evidence: tuple[dict, ...] = ()  # Muse call metadata only (model, call type, latency)


@dataclass(frozen=True)
class DayRecord:
    final: bool
    groups: tuple[DayGroup, ...]
    players: tuple[str, ...]  # everyone placed or not, private ids
    blocked: tuple[tuple[str, str], ...] = ()  # private-id pairs, for the Sunday main


class InMemoryDayStore:
    """Per-process. A durable store replaces it for multi-process deploys (Kai/Patrik)."""

    def __init__(self) -> None:
        self.days: dict[tuple[str, int], DayRecord] = {}
        self.mains: dict[str, tuple[tuple[str, ...], ...]] = {}
        self.main_meanings: dict[tuple[str, tuple[str, ...]], str] = {}

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


def _evidence_chip(evidence) -> dict | None:
    """Model name, call type and latency only. No prompt, no text."""
    if not evidence:
        return None
    e = evidence[0]
    return {"model": e.get("model"), "callType": e.get("callType"), "latencyMs": e.get("latencyMs")}


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
        guard=None,
    ) -> None:
        self._guard = guard
        self._muse, self._snapshots = muse, snapshots
        self.store = store or InMemoryDayStore()
        self._m3_timeout_s = m3_timeout_s

    async def _snap(self, cycle: str, day: int) -> FormationSnapshot:
        return FormationSnapshot.from_dict(await self._snapshots.day_snapshot(cycle, day))

    def _safe_meaning(self, text, answer_texts, size: int) -> str | None:
        """A Muse-written line, shown only for 3+ members and only if OutputGuard passes it.
        No guard configured means no line: never ship unguarded model text."""
        if size < MIN_MEANING_MEMBERS or self._guard is None or not isinstance(text, str):
            return None
        text = text.strip()
        if not text:
            return None
        verdict = self._guard.check(text, answer_texts)
        return text if isinstance(verdict, Mapping) and verdict.get("ok") is True else None

    def _record(
        self, cycle: str, day: int, snap: FormationSnapshot, tags, final: bool, themes=None,
        evidence=None,
    ) -> DayRecord:
        if themes:  # Muse's own groups; code only enforces the guarantees
            groups, _unplaced = groups_from_themes(
                [t[3] for t in themes], snap.refs, _ref_blocks(snap)
            )
        else:
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
            meaning = None
            if themes:
                best = max(themes, key=lambda t: len(set(t[3]) & set(g)))
                if set(best[3]) & set(g):
                    meaning = self._safe_meaning(best[2], [a.text for a in snap.answers], len(g))
            out.append(
                DayGroup(_gid(cycle, day, ids), ids, bright, meaning, not themes, tuple(evidence or ()))
            )
        blocked = tuple(sorted({pair(a, b) for a, b in snap.blocked_pairs}))
        return DayRecord(
            final, tuple(out), tuple(sorted(snap.id_map[r] for r in snap.refs)), blocked
        )

    # ---- FormationPort ----------------------------------------------------

    async def dailyPlace(self, cycleId: str, day: int, playerRef: str) -> dict:  # noqa: N802,N803
        try:
            snap = await self._snap(cycleId, day)
        except ValidationError:
            return _failure("INVALID_INPUT", "Bad snapshot")
        existing = self.store.load_days(cycleId).get(day)
        if existing is not None and existing.final:
            # A closed day is never overwritten by a late answer's keyword groups.
            rec = existing
        else:
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
        themes, evidence = await self._propose_themes(cycleId, day, snap)
        if themes:
            rec = self._record(cycleId, day, snap, None, final=True, themes=themes, evidence=evidence)
        else:
            rec = self._record(cycleId, day, snap, None, final=True)
        self.store.save_day(cycleId, day, rec)
        placed = {p for g in rec.groups for p in g.members}
        return {
            "status": "ok",
            "constellations": len(rec.groups),
            "unplaced": len(set(rec.players) - placed),
            "evidence": evidence,
        }

    async def _propose_themes(self, cycle: str, day: int, snap: FormationSnapshot):
        """Validated M3 themes if Muse answers; else None (keyword fallback, no evidence)."""
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
            return (themes or None), [MuseCallEvidence.from_dict(resp["evidence"]).to_wire()]
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
        blocked = sorted({p for r in days.values() for p in r.blocked})
        graph = self._graph(cycleId)
        groups, unplaced = main_groups(players, graph, (), blocked)
        evidence: list = []
        refined = await self._refine_main(cycleId, days, players, blocked)
        if refined is not None:
            (groups, unplaced), evidence = refined
        self.store.save_main(cycleId, groups)
        return {
            "status": "ok",
            "groups": len(groups),
            "unplaced": len(unplaced),
            "evidence": evidence,
        }

    async def _refine_main(self, cycle: str, days, players, blocked):
        """M4 over the week's answers. Used only if it passes the same guarantees; else None."""
        if self._muse is None:
            return None
        try:
            ref_of = {p: f"w{i}" for i, p in enumerate(players)}
            answers: list[PromptText] = []
            for day in sorted(days):
                snap = await self._snap(cycle, day)
                answers += [
                    PromptText(ref_of[snap.id_map[a.id]], a.text, a.weight)
                    for a in snap.answers
                    if snap.id_map.get(a.id) in ref_of
                ]
            refs = {ref_of[p] for p in players}
            ref_blocks = [(ref_of[a], ref_of[b]) for a, b in blocked if a in ref_of and b in ref_of]
            resp = await asyncio.wait_for(
                self._muse.run(
                    task="constellation_formation",
                    requestId=f"main-{cycle}",
                    promptVersion=prompts.PROMPT_VERSION_M4,
                    payload=prompts.build_m4_payload((), answers[:400], ref_blocks),
                ),
                timeout=self._m3_timeout_s,
            )
            proposed = prompts.parse_m4(resp["output"], refs)
            groups = [tuple(m) for m, _meaning, _conf in proposed]
            placed = {r for g in groups for r in g}
            if violations(groups, placed, ref_blocks):
                return None
            by_ref = {v: k for k, v in ref_of.items()}
            out = tuple(tuple(sorted(by_ref[r] for r in g)) for g in groups)
            texts = [a.text for a in answers]
            for (_m, meaning, _c), g in zip(proposed, out, strict=True):
                safe = self._safe_meaning(meaning, texts, len(g))
                if safe:
                    self.store.main_meanings = {**self.store.main_meanings, (cycle, g): safe}
            unplaced = tuple(sorted(set(players) - {p for g in out for p in g}))
            return (out, unplaced), [MuseCallEvidence.from_dict(resp["evidence"]).to_wire()]
        except Exception:  # noqa: BLE001 - code grouping stands, never fails Sunday
            return None

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
                    "sharedMeaning": g.meaning,
                    "memberCount": len(g.members) if len(g.members) >= MIN_MEANING_MEMBERS else None,
                    "isFallback": g.is_fallback,
                    "museEvidence": _evidence_chip(g.evidence),
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
                "sharedMeaning": self.store.main_meanings.get((cycle, tuple(sorted(group)))),
                "revealedAt": revealed_at,
                "roomExpiresAt": expires_at,
            },
            "reason": None,
        }


def _ref_blocks(snap: FormationSnapshot) -> list[tuple[str, str]]:
    by_id = {v: k for k, v in snap.id_map.items()}
    return [(by_id[a], by_id[b]) for a, b in snap.blocked_pairs if a in by_id and b in by_id]


class QuietSignals:
    """One anonymous pulse per member per constellation. Stores counts only, never who."""

    def __init__(self) -> None:
        self._sent: set[tuple[str, str]] = set()
        self._pulses: dict[str, int] = {}

    def send(self, constellation_id: str, player: str) -> dict:
        key = (constellation_id, player)
        if key in self._sent:
            return {"sent": False, "pulses": self._pulses.get(constellation_id, 0)}
        self._sent.add(key)
        self._pulses[constellation_id] = self._pulses.get(constellation_id, 0) + 1
        return {"sent": True, "pulses": self._pulses[constellation_id]}

    def pulses(self, constellation_id: str) -> int:
        return self._pulses.get(constellation_id, 0)

    def has_sent(self, constellation_id: str, player: str) -> bool:
        return (constellation_id, player) in self._sent
