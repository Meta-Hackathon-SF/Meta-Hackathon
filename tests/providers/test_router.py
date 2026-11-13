"""Task -> model router: routing, fallback rules, deadlines, shared logs (offline)."""
from __future__ import annotations

import asyncio
import unittest

from server.providers import ProviderError, TaskRegistry
from server.providers.config import MuseConfig
from server.providers.port import MuseRequest, MuseResult
from server.providers.router import MEASURED_ROUTES, MuseRouter, Route, parse_routes

BASE = MuseConfig(api_key="k-test", model="muse-spark-1.3", timeout_s=30.0, reasoning_effort="low")


class FakeAdapter:
    """Stands in for MuseAdapter; behaviour scripted per model."""

    script: dict[str, list] = {}
    calls: list[tuple[str, str | None, float | None, float | None]] = []

    def __init__(self, registry, *, config, evidence_log, reasoning_trace, **_):
        self.config, self.evidence_log, self.reasoning_trace = config, evidence_log, reasoning_trace

    async def run(self, request):
        FakeAdapter.calls.append((self.config.model, self.config.reasoning_effort, self.config.timeout_s, request.deadline_s))
        step = FakeAdapter.script[self.config.model].pop(0)
        if isinstance(step, BaseException):
            raise step
        self.reasoning_trace.record_call({"requestId": request.request_id, "task": request.task, "model": self.config.model})
        return MuseResult(output=step, evidence={"model": self.config.model, "source": "live", "generatedAt": "x",
                                                 "latencyMs": 1, "callType": "M2"})


def router(routes, script, clock=None):
    FakeAdapter.script = {k: list(v) for k, v in script.items()}
    FakeAdapter.calls = []
    kw = {"clock": clock} if clock else {}
    return MuseRouter(TaskRegistry(), BASE, routes, adapter_factory=FakeAdapter, **kw)


def req(task="clarify", deadline=None):
    return MuseRequest(task=task, request_id="r-1", prompt_version="v", payload={}, deadline_s=deadline)


class RouterTests(unittest.TestCase):
    def test_no_route_uses_base_model(self):
        r = router({}, {"muse-spark-1.3": [{"ok": 1}]})
        asyncio.run(r.run(req()))
        self.assertEqual(FakeAdapter.calls, [("muse-spark-1.3", "low", 30.0, None)])

    def test_route_picks_model_effort_and_timeout(self):
        r = router({"clarify": Route("muse-ember-1.0", "minimal", 20.0)}, {"muse-ember-1.0": [{"ok": 1}]})
        asyncio.run(r.run(req()))
        self.assertEqual(FakeAdapter.calls, [("muse-ember-1.0", "minimal", 20.0, None)])

    def test_falls_back_on_timeout_and_records_it(self):
        r = router({"clarify": Route("muse-ember-1.0", "low", fallbacks=("muse-spark-1.3",))},
                   {"muse-ember-1.0": [ProviderError("timeout", "t")], "muse-spark-1.3": [{"ok": 1}]})
        res = asyncio.run(r.run(req()))
        self.assertEqual(res.evidence["model"], "muse-spark-1.3")
        codes = [c["code"] for c in r.reasoning_trace.list()[0]["checks"]]
        self.assertEqual(codes, ["fallback_after_timeout", "served_by_fallback"])

    def test_never_falls_back_on_auth_or_invalid_request(self):
        for kind in ("auth", "invalid_request", "unknown_task", "not_configured"):
            r = router({"clarify": Route("muse-ember-1.0", "low", fallbacks=("muse-spark-1.3",))},
                       {"muse-ember-1.0": [ProviderError(kind, "x")], "muse-spark-1.3": [{"ok": 1}]})
            with self.assertRaises(ProviderError):
                asyncio.run(r.run(req()))
            self.assertEqual(len(FakeAdapter.calls), 1, kind)

    def test_fallback_gets_only_the_remaining_deadline(self):
        t = [0.0]
        r = router({"clarify": Route("muse-wonder-1.0", "low", fallbacks=("muse-spark-1.3",))},
                   {"muse-wonder-1.0": [ProviderError("timeout", "t")], "muse-spark-1.3": [{"ok": 1}]},
                   clock=lambda: t[0])
        orig = FakeAdapter.run

        async def slow(self, request):
            if self.config.model == "muse-wonder-1.0":
                t[0] += 15.0
            return await orig(self, request)

        FakeAdapter.run = slow
        try:
            asyncio.run(r.run(req(deadline=20.0)))
        finally:
            FakeAdapter.run = orig
        self.assertEqual([c[3] for c in FakeAdapter.calls], [20.0, 5.0])

    def test_no_fallback_when_too_little_time_is_left(self):
        t = [0.0]
        r = router({"clarify": Route("muse-wonder-1.0", "low", fallbacks=("muse-spark-1.3",))},
                   {"muse-wonder-1.0": [ProviderError("timeout", "t")], "muse-spark-1.3": [{"ok": 1}]},
                   clock=lambda: t[0])
        orig = FakeAdapter.run

        async def slow(self, request):
            t[0] += 19.5
            return await orig(self, request)

        FakeAdapter.run = slow
        try:
            with self.assertRaises(ProviderError):
                asyncio.run(r.run(req(deadline=20.0)))
        finally:
            FakeAdapter.run = orig
        self.assertEqual(len(FakeAdapter.calls), 1)

    def test_routes_validate_models_efforts_and_tasks(self):
        with self.assertRaises(ValueError):
            Route("muse-spark-1.3-contributor")
        with self.assertRaises(ValueError):
            Route("muse-spark-1.2", "max")
        with self.assertRaises(ValueError):
            Route("muse-ember-1.0", max_attempts=4)
        with self.assertRaises(ValueError):
            Route("muse-ember-1.0", fallbacks=("muse-ember-1.0",))
        with self.assertRaises(ValueError):
            MuseRouter(TaskRegistry(), BASE, {"rank_group": Route("muse-spark-1.3")})

    def test_measured_routes_are_the_default_and_valid(self):
        from server.providers.router import DEFAULT_ROUTES, MEASURED_ROUTES, build_muse_router

        self.assertIs(DEFAULT_ROUTES, MEASURED_ROUTES)
        self.assertEqual(MEASURED_ROUTES["clarify"].model, "muse-ember-1.0")
        self.assertNotIn("muse-spark-1.3", (MEASURED_ROUTES["sky_narration"].model, *MEASURED_ROUTES["sky_narration"].fallbacks))
        r = build_muse_router(TaskRegistry(), BASE, adapter_factory=FakeAdapter)
        self.assertEqual(r.route_for("constellation_formation").model, "muse-ember-1.0")
        # Audit 3 fixes: every task routed; M3 Ember; M10 Spark first; M2 10 s.
        from server.providers.port import TASKS
        self.assertEqual(set(MEASURED_ROUTES), set(TASKS))
        self.assertEqual(r.route_for("theme_discovery").model, "muse-ember-1.0")
        self.assertEqual(r.route_for("sensitivity_screen").model, "muse-spark-1.3")
        self.assertEqual(r.route_for("clarify").timeout_s, 10.0)

    def test_route_attempts_reach_the_adapter_config(self):
        seen = []

        class Capture(FakeAdapter):
            def __init__(self, registry, *, config, **kw):
                seen.append(config.max_attempts)
                super().__init__(registry, config=config, **kw)

        FakeAdapter.script = {"muse-ember-1.0": [{"ok": 1}]}
        r = MuseRouter(TaskRegistry(), BASE, {"clarify": Route("muse-ember-1.0", "minimal", 6.0, max_attempts=1)},
                       adapter_factory=Capture)
        asyncio.run(r.run(req()))
        self.assertEqual(seen, [1])

    def test_env_override_merges_over_measured_routes_and_rejects_bad_specs(self):
        from server.providers.router import MEASURED_ROUTES, routes_from_env

        routes = routes_from_env({"MUSE_ROUTES": "clarify=muse-spark-1.3:low:12:2"})
        self.assertEqual(routes["clarify"], Route("muse-spark-1.3", "low", 12.0, (), max_attempts=2))
        self.assertEqual(routes["safety_screen"], MEASURED_ROUTES["safety_screen"])
        self.assertEqual(routes_from_env({}), MEASURED_ROUTES)
        for bad in ("clarify=gpt-4o", "nope=muse-spark-1.3", "clarify=muse-spark-1.3:low:12:9"):
            with self.assertRaises(ValueError):
                routes_from_env({"MUSE_ROUTES": bad})

    def test_route_check_reports_served_model_and_fallbacks(self):
        from server.providers.route_check import check, ping_registry, route_table

        routes = {"clarify": Route("muse-ember-1.0", "minimal", 6.0, ("muse-spark-1.3",), max_attempts=1),
                  "safety_screen": Route("muse-ember-1.0", "low", 8.0, ("muse-spark-1.3",), max_attempts=1)}
        FakeAdapter.script = {"muse-ember-1.0": [{"ok": True}, ProviderError("timeout", "t")] + [{"ok": True}] * 20,
                              "muse-spark-1.3": [{"ok": True}] * 20}
        FakeAdapter.calls = []
        r = MuseRouter(ping_registry(), BASE, routes, adapter_factory=FakeAdapter)
        rows = {row["task"]: row for row in asyncio.run(check(r, routes))}
        self.assertTrue(rows["clarify"]["onPrimary"])
        self.assertEqual((rows["safety_screen"]["served"], rows["safety_screen"]["fellBack"],
                          rows["safety_screen"]["onPrimary"]), ("muse-spark-1.3", True, False))
        table = {row["task"]: row for row in route_table(routes, "muse-spark-1.3")}
        self.assertFalse(table["sky_narration"]["routed"])

    def test_parse_routes(self):
        routes = parse_routes("clarify=muse-ember-1.0:minimal:20>muse-spark-1.3; constellation_formation=muse-spark-1.3:low")
        self.assertEqual(routes["clarify"], Route("muse-ember-1.0", "minimal", 20.0, ("muse-spark-1.3",)))
        self.assertEqual(routes["constellation_formation"], Route("muse-spark-1.3", "low", None, ()))
        for bad in ("nope=muse-spark-1.3", "clarify", "clarify=gpt-4o"):
            with self.assertRaises(ValueError):
                parse_routes(bad)


if __name__ == "__main__":
    unittest.main()
