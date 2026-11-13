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
    assert 3 <= len(m["roomIndices"]) <= 5 and m["myRoomIndex"] in m["roomIndices"]
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
