"""Run one classifier pass: python run.py <label> <model> [subset] [batch]"""
import asyncio, json, random, sys, time
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))
from evalkit import live_port, ledger_total, BudgetExceeded, LEDGER  # noqa: E402
from server.providers import MuseRequest, ProviderError  # noqa: E402
from corpus import CORPUS, WONDER_SUBSET  # noqa: E402
import os  # noqa: E402
if os.environ.get('CORPUS') == 'v2':
    from corpus_v2 import CORPUS_V2 as CORPUS  # noqa: E402
from classifier import spec, validate_batch, PROMPT_VERSION  # noqa: E402

label, model = sys.argv[1], sys.argv[2]
subset = sys.argv[3] if len(sys.argv) > 3 else "all"
batch_size = int(sys.argv[4]) if len(sys.argv) > 4 else 8
temperature = None if "notemp" in label else 0.0

rows = [r for r in CORPUS if subset == "all" or r["id"] in WONDER_SUBSET]
rng = random.Random(label.split("-")[0] + subset)  # same order for repeat runs of a model
rows = rows[:]
rng.shuffle(rows)
opaque = {f"t{i:03d}": r["id"] for i, r in enumerate(rows)}  # ids sent to Muse reveal nothing
back = list(opaque.items())
batches = [back[i:i + batch_size] for i in range(0, len(back), batch_size)]
text_of = {r["id"]: r["text"] for r in CORPUS}


async def main():
    port, reg = live_port(agent="B-topics", model=model, effort="low", cap_usd=0.60, timeout_s=120)
    reg.register(spec(temperature))
    sem = asyncio.Semaphore(3)
    results, batch_stats = {}, []
    n_before = len(LEDGER.read_text().splitlines())

    async def one(bi, batch):
        payload = {"texts": [{"id": oid, "text": text_of[gid]} for oid, gid in batch]}
        async with sem:
            t0 = time.monotonic()
            try:
                res = await port.run(MuseRequest(task="safety_screen", request_id=f"{label}-b{bi}",
                                                 prompt_version=PROMPT_VERSION, payload=payload))
            except (ProviderError, BudgetExceeded) as exc:
                kind = getattr(exc, "kind", type(exc).__name__)
                batch_stats.append({"batch": bi, "ok": False, "kind": kind, "wallMs": int((time.monotonic() - t0) * 1000)})
                for oid, gid in batch:
                    results[gid] = {"kept": [], "sensitive": False, "raw": [], "failed": True}
                return
        out, stats = validate_batch([o for o, _ in batch], res.output)
        batch_stats.append({"batch": bi, "ok": True, "attempts": res.attempts, "latencyMs": res.evidence["latencyMs"],
                            "wallMs": int((time.monotonic() - t0) * 1000), "model": res.evidence["model"], **stats})
        for oid, gid in batch:
            results[gid] = out[oid]

    await asyncio.gather(*(one(i, b) for i, b in enumerate(batches)))
    ledger_rows = [json.loads(l) for l in LEDGER.read_text().splitlines()[n_before:]]
    mine = [r for r in ledger_rows if r.get("agent") == "B-topics" and r.get("requestedModel") == model]
    summary = {"label": label, "model": model, "subset": subset, "batchSize": batch_size, "n": len(rows),
               "costUsd": round(sum(r.get("estCostUsd") or 0 for r in mine), 6),
               "inputTokens": sum(r.get("inputTokens") or 0 for r in mine),
               "outputTokens": sum(r.get("outputTokens") or 0 for r in mine),
               "batches": sorted(batch_stats, key=lambda b: b["batch"])}
    (HERE / "runs" / f"{label}.json").write_text(json.dumps({"summary": summary, "results": results}, indent=1))
    print(json.dumps({k: v for k, v in summary.items() if k != "batches"}))
    for b in summary["batches"]:
        print(json.dumps(b))
    print("B-topics total", ledger_total("B-topics"))

asyncio.run(main())
