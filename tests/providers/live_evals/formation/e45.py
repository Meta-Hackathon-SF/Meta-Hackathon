import asyncio, json, sys, time
import fx
from fx import datasets, prompts

def brief(r):
    return (r["metrics"]["precision"], r["metrics"]["recall"], "fb", r["fallback"], "rs", r["resolves"], "lat", r["latencyMs"], "$", r["costUsd"],
            [(j.get("parse"), j.get("rawSizes"), j.get("violations"), j.get("repairedGroups"), j.get("unknownRefs")) for j in r["judge"]], [c.get("error") for c in r["calls"]])

async def e4_run(port, ds, i):
    texts = fx.prompt_texts(ds)
    m3p = prompts.build_m3_payload(texts, [])
    out, err, meta = await fx.call(port, "theme_discovery", prompts.PROMPT_VERSION_M3, m3p, f"e4-m3-{i}")
    themes, m3info = (), {"error": err}
    if out is not None:
        try:
            themes = prompts.parse_m3(out, set(ds["gold"]))
            m3info = {"themes": len(themes), "labels": [t[1][:40] for t in themes],
                      "themeMetrics": fx.pair_metrics([t[3] for t in themes], ds["gold"]).to_wire(),
                      "overlapRefs": sum(len(t[3]) for t in themes) - len({r for t in themes for r in t[3]})}
        except Exception as exc:
            m3info = {"parseError": getattr(exc, "path", str(type(exc)))}
    payload = prompts.build_m4_payload(themes, texts, ())
    r = await fx.run_m4(port, prompts.PROMPT_VERSION_M4, payload, ds, f"e4-m4-{i}")
    r["m3"] = {**meta, **m3info}
    r["sequentialLatencyMs"] = meta["wallMs"] + r["latencyMs"]
    r["costUsd"] = round(r["costUsd"] + (meta.get("estCostUsd") or 0), 5)
    return r

async def main():
    ds = datasets.gold_set()
    payload = prompts.build_m4_payload((), fx.prompt_texts(ds), ())
    spark = fx.make_port("muse-spark-1.3")
    ember = fx.make_port("muse-ember-1.0")
    e5 = [fx.run_m4(ember, prompts.PROMPT_VERSION_M4, payload, ds, f"e5-ember-{i}") for i in (1, 2, 3)]
    e4 = [e4_run(spark, ds, i) for i in (1, 2)]
    res = await asyncio.gather(*e5, *e4)
    e5r, e4r = res[:3], res[3:]
    rows5 = [{"model": "muse-ember-1.0", "run": i + 1, **r} for i, r in enumerate(e5r)]
    rows4 = [{"model": "muse-spark-1.3", "run": i + 1, "condition": "M3->M4 with themes", **r} for i, r in enumerate(e4r)]
    for r in rows5: print("E5 ember", brief(r))
    for r in rows4: print("E4", brief(r), "m3", {k: r["m3"].get(k) for k in ("wallMs","themes","themeMetrics","overlapRefs","estCostUsd","error","parseError")})
    fx.save("E5_model_choice", rows5, {"note": "Spark and Wonder rows are the E1 runs"})
    fx.save("E4_themes_into_m4", rows4, {"note": "M4-alone comparison rows are E1 Spark runs"})
    print(fx.spend())
if __name__ == "__main__":
    asyncio.run(main())
