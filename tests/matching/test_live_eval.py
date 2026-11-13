"""Offline test of the formation timing harness through Adam's fixture adapter."""
from __future__ import annotations

import asyncio
import json

from server.matching.live_eval import evaluate, synthetic_snapshot
from server.matching.muse_specs import register_formation_specs
from server.providers import TaskRegistry


def test_specs_registered_for_all_formation_tasks():
    registry = register_formation_specs(TaskRegistry())
    tasks = {t for t, _ in registry.keys()}
    assert tasks == {"theme_discovery", "constellation_formation", "constellation_naming",
                     "sky_narration"}


def test_thirty_player_fixture_run_is_valid_and_labeled():
    report = asyncio.run(evaluate(30, live=False))
    assert report["status"] == "ok" and report["label"] == "Synthetic player"
    assert report["mode"] == "fixture" and not report["usedFallback"]
    assert all(3 <= s <= 5 for s in report["constellationSizes"])
    assert sum(report["constellationSizes"]) == 30
    assert all(e["source"] == "replay" for e in report["evidence"])
    assert {e["callType"] for e in report["evidence"]} == {"M3", "M4", "M5", "M8"}


def test_report_has_no_answer_text():
    report = json.dumps(asyncio.run(evaluate(12, live=False)))
    for answer in synthetic_snapshot(12)["answers"]:
        assert answer["text"] not in report
