# ruff: noqa: E501  (embedded HTML page)
"""Live backend dashboard: runs the real v3 matching pipeline on SYNTHETIC players in a loop and
streams every stage (timing, counts, signal weights) to a page over SSE.

    python -m server.matching.dashboard --port 5290

Offline and labeled: no Muse call is made (tags fall back to keywords), no real player data exists
here, and nothing is persisted. Private ids never appear: only counts, timings and ref-free stats.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import queue
import random
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from server.matching import extras
from server.matching.adaptive import adaptive_weights
from server.matching.baseline import baseline_groups, similarity_matrix
from server.matching.models import FormationSnapshot, PromptText
from server.matching.v3 import FormationV3, InMemoryDayStore

THEMES = {
    "dining": "eating alone in the dining hall headphones in before class",
    "major": "scared that changing my major late means falling behind everyone",
    "home": "missing home and family more than i admit during midterms",
    "gym": "the gym is the only place my head gets quiet",
    "lab": "late night robotics lab with people who get it",
    "walk": "long walks at night with music to decompress",
}
# Each synthetic day has a different input profile, so the weights visibly move.
PROFILES = {
    1: ("short answers, nobody opted in", 0.0, "short"),
    2: ("short answers, some opted in", 0.35, "short"),
    3: ("richer answers, half opted in", 0.5, "mid"),
    4: ("rich answers, most opted in", 0.8, "rich"),
    5: ("rich answers, everyone opted in", 1.0, "rich"),
}
SHORT = {
    "dining": "eating alone",
    "major": "scared about my major",
    "home": "missing home",
    "gym": "the gym helps",
    "lab": "robotics lab",
    "walk": "night walks",
}
MID = {k: v.split(" before")[0].split(" during")[0] for k, v in THEMES.items()}


bus: queue.Queue[dict] = queue.Queue()
history: list[dict] = []
subscribers: list[queue.Queue[dict]] = []
lock = threading.Lock()


def emit(kind: str, **data) -> None:
    ev = {"t": round(time.time(), 3), "kind": kind, **data}
    with lock:
        history.append(ev)
        del history[:-400]
        for q in subscribers:
            q.put(ev)


class _Src:
    def __init__(self, texts, activity=None):
        self.texts, self.activity = texts, activity or {}

    async def day_snapshot(self, cycle_id, day):
        refs = list(self.texts)
        snap = {
            "answers": [{"id": "r-" + p, "text": t, "weight": 1.0} for p, t in self.texts.items()],
            "idMap": {"r-" + p: p for p in refs},
            "blockedPairs": [],
        }
        if self.activity:
            snap["activity"] = self.activity
        return snap


def _population(rng, n, style, coverage):
    keys = list(THEMES)
    bank = SHORT if style == "short" else MID if style == "mid" else THEMES
    texts, activity = {}, {}
    for i in range(n):
        k = rng.choice(keys)
        texts[f"p{i}"] = bank[k] + f" {rng.choice(['lately', 'again'])}"
        if rng.random() < coverage:
            activity[f"r-p{i}"] = {
                "groupIds": [f"g-{k}"],
                "eventIds": [],
                "friendIds": [],
                "topics": [],
            }
    return texts, activity


async def run_cycle(seed: int, n: int) -> None:
    rng = random.Random(seed)
    cycle = f"demo-{seed}"
    emit(
        "cycle",
        cycle=cycle,
        players=n,
        note="SYNTHETIC players. Muse is not called in this dashboard.",
    )
    store = InMemoryDayStore()
    for day in range(1, 6):
        label, coverage, style = PROFILES[day]
        texts, activity = _population(rng, n, style, coverage)
        port = FormationV3(None, _Src(texts, activity), store)
        snap = FormationSnapshot.from_dict(await _Src(texts, activity).day_snapshot(cycle, day))
        emit("weights", day=day, profile=label, **adaptive_weights(snap).to_dict())
        answers = [PromptText("r-" + p, t) for p, t in texts.items()]

        t0 = time.perf_counter()
        base = baseline_groups(answers, [])
        emit(
            "stage",
            day=day,
            stage="keyword baseline",
            ms=round((time.perf_counter() - t0) * 1000, 1),
            detail=f"{len(base)} fallback groups of 5+ from keyword cosine",
        )

        t0 = time.perf_counter()
        sim = similarity_matrix(answers)
        top = sorted(sim.values(), reverse=True)
        emit(
            "stage",
            day=day,
            stage="pairwise similarity",
            ms=round((time.perf_counter() - t0) * 1000, 1),
            detail=f"{len(sim)} pairs scored; strongest {top[0]:.2f}, median {top[len(top) // 2]:.2f}",
        )

        t0 = time.perf_counter()
        placed = await port.dailyPlace(cycle, day, "p0")
        emit(
            "stage",
            day=day,
            stage="instant daily placement",
            ms=round((time.perf_counter() - t0) * 1000, 1),
            detail=f"placement={placed['placement']} (code only, no model call)",
        )

        t0 = time.perf_counter()
        closed = await port.closeDay(cycle, day)
        emit(
            "stage",
            day=day,
            stage="day close",
            ms=round((time.perf_counter() - t0) * 1000, 1),
            detail=f"{closed['constellations']} constellations, {closed['unplaced']} unplaced; "
            f"Muse tags: {'used' if closed['evidence'] else 'skipped (keyword tags)'}",
        )
        await asyncio.sleep(0.4)

    t0 = time.perf_counter()
    graph = await port.weekGraph(cycle)
    emit(
        "stage",
        day="week",
        stage="co-membership graph",
        ms=round((time.perf_counter() - t0) * 1000, 1),
        detail=f"{graph['players']} players, {graph['edges']} weighted edges",
    )
    t0 = time.perf_counter()
    main = await port.mainConstellation(cycle)
    emit(
        "stage",
        day="week",
        stage="Sunday main constellations",
        ms=round((time.perf_counter() - t0) * 1000, 1),
        detail=f"{main['groups']} groups of 5+, {main['unplaced']} unplaced",
    )
    t0 = time.perf_counter()
    sky = await port.skyLayout(cycle)
    emit(
        "stage",
        day="week",
        stage="sky layout",
        ms=round((time.perf_counter() - t0) * 1000, 1),
        detail=f"{sky['stars']['count']} star positions; second degree "
        f"{'on' if sky['secondDegree'] else 'off (under 30 eligible)'}",
    )
    weeks = [{(a, b): 1 for a in range(6) for b in range(a + 1, 6)}]
    weeks = [{(f"p{a}", f"p{b}"): 1 for a in range(7) for b in range(a + 1, 7)}] * 3
    emit(
        "stage",
        day="week",
        stage="custom-event cluster finder",
        ms=0.0,
        detail=f"{len(extras.find_clusters(weeks))} repeat-match cluster(s) found over 3 weeks",
    )
    emit("done", cycle=cycle)


def loop(n: int) -> None:
    seed = 1
    while True:
        asyncio.run(run_cycle(seed, n))
        seed += 1
        time.sleep(6)


PAGE = """<!doctype html><meta charset=utf-8><title>Facebook Space backend</title>
<meta name=viewport content="width=device-width,initial-scale=1">
<style>
:root{color-scheme:dark;--bg:#0c0f15;--card:#151a24;--line:#262d3b;--tx:#eef1f6;--sub:#9aa3b5;--blue:#4c9bff;--teal:#35d0b0;--amber:#f2b84b}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--tx);font:16px/1.5 system-ui,-apple-system,sans-serif}
header{padding:20px 28px;display:flex;flex-wrap:wrap;gap:10px 14px;align-items:center;border-bottom:1px solid var(--line)}
h1{font-size:20px;margin:0 8px 0 0}.pill{padding:3px 10px;border:1px solid var(--line);border-radius:99px;color:var(--sub);font-size:13px}
.live{color:var(--teal);border-color:#1d5a4c}
main{max-width:1100px;margin:0 auto;padding:24px 28px;display:grid;gap:20px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:20px 22px}
h2{font-size:13px;letter-spacing:.09em;text-transform:uppercase;color:var(--sub);margin:0 0 4px}
.lead{color:var(--sub);margin:0 0 16px;font-size:15px}
.sig{display:grid;grid-template-columns:200px 1fr 56px;gap:14px;align-items:center;margin:14px 0}
.sig b{font-weight:600}.sig small{display:block;color:var(--sub);font-weight:400;font-size:13px}
.bar{height:12px;background:#1d2330;border-radius:6px;overflow:hidden}.bar i{display:block;height:100%;border-radius:6px;transition:width .6s ease}
.num{text-align:right;font-variant-numeric:tabular-nums;font-size:18px;font-weight:600}
.inputs{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:6px}
.chip{background:#1d2330;border-radius:8px;padding:6px 12px;font-size:14px}.chip b{color:var(--tx)}.chip{color:var(--sub)}
.now{font-size:17px;margin:6px 0 14px}
.days{display:flex;gap:6px;margin-top:16px}.d{flex:1;height:8px;border-radius:4px;background:#1d2330}.d.on{background:var(--blue)}.d.cur{background:var(--teal)}
.fixed{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px}
.fx{background:#1d2330;border-radius:10px;padding:12px 14px}.fx b{display:block;font-size:20px}.fx span{color:var(--sub);font-size:13px}
#log .row{display:grid;grid-template-columns:70px 1fr 80px;gap:12px;padding:9px 0;border-bottom:1px solid var(--line);align-items:baseline}
.ms{text-align:right;color:var(--teal);font-variant-numeric:tabular-nums}.sub{color:var(--sub);font-size:14px}
.cyc{color:var(--blue);padding:10px 0;font-weight:600}
</style>
<header><h1>Facebook Space · how matching works</h1><span class=pill>Synthetic players</span><span class=pill>Muse not called here</span><span id=st class="pill live">connecting</span></header>
<main>
<section class=card><h2>Signals that move with the input</h2>
<p class=lead>Muse decides groups by meaning. These are the weights our code adapts to the data, used for brightness and tie-breaks.</p>
<div class=now id=now>Waiting for the first day…</div>
<div class=inputs id=inputs></div>
<div class=sig><b>Keyword evidence<small>trusted more when answers are longer</small></b><div class=bar><i id=bk style="background:var(--blue);width:0"></i></div><div class=num id=nk>–</div></div>
<div class=sig><b>Activity signals<small>Groups, Events, topics; trusted when enough people opted in</small></b><div class=bar><i id=ba style="background:var(--amber);width:0"></i></div><div class=num id=na>–</div></div>
<div class=days id=days></div></section>
<section class=card><h2>Always the same</h2><p class=lead>These never move. They are the guarantees.</p>
<div class=fixed>
<div class=fx><b>Meaning first</b><span>Muse groups by what answers mean</span></div>
<div class=fx><b>5 or more</b><span>people per constellation, no maximum, everyone placed once</span></div>
<div class=fx><b>Answers dominate</b><span>activity boosts capped at +0.30</span></div>
<div class=fx><b>0.6 / +0.1</b><span>catch-up answer weight / follow-up bonus</span></div>
<div class=fx><b>No quotes</b><span>blocked pairs and thresholds enforced by code</span></div></div></section>
<section class=card><h2>Pipeline, live</h2><p class=lead>Each step runs on the real code. Times are measured.</p><div id=log></div></section>
</main>
<script>
const log=document.getElementById('log'),st=document.getElementById('st');
const days=document.getElementById('days');days.innerHTML=[1,2,3,4,5].map(()=>'<div class=d></div>').join('');
const pct=v=>Math.round(v*100)+'%';
function weights(e){
 document.getElementById('now').textContent=`Day ${e.day}: ${e.profile}`;
 document.getElementById('inputs').innerHTML=`<span class=chip>Players <b>${e.players}</b></span><span class=chip>Median answer <b>${e.medianTokens} words</b></span><span class=chip>Opted in <b>${pct(e.optinCoverage)}</b></span>`;
 document.getElementById('bk').style.width=pct(e.keyword);document.getElementById('nk').textContent=e.keyword.toFixed(2);
 document.getElementById('ba').style.width=pct(e.activity);document.getElementById('na').textContent=e.activity.toFixed(2);
 [...days.children].forEach((d,i)=>d.className='d'+(i+1<e.day?' on':i+1===e.day?' cur':''));}
function add(e){
 if(e.kind==='weights'){weights(e);return}
 const d=document.createElement('div');
 if(e.kind==='stage'){d.className='row';d.innerHTML=`<span class=sub>${e.day==='week'?'week':'day '+e.day}</span><span>${e.stage}<div class=sub>${e.detail}</div></span><span class=ms>${e.ms} ms</span>`}
 else{d.className='cyc';d.textContent=e.kind==='cycle'?`${e.cycle} · ${e.players} synthetic players`:`${e.cycle} complete`}
 log.prepend(d);while(log.children.length>60)log.lastChild.remove()}
const es=new EventSource('/events');es.onopen=()=>st.textContent='live';es.onerror=()=>st.textContent='reconnecting';
es.onmessage=m=>add(JSON.parse(m.data));
</script>"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):  # quiet
        pass

    def do_GET(self):
        if self.path.startswith("/events"):
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            q: queue.Queue[dict] = queue.Queue()
            with lock:
                for ev in history[-60:]:
                    q.put(ev)
                subscribers.append(q)
            try:
                while True:
                    try:
                        ev = q.get(timeout=15)
                        self.wfile.write(f"data: {json.dumps(ev)}\n\n".encode())
                    except queue.Empty:
                        self.wfile.write(b": keepalive\n\n")
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                pass
            finally:
                with lock:
                    if q in subscribers:
                        subscribers.remove(q)
            return
        body = PAGE.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=5290)
    ap.add_argument("--players", type=int, default=120)
    a = ap.parse_args()
    threading.Thread(target=loop, args=(a.players,), daemon=True).start()
    ThreadingHTTPServer(("127.0.0.1", a.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
