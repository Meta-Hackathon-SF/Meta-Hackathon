import asyncio, json, sys
import fx
from fx import datasets, prompts

async def main():
    ds = datasets.gold_set()
    payload = prompts.build_m4_payload((), fx.prompt_texts(ds), ())
    spark = fx.make_port("muse-spark-1.3")
    wonder = fx.make_port("muse-wonder-1.0", timeout_s=120, max_attempts=1)
    jobs = [("muse-spark-1.3", spark, 1), ("muse-spark-1.3", spark, 2), ("muse-wonder-1.0", wonder, 1)]
    res = await asyncio.gather(*(fx.run_m4(p, prompts.PROMPT_VERSION_M4, payload, ds, f"e1-{m}-{i}") for m, p, i in jobs))
    rows = []
    for (m, _, i), r in zip(jobs, res):
        r.pop("groups_debug", None)
        rows.append({"model": m, "run": i, "promptVersion": prompts.PROMPT_VERSION_M4, **r})
        print(m, i, r["metrics"], "fallback", r["fallback"], "resolves", r["resolves"], "lat", r["latencyMs"], "$", r["costUsd"],
              [ (j.get("parse"), j.get("rawSizes"), j.get("violations"), j.get("repairedGroups")) for j in r["judge"]], [c.get("error") for c in r["calls"]])
    fx.save("E1_baseline_truth", rows, {"keywordBaseline": fx.baseline_metrics(ds), "dataset": "repo gold set, 30 players, random refs"})
    print(fx.spend())
asyncio.run(main())
