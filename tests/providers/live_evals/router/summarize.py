"""Aggregate D-router results.jsonl + ledger rows into a task x model table."""
import json
import statistics
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).parent
LEDGER = HERE.parent.parent / "evalkit" / "ledger.jsonl"
TASKMAP = {"clarify": "M2", "question_generation": "M6", "event_nudge": "M7",
           "constellation_naming": "M5", "sky_narration": "M8"}

res = defaultdict(list)
for line in (HERE / "results.jsonl").read_text().splitlines():
    r = json.loads(line)
    if r.get("task") in TASKMAP.values():
        res[(r["task"], r["model"], r["effort"])].append(r)

led = defaultdict(list)
for line in LEDGER.read_text().splitlines():
    r = json.loads(line)
    if r.get("agent") == "D-router":
        led[(TASKMAP[r["task"]], r["requestedModel"], r["effort"])].append(r)

print("task model effort | n schemaOK1st accepted | p50s maxs (provider) | $/call | outTok p50")
for key in sorted(set(res) | set(led)):
    rows, lrows = res.get(key, []), led.get(key, [])
    n = len(rows)
    first = sum(1 for r in rows if r.get("provider") == "ok" and r.get("attempts") == 1)
    acc = sum(1 for r in rows if r.get("accepted"))
    lat = [r["latencyMs"] / 1000 for r in lrows if r.get("latencyMs") is not None]
    cost = [r["estCostUsd"] for r in lrows if r.get("estCostUsd") is not None]
    out = [r["outputTokens"] for r in lrows if r.get("outputTokens") is not None]
    print(f"{key[0]} {key[1][5:]} {key[2]} | {n} {first}/{n} {acc}/{n} | "
          f"{statistics.median(lat) if lat else '-':.1f} {max(lat) if lat else 0:.1f} | "
          f"{(sum(cost) / len(cost)) if cost else 0:.5f} | {statistics.median(out) if out else '-'}")
    for r in rows:
        if not r.get("accepted") or r.get("provider") != "ok":
            print("   reject:", r.get("case"), r.get("provider"), r.get("reason") or r.get("rejections") or r.get("source"))
print("D-router total", round(sum(r["estCostUsd"] or 0 for v in led.values() for r in v), 6))
