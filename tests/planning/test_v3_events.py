"""v3 events, nudge copy and custom events (scripted Muse; offline)."""
from __future__ import annotations

import asyncio
import unittest
from datetime import datetime, timedelta, timezone

from server.planning import (
    CustomEventService, EventNudgeService, EventsService, PlanningError, VenueCatalog, register_planning_tasks,
)
from server.planning.nudge_copy import template_copy
from server.providers import ProviderError, TaskRegistry
from server.providers.fixture import FixtureMuse, ScriptedTransport, decode_user_message
from tests.providers.test_contract_schemas import ts_interface_keys

from .doubles import TestOnlyOutputGuard

NOW = datetime(2026, 11, 18, 12, 0, tzinfo=timezone.utc)  # before every catalog event
CATALOG = VenueCatalog.load()


def run(coro):
    return asyncio.run(coro)


def muse(*steps):
    transport = ScriptedTransport()
    if steps:
        transport.queue("event_nudge", *steps)
    return FixtureMuse(register_planning_tasks(TaskRegistry()), transport), transport


class Screen:
    """TEST ONLY stand-in for Patrik's SensitivityScreen."""

    def __init__(self, ok=True, boom=False):
        self.ok, self.boom, self.calls = ok, boom, 0

    async def allowed(self, texts):
        self.calls += 1
        if self.boom:
            raise RuntimeError("down")
        return [self.ok] * len(texts)


class EventsServiceTests(unittest.TestCase):
    def test_lists_approved_upcoming_events_with_viewer_signals(self):
        async def buckets(viewer):
            return [{"eventId": "ev-open-mic", "bucket": "6-9"}, {"eventId": "ev-board-games", "bucket": "2"},
                    {"eventId": "ev-invented", "bucket": "10+"}]

        async def mine(viewer, ids):
            return ["ev-film-club", "ev-invented"]

        svc = EventsService(CATALOG, interest_buckets=buckets, my_interests=mine)
        views = run(svc.list("viewer-1", now=NOW))
        self.assertEqual([v["eventId"] for v in views], ["ev-volleyball", "ev-open-mic", "ev-board-games", "ev-film-club"])
        by_id = {v["eventId"]: v for v in views}
        self.assertEqual(by_id["ev-open-mic"]["constellationInterestBucket"], "6-9")
        self.assertEqual(by_id["ev-board-games"]["constellationInterestBucket"], "none")  # "2" is never shown
        self.assertTrue(by_id["ev-film-club"]["myInterest"])
        self.assertNotIn("ev-invented", by_id)
        for v in views:
            self.assertEqual(set(v), ts_interface_keys("EventView"))
            self.assertEqual(v["kind"], "catalog")
        self.assertEqual(by_id["ev-open-mic"]["endsAt"], "2026-11-19T05:00:00Z")

    def test_failing_signal_ports_degrade_to_none_never_invent(self):
        async def boom(*_):
            raise RuntimeError("down")

        views = run(EventsService(CATALOG, interest_buckets=boom, my_interests=boom).list("v", now=NOW))
        self.assertTrue(all(v["constellationInterestBucket"] == "none" and not v["myInterest"] for v in views))

    def test_window_and_get(self):
        svc = EventsService(CATALOG)
        self.assertEqual(run(svc.list("v", now=NOW + timedelta(days=30))), [])
        self.assertEqual(run(svc.get("v", "ev-open-mic"))["title"], "Open mic night")
        with self.assertRaises(PlanningError) as ctx:
            run(svc.get("v", "ev-invented"))
        self.assertEqual(ctx.exception.code, "NOT_FOUND")


GOOD_COPY = {"copy": "A few people from your constellations might head to Open mic night at Campus Cafe."}
OPEN_MIC = {"eventId": "ev-open-mic", "bucket": "3-5"}


def nudger(*steps, sensitivity=None, **kw):
    m, t = muse(*steps)
    ids = iter(f"{i:032x}" for i in range(1, 1000))
    svc = EventNudgeService(m, TestOnlyOutputGuard(), CATALOG, sensitivity=sensitivity,
                            new_id=lambda: next(ids), trace=m.reasoning_trace, **kw)
    return svc, t, m


class NudgeCopyTests(unittest.TestCase):
    def test_muse_copy_used_when_it_passes_every_check(self):
        svc, t, _ = nudger(GOOD_COPY, sensitivity=Screen())
        n = run(svc.propose_for("v1", [OPEN_MIC], now=NOW))
        self.assertEqual(set(n), ts_interface_keys("EventNudgeView"))
        self.assertEqual(n["copy"], GOOD_COPY["copy"])
        self.assertEqual(n["expiresAt"], "2026-11-19T03:00:00Z")
        payload = decode_user_message(t.calls[0].user)["input"]
        self.assertEqual(payload, {"event": {"title": "Open mic night", "venueName": "Campus Cafe",
                                             "startsAt": "2026-11-19T03:00:00Z"}, "interestBucket": "3-5"})

    def test_bad_or_unscreened_copy_falls_back_to_the_template(self):
        template = template_copy("3-5", "Open mic night", "Campus Cafe")
        cases = [
            ({"copy": "5 of your people are going to Open mic night."}, Screen()),   # digits
            ({"copy": "Come hang out this week."}, Screen()),                        # off topic
            (GOOD_COPY, None),                                                       # no M10 screen: fail closed
            (GOOD_COPY, Screen(ok=False)),                                           # M10 blocks
            (GOOD_COPY, Screen(boom=True)),                                          # M10 error
            (ProviderError("timeout", "t"), Screen()),                               # provider failure
        ]
        for step, screen in cases:
            svc, _, _ = nudger(step, sensitivity=screen)
            self.assertEqual(run(svc.propose_for("v1", [OPEN_MIC], now=NOW))["copy"], template, str(step))

    def test_copy_is_shared_per_event_and_bucket(self):
        svc, t, _ = nudger(GOOD_COPY, sensitivity=Screen())
        run(svc.propose_for("v1", [OPEN_MIC], now=NOW))
        run(svc.propose_for("v2", [OPEN_MIC], now=NOW))
        self.assertEqual(len(t.calls), 1)

    def test_cadence_gap_weekly_cap_active_cap_and_no_repeats(self):
        svc, _, _ = nudger(GOOD_COPY, GOOD_COPY, GOOD_COPY, sensitivity=Screen())
        rows = [OPEN_MIC, {"eventId": "ev-board-games", "bucket": "10+"}, {"eventId": "ev-film-club", "bucket": "6-9"}]
        first = run(svc.propose_for("v1", rows, now=NOW))
        self.assertEqual(first["eventId"], "ev-board-games")  # highest bucket first
        self.assertIsNone(run(svc.propose_for("v1", rows, now=NOW + timedelta(hours=47))))  # 48 h gap
        second = run(svc.propose_for("v1", rows, now=NOW - timedelta(days=4) + timedelta(days=6)))
        self.assertIsNotNone(second)
        self.assertNotEqual(second["eventId"], first["eventId"])
        self.assertIsNone(run(svc.propose_for("v1", rows, now=NOW + timedelta(days=4))))  # 2 per 7 days

    def test_weekly_cap_isolated_from_event_timing(self):
        # Four approved custom events, all still upcoming when each proposal runs.
        def far(i):
            start = NOW + timedelta(days=6 + i)
            return {"eventId": f"ev-custom-{i}", "title": f"Walk {chr(65 + i)}", "placeId": "v-quad",
                    "startsAt": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "endsAt": (start + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "constellationInterestBucket": "none", "myInterest": False, "kind": "custom"}
        events = [far(i) for i in range(4)]
        svc, _, _ = nudger(*([{"copy": "A few people from your constellations like Main Quad walks."}] * 4),
                           sensitivity=Screen(), approved_events=lambda: events)
        rows = [{"eventId": e["eventId"], "bucket": "3-5"} for e in events]
        t0 = NOW + timedelta(days=3)
        self.assertIsNotNone(run(svc.propose_for("v1", rows, now=t0)))
        self.assertIsNotNone(run(svc.propose_for("v1", rows, now=t0 + timedelta(hours=49))))
        # 3rd within 7 days of the 1st is refused although events are upcoming and 48 h passed.
        self.assertIsNone(run(svc.propose_for("v1", rows, now=t0 + timedelta(hours=98))))
        # Not the active cap (both earlier nudges have expired) and an event is still upcoming (ev-custom-2 at
        # t0 + 120 h), so the 2-per-7-days rule is what refused it.
        self.assertEqual(svc.active("v1", now=t0 + timedelta(hours=98)), [])

    def test_only_approved_upcoming_events_within_a_week_and_visible_buckets(self):
        svc, _, _ = nudger(GOOD_COPY, sensitivity=Screen())
        bad = [{"eventId": "ev-invented", "bucket": "10+"}, {"eventId": "ev-open-mic", "bucket": "1-2"},
               {"eventId": "ev-open-mic"}]
        self.assertIsNone(run(svc.propose_for("v1", bad, now=NOW)))
        self.assertIsNone(run(svc.propose_for("v1", [OPEN_MIC], now=NOW + timedelta(days=2))))  # already started
        self.assertIsNone(run(svc.propose_for("v1", [OPEN_MIC], now=NOW - timedelta(days=8))))  # more than a week out

    def test_dismiss_forget_and_active(self):
        svc, _, _ = nudger(GOOD_COPY, sensitivity=Screen())
        n = run(svc.propose_for("v1", [OPEN_MIC], now=NOW))
        self.assertEqual([a["nudgeId"] for a in svc.active("v1", now=NOW)], [n["nudgeId"]])
        self.assertTrue(svc.dismiss("v1", n["nudgeId"]))
        self.assertEqual(svc.active("v1", now=NOW), [])
        self.assertFalse(svc.dismiss("v2", n["nudgeId"]))  # another viewer cannot dismiss it
        svc.forget("v1")
        self.assertEqual(svc.active("v1", now=NOW), [])
        self.assertEqual(svc.active("v1", now=datetime(2026, 11, 20, tzinfo=timezone.utc)), [])

    def test_preview_and_counts_carry_no_player_ids(self):
        svc, _, _ = nudger(GOOD_COPY, sensitivity=Screen())
        p = run(svc.preview("ev-open-mic", "3-5", now=NOW))
        self.assertEqual(set(p), {"eventId", "interestBucket", "copy", "source", "guardOk"})
        self.assertEqual(svc.bucket_counts(now=NOW), {"3-5": 0, "6-9": 0, "10+": 0})


WINDOW = {"start": "2026-11-21T01:00:00Z", "end": "2026-11-21T04:00:00Z"}
PROPOSAL = {"title": "Coffee and a low-key jam", "why": "You all seem to enjoy coffee and music.",
            "placeId": "v-cafe", "timeWindow": {"start": "2026-11-21T01:00:00Z", "end": "2026-11-21T03:00:00Z"}}
CLUSTER = {"clusterSize": 9, "tags": ["coffee", "music"]}


def customs(*steps, sensitivity="ok", approved=None):
    m, t = muse(*steps)
    ids = iter(f"{i:032x}" for i in range(1, 1000))
    screen = Screen() if sensitivity == "ok" else sensitivity
    svc = CustomEventService(m, TestOnlyOutputGuard(), CATALOG, area="Berkeley", sensitivity=screen,
                             on_approved=approved, new_id=lambda: next(ids))
    return svc, t


class CustomEventTests(unittest.TestCase):
    def test_valid_proposal_is_pending_with_aggregate_only_input(self):
        svc, t = customs(PROPOSAL)
        p = run(svc.propose(CLUSTER, [WINDOW]))
        self.assertEqual(set(p), ts_interface_keys("CustomEventProposal"))
        self.assertEqual((p["status"], p["evidence"]["callType"], p["evidence"]["source"]), ("pending", "M7", "replay"))
        payload = decode_user_message(t.calls[0].user)["input"]
        self.assertEqual(set(payload), {"clusterSize", "interestTags", "area", "windows", "venues"})
        self.assertEqual(payload["interestTags"], ["coffee", "music"])
        self.assertEqual(svc.pending(), [p])

    def test_code_refuses_bad_proposals(self):
        bad = [
            {**PROPOSAL, "placeId": "v-someones-flat"},
            {**PROPOSAL, "timeWindow": {"start": "2026-11-22T01:00:00Z", "end": "2026-11-22T02:00:00Z"}},
            {**PROPOSAL, "timeWindow": {"start": "2026-11-21T01:00:00Z", "end": "2026-11-21T05:30:00Z"}},
            {**PROPOSAL, "why": "9 of you love coffee."},
            {**PROPOSAL, "title": "Coffee at www.example.com"},
        ]
        for out in bad:
            svc, _ = customs(out)
            self.assertIsNone(run(svc.propose(CLUSTER, [WINDOW])), str(out))
        for screen in (None, Screen(ok=False), Screen(boom=True)):  # M10 required
            svc, _ = customs(PROPOSAL, sensitivity=screen)
            self.assertIsNone(run(svc.propose(CLUSTER, [WINDOW])))

    def test_cluster_input_must_be_allowlisted_aggregates(self):
        svc, t = customs(PROPOSAL)
        for cluster in ({"clusterSize": 9, "tags": ["p-maya"]}, {"clusterSize": "9", "tags": []}, {"tags": ["coffee"]}):
            with self.assertRaises(PlanningError):
                run(svc.propose(cluster, [WINDOW]))
        self.assertEqual(t.calls, [])

    def test_approve_creates_custom_event_and_notifies_once(self):
        seen = []
        svc, _ = customs(PROPOSAL, approved=seen.append)
        p = run(svc.propose(CLUSTER, [WINDOW]))
        decided = svc.decide(p["proposalId"], "approve")
        self.assertEqual(decided["status"], "approved")
        self.assertEqual(seen[0]["eventId"], f"ev-custom-{p['proposalId']}")
        self.assertEqual(set(seen[0]), ts_interface_keys("EventView"))
        with self.assertRaises(PlanningError):
            svc.decide(p["proposalId"], "reject")
        events = EventsService(CATALOG, custom_events=svc.approved_events)
        self.assertIn(seen[0]["eventId"], {v["eventId"] for v in run(events.list("v", now=NOW))})
        self.assertEqual(svc.pending(), [])

    def test_reject_and_unknown(self):
        svc, _ = customs(PROPOSAL)
        p = run(svc.propose(CLUSTER, [WINDOW]))
        self.assertEqual(svc.decide(p["proposalId"], "reject")["status"], "rejected")
        self.assertEqual(svc.approved_events(), [])
        for pid, decision in (("cp-missing", "approve"), (p["proposalId"], "maybe")):
            with self.assertRaises(PlanningError):
                svc.decide(pid, decision)


if __name__ == "__main__":
    unittest.main()
