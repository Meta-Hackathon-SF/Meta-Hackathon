import asyncio
from itertools import combinations
import fx
from fx import datasets, prompts, TaskSpec, OUT_SCHEMAS, _obj, _arr, _ID, _THEMES, _str
from e45 import brief
from e3 import extra

PV2 = "m4.exp.act2"
M4_ACT2 = prompts.M4_INSTRUCTIONS + (
    " affinity lists optional soft hints computed by the server for players who opted in: "
    "pairs of ids and how many interests, Groups or Events they share. Meaning comes first: "
    "never split people whose answers clearly share a meaning, and never join people whose "
    "answers clearly differ, because of affinity. Use affinity only to break ties between "
    "groupings that are equally good by meaning. Never mention affinity, interests, Groups or "
    "Events in sharedMeaning.")
M4_ACT2_IN = _obj({
    "themes": _THEMES,
    "answers": _arr(_obj({"id": _ID, "text": _str(500), "weight": {"type": "number", "minimum": 0, "maximum": 1.1}}, optional=("weight",)), 400, 1),
    "blockedPairs": _arr(_arr(_ID, 2, 2), 2000),
    "affinity": _arr(_obj({"memberIds": _arr(_ID, 2, 2), "shared": {"type": "integer", "minimum": 1, "maximum": 20}}), 2000),
})

def affinity(ds):
    sig = {a["id"]: set(a["topics"]) | set(a["groupIds"]) | set(a["eventIds"]) for a in ds["activity"]}
    out = []
    for x, y in combinations(sorted(sig), 2):
        n = len(sig[x] & sig[y])
        if n:
            out.append({"memberIds": [x, y], "shared": n})
    return out

async def main():
    ds = datasets.e3_set()
    texts = fx.prompt_texts(ds)
    base = prompts.build_m4_payload((), texts, ())
    p1 = {**base, "activity": ds["activity"]}
    p2 = {**base, "affinity": affinity(ds)}
    ports = {}
    for m in ("muse-spark-1.3", "muse-ember-1.0"):
        ports[m] = fx.make_port(m)
    # register act2 on each registry: make_port returns port only, so rebuild with registry access
    import evalkit
    for m in list(ports):
        port, reg = evalkit.live_port(agent=fx.AGENT, model=m, effort="low", cap_usd=fx.CAP, timeout_s=120)
        reg.register(TaskSpec("constellation_formation", fx.PV_ACT, fx.M4_ACT_INSTRUCTIONS, OUT_SCHEMAS["constellation_formation"], "constellation_formation", input_schema=fx.M4_ACT_IN))
        reg.register(TaskSpec("constellation_formation", PV2, M4_ACT2, OUT_SCHEMAS["constellation_formation"], "constellation_formation", input_schema=M4_ACT2_IN))
        ports[m] = port
    plan = [("muse-spark-1.3", 3, "after_with_activity", fx.PV_ACT, p1), ("muse-spark-1.3", 4, "after_with_activity", fx.PV_ACT, p1),
            ("muse-spark-1.3", 1, "after_with_affinity_pairs", PV2, p2), ("muse-spark-1.3", 2, "after_with_affinity_pairs", PV2, p2),
            ("muse-ember-1.0", 1, "after_with_affinity_pairs", PV2, p2), ("muse-ember-1.0", 2, "after_with_affinity_pairs", PV2, p2)]
    res = await asyncio.gather(*(fx.run_m4(ports[m], pv, p, ds, f"e3b-{m}-{c}-{i}") for m, i, c, pv, p in plan))
    rows = []
    for (m, i, c, pv, _), r in zip(plan, res):
        r.update(extra(r, ds))
        rows.append({"model": m, "run": i, "condition": c, "promptVersion": pv, **r})
        print(m, c, i, brief(r))
        print("   tie", r["tieVsActivityGold"]["precision"], r["tieVsActivityGold"]["recall"], "strong", r["strongVsMeaningGold"]["precision"], r["strongVsMeaningGold"]["recall"],
              "override", r["strongPairsSameTopicDiffMeaning"], "/", r["strongPairs"], "mixed", r["mixedStrongTieGroups"])
    fx.save("E3_activity", rows, {"affinityPairs": len(p2["affinity"])})
    print(fx.spend())
asyncio.run(main())
