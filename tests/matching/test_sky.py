"""Sky prevalence + M8 narration tests (offline, TEST-ONLY adapters, synthetic data)."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from server.matching.models import Constellation, FormationResult, Theme, ValidationError
from server.matching.sky import (
    SkyService,
    build_m8_payload,
    compute_themes,
    formation_debug,
    parse_m8,
    synthetic_signals_from_population,
    validate_guesses,
)
from tests.matching.adapters import FixtureGuard, evidence, load_week

ROOT = Path(__file__).resolve().parents[2]
SKY_FIXTURE = json.loads((ROOT / "contracts" / "fixtures" / "sky-stats.json").read_text())
EAT_ALONE = ("p-maya", "p-dev", "p-jordan", "p-omar")


def guesses():
    return {g["playerId"]: g["percent"] for g in load_week()["guesses"]}


def formation():
    themes = (Theme("t1", "c", "Eating alone more than they let on", "d", EAT_ALONE, 4.0),
              Theme("t2", "c", "Missing a pickup game", "d", ("p-ren", "p-sam"), 2.0))
    members = [("p-maya", "p-dev", "p-omar", "p-lee"), ("p-jordan", "p-sam", "p-ren")]
    cons = tuple(Constellation(f"c{i}", "c", m, "x", 0.8, False, "N", "kite", "dusk", True)
                 for i, m in enumerate(members))
    return FormationResult("ok", constellations=cons, themes=themes)


class ScriptedM8:
    label = "TEST-ONLY adapter"

    def __init__(self, *outputs):
        self.outputs = list(outputs)
        self.payloads = []

    async def run(self, *, task, requestId, promptVersion, payload, signal=None):
        self.payloads.append(payload)
        out = self.outputs.pop(0) if len(self.outputs) > 1 else self.outputs[0]
        return {"output": out, "evidence": evidence("M8")}


def sky(muse, threshold=3, **kw):
    return asyncio.run(SkyService(muse, FixtureGuard()).compute(
        "c", formation(), guesses(), threshold, **kw))


def test_theme_counts_percent_and_median():
    themes, suppressed = compute_themes(formation().themes, guesses(), 7, 3, FixtureGuard())
    assert suppressed == 1 and len(themes) == 1
    t = themes[0]
    assert (t.count, t.actual_percent) == (4, 57)
    assert t.guessed_percent_median == 12  # median of 10,15,20,5 -> 12.5 -> banker's 12


def test_two_member_theme_never_rendered_and_label_never_sent():
    m = ScriptedM8({"headlines": ["4 of 7 eat alone more than they let on."]})
    stats = sky(m).to_wire()
    assert all(t["count"] >= 3 for t in stats["themes"])
    assert "Missing a pickup game" not in json.dumps(stats) + json.dumps(m.payloads)


def test_production_threshold_suppresses_all():
    stats = sky(ScriptedM8({"headlines": ["7 people shared."]}), threshold=25)
    assert stats.themes == () and stats.suppressed_themes == 2


def test_wire_keys_match_contract_fixture():
    sig = synthetic_signals_from_population(1, 200, ["skipped a plan"])
    stats = sky(ScriptedM8({"headlines": ["4 of 7."]}), synthetic_signals=sig).to_wire()
    ref = SKY_FIXTURE["sky"]
    assert set(stats) == set(ref)
    assert set(stats["themes"][0]) == set(ref["themes"][0])
    assert set(stats["syntheticSignals"][0]) == set(ref["syntheticSignals"][0])
    assert set(stats["evidence"][0]) == set(ref["evidence"][0])


def test_m8_payload_matches_m8in_counts_only():
    m = ScriptedM8({"headlines": ["4 of 7."]})
    sky(m)
    payload = m.payloads[0]
    assert set(payload) == {"eligiblePlayers", "constellations", "themes"}
    assert set(payload["themes"][0]) == {"label", "count", "actualPercent",
                                         "guessedPercentMedian"}
    blob = json.dumps(payload)
    for a in load_week()["answers"]:
        assert a["text"] not in blob
    assert "p-maya" not in blob


def test_invented_number_retries_then_template():
    m = ScriptedM8({"headlines": ["99% of people eat alone."]})
    stats = sky(m)
    assert len(m.payloads) == 2
    assert stats.headlines[0].startswith("4 of 7 people")
    assert "12%" in stats.headlines[0]


def test_valid_headline_accepted_after_bad_one():
    m = ScriptedM8("{not json", {"headlines": ["4 of 7 eat alone. They guessed 12%."]})
    assert sky(m).headlines == ("4 of 7 eat alone. They guessed 12%.",)


def test_quoting_headline_rejected_by_guard():
    quote = "i eat in my room so no one sees me"
    m = ScriptedM8({"headlines": [quote]})
    stats = sky(m, answer_texts=["I eat in my room so no one sees me alone"])
    assert quote not in stats.headlines


@pytest.mark.parametrize("bad", [{"p": 101}, {"p": -1}, {"p": True}, {"p": 5.5}])
def test_invalid_guesses_rejected(bad):
    with pytest.raises(ValidationError):
        validate_guesses(bad)


def test_parse_m8_rejects_extra_keys_and_decimals():
    with pytest.raises(ValidationError):
        parse_m8({"headlines": ["4 of 7"], "x": 1}, {4, 7})
    with pytest.raises(ValidationError):
        parse_m8({"headlines": ["4.5 of 7"]}, {4, 7})


def test_synthetic_signals_deterministic_labeled_and_separate():
    a = synthetic_signals_from_population(42, 500, ["skipped a plan", "ate alone"])
    assert a == synthetic_signals_from_population(42, 500, ["skipped a plan", "ate alone"])
    assert all(s.to_wire()["source"] == "synthetic" and "Synthetic signal" in s.label for s in a)
    stats = sky(ScriptedM8({"headlines": ["4 of 7."]}), synthetic_signals=a)
    assert stats.themes[0].count == 4


def test_formation_debug_ids_only():
    debug = formation_debug([["r1", "r2", "r3"]], [["r1", "r4", "r5"], ["r2", "r3", "r6"]])
    assert debug["splitByBaseline"] == [["r1", "r2"], ["r1", "r3"]]
    assert debug["agreements"] == 0
    assert build_m8_payload(7, 2, ())["themes"] == []
