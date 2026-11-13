"""D-router: task x model eval through the capped evalkit port. Synthetic inputs only.

usage: run_router.py <phase> [models...]   phase in {m2, m6, m7, m5, m8, probe, all}
Writes per-call metrics (+ short synthetic model strings) to results.jsonl next to this file.
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))
from evalkit import BudgetExceeded, ledger_total, live_port  # noqa: E402

import server.providers.config as pcfg  # noqa: E402
from server.matching import prompts as mprompts  # noqa: E402
from server.matching.muse_specs import register_formation_specs  # noqa: E402
from server.matching.sky import PROMPT_VERSION_M8, allowed_numbers, parse_m8  # noqa: E402
from server.planning import (  # noqa: E402
    ClarifyService, InMemorySelectionStore, NudgeService, PlanningError, QuestionGenerator,
    QuestionService, VenueCatalog, load_default_bank, register_planning_tasks,
)
from server.providers import MuseRequest, ProviderError  # noqa: E402
from tests.planning.doubles import FIXTURES, TestOnlyChat, TestOnlyWeekStart  # noqa: E402

OUT = Path(__file__).with_name("results.jsonl")
AGENT, CAP = "D-router", 0.80
SEM = asyncio.Semaphore(3)

try:
    from server.privacy import OutputGuard
    GUARD, GUARD_NAME = OutputGuard(), "real"
except ImportError:
    from tests.planning.doubles import TestOnlyOutputGuard
    GUARD, GUARD_NAME = TestOnlyOutputGuard(), "test-only"

# Allow probing Spark efforts the config does not list (in-process only, not the repo).
pcfg.MODEL_EFFORTS["muse-spark-1.3"] = frozenset({"minimal", "low", "medium", "high", "max"})

_ports: dict[tuple[str, str], object] = {}


def port_for(model: str, effort: str):
    key = (model, effort)
    if key not in _ports:
        p, reg = live_port(agent=AGENT, model=model, effort=effort, cap_usd=CAP, timeout_s=120)
        register_planning_tasks(reg)
        register_formation_specs(reg)
        _ports[key] = p
    return _ports[key]


def emit(row: dict) -> None:
    row["guard"] = GUARD_NAME
    with OUT.open("a") as fh:
        fh.write(json.dumps(row) + "\n")
    print(json.dumps(row)[:300], flush=True)


class Probe:
    """Wraps the capped port to see provider outcome behind services that swallow errors."""

    def __init__(self, inner):
        self.inner, self.outcome, self.attempts = inner, None, None

    async def run(self, request):
        try:
            r = await self.inner.run(request)
            self.outcome, self.attempts = "ok", r.attempts
            return r
        except ProviderError as e:
            self.outcome, self.attempts = f"err:{e.kind}", getattr(e, "attempts", None)
            raise


def guard_ok(text, against):
    v = GUARD.check(text, list(against))
    return isinstance(v, dict) and v.get("ok") is True


# ---------------------------------------------------------------- M2
BANK = load_default_bank()
M2_CASES = [
    ("vague", "q-joys-small-win", "idk, coffee I guess"),
    ("vague", "q-routine-meals", "the usual"),
    ("vague", "q-hopes-weekend", "sleeping lol"),
    ("vague", "q-interests-rabbit-hole", "youtube stuff"),
    ("vague", "q-belonging-almost", "a thing"),
    ("specific", "q-routine-meals", "Mostly the dining hall corner table with headphones in, usually on my own between labs"),
    ("specific", "q-joys-small-win", "My lab partner saved me a seat and we split a bag of clementines before the quiz"),
    ("specific", "q-hopes-try", "I want to try the climbing wall but I keep chickening out because I don't know anyone who goes"),
    ("specific", "q-routine-between", "Third floor of the library by the window, reheating noodles and doing problem sets"),
    ("vague", "q-values-changed-mind", "a lot of things"),
]


async def m2(model, effort, idx, label, qid, text):
    probe = Probe(port_for(model, effort))
    svc = ClarifyService(probe, GUARD)
    async with SEM:
        t = time.monotonic()
        res = await svc.decide(BANK.get(qid), text, f"drouter-m2-{model}-{effort}-{idx}")
        wall = round(time.monotonic() - t, 1)
    emit({"task": "M2", "model": model, "effort": effort, "case": f"{label}:{qid}", "provider": probe.outcome,
          "attempts": probe.attempts, "source": res.source, "needsFollowup": res.output.get("needsFollowup"),
          "accepted": res.source == "muse", "wallS": wall,
          "text": (res.output.get("question") if res.source == "muse" else None)})


# ---------------------------------------------------------------- M6
async def m6(model, effort, idx):
    probe = Probe(port_for(model, effort))
    gen = QuestionGenerator(probe, GUARD, QuestionService(BANK, InMemorySelectionStore(), TestOnlyWeekStart()))
    mixes = [{"belonging": 2, "small_joys": 1, "routine": 1}, {"hopes": 1, "interests": 2, "values": 1}]
    sigs = [[{"tag": "music", "share": 0.45}, {"tag": "coffee", "share": 0.35}, {"tag": "outdoors", "share": 0.3},
             {"tag": "study", "share": 0.6}],
            [{"tag": "cooking", "share": 0.4}, {"tag": "gaming", "share": 0.5}, {"tag": "sports", "share": 0.25}]]
    async with SEM:
        t = time.monotonic()
        try:
            r = await gen.generate(count=3, request_id=f"drouter-m6-{model}-{idx}", category_mix=mixes[idx % 2],
                                   aggregate_signals=sigs[idx % 2],
                                   recent_question_ids=[q["questionId"] for q in BANK.questions][:12])
            row = {"kept": len(r.pending), "rejected": r.rejected, "rejections": r.rejections,
                   "grounded": sum(1 for b in r.basis if b["matchedSignals"]),
                   "text": [q["text"] for q in r.pending]}
        except PlanningError as e:
            row = {"kept": 0, "error": e.code}
        wall = round(time.monotonic() - t, 1)
    emit({"task": "M6", "model": model, "effort": effort, "case": idx, "provider": probe.outcome,
          "attempts": probe.attempts, "accepted": row.get("kept", 0) > 0, "wallS": wall, **row})


# ---------------------------------------------------------------- M7
WEEK = json.loads((FIXTURES / "week-sample.json").read_text())
ANSWERS = [a["text"] for a in WEEK["answers"] if a["playerId"] in ("p-maya", "p-dev", "p-jordan")]
MEANINGS = [
    "They end up having most meals on their own and would rather not.",
    "They all unwind with music late at night and want someone to share it with.",
    "They want to get outside more but have not found people to go with.",
]


async def m7(model, effort, idx):
    probe = Probe(port_for(model, effort))
    meaning = MEANINGS[idx % 3]

    async def context(_cid):
        return {"constellationId": "c-live", "roomId": "room-live", "memberCount": 3, "roomOpen": True,
                "sharedMeaning": meaning, "againstAnswers": ANSWERS}

    now = datetime(2026, 11, 18, 18, 0, tzinfo=timezone.utc)
    svc = NudgeService(probe, GUARD, VenueCatalog.load(), context, TestOnlyChat(), now=lambda: now)
    async with SEM:
        t = time.monotonic()
        o = await svc.propose_detailed(f"c-{idx}", request_id=f"drouter-m7-{model}-{idx}",
                                       window=(now, now + timedelta(hours=72)))
        wall = round(time.monotonic() - t, 1)
    n = o.nudge or {}
    emit({"task": "M7", "model": model, "effort": effort, "case": idx, "provider": probe.outcome,
          "attempts": probe.attempts, "reason": o.reason, "accepted": o.reason == "ok", "wallS": wall,
          "text": {"title": n.get("title"), "placeId": n.get("placeId"), "why": n.get("why")} if n else None})


# ---------------------------------------------------------------- M5
M5_CASES = [
    ("They end up having most meals on their own and would rather not.", 3),
    ("They all unwind with music late at night and want someone to share it with.", 4),
    ("They feel a step behind in class and quietly push through anyway.", 5),
]
SYN_ANSWERS = ["I eat dinner in my room most nights", "cooking for one feels lonely",
               "late night coding with music on", "I feel behind everyone in my classes"]


async def m5(model, effort, idx):
    meaning, size = M5_CASES[idx % 3]
    port = port_for(model, effort)
    async with SEM:
        t = time.monotonic()
        prov, attempts, ok, text, why = None, None, False, None, None
        try:
            r = await port.run(MuseRequest(task="constellation_naming", request_id=f"drouter-m5-{model}-{idx}",
                                           prompt_version=mprompts.PROMPT_VERSION_M5,
                                           payload=mprompts.build_m5_payload(meaning, size)))
            prov, attempts = "ok", r.attempts
            try:
                name, shape, color = mprompts.parse_m5(r.output, size)
                text = f"{name} [{shape}/{color}]"
                ok = guard_ok(name, SYN_ANSWERS)
                why = None if ok else "guard"
            except Exception as e:  # noqa: BLE001
                why = f"parse:{type(e).__name__}"
        except ProviderError as e:
            prov, attempts = f"err:{e.kind}", getattr(e, "attempts", None)
        wall = round(time.monotonic() - t, 1)
    emit({"task": "M5", "model": model, "effort": effort, "case": idx, "provider": prov, "attempts": attempts,
          "accepted": ok, "reason": why, "wallS": wall, "text": text})


# ---------------------------------------------------------------- M8
M8_CASES = [
    {"eligiblePlayers": 30, "constellations": 8, "themes": [
        {"label": "Eating alone more than they want", "count": 11, "actualPercent": 37, "guessedPercentMedian": 12},
        {"label": "Missing friends from home", "count": 9, "actualPercent": 30, "guessedPercentMedian": 45}]},
    {"eligiblePlayers": 18, "constellations": 5, "themes": [
        {"label": "Feeling behind in classes", "count": 7, "actualPercent": 39, "guessedPercentMedian": 20}]},
    {"eligiblePlayers": 42, "constellations": 11, "themes": [
        {"label": "Late-night music", "count": 14, "actualPercent": 33, "guessedPercentMedian": 25},
        {"label": "Quiet weekends", "count": 16, "actualPercent": 38, "guessedPercentMedian": 15},
        {"label": "Pickup games with strangers", "count": 6, "actualPercent": 14, "guessedPercentMedian": 22}]},
]


async def m8(model, effort, idx):
    payload = M8_CASES[idx % 3]
    port = port_for(model, effort)
    async with SEM:
        t = time.monotonic()
        prov, attempts, ok, text, why = None, None, False, None, None
        try:
            r = await port.run(MuseRequest(task="sky_narration", request_id=f"drouter-m8-{model}-{idx}",
                                           prompt_version=PROMPT_VERSION_M8, payload=payload))
            prov, attempts = "ok", r.attempts
            try:
                lines = parse_m8(r.output, allowed_numbers(payload))
                text = list(lines)
                ok = all(guard_ok(line, SYN_ANSWERS) for line in lines)
                why = None if ok else "guard"
            except Exception as e:  # noqa: BLE001
                why = f"parse:{type(e).__name__}:{getattr(e, 'path', '')}"
        except ProviderError as e:
            prov, attempts = f"err:{e.kind}", getattr(e, "attempts", None)
        wall = round(time.monotonic() - t, 1)
    emit({"task": "M8", "model": model, "effort": effort, "case": idx, "provider": prov, "attempts": attempts,
          "accepted": ok, "reason": why, "wallS": wall, "text": text})


async def safe(coro):
    try:
        await coro
    except BudgetExceeded as e:
        emit({"task": "budget", "error": str(e)})


async def main():
    phase = sys.argv[1]
    models = sys.argv[2:] or ["muse-ember-1.0", "muse-spark-1.3"]
    jobs = []
    for model in models:
        if phase in ("m2", "all"):
            jobs += [m2(model, "low", i, *c) for i, c in enumerate(M2_CASES)]
        if phase in ("m6", "all"):
            jobs += [m6(model, "low", i) for i in range(2)]
        if phase in ("m7", "all"):
            jobs += [m7(model, "low", i) for i in range(3)]
        if phase in ("m5", "all"):
            jobs += [m5(model, "low", i) for i in range(3)]
        if phase in ("m8", "all"):
            jobs += [m8(model, "low", i) for i in range(3)]
    if phase == "probe":
        jobs += [m2("muse-spark-1.3", "minimal", 90, *M2_CASES[5]), m2("muse-spark-1.3", "max", 91, *M2_CASES[5])]
        jobs += [m2("muse-ember-1.0", "minimal", i, *c) for i, c in enumerate(M2_CASES)]
    if phase == "wonder":  # reduced M2 set for Wonder cost/latency; player-facing tasks first
        w = "muse-wonder-1.0"
        jobs += [m5(w, "low", i) for i in range(3)] + [m8(w, "low", i) for i in range(3)]
        jobs += [m7(w, "low", i) for i in range(3)] + [m6(w, "low", i) for i in range(2)]
        jobs += [m2(w, "low", i, *M2_CASES[i]) for i in (0, 1, 4, 5, 6, 7)]
    await asyncio.gather(*(safe(j) for j in jobs))
    print("D-router total", ledger_total(AGENT), "global", ledger_total())


if __name__ == "__main__":
    asyncio.run(main())
