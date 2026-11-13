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

from server.matching import closeness, daily, extras
from server.matching.baseline import baseline_groups, similarity_matrix
from server.matching.models import PromptText
from server.matching.v3 import FormationV3, InMemoryDayStore

THEMES = {
    "dining": "eating alone in the dining hall headphones in before class",
    "major": "scared that changing my major late means falling behind everyone",
    "home": "missing home and family more than i admit during midterms",
    "gym": "the gym is the only place my head gets quiet",
    "lab": "late night robotics lab with people who get it",
    "walk": "long walks at night with music to decompress",
}
SIGNALS = [
    ("Answer meaning (Muse M3/M4)", "primary: grouping is decided by meaning; code never overrides it", "n/a"),
    ("Keyword cosine (baseline)", "fallback grouper and the base of brightness", "1.00"),
    ("Catch-up answer weight", "answers after the day count less", "0.60"),
    ("Follow-up bonus", "a clarified answer counts a little more", "+0.10"),
    ("Shared Group boost", f"cap {closeness.GROUP_CAP}", f"{closeness.GROUP_BOOST} each"),
    ("Shared Event boost", f"cap {closeness.EVENT_CAP}", f"{closeness.EVENT_BOOST} each"),
    ("Shared topic boost", f"cap {closeness.TOPIC_CAP}", f"{closeness.TOPIC_BOOST} each"),
    ("All activity boosts", "answers always dominate", f"max {closeness.MAX_BOOST}"),
    ("Main constellation", "2+ shared constellations or similarity >= 0.35", "3-5 people"),
]

bus: "queue.Queue[dict]" = queue.Queue()
history: list[dict] = []
subscribers: list["queue.Queue[dict]"] = []
lock = threading.Lock()


def emit(kind: str, **data) -> None:
    ev = {"t": round(time.time(), 3), "kind": kind, **data}
    with lock:
        history.append(ev)
        del history[:-400]
        for q in subscribers:
            q.put(ev)


class _Src:
    def __init__(self, texts):
        self.texts = texts

    async def day_snapshot(self, cycle_id, day):
        refs = list(self.texts)
        return {
            "answers": [{"id": "r-" + p, "text": t, "weight": 1.0} for p, t in self.texts.items()],
            "idMap": {"r-" + p: p for p in refs},
            "blockedPairs": [],
        }


def _population(rng, n):
    keys = list(THEMES)
    return {f"p{i}": THEMES[rng.choice(keys)] + f" {rng.choice(['lately', 'again', 'most days'])}" for i in range(n)}


async def run_cycle(seed: int, n: int) -> None:
    rng = random.Random(seed)
    cycle = f"demo-{seed}"
    emit("cycle", cycle=cycle, players=n, note="SYNTHETIC players. Muse is not called in this dashboard.")
    store = InMemoryDayStore()
    for day in range(1, 6):
        texts = _population(rng, n)
        port = FormationV3(None, _Src(texts), store)
        answers = [PromptText("r-" + p, t) for p, t in texts.items()]

        t0 = time.perf_counter()
        base = baseline_groups(answers, [])
        emit("stage", day=day, stage="keyword baseline", ms=round((time.perf_counter() - t0) * 1000, 1),
             detail=f"{len(base)} fallback groups of 3-5 from keyword cosine")

        t0 = time.perf_counter()
        sim = similarity_matrix(answers)
        top = sorted(sim.values(), reverse=True)
        emit("stage", day=day, stage="pairwise similarity", ms=round((time.perf_counter() - t0) * 1000, 1),
             detail=f"{len(sim)} pairs scored; strongest {top[0]:.2f}, median {top[len(top)//2]:.2f}")

        t0 = time.perf_counter()
        placed = await port.dailyPlace(cycle, day, "p0")
        emit("stage", day=day, stage="instant daily placement", ms=round((time.perf_counter() - t0) * 1000, 1),
             detail=f"placement={placed['placement']} (code only, no model call)")

        t0 = time.perf_counter()
        closed = await port.closeDay(cycle, day)
        emit("stage", day=day, stage="day close", ms=round((time.perf_counter() - t0) * 1000, 1),
             detail=f"{closed['constellations']} constellations, {closed['unplaced']} unplaced; "
                    f"Muse tags: {'used' if closed['evidence'] else 'skipped (keyword tags)'}")
        await asyncio.sleep(0.4)

    t0 = time.perf_counter()
    graph = await port.weekGraph(cycle)
    emit("stage", day="week", stage="co-membership graph", ms=round((time.perf_counter() - t0) * 1000, 1),
         detail=f"{graph['players']} players, {graph['edges']} weighted edges")
    t0 = time.perf_counter()
    main = await port.mainConstellation(cycle)
    emit("stage", day="week", stage="Sunday main constellations", ms=round((time.perf_counter() - t0) * 1000, 1),
         detail=f"{main['groups']} groups of 3-5, {main['unplaced']} unplaced")
    t0 = time.perf_counter()
    sky = await port.skyLayout(cycle)
    emit("stage", day="week", stage="sky layout", ms=round((time.perf_counter() - t0) * 1000, 1),
         detail=f"{sky['stars']['count']} star positions; second degree "
                f"{'on' if sky['secondDegree'] else 'off (under 30 eligible)'}")
    weeks = [{(a, b): 1 for a in range(6) for b in range(a + 1, 6)}]
    weeks = [{(f"p{a}", f"p{b}"): 1 for a in range(7) for b in range(a + 1, 7)}] * 3
    emit("stage", day="week", stage="custom-event cluster finder",
         ms=0.0, detail=f"{len(extras.find_clusters(weeks))} repeat-match cluster(s) found over 3 weeks")
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
:root{color-scheme:dark;--bg:#0b0d12;--card:#141821;--line:#232a38;--tx:#e6e9ef;--sub:#8b93a5;--ok:#4cd7a0;--blue:#4599ff}
body{margin:0;background:var(--bg);color:var(--tx);font:14px/1.45 ui-monospace,SFMono-Regular,Menlo,monospace}
header{padding:16px 20px;border-bottom:1px solid var(--line);display:flex;gap:12px;align-items:center}
h1{font:600 16px system-ui;margin:0}.tag{padding:2px 8px;border:1px solid var(--line);border-radius:4px;color:var(--sub);font-size:12px}
main{display:grid;grid-template-columns:minmax(300px,1fr) minmax(320px,1.4fr);gap:16px;padding:16px 20px}
@media(max-width:860px){main{grid-template-columns:1fr}}
section{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:14px}
h2{font:600 12px system-ui;letter-spacing:.08em;text-transform:uppercase;color:var(--sub);margin:0 0 10px}
table{width:100%;border-collapse:collapse}td{padding:5px 0;border-bottom:1px solid var(--line);vertical-align:top}
td:last-child{text-align:right;color:var(--blue);white-space:nowrap;padding-left:10px}.s{color:var(--sub);font-size:12px}
#log{max-height:70vh;overflow:auto}.row{display:grid;grid-template-columns:54px 1fr 64px;gap:8px;padding:5px 0;border-bottom:1px solid var(--line)}
.ms{text-align:right;color:var(--ok)}.cyc{color:var(--blue);padding:8px 0}
</style>
<header><h1>Facebook Space · backend pipeline</h1><span class=tag>SYNTHETIC players</span><span class=tag>Muse not called</span><span id=st class=tag>connecting</span></header>
<main><section><h2>What decides your constellation</h2><table id=sig></table>
<p class=s>Muse decides grouping by meaning. Code enforces size 3-5, everyone once, no blocked pair, thresholds, no quotes. Brightness is code-only.</p></section>
<section><h2>Live stages</h2><div id=log></div></section></main>
<script>
const SIG=__SIG__;document.getElementById('sig').innerHTML=SIG.map(r=>`<tr><td>${r[0]}<div class=s>${r[1]}</div></td><td>${r[2]}</td></tr>`).join('');
const log=document.getElementById('log'),st=document.getElementById('st');
function add(e){const d=document.createElement('div');
if(e.kind==='stage'){d.className='row';d.innerHTML=`<span class=s>${e.day==='week'?'week':'day '+e.day}</span><span>${e.stage}<div class=s>${e.detail}</div></span><span class=ms>${e.ms} ms</span>`}
else{d.className='cyc';d.textContent=e.kind==='cycle'?`▶ ${e.cycle} · ${e.players} synthetic players`:`✓ ${e.cycle} complete`}
log.prepend(d);while(log.children.length>120)log.lastChild.remove()}
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
            q: "queue.Queue[dict]" = queue.Queue()
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
        body = PAGE.replace("__SIG__", json.dumps(SIGNALS)).encode()
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
