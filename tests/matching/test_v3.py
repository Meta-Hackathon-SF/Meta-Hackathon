"""FormationV3 port: end-to-end offline, synthetic."""

from __future__ import annotations

import asyncio

from server.matching.v3 import FormationV3, InMemoryDayStore


def run(c):
    return asyncio.get_event_loop_policy().new_event_loop().run_until_complete(c)


class Src:
    def __init__(self, texts, blocked=()):
        self.texts, self.blocked = texts, blocked

    async def day_snapshot(self, cycle_id, day):
        refs = list(self.texts)
        return {
            "answers": [{"id": "r-" + p, "text": t, "weight": 1.0} for p, t in self.texts.items()],
            "idMap": {"r-" + p: p for p in refs},
            "blockedPairs": [list(b) for b in self.blocked],
        }


TEXTS = {
    **{f"g{i}": "board games with my floor in the dining hall" for i in range(4)},
    **{f"h{i}": "long quiet hikes with music outdoors" for i in range(3)},
    "z": "competitive chess tournaments",
}


def port(blocked=()):
    return FormationV3(None, Src(TEXTS, blocked), InMemoryDayStore())


def test_place_close_graph_main_sky_flow():
    p = port()
    placed = run(p.dailyPlace("c1", 1, "g0"))
    assert (
        placed["status"] == "ok" and placed["placement"] == "ready" and placed["constellationIds"]
    )
    assert run(p.dailyPlace("c1", 1, "z"))["placement"] == "pending"
    closed = run(p.closeDay("c1", 1))
    assert closed["status"] == "ok" and closed["constellations"] >= 2 and closed["unplaced"] == 1
    run(p.closeDay("c1", 2))
    assert run(p.weekGraph("c1"))["edges"] > 0
    main = run(p.mainConstellation("c1"))
    assert main["status"] == "ok" and main["groups"] >= 1
    sky = run(p.skyLayout("c1"))
    assert sky["stars"]["count"] == 10000 and sky["secondDegree"] is False  # 8 players < 30


def test_views_use_indices_only_and_main_room_index_is_not_star_index():
    p = port()
    run(p.closeDay("c1", 1))
    run(p.closeDay("c1", 2))
    run(p.mainConstellation("c1"))
    v = p.daily_view("c1", 1, "g0", "blue", 8)
    assert v["placement"] == "final" and "g0" not in str(v) and v["constellations"]
    sky = p.my_sky("c1", "g0", {1: "blue", 2: "teal"})
    assert sky["secondDegree"] == [] and "g1" not in str(sky)
    m = p.main_view("c1", "g0", "room-1", "2026-11-15T00:00:00Z", "2026-11-16T00:00:00Z")["main"]
    assert len(m["roomIndices"]) >= 5 and m["myRoomIndex"] in m["roomIndices"]
    assert "g1" not in str(m)
    assert p.main_view("c1", "z", "room-2", "a", "b") == {"main": None, "reason": "no_match"}


def test_blocks_respected_and_failures_are_wire_shaped():
    p = port(blocked=[("g0", "g1")])
    run(p.closeDay("c1", 1))
    for r in p.store.load_days("c1")[1].groups:
        assert not {"g0", "g1"} <= set(r.members)
    assert run(p.mainConstellation("nope"))["status"] == "failed"
    assert run(p.skyLayout("nope"))["error"]["code"] == "NOT_FOUND"


def test_purge_cycle_clears_everything():
    p = port()
    run(p.closeDay("c1", 1))
    p.store.purge_cycle("c1")
    assert p.store.load_days("c1") == {} and p.store.load_main("c1") is None


class ThemeMuse:
    """Fake Muse: M3 returns paraphrase themes that share no keywords; M4 returns one group."""

    def __init__(self, themes, m4=None):
        self.themes, self.m4 = themes, m4

    async def run(self, *, task, requestId, promptVersion, payload, **_):
        ev = {
            "callType": "M3" if task == "theme_discovery" else "M4",
            "model": "fake",
            "source": "replay",
            "generatedAt": "2026-11-14T20:00:00Z",
            "latencyMs": 1,
        }
        if task == "theme_discovery":
            refs = {a["id"]: a["id"] for a in payload["answers"]}
            out = {
                "themes": [
                    {
                        "id": f"t{i}",
                        "label": "x",
                        "description": "y",
                        "memberIds": [r for r in m if r in refs],
                    }
                    for i, m in enumerate(self.themes)
                ]
            }
        else:
            out = {
                "constellations": [
                    {"memberIds": g, "sharedMeaning": "same", "confidence": 0.9} for g in self.m4
                ]
            }
        return {"output": out, "evidence": ev}


PARAPHRASE = {
    "a": "i eat in my room alone",
    "b": "cooking for one is sad",
    "c": "dinner by myself again",
    "d": "no one to eat with",
    "e": "meals alone at my desk",
    "x": "chess",
    "y": "hiking",
    "w": "pottery",
}


def test_daily_uses_muse_theme_members_even_when_words_differ():
    muse = ThemeMuse([["r-a", "r-b", "r-c", "r-d", "r-e"]])
    v3 = FormationV3(muse, Src(PARAPHRASE), InMemoryDayStore())
    out = run(v3.closeDay("c1", 1))
    rec = v3.store.load_days("c1")[1]
    assert out["constellations"] == 1 and out["evidence"]
    assert set(rec.groups[0].members) == {"a", "b", "c", "d", "e"}


def test_late_answer_does_not_overwrite_closed_day():
    muse = ThemeMuse([["r-a", "r-b", "r-c", "r-d", "r-e"]])
    v3 = FormationV3(muse, Src(PARAPHRASE), InMemoryDayStore())
    run(v3.closeDay("c1", 1))
    run(v3.dailyPlace("c1", 1, "a"))
    rec = v3.store.load_days("c1")[1]
    assert rec.final and set(rec.groups[0].members) == {"a", "b", "c", "d", "e"}


def test_main_never_puts_blocked_pair_together_and_uses_m4_evidence():
    ids = list("abcdefghij")
    texts = {p: "eating alone in the dining hall" for p in ids}
    src = Src(texts, blocked=[("a", "b")])
    muse = ThemeMuse([["r-" + p for p in ids]], m4=[["r-w0", "r-w1", "r-w2", "r-w3", "r-w4"]])
    v3 = FormationV3(muse, src, InMemoryDayStore())
    run(v3.closeDay("c1", 1))
    out = run(v3.mainConstellation("c1"))
    assert out["status"] == "ok"
    for g in v3.store.load_main("c1"):
        assert not ({"a", "b"} <= set(g))
