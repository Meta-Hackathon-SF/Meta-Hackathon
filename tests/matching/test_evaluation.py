import asyncio
import json

import pytest

from server.matching import eval_cli
from server.matching.evaluation import count_violations, evaluate, generate_synthetic_pools
from server.matching.models import MatchInput
from tests.matching.fixtures import FakeMusePort

LABEL = "unit-test label"


def run(coro):
    return asyncio.run(coro)


class BadOptionPort:
    async def generate(self, **kwargs):
        return {"output": {"optionId": "g99", "sharedInterests": [], "reasonCodes": ["balanced_size"]},
                "evidence": {"model": "bad", "source": "replay",
                             "generatedAt": "2026-11-12T20:00:00Z", "latencyMs": 1}}


def stable(report):
    return {k: v for k, v in report.items() if k != "latency_ms"}


def test_pools_deterministic_and_synthetic():
    a = generate_synthetic_pools(3, 5)
    assert a == generate_synthetic_pools(3, 5)
    assert a != generate_synthetic_pools(4, 5)
    for raw in a:
        inp = MatchInput.from_dict(raw)
        assert len(inp.candidates) == 8
        assert all(c.public_profile.is_synthetic for c in inp.candidates)
        assert all(c.public_profile.display_name.startswith("Synthetic ") for c in inp.candidates)


def test_pools_exercise_gates():
    pools = generate_synthetic_pools(1, 30)
    cands = [c["intent"] for p in pools for c in p["candidates"]]
    assert len({c["areaId"] for c in cands}) > 1
    assert len({c["currency"] for c in cands}) > 1
    assert len({c["availability"][0]["start"] for c in cands}) > 1


def test_evaluate_deterministic_by_seed():
    r1 = run(evaluate(generate_synthetic_pools(7, 20), FakeMusePort(), label=LABEL))
    r2 = run(evaluate(generate_synthetic_pools(7, 20), FakeMusePort(), label=LABEL))
    assert stable(r1) == stable(r2)


def test_zero_violations_on_30_pools():
    r = run(evaluate(generate_synthetic_pools(11, 30), FakeMusePort(), label=LABEL))
    assert r["pools"] == 30
    assert r["matched"] > 0
    assert r["hard_constraint_violations"] == 0
    assert r["matched"] + sum(r["no_match_by_reason"].values()) + r["provider_errors"] == 30
    assert r["evidence_sources"]["replay"] == r["matched"]


def test_bad_port_yields_provider_errors_not_violations():
    r = run(evaluate(generate_synthetic_pools(11, 10), BadOptionPort(), label=LABEL))
    assert r["hard_constraint_violations"] == 0
    assert r["provider_errors"] > 0
    assert r["matched"] == 0


def test_label_propagates_and_empty_pools():
    r = run(evaluate([], FakeMusePort(), label=LABEL))
    assert r["label"] == LABEL
    assert r["pools"] == 0 and r["muse_vs_baseline_agreement"] is None


def test_independent_check_flags_bad_groups():
    inp = MatchInput.from_dict(generate_synthetic_pools(2, 1)[0])
    ids = [c.participant_id for c in inp.candidates]
    assert "size" in count_violations(inp, ids[:2])
    assert "requester_missing" in count_violations(inp, ids[1:4])
    assert "duplicate_member" in count_violations(inp, [ids[0], ids[0], ids[1]])
    assert "unknown_member" in count_violations(inp, [ids[0], ids[1], "ghost"])


def test_cli_output_label_and_no_private_fields(capsys):
    assert eval_cli.main(["--seed", "7", "--pools", "10"]) == 0
    out = capsys.readouterr().out
    data = json.loads(out)
    assert data["label"] == "fixture (fake Muse, not a quality result)"
    for forbidden in ("syn_", "Synthetic", "Budget", "budget", "availability", "goal",
                      "participantId", "publicInterests"):
        assert forbidden not in out


def test_live_flag_not_implemented(capsys):
    assert eval_cli.main(["--live"]) == 2
    with pytest.raises(NotImplementedError):
        eval_cli.build_port()
