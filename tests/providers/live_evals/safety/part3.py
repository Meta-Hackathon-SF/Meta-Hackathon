"""M1 robustness with the production spec (register_safety_task) unchanged."""
import asyncio, json, secrets, sys, time
HERE = __file__.rsplit("/", 1)[0]
sys.path.insert(0, HERE)
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))
from evalkit import live_port, ledger_total, BudgetExceeded, LEDGER
from corpus import M1_CASES, M1_HARD
if len(sys.argv) > 2 and sys.argv[2] == "hard": M1_CASES = M1_HARD
from server.privacy.safety import register_safety_task, code_screen, stricter, SAFETY_PROMPT_VERSION
from server.providers import MuseRequest, ProviderError


async def one(port, text, st, sem):
    # identical request shape to SafetyScreener.screen, but always calls Muse so the
    # model's flag is measured even where the code pre-screen would short-circuit
    req = MuseRequest(task="safety_screen", request_id="m1_" + secrets.token_hex(8),
                      prompt_version=SAFETY_PROMPT_VERSION,
                      payload={"text": {"id": "t" + secrets.token_hex(6), "text": text}, "subjectType": st})
    async with sem:
        t0 = time.monotonic()
        try:
            r = await port.run(req)
            flag = r.output.get("flag")
        except ProviderError as e:
            flag = "ERR:" + e.kind
        return flag, time.monotonic() - t0


async def main():
    models = sys.argv[1].split(",")
    sem = asyncio.Semaphore(3)
    report = {}
    for model in models:
        port, reg = live_port(agent="C-safety", model=model, effort="low", cap_usd=0.60, timeout_s=120)
        register_safety_task(reg)
        try:
            res = await asyncio.gather(*(one(port, t, st, sem) for t, st, _ in M1_CASES))
        except BudgetExceeded as e:
            print("BUDGET", e); return
        rows = []
        for (t, st, exp), (flag, lat) in zip(M1_CASES, res):
            code = code_screen(t)
            combined = stricter(code, flag) if flag in ("none", "distress", "harm") else "HOLD(provider)"
            rows.append({"text": t, "expected": exp, "code": code, "muse": flag, "combined": combined,
                         "lat": round(lat, 1)})
        report[model] = rows
        ok_m = sum(r["muse"] == r["expected"] for r in rows)
        ok_c = sum(r["combined"] == r["expected"] for r in rows)
        caught = sum(r["combined"] != "none" for r in rows if r["expected"] != "none")
        n_risk = sum(r["expected"] != "none" for r in rows)
        fp = sum(r["combined"] != "none" for r in rows if r["expected"] == "none")
        lats = sorted(r["lat"] for r in rows)
        print(f"{model}: muse exact {ok_m}/{len(rows)} combined exact {ok_c}/{len(rows)} "
              f"risk caught {caught}/{n_risk} benign flagged {fp}/{len(rows)-n_risk} "
              f"lat median {lats[len(lats)//2]} max {lats[-1]}")
        for r in rows:
            mark = "" if r["combined"] == r["expected"] else "  <-- MISMATCH"
            print(f"  exp={r['expected']:8s} code={r['code']:8s} muse={r['muse']:8s} -> {r['combined']:8s}{mark} | {r['text']}")
    json.dump(report, open(f"{HERE}/part3_{sys.argv[2] if len(sys.argv)>2 else ''}{'_'.join(m.split('-')[1] for m in models)}.json", "w"),
              indent=1, ensure_ascii=False)
    print("C-safety total", ledger_total("C-safety"))

asyncio.run(main())
