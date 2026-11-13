"""Formation + Sky timing harness. Offline (fixture transport) by default.

    python -m server.matching.live_eval --players 30          # offline, scripted Muse
    python -m server.matching.live_eval --players 30 --live   # real Muse, needs MUSE_API_KEY
    python -m server.matching.live_eval --gold --live         # quality vs gold set + baseline

All players are synthetic ("Synthetic player"). Prints timings, sizes, fallback use and
evidence only; never answer text or prompts.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from collections.abc import Mapping, Sequence
from typing import Any

from server.matching.baseline import baseline_groups
from server.matching.evaluation import gold_snapshot, pair_metrics
from server.matching.models import FormationSnapshot
from server.matching.muse_specs import register_formation_specs
from server.matching.port import build_matching_port
from server.privacy import OutputGuard
from server.providers import (
    KeywordMusePort,
    TaskRegistry,
    build_muse_adapter,
    load_muse_config,
)
from server.providers.fixture import FixtureMuse, ScriptedTransport

SYNTHETIC_LABEL = "Synthetic player"
TOPICS = (
    ("I eat dinner in my room most nights", "cooking for one feels lonely"),
    ("I miss my friends from home a lot", "nobody here knows my old life"),
    ("I pretend I'm busy so nobody sees I have no plans", "weekends are quiet for me"),
    ("I feel behind everyone in my classes", "everyone else seems to get it faster"),
    ("pickup soccer is the best part of my week", "I love games with strangers"),
    ("late night coding with music on", "I build little apps at 2am"),
)


def synthetic_snapshot(players: int) -> dict:
    answers, id_map = [], {}
    for i in range(players):
        ref, player = f"r{i + 1}", f"syn-{i + 1}"
        id_map[ref] = player
        pair = TOPICS[i % len(TOPICS)]
        answers.append({"id": ref, "text": pair[i % 2], "weight": 1.0})
        answers.append({"id": ref, "text": pair[(i + 1) % 2], "weight": 0.6})
    return {"answers": answers, "idMap": id_map, "blockedPairs": [["syn-1", "syn-7"]]}


class _Snapshots:
    def __init__(self, snap: dict) -> None:
        self._snap = snap

    async def formation_snapshot(self, cycle_id: str) -> Mapping[str, Any]:
        return self._snap


class _Guesses:
    """Synthetic guesses; Patrik's bulk guess getter is not delivered yet."""

    def __init__(self, players: Sequence[str]) -> None:
        self._guesses = {p: (sum(map(ord, p)) * 7) % 100 for p in players}

    async def prevalence_guesses(self, cycle_id: str) -> Mapping[str, int]:
        return self._guesses


def scripted_transport(players: int) -> ScriptedTransport:
    """Offline Muse: groups refs by topic, valid sizes, fixed sets."""
    def m3(inp: dict) -> dict:
        refs = sorted({a["id"] for a in inp["answers"]}, key=lambda r: int(r[1:]))
        return {"themes": [{"id": f"t{k}", "label": f"Shared week {k}", "description": "d",
                            "memberIds": [r for r in refs if (int(r[1:]) - 1) % 6 == k]}
                           for k in range(6)]}

    def m4(inp: dict) -> dict:
        refs = sorted({a["id"] for a in inp["answers"]}, key=lambda r: int(r[1:]))
        size = 5 if len(refs) % 5 == 0 else 3
        groups = [refs[i:i + size] for i in range(0, len(refs), size)]
        return {"constellations": [{"memberIds": g, "sharedMeaning": "s", "confidence": 0.7}
                                   for g in groups]}

    shapes = {3: "triangle", 4: "kite", 5: "pentagon"}
    return (ScriptedTransport()
            .on("theme_discovery", m3).on("constellation_formation", m4)
            .on("constellation_naming", lambda inp: {"name": "Quiet Lanterns",
                                                     "shapeId": shapes[inp["size"]],
                                                     "colorId": "dusk"})
            .on("sky_narration", lambda inp: {"headlines": [
                f"{inp['eligiblePlayers']} people shared their week."]}))


def build_port(live: bool, players: int) -> KeywordMusePort:
    registry = register_formation_specs(TaskRegistry())
    if not live:
        return KeywordMusePort(FixtureMuse(registry, scripted_transport(players)))
    config = load_muse_config()
    if config is None:
        raise SystemExit("--live needs MUSE_API_KEY (or MODEL_API_KEY) in the environment")
    return KeywordMusePort(build_muse_adapter(registry, config))


def _quality(snap: dict, result_groups: Sequence[Sequence[str]], gold: Mapping[str, str]) -> dict:
    parsed = FormationSnapshot.from_dict(snap)
    base = [[parsed.id_map[r] for r in g] for g in baseline_groups(parsed.answers)]
    return {"muse": pair_metrics(result_groups, gold).to_wire(),
            "keywordBaseline": pair_metrics(base, gold).to_wire()}


async def evaluate(players: int, live: bool, threshold: int = 3, gold: bool = False) -> dict:
    port = build_port(live, players)
    gold_labels: dict[str, str] = {}
    if gold:
        snap, gold_labels = gold_snapshot(players)
    else:
        snap = synthetic_snapshot(players)
    matching = build_matching_port(muse=port, snapshots=_Snapshots(snap),
                                   guesses=_Guesses(list(snap["idMap"].values())),
                                   guard=OutputGuard(), precompute_threshold=threshold)
    started = time.monotonic()
    raw = await matching.form("eval-cycle")
    formed_ms = int((time.monotonic() - started) * 1000)
    if raw["status"] != "ok":
        return {"label": SYNTHETIC_LABEL, "status": "failed", "error": raw["error"]["code"]}
    sky = await matching.computeSky("eval-cycle", threshold)
    debug = matching.debug("eval-cycle")
    result_groups = [c["memberIds"] for c in raw["constellations"]]
    return {
        "label": SYNTHETIC_LABEL, "mode": "live" if live else "fixture", "players": players,
        "status": "ok", "usedFallback": debug["usedFallback"],
        "formationTotalMs": debug["totalMs"], "formWallMs": formed_ms,
        "totalWithSkyMs": int((time.monotonic() - started) * 1000),
        "constellationSizes": sorted(len(g) for g in result_groups),
        "baselineAgrees": sum(c["baselineAgrees"] for c in raw["constellations"]),
        "fixedNames": sum(1 for c in raw["constellations"] if c["name"].startswith("The ")),
        "skyThemesShown": len(sky["themes"]), "skyThemesSuppressed": sky["suppressedThemes"],
        "guard": "server.privacy.OutputGuard",
        "evidence": [*raw["evidence"], *sky["evidence"]],
        **({"quality": _quality(snap, result_groups, gold_labels),
            "qualityNote": "fixture Muse is scripted; only --live measures Muse quality"
            if not live else "live Muse vs keyword baseline on synthetic gold set"}
           if gold else {}),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--players", type=int, default=30)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--gold", action="store_true", help="score against synthetic gold set")
    args = parser.parse_args(argv)
    if not 3 <= args.players <= 200:
        parser.error("--players must be 3-200")
    report = asyncio.run(evaluate(args.players, args.live, gold=args.gold))
    json.dump(report, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
