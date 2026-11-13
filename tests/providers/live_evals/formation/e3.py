import asyncio
from itertools import combinations
import fx
from fx import datasets, prompts
from e45 import brief

def extra(r, ds):
    g = r["groups"]; gold = ds["gold"]; lab = ds["activityLabel"]
    strong = {k for k, v in ds["subset"].items() if v == "strong"}
    tie = {k for k, v in ds["subset"].items() if v == "tie"}
    pairs = [(a, b) for grp in g for a, b in combinations(sorted(grp), 2) if a in strong and b in strong]
    override = sum(1 for a, b in pairs if lab[a] == lab[b] and gold[a] != gold[b])
    cross = sum(1 for grp in g if {ds["subset"][x] for x in grp} == {"strong", "tie"})
    return {"tieVsActivityGold": fx.subset_metrics(g, gold, tie), "strongVsMeaningGold": fx.subset_metrics(g, gold, strong),
            "strongPairsSameTopicDiffMeaning": override, "strongPairs": len(pairs), "mixedStrongTieGroups": cross}

async def main():
    ds = datasets.e3_set()
    texts = fx.prompt_texts(ds)
    p_before = prompts.build_m4_payload((), texts, ())
    p_after = {**p_before, "activity": ds["activity"]}
    ports = {"muse-spark-1.3": fx.make_port("muse-spark-1.3"), "muse-ember-1.0": fx.make_port("muse-ember-1.0")}
    plan = []
    for m in ports:
        for i in (1, 2):
            plan.append((m, i, "before_answers_only", prompts.PROMPT_VERSION_M4, p_before))
            plan.append((m, i, "after_with_activity", fx.PV_ACT, p_after))
    res = await asyncio.gather(*(fx.run_m4(ports[m], pv, p, ds, f"e3-{m}-{c}-{i}") for m, i, c, pv, p in plan))
    rows = []
    for (m, i, c, pv, _), r in zip(plan, res):
        r.update(extra(r, ds))
        rows.append({"model": m, "run": i, "condition": c, "promptVersion": pv, **r})
    by = {(r["model"], r["condition"], r["run"]): r for r in rows}
    for m in ports:
        for i in (1, 2):
            by[(m, "after_with_activity", i)]["movedVsBefore"] = fx.moved(by[(m, "before_answers_only", i)]["groups"], by[(m, "after_with_activity", i)]["groups"])
        by[(m, "before_answers_only", 2)]["movedNoiseBeforeRun1vs2"] = fx.moved(by[(m, "before_answers_only", 1)]["groups"], by[(m, "before_answers_only", 2)]["groups"])
        by[(m, "after_with_activity", 2)]["movedNoiseAfterRun1vs2"] = fx.moved(by[(m, "after_with_activity", 1)]["groups"], by[(m, "after_with_activity", 2)]["groups"])
    for r in rows:
        print(r["model"], r["condition"], r["run"], brief(r))
        print("   tie", r["tieVsActivityGold"]["precision"], r["tieVsActivityGold"]["recall"], "strong", r["strongVsMeaningGold"]["precision"], r["strongVsMeaningGold"]["recall"],
              "override", r["strongPairsSameTopicDiffMeaning"], "/", r["strongPairs"], "mixed", r["mixedStrongTieGroups"],
              "moved", r.get("movedVsBefore"), r.get("movedNoiseBeforeRun1vs2"), r.get("movedNoiseAfterRun1vs2"), r["judge"][-1].get("meanings"))
    fx.save("E3_activity", rows, {"keywordBaseline": fx.baseline_metrics(ds),
            "dataset": "synthetic 30: 15 strong-meaning (3 feelings x5, activity topics cross-cut meaning) + 15 tie (same generic meaning, activity splits into music/outdoors/gaming x5)"})
    print(fx.spend())
if __name__ == "__main__":
    asyncio.run(main())
