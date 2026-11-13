# ruff: noqa: E501
"""Matching dashboard: one pair of SYNTHETIC answers walked through Muse and Code, plus a typed log.

    python -m server.matching.dashboard --port 5291          # offline: Muse is not called
    python -m server.matching.dashboard --port 5291 --live   # calls Muse (spends); needs a key in env

Log kinds: READ (input given to Muse), REASON (recorded reasoning trace, not hidden chain of
thought), OUTPUT (what Muse returned), CODE (a guarantee our code enforced). Counts and codes only:
no answer text from the formation run is logged. Stdlib only; nothing is persisted.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import queue
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from server.matching.adaptive import UserWeights, pair_user_weights, user_weights
from server.matching.baseline import cosine, player_vectors, tokens
from server.matching.closeness import (
    EVENT_BOOST,
    EVENT_CAP,
    FAINT_FLOOR,
    GROUP_BOOST,
    GROUP_CAP,
    MAX_BOOST,
)
from server.matching.dashboard_page import PAGE
from server.matching.live_eval import _Guesses, _Snapshots, build_port, synthetic_snapshot
from server.matching.models import MAX_CONSTELLATION_SIZE, MIN_CONSTELLATION_SIZE, PromptText
from server.matching.port import build_matching_port
from server.privacy import OutputGuard

PLAYERS = 30
HISTORY = 120
# (label, player ids). Same-topic players share a theme but few words; the other pair does not.
SCENARIOS = (
    ("same meaning, different words", "I eat dinner alone in my room most nights", "cooking for one feels lonely and quiet"),
    ("different meaning", "I eat dinner alone in my room most nights", "pickup soccer is the best part of my week"),
)

bus: list[dict[str, Any]] = []
subscribers: list[queue.Queue] = []
lock = threading.Lock()


def emit(**event: Any) -> None:
    with lock:
        bus.append(event)
        del bus[:-HISTORY]
        for q in subscribers:
            q.put(event)


def log(kind: str, msg: str, meta: str = "") -> None:
    emit(k=kind, msg=msg, meta=meta)
    time.sleep(0.35)


def _boost(groups: int, events: int) -> float:
    return min(MAX_BOOST, min(GROUP_CAP, groups * GROUP_BOOST) + min(EVENT_CAP, events * EVENT_BOOST))


def _closeness(cos: float, w: UserWeights, boost: float) -> float:
    return min(1.0, cos * w.keyword + w.activity * boost)


def pair_walkthrough(label: str, text_a: str, text_b: str) -> dict[str, Any]:
    """Real tokens, cosine and weights for one pair. Established = same words, 5 answers + activity."""
    vecs = player_vectors([PromptText("a", text_a), PromptText("b", text_b)])
    cos = cosine(vecs["a"], vecs["b"])
    shared = sorted(set(tokens(text_a)) & set(tokens(text_b)))
    med = float(min(len(tokens(text_a)), len(tokens(text_b))))
    new = pair_user_weights(user_weights(1, med, False), user_weights(1, med, False))
    est = pair_user_weights(user_weights(5, med, True), user_weights(5, med, True))
    boost = _boost(1, 1)
    ce, cn = _closeness(cos, est, boost), _closeness(cos, new, boost)
    return {
        "k": "pair", "scenario": label, "a": text_a, "b": text_b, "shared": shared,
        "cosine": cos, "wn": new.to_dict(), "we": est.to_dict(), "boost": boost, "cn": cn, "ce": ce,
        "nsub": "1 answer today, no history, no activity opt-in.",
        "esub": "5 answers this week, activity opted in. Same words.",
        "band": "faint" if ce < FAINT_FLOOR else ("bright" if ce >= 0.5 else "visible"),
    }


def _trace_entries(port: Any) -> list[dict]:
    trace = getattr(getattr(port, "_muse", None), "reasoning_trace", None)
    return list(reversed(trace.list())) if trace is not None else []


def _code_checks(raw: dict, snap: dict) -> list[tuple[str, str, str]]:
    groups = [c["memberIds"] for c in raw["constellations"]]
    players = set(snap["idMap"].values())
    placed = [m for g in groups for m in g]
    blocked = {frozenset(p) for p in snap.get("blockedPairs", [])}
    clash = sum(1 for g in groups for a in g for b in g if a < b and frozenset((a, b)) in blocked)
    sizes = sorted({len(g) for g in groups})
    return [
        ("Group sizes kept inside the allowed range.", f"allowed {MIN_CONSTELLATION_SIZE}-{MAX_CONSTELLATION_SIZE} · seen {sizes}", "size"),
        ("Everyone is placed at most once.", f"{len(placed)} placed · {len(set(placed))} unique · {len(players)} players", "everyone_once"),
        ("Blocked pairs are never put together.", f"{len(blocked)} blocked pair(s) · {clash} clash(es)", "blocked_pair"),
        ("Public text is checked so no answer is quoted.", f"{len(groups)} shared-meaning labels through OutputGuard", "no_quote"),
    ]


async def formation_run(live: bool, a_id: str = "syn-2", b_id: str = "syn-8") -> dict[str, Any]:
    snap = synthetic_snapshot(PLAYERS)
    port = build_port(live, PLAYERS)
    answers = len(snap["answers"])
    log("READ", "Muse is given every player's answers to cluster by meaning.",
        f"{answers} answers · {len(snap['idMap'])} players · task constellation_formation · text sent, not logged")
    matching = build_matching_port(muse=port, snapshots=_Snapshots(snap),
                                   guesses=_Guesses(list(snap["idMap"].values())),
                                   guard=OutputGuard(), precompute_threshold=3)
    started = time.monotonic()
    raw = await matching.form("dash-cycle")
    wall = int((time.monotonic() - started) * 1000)
    if raw["status"] != "ok":
        log("CODE", "Formation failed closed.", str(raw.get("error", {}).get("code", "unknown")))
        return {"called": live, "matched": None}
    by_task: dict[str, list[dict]] = {}
    for e in _trace_entries(port):
        by_task.setdefault(str(e.get("task", "task")), []).append(e)
    for task, entries in by_task.items():
        e = entries[0]
        replay = e.get("source") == "replay"
        who = "Scripted fixture stood in for Muse" if replay else "Muse worked"
        times = f" ×{len(entries)}" if len(entries) > 1 else ""
        log("REASON", f"{who} on {task.replace('_', ' ')}{times}: {e.get('outcome', 'ok')}.",
            f"recorded reasoning trace · prompt {e.get('promptVersion', '?')} · model {e.get('model', '?')} · attempts {e.get('attempts', '?')} · {max(x.get('latencyMs', 0) for x in entries)} ms max")
        for c in e.get("checks", []):
            log("CODE", f"Code check after Muse: {str(c['code']).replace('_', ' ')} ({c['stage']}).", f"count {c['count']}")
    cons = raw["constellations"]
    conf = [c["confidence"] for c in cons if c.get("confidence") is not None]
    log("OUTPUT", f"Muse returned {len(cons)} constellations." if live else f"Scripted fixture returned {len(cons)} constellations. Muse not called (offline).",
        f"mean confidence {sum(conf) / len(conf):.2f} · {len(conf)} scored · {wall} ms wall" if conf else f"{wall} ms wall")
    for msg, meta, _code in _code_checks(raw, snap):
        log("CODE", msg, meta)
    both = next((c for c in cons if a_id in c["memberIds"] and b_id in c["memberIds"]), None)
    return {"called": live, "matched": (both is not None) if live else None,
            "meaning": both["sharedMeaning"] if both else None,
            "confidence": both["confidence"] if both else None}


async def run_cycle(live: bool, n: int) -> None:
    walk = pair_walkthrough(*SCENARIOS[n % len(SCENARIOS)])
    emit(k="mode", msg="live Muse (spends)" if live else "offline, Muse not called")
    result = await formation_run(live)
    emit(**walk, muse=result)


def loop(live: bool, pause: float) -> None:
    n = 0
    while True:
        try:
            asyncio.run(run_cycle(live, n))
        except Exception as exc:  # keep the dashboard alive; show the error class only
            emit(k="CODE", msg="Run failed.", meta=type(exc).__name__)
        n += 1
        time.sleep(pause)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_: Any) -> None:
        pass

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/events":
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            q: queue.Queue = queue.Queue()
            with lock:
                for ev in bus:
                    q.put(ev)
                subscribers.append(q)
            try:
                while True:
                    try:
                        self.wfile.write(f"data: {json.dumps(q.get(timeout=15))}\n\n".encode())
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
    ap.add_argument("--port", type=int, default=5291)
    ap.add_argument("--live", action="store_true", help="call Muse (spends money); needs a key in env")
    a = ap.parse_args()
    if a.live:
        build_port(True, 1)  # fail fast if no key
    threading.Thread(target=loop, args=(a.live, 90.0 if a.live else 25.0), daemon=True).start()
    ThreadingHTTPServer(("127.0.0.1", a.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
