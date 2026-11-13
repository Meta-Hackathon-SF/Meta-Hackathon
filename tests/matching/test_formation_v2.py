"""constellation_formation.v2 (D014): question context, affinity hints, re-solve correction,
sharedMeaning guard. TEST-ONLY adapters; proves payloads and guards, not live quality."""
from __future__ import annotations

import asyncio
import json

import pytest

from server.matching import prompts
from server.matching.closeness import MAX_AFFINITY_PAIRS, affinity_pairs
from server.matching.formation import NEUTRAL_MEANING, FormationService
from server.matching.models import FormationSnapshot, ValidationError
from server.matching.muse_specs import register_formation_specs
from server.matching.port import build_matching_port
from server.providers import TaskRegistry
from server.providers.contract import M3_IN, M4_IN
from server.providers.schema import validate
from tests.matching.adapters import FakeMuse, FixtureGuard, FixtureSnapshotSource, load_week
from tests.matching.test_formation import BLOCKED, GOOD

QUESTION_TEXT = {  # synthetic question text for the fixture's question ids
    "q-routine-meals": "Where do you usually eat, and who's around?",
    "q-joys-small-win": "What was one small win this week?",
    "q-belong-third-place": "Where do you feel most like yourself on campus?",
    "q-hopes-try": "What is something you want to try this month?",
    "q-values-recharge": "How do you recharge after a long day?",
}


def run(coro):
    return asyncio.run(coro)


class DictSource:
    def __init__(self, snap: dict) -> None:
        self.snap = snap

    async def formation_snapshot(self, cycle_id):
        return json.loads(json.dumps(self.snap))


def questioned_snapshot() -> tuple[dict, FixtureSnapshotSource]:
    """Fixture snapshot with D014 questionId per answer and the week's questions."""
    source = FixtureSnapshotSource(include_injection=False)
    snap = source.snapshot()
    week = load_week()
    qid_by_day = {d["day"]: d["questionId"] for d in week["dailyQuestions"]}
    flagged = {week["distressFixture"]["playerId"]}
    rows = [a for a in week["answers"] if a["playerId"] not in flagged]
    assert len(rows) == len(snap["answers"])
    for answer, row in zip(snap["answers"], rows, strict=True):
        answer["questionId"] = qid_by_day[row["day"]]
    used = sorted({a["questionId"] for a in snap["answers"]})
    snap["questions"] = [{"questionId": q, "text": QUESTION_TEXT.get(q, f"Synthetic {q}?")}
                         for q in used]
    return snap, source


def build(snap: dict, source: FixtureSnapshotSource, **kw):
    muse_kw = {k: kw.pop(k) for k in ("m4_script", "meaning") if k in kw}
    muse = FakeMuse(source.ref_of, GOOD, blocked_groups=BLOCKED, **muse_kw)
    return FormationService(muse, DictSource(snap), FixtureGuard(), **kw), muse


def calls(muse, task):
    return [c for c in muse.calls if c["task"] == task]


# ---------------------------------------------------------------- snapshot model

def test_old_snapshot_without_questions_still_forms_with_2_0_payloads():
    source = FixtureSnapshotSource()
    snap = FormationSnapshot.from_dict(source.snapshot())
    assert snap.questions == () and all(a.question_id is None for a in snap.answers)
    service, muse = build(source.snapshot(), source)
    result = run(service.form("c", "r"))
    assert result.status == "ok" and not result.used_fallback
    m4 = calls(muse, "constellation_formation")[0]["payload"]
    assert set(m4) == {"themes", "answers", "blockedPairs"}
    assert all(set(a) == {"id", "text", "weight"} for a in m4["answers"])
    assert calls(muse, "theme_discovery")[0]["payload"]["questions"] == []


def test_snapshot_reads_question_ids_and_questions():
    raw, _ = questioned_snapshot()
    snap = FormationSnapshot.from_dict(raw)
    assert {q.question_id for q in snap.questions} == {a.question_id for a in snap.answers}
    assert all(a.to_wire()["questionId"] == a.question_id for a in snap.answers)


@pytest.mark.parametrize("mutate", [
    lambda s: s["answers"][0].update(questionId="q-unknown"),
    lambda s: s.pop("questions"),  # answers carry questionIds but no questions given
    lambda s: s["questions"].extend({"questionId": f"x{i}", "text": "Synthetic?"}
                                    for i in range(10)),
    lambda s: s["questions"][0].update(text="x" * 301),
    lambda s: s["questions"].append({"questionId": "q" * 65, "text": "Synthetic?"}),
    lambda s: s["questions"].append(dict(s["questions"][0])),  # duplicate id
    lambda s: s["questions"][0].update(extra="field"),
    lambda s: s["answers"][0].update(questionId="q" * 65),
    lambda s: s.update(questions="not a list"),
])
def test_bad_questions_rejected(mutate):
    raw, _ = questioned_snapshot()
    mutate(raw)
    with pytest.raises(ValidationError):
        FormationSnapshot.from_dict(raw)


def test_invalid_questions_fail_formation_closed():
    raw, source = questioned_snapshot()
    raw["answers"][0]["questionId"] = "q-unknown"
    service, muse = build(raw, source)
    result = run(service.form("c", "r"))
    assert result.status == "failed" and result.error.code == "INVALID_INPUT"
    assert muse.calls == []


# ---------------------------------------------------------------- payloads

def test_m3_and_m4_send_question_ids_and_questions_and_match_contract():
    raw, source = questioned_snapshot()
    service, muse = build(raw, source)
    result = run(service.form("c", "r"))
    assert result.status == "ok"
    m3 = calls(muse, "theme_discovery")[0]["payload"]
    m4 = calls(muse, "constellation_formation")[0]["payload"]
    for payload in (m3, m4):
        assert payload["questions"] == raw["questions"]
        assert all(set(a) == {"id", "text", "weight", "questionId"} for a in payload["answers"])
        assert [a["questionId"] for a in payload["answers"]] == [
            a["questionId"] for a in raw["answers"]]
    assert "affinity" not in m4  # no activity in this snapshot
    validate(m3, M3_IN)
    validate(m4, M4_IN)
    blob = json.dumps([m3, m4])
    for player in load_week()["players"]:
        assert player["playerId"] not in blob


def test_built_payloads_validate_against_contract_schemas():
    raw, _ = questioned_snapshot()
    snap = FormationSnapshot.from_dict(raw)
    refs = snap.refs
    theme = ("t1", "Shared week", "fake", tuple(refs[:3]))
    affinity = ((refs[0], refs[1], 2), (refs[1], refs[2], 1))
    m4 = prompts.build_m4_payload((theme,), snap.answers, snap.blocked_ref_pairs(),
                                  snap.questions, affinity)
    validate(m4, M4_IN)
    assert m4["affinity"] == [{"memberIds": [refs[0], refs[1]], "shared": 2},
                              {"memberIds": [refs[1], refs[2]], "shared": 1}]
    validate(prompts.build_m3_payload(snap.answers, snap.questions), M3_IN)
    old = prompts.build_m4_payload((), snap.answers, ())
    assert set(old) == {"themes", "answers", "blockedPairs"}


def test_registered_m4_spec_is_v2_with_tested_sentences():
    assert prompts.PROMPT_VERSION_M4 == "constellation_formation.v2"
    spec = register_formation_specs(TaskRegistry()).get("constellation_formation",
                                                        prompts.PROMPT_VERSION_M4)
    assert spec is not None and spec.input_schema == M4_IN
    for sentence in (prompts.QUESTION_CONTEXT, prompts.AFFINITY_HINTS, prompts.FULLER_GROUPS):
        assert sentence in spec.instructions
    m3 = register_formation_specs(TaskRegistry()).get("theme_discovery",
                                                      prompts.PROMPT_VERSION_M3)
    assert m3 is not None and prompts.M3_QUESTION_CONTEXT in m3.instructions


# ---------------------------------------------------------------- affinity

def activity_snapshot() -> dict:
    refs = ["ra", "rb", "rc", "rd", "re"]
    return {
        "answers": [{"id": r, "text": f"synthetic answer {r}"} for r in refs],
        "idMap": {r: f"syn-{r}" for r in refs} | {"rz": "syn-rz"},
        "blockedPairs": [],
        "activity": {
            "ra": {"topics": ["music", "sports"], "groupIds": ["g-1"],
                   "eventIds": ["ev-approved", "ev-rogue"], "friendIds": ["syn-rb"]},
            "rb": {"topics": ["music"], "groupIds": ["g-1"],
                   "eventIds": ["ev-approved", "ev-rogue"]},
            "rc": {"topics": [], "groupIds": [], "eventIds": ["ev-rogue"],
                   "friendIds": ["syn-ra"]},
            "rd": {"topics": ["sports"]},
            "re": {"topics": []},
            "rz": {"topics": ["music"], "groupIds": ["g-1"]},  # no answers: never a pair
        },
    }


def test_affinity_counts_topics_groups_and_approved_events_only():
    snap = FormationSnapshot.from_dict(activity_snapshot())
    pairs = affinity_pairs(snap, {"ev-approved"})
    # ra-rb: music + g-1 + ev-approved = 3 (ev-rogue never counts); ra-rd: sports = 1.
    # ra-rc share only the unapproved event (and a client-asserted friend): no pair.
    assert pairs == (("ra", "rb", 3), ("ra", "rd", 1))
    assert affinity_pairs(snap) == (("ra", "rb", 2), ("ra", "rd", 1))  # empty allowlist


def test_affinity_capped_strongest_first():
    refs = [f"r{i:03d}" for i in range(100)]
    raw = {"answers": [{"id": r, "text": "synthetic"} for r in refs],
           "idMap": {r: f"syn-{r}" for r in refs}, "blockedPairs": [],
           "activity": {r: {"topics": ["music"], "groupIds": ["g-1"] if i < 5 else []}
                        for i, r in enumerate(refs)}}
    pairs = affinity_pairs(FormationSnapshot.from_dict(raw))
    assert len(pairs) == MAX_AFFINITY_PAIRS  # 4950 candidate pairs
    assert all(n == 2 for _, _, n in pairs[:10]) and pairs[-1][2] == 1


def test_affinity_reaches_m4_as_refs_and_counts_only():
    raw = activity_snapshot()
    muse = FakeMuse({}, [])
    muse.groups = [["ra", "rb", "rc", "rd", "re"]]
    service = FormationService(muse, DictSource(raw), FixtureGuard(),
                               approved_event_ids={"ev-approved"})
    result = run(service.form("c", "r"))
    assert result.status == "ok"
    m4 = calls(muse, "constellation_formation")[0]["payload"]
    assert m4["affinity"] == [{"memberIds": ["ra", "rb"], "shared": 3},
                              {"memberIds": ["ra", "rd"], "shared": 1}]
    validate(m4, M4_IN)
    blob = json.dumps(muse.calls)
    for secret in ("music", "sports", "g-1", "ev-approved", "ev-rogue", "syn-"):
        assert secret not in blob


def test_matching_port_passes_approved_event_ids():
    class NoGuesses:
        async def prevalence_guesses(self, cycle_id):
            return {}

    muse = FakeMuse({}, [])
    muse.groups = [["ra", "rb", "rc", "rd"]]
    port = build_matching_port(muse=muse, snapshots=DictSource(activity_snapshot()),
                               guesses=NoGuesses(), guard=FixtureGuard(),
                               approved_event_ids=["ev-approved"], precompute_threshold=None)
    assert run(port.form("c"))["status"] == "ok"
    m4 = calls(muse, "constellation_formation")[0]["payload"]
    assert m4["affinity"][0] == {"memberIds": ["ra", "rb"], "shared": 3}


# ---------------------------------------------------------------- re-solve correction

@pytest.mark.parametrize("first,expect", [
    ("garbage", "ids not placed:"),
    ("invalid_json", "output did not match"),
])
def test_resolve_carries_code_generated_correction(first, expect):
    raw, source = questioned_snapshot()
    service, muse = build(raw, source, m4_script=(first, "good"))
    result = run(service.form("c", "r"))
    assert result.status == "ok" and not result.used_fallback
    m4 = calls(muse, "constellation_formation")
    assert [c["correction"] is None for c in m4] == [True, False]
    correction = m4[1]["correction"]
    assert expect in correction and len(correction) <= 600
    texts = [a["text"] for a in raw["answers"]] + [q["text"] for q in raw["questions"]]
    for text in texts:
        assert text not in correction
    lowered = correction.lower()
    assert not any(w in lowered for t in texts for w in t.lower().split() if len(w) > 6)
    if first == "garbage":  # names the missing refs, which are random per-lease ids
        assert any(ref in correction for ref in source.ref_of.values())


def test_correction_counts_violation_kinds():
    text = prompts.m4_correction(["size:0", "size:2", "blocked_pair:1", "placed_twice:3",
                                  "unknown_refs:2"], unplaced=[f"r{i}" for i in range(15)])
    assert "2 groups under size 5 (group 1, 3)" in text
    assert "1 groups containing a blocked pair (group 2)" in text
    assert "3 ids placed more than once" in text and "2 ids that are not in answers" in text
    assert "15 ids not placed" in text and "and 3 more" in text


def test_port_without_correction_kwarg_still_gets_resolve():
    raw, source = questioned_snapshot()

    class OldMuse(FakeMuse):
        async def run(self, *, task, requestId, promptVersion, payload, signal=None):
            return await super().run(task=task, requestId=requestId,
                                     promptVersion=promptVersion, payload=payload)

    muse = OldMuse(source.ref_of, GOOD, m4_script=("garbage", "good"))
    result = run(FormationService(muse, DictSource(raw), FixtureGuard()).form("c"))
    assert result.status == "ok" and not result.used_fallback
    assert len(calls(muse, "constellation_formation")) == 2


# ---------------------------------------------------------------- sharedMeaning guard

@pytest.mark.parametrize("meaning", [
    "They eat in my room so no one sees them",  # 5-word quote of a fixture answer
    "A week that felt depressing for everyone",  # sensitive term
])
def test_failing_shared_meaning_replaced_before_naming(meaning):
    raw, source = questioned_snapshot()
    service, muse = build(raw, source, meaning=meaning)
    result = run(service.form("c", "r"))
    assert result.status == "ok"
    assert all(c.shared_meaning == NEUTRAL_MEANING for c in result.constellations)
    m5 = calls(muse, "constellation_naming")
    assert m5 and all(c["payload"]["sharedMeaning"] == NEUTRAL_MEANING for c in m5)
    assert FixtureGuard().check(NEUTRAL_MEANING, [a["text"] for a in raw["answers"]])["ok"]


def test_clean_shared_meaning_kept():
    raw, source = questioned_snapshot()
    service, muse = build(raw, source, meaning="Finding a corner of the week to breathe")
    result = run(service.form("c", "r"))
    assert {c.shared_meaning for c in result.constellations} == {
        "Finding a corner of the week to breathe"}
