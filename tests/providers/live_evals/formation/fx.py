"""Formation experiments runner. Writes metrics only (no prompts, no model output text
except short sharedMeaning labels truncated to 60 chars)."""
from __future__ import annotations

import asyncio
import json
import sys
import time
from collections import Counter
from itertools import combinations
from pathlib import Path

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).parent))

from evalkit import BudgetExceeded, ledger_calls, ledger_total, live_port  # noqa: E402

import fx_data as datasets  # noqa: E402
from server.matching import prompts  # noqa: E402
from server.matching.baseline import baseline_groups, similarity_matrix  # noqa: E402
from server.matching.evaluation import pair_metrics  # noqa: E402
from server.matching.models import PromptText, pair  # noqa: E402
from server.matching.muse_specs import register_formation_specs  # noqa: E402
from server.matching.repair import repair_proposal  # noqa: E402
from server.matching.validation import violations  # noqa: E402
from server.privacy.activity import SAFE_TOPICS  # noqa: E402
from server.providers import MuseRequest, TaskSpec  # noqa: E402
from server.providers.contract import (  # noqa: E402
    _THEMES, OUT_SCHEMAS, _arr, _ID, _obj, _str,
)

AGENT = "A-formation"
CAP = 2.00
OUT = Path(__file__).with_name("results.json")
SEM = asyncio.Semaphore(3)

PV_Q = "m4.exp.q1"
PV_ACT = "m4.exp.act1"

M4_Q_INSTRUCTIONS = prompts.M4_INSTRUCTIONS + (
    " Each answer carries a questionId; questions gives the question text. Read every answer "
    "as a reply to its question: a short answer such as 'nobody' or 'every day' means "
    "different things under different questions. Group by what each answer means in the "
    "context of its question, not by shared words. Never quote questions or answers in "
    "sharedMeaning.")
M4_ACT_INSTRUCTIONS = prompts.M4_INSTRUCTIONS + (
    " activity holds optional soft hints for players who opted in: allowlisted interest "
    "topics and opaque Group/Event ids (two people sharing an id are in the same Group or "
    "Event). Meaning comes first: never split people whose answers clearly share a meaning, "
    "and never join people whose answers clearly differ, because of activity. Use activity "
    "only to break ties between groupings that are equally good by meaning. Never mention "
    "activity, topics, Groups or Events in sharedMeaning.")

ANSWER_Q = _obj({"id": _ID, "text": _str(500),
                 "weight": {"type": "number", "minimum": 0, "maximum": 1.1},
                 "questionId": _ID}, optional=("weight",))
M4_Q_IN = _obj({
    "themes": _THEMES,
    "answers": _arr(ANSWER_Q, 400, 1),
    "questions": _arr(_obj({"questionId": _ID, "text": _str(300)}), 10),
    "blockedPairs": _arr(_arr(_ID, 2, 2), 2000),
})
M4_ACT_IN = _obj({
    "themes": _THEMES,
    "answers": _arr(_obj({"id": _ID, "text": _str(500),
                          "weight": {"type": "number", "minimum": 0, "maximum": 1.1}},
                         optional=("weight",)), 400, 1),
    "blockedPairs": _arr(_arr(_ID, 2, 2), 2000),
    "activity": _arr(_obj({
        "id": _ID,
        "topics": _arr({"type": "string", "enum": sorted(SAFE_TOPICS)}, 14),
        "groupIds": _arr(_ID, 50),
        "eventIds": _arr(_ID, 50),
    }), 400),
})


def make_port(model: str, timeout_s: float = 120, max_attempts: int = 2):
    port, reg = live_port(agent=AGENT, model=model, effort="low", cap_usd=CAP, timeout_s=timeout_s,
                          max_attempts=max_attempts)
    register_formation_specs(reg)
    out = OUT_SCHEMAS["constellation_formation"]
    reg.register(TaskSpec("constellation_formation", PV_Q, M4_Q_INSTRUCTIONS, out,
                          "constellation_formation", input_schema=M4_Q_IN))
    reg.register(TaskSpec("constellation_formation", PV_ACT, M4_ACT_INSTRUCTIONS, out,
                          "constellation_formation", input_schema=M4_ACT_IN))
    return port


def trace_for(port, rid: str) -> dict:
    for e in port.reasoning_trace.list(limit=300):
        if e.get("requestId") == rid:
            return {k: e.get(k) for k in ("outcome", "attempts", "latencyMs", "inputTokens",
                                          "outputTokens", "reasoningTokens", "estCostUsd")}
    return {}


async def call(port, task: str, pv: str, payload: dict, rid: str):
    if ledger_total(AGENT) >= CAP - 0.05:
        raise BudgetExceeded("agent near cap")
    async with SEM:
        t0 = time.monotonic()
        try:
            res = await port.run(MuseRequest(task=task, request_id=rid, prompt_version=pv,
                                             payload=payload))
            out, err = res.output, None
        except BudgetExceeded:
            raise
        except Exception as exc:  # noqa: BLE001
            out, err = None, f"{type(exc).__name__}:{getattr(exc, 'kind', '')}"
        wall = int((time.monotonic() - t0) * 1000)
    return out, err, {"wallMs": wall, **trace_for(port, rid)}


def prompt_texts(ds) -> list[PromptText]:
    return [PromptText(a["id"], a["text"], a.get("weight", 1.0)) for a in ds["answers"]]


def judge(output, ds):
    """Mimic FormationService._groups parse: strict parse -> valid? -> repair."""
    known = set(ds["gold"])
    texts = prompt_texts(ds)
    sim = similarity_matrix(texts)
    try:
        proposal = prompts.parse_m4(output, known, allow_unknown_refs=True)
    except Exception as exc:  # noqa: BLE001
        return None, {"parse": f"fail:{getattr(exc, 'path', '')}"}
    groups = [c[0] for c in proposal]
    counts = Counter(r for g in groups for r in g)
    info = {
        "parse": "ok",
        "rawSizes": sorted(len(g) for g in groups),
        "violations": violations(groups, known, []),
        "unknownRefs": len(set(counts) - known),
        "missingRefs": len(known - set(counts)),
        "placedTwice": sum(1 for c in counts.values() if c > 1),
        "rawMetrics": pair_metrics([[r for r in g if r in known] for g in groups],
                                   ds["gold"]).to_wire(),
        "meanings": [c[1][:60] for c in proposal],
        "confidences": [round(c[2], 2) for c in proposal],
    }
    if not info["violations"]:
        info["repairedGroups"] = 0
        return [tuple(g) for g in groups], info
    fixed = repair_proposal(proposal, sorted(known), [], sim)
    if fixed is None:
        info["repairedGroups"] = None
        return None, info
    info["repairedGroups"] = sum(fixed.touched)
    info["movedByRepair"] = fixed.moved_refs
    return [tuple(g) for g in fixed.groups], info


async def run_m4(port, pv: str, payload: dict, ds, rid: str) -> dict:
    """One formation attempt + one re-solve (production M4_ATTEMPTS=2), then fallback."""
    calls, final, infos = [], None, []
    for attempt in range(2):
        out, err, meta = await call(port, "constellation_formation", pv, payload, f"{rid}:a{attempt}")
        calls.append({**meta, "error": err})
        if out is None:
            infos.append({"parse": "provider_error"})
            continue
        groups, info = judge(out, ds)
        infos.append(info)
        if groups is not None:
            final = groups
            break
    fallback = final is None
    if fallback:
        final = list(baseline_groups(prompt_texts(ds)))
    return {"groups": [list(g) for g in final], "fallback": fallback, "resolves": len(calls) - 1,
            "calls": calls, "judge": infos,
            "metrics": pair_metrics(final, ds["gold"]).to_wire(),
            "latencyMs": sum(c.get("wallMs", 0) for c in calls),
            "costUsd": round(sum(c.get("estCostUsd") or 0 for c in calls), 5)}


def baseline_metrics(ds) -> dict:
    return pair_metrics(baseline_groups(prompt_texts(ds)), ds["gold"]).to_wire()


def save(exp: str, rows: list[dict], extra: dict | None = None) -> None:
    data = json.loads(OUT.read_text()) if OUT.exists() else {}
    entry = data.setdefault(exp, {"runs": []})
    entry["runs"].extend(rows)
    if extra:
        entry.update(extra)
    data["_spend"] = {"agentUsd": ledger_total(AGENT), "agentCalls": ledger_calls(AGENT)}
    OUT.write_text(json.dumps(data, indent=1))


def coassign(groups) -> dict[str, set[str]]:
    m = {}
    for g in groups:
        for r in g:
            m[r] = set(g) - {r}
    return m


def moved(a, b) -> int:
    """Players whose co-member set changed (Jaccard < 0.5) between two partitions."""
    ca, cb = coassign(a), coassign(b)
    n = 0
    for r in ca:
        x, y = ca[r], cb.get(r, set())
        j = len(x & y) / len(x | y) if x | y else 1.0
        n += j < 0.5
    return n


def subset_metrics(groups, gold, members) -> dict:
    sub = [[r for r in g if r in members] for g in groups]
    return pair_metrics([g for g in sub if g], {r: gold[r] for r in members}).to_wire()


def spend() -> str:
    return f"agent ${ledger_total(AGENT):.4f} calls={ledger_calls(AGENT)} global ${ledger_total():.4f}"
