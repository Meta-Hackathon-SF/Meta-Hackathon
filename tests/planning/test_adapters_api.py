"""Sync adapters for the cycle service and the operator router (offline)."""
from __future__ import annotations

import asyncio
import json
import unittest
from datetime import date

from server.planning import (
    ClarifyService, CycleQuestionPort, InMemorySelectionStore, NudgeService, QuestionService,
    SyncClarify, VenueCatalog, load_default_bank, register_planning_tasks, run_sync,
)
from server.providers import ProviderError, TaskRegistry
from server.providers.fixture import FixtureMuse, ScriptedTransport

from .doubles import FIXTURES, TestOnlyChat, TestOnlyOutputGuard, TestOnlyWeekStart
from .test_nudges import GOOD, NOW, Context

try:  # the router needs FastAPI (Kai's server dependencies); the adapters do not
    from fastapi import FastAPI, Request
    from fastapi.testclient import TestClient

    from server.planning.api import PlanningRuntime, build_router, install_planning_error_handler
    HAVE_FASTAPI = True
except ImportError:  # pragma: no cover
    HAVE_FASTAPI = False

WEEK = json.loads((FIXTURES / "week-sample.json").read_text())
CYCLE, COMMUNITY = WEEK["cycle"]["cycleId"], WEEK["communityId"]
ASK = {"needsFollowup": True, "question": "What do you like about that corner?"}


def muse(task=None, *steps):
    transport = ScriptedTransport()
    if task:
        transport.queue(task, *steps)
    return FixtureMuse(register_planning_tasks(TaskRegistry()), transport), transport


class CycleAdapterTests(unittest.TestCase):
    def test_sync_question_port_matches_the_cycle_service_shape(self):
        svc = QuestionService(load_default_bank(), InMemorySelectionStore(), TestOnlyWeekStart())
        port = CycleQuestionPort(svc, today=lambda: date(2026, 11, 12))
        week = port.select_week("cycle-new", COMMUNITY)
        self.assertEqual([d["day"] for d in week], [1, 2, 3, 4, 5])
        self.assertEqual(week[0]["date"], "2026-11-09")  # Monday of the current week; the cycle overwrites it
        self.assertEqual(week[0]["question"]["sensitivity"], "low")
        self.assertEqual(port.select_week("cycle-new", COMMUNITY), week)
        nxt = port.select_week("cycle-next", COMMUNITY)
        self.assertFalse({d["question"]["questionId"] for d in week} & {d["question"]["questionId"] for d in nxt})
        explicit = CycleQuestionPort(svc, week_start=lambda _c: "2026-11-16").select_week("cycle-3", COMMUNITY)
        self.assertEqual(explicit[4]["date"], "2026-11-20")

    def test_sync_clarify_returns_m2out_and_never_raises_on_provider_failure(self):
        bank = load_default_bank()
        meals = bank.get("q-routine-meals")
        m, transport = muse("clarify", ASK, ProviderError("unavailable", "x", status=503),
                            ProviderError("unavailable", "x", status=503), "junk", "junk")
        clarify = SyncClarify(ClarifyService(m, TestOnlyOutputGuard()), bank)
        self.assertEqual(clarify(meals["text"], "Mostly the dining hall"), ASK)
        self.assertEqual(clarify.last_source, "muse")
        self.assertEqual(clarify(meals["text"], "Mostly the dining hall"),
                         {"needsFollowup": True, "question": meals["followUpHint"]})
        self.assertEqual(clarify.last_source, "fallback")
        self.assertEqual(clarify("A question the bank has never seen?", "ok"),
                         {"needsFollowup": False, "question": ""})

    def test_run_sync_works_inside_a_running_loop(self):
        async def value():
            return 7

        async def outer():
            return run_sync(value())

        self.assertEqual(run_sync(value()), 7)
        self.assertEqual(asyncio.run(outer()), 7)


@unittest.skipUnless(HAVE_FASTAPI, "FastAPI not installed")
class OperatorRouterTests(unittest.TestCase):
    def client(self, *, nudge_steps=(GOOD,), muse_configured=True):
        questions = QuestionService(load_default_bank(), InMemorySelectionStore(), TestOnlyWeekStart())
        m, _ = muse("event_nudge", *nudge_steps)
        self.chat = TestOnlyChat()
        nudges = NudgeService(m, TestOnlyOutputGuard(), VenueCatalog.load(), Context(), self.chat, now=lambda: NOW)

        async def room_constellation(room_id):
            return {"room-orion": "c-1"}.get(room_id)

        self.runtime = PlanningRuntime(questions, nudges, room_constellation, VenueCatalog.load(), muse_configured)

        def session(request: Request):  # TEST-ONLY stand-in for Patrik's verified-session dependency
            role = request.headers.get("x-test-role")
            return {"playerId": "p-op", "communityId": COMMUNITY, "isOperator": role == "operator"}

        app = FastAPI()
        install_planning_error_handler(app)
        app.include_router(build_router(self.runtime, session), prefix="/api/v1")
        return TestClient(app)

    OP = {"x-test-role": "operator"}

    def test_every_route_requires_the_operator_role(self):
        c = self.client()
        for method, path in (("get", "/api/v1/operator/questions"),
                             ("post", f"/api/v1/operator/cycles/{CYCLE}/select-week"),
                             ("post", "/api/v1/operator/rooms/room-orion/nudge")):
            res = getattr(c, method)(path, headers={"x-test-role": "player"})
            self.assertEqual(res.status_code, 403, path)
            body = res.json()
            self.assertEqual(set(body), {"error"})
            self.assertEqual(set(body["error"]), {"code", "message", "requestId", "retryable"})
            self.assertEqual(body["error"]["code"], "FORBIDDEN")
        self.assertEqual(self.chat.posted, [])

    def test_questions_list_and_filters(self):
        c = self.client()
        rows = c.get("/api/v1/operator/questions", headers=self.OP).json()
        self.assertEqual(len(rows), len(load_default_bank().questions))
        routine = c.get("/api/v1/operator/questions?category=routine&active=true", headers=self.OP).json()
        self.assertTrue(routine and all(q["category"] == "routine" for q in routine))
        self.assertEqual(c.get("/api/v1/operator/questions?category=dating", headers=self.OP).status_code, 422)

    def test_select_week_is_scoped_to_the_session_community(self):
        c = self.client()
        res = c.post(f"/api/v1/operator/cycles/{CYCLE}/select-week", headers=self.OP)
        self.assertEqual(res.status_code, 200)
        week = res.json()
        self.assertEqual([d["day"] for d in week], [1, 2, 3, 4, 5])
        self.assertEqual({d["cycleId"] for d in week}, {CYCLE})
        self.assertEqual(c.post(f"/api/v1/operator/cycles/{CYCLE}/select-week", headers=self.OP).json(), week)
        missing = c.post("/api/v1/operator/cycles/cycle-unknown/select-week", headers=self.OP)
        self.assertEqual(missing.status_code, 404)
        self.assertEqual(missing.json()["error"]["code"], "NOT_FOUND")

    def test_nudge_route_posts_once_and_returns_the_event_nudge(self):
        c = self.client()
        res = c.post("/api/v1/operator/rooms/room-orion/nudge", headers=self.OP)
        self.assertEqual(res.status_code, 200)
        nudge = res.json()
        self.assertEqual(nudge["placeId"], "v-cafe")
        self.assertEqual(nudge["minAttendees"], 3)
        self.assertEqual(nudge["evidence"]["source"], "replay")
        self.assertEqual(c.post("/api/v1/operator/rooms/room-orion/nudge", headers=self.OP).json(), nudge)
        self.assertEqual(len(self.chat.posted), 1)
        self.assertEqual(c.post("/api/v1/operator/rooms/room-nope/nudge", headers=self.OP).status_code, 404)

    def test_nudge_route_reports_provider_unavailable_without_leaking_detail(self):
        c = self.client(nudge_steps=({**GOOD, "placeId": "v-someones-flat"},))
        res = c.post("/api/v1/operator/rooms/room-orion/nudge", headers=self.OP)
        self.assertEqual(res.status_code, 503)
        error = res.json()["error"]
        self.assertEqual((error["code"], error["retryable"]), ("PROVIDER_UNAVAILABLE", True))
        self.assertNotIn("flat", json.dumps(error))
        self.assertEqual(self.chat.posted, [])

    def test_readiness_is_false_without_muse_and_never_calls_it(self):
        self.client()
        self.assertTrue(asyncio.run(self.runtime.ready()))
        self.client(muse_configured=False)
        self.assertFalse(asyncio.run(self.runtime.ready()))

    def test_generate_route_is_not_registered(self):
        c = self.client()
        self.assertEqual(c.post("/api/v1/operator/questions/generate", headers=self.OP).status_code, 404)


if __name__ == "__main__":
    unittest.main()
