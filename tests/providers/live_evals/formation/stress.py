import asyncio, random
import fx
from fx import datasets, prompts
from e45 import brief
from server.matching.evaluation import gold_snapshot, pair_metrics
from server.matching.validation import violations

def ds32():
    snap, gp = gold_snapshot(32)
    rng = random.Random(7)
    refs = datasets._refs(32, rng)
    m = {a["id"]: refs[i] for i, a in enumerate(snap["answers"])}
    answers = [{"id": m[a["id"]], "text": a["text"], "weight": 1.0} for a in snap["answers"]]
    rng.shuffle(answers)
    gold = {m[o]: gp[p] for o, p in snap["idMap"].items()}
    by = {}
    for r, f in sorted(gold.items()):
        by.setdefault(f, []).append(r)
    blocked = [tuple(sorted(by[f][:2])) for f in list(by)[:3]]  # 3 within-feeling blocks
    return {"answers": answers, "questions": [], "gold": gold}, blocked

async def main():
    ds, blocked = ds32()
    payload = prompts.build_m4_payload((), fx.prompt_texts(ds), blocked)
    ports = {"muse-spark-1.3": fx.make_port("muse-spark-1.3"), "muse-ember-1.0": fx.make_port("muse-ember-1.0"),
             "muse-wonder-1.0": fx.make_port("muse-wonder-1.0", max_attempts=1)}
    plan = [("muse-spark-1.3", 1), ("muse-spark-1.3", 2), ("muse-ember-1.0", 1), ("muse-ember-1.0", 2), ("muse-wonder-1.0", 1)]
    # judge with blocked pairs: patch violations check by wrapping judge
    orig = fx.violations
    fx.violations = lambda g, k, b: orig(g, k, blocked)
    orig_rep = fx.repair_proposal
    fx.repair_proposal = lambda p, e, b, s: orig_rep(p, e, blocked, s)
    res = await asyncio.gather(*(fx.run_m4(ports[m], prompts.PROMPT_VERSION_M4, payload, ds, f"st-{m}-{i}") for m, i in plan))
    rows = []
    for (m, i), r in zip(plan, res):
        r["finalViolations"] = orig(r["groups"], set(ds["gold"]), blocked)
        rows.append({"model": m, "run": i, **r})
        print(m, i, brief(r), "final", r["finalViolations"])
    fx.save("X_validity_stress", rows, {"dataset": "gold 32 players (6/6/5/5/5/5 per feeling) + 3 within-feeling blocked pairs", "keywordBaseline": pair_metrics(fx.baseline_groups(fx.prompt_texts(ds), blocked), ds["gold"]).to_wire()})
    print(fx.spend())
asyncio.run(main())
