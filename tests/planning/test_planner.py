"""PlanningPort plan/revise/continue against FixtureMuse (synthetic, offline)."""
from __future__ import annotations

import asyncio
import json
import unittest

from server.planning import PlanningError, QuestPlanner, plan_changes, register_planning_tasks, requires_reconfirmation
from server.planning import public_text, wire
from server.planning.prompts import RATIONALE_FACT_ENUM
from server.providers import ProviderError, TaskRegistry
from server.providers.fixture import FixtureMuse, ScriptedTransport

from . import fixtures as fx


def make(task: str = "plan", *steps, delay: float = 0.0):
    transport = ScriptedTransport(delay_s=delay)
    if steps:
        transport.queue(task, *steps)
    muse = FixtureMuse(register_planning_tasks(TaskRegistry()), transport)
    records: list[dict] = []
    planner = QuestPlanner(muse, now=lambda: fx.REF, new_id=iter(f"plan-{i}" for i in range(1, 99)).__next__,
                           telemetry=records.append)
    return planner, transport, records


def sent_payload(transport) -> dict:
    return json.loads(transport.calls[-1].user.partition("\n")[2])["input"]


class PlanTests(unittest.IsolatedAsyncioTestCase):
    async def test_feasible_group_produces_validated_plan(self):
        planner, transport, records = make("plan", fx.good_plan_output())
        res = await planner.plan(fx.plan_input())
        wire.plan_result(res)
        plan = res["plan"]
        self.assertEqual(res["status"], "proposed")
        self.assertEqual((plan["revision"], plan["basedOnRevision"]), (1, None))
        self.assertEqual(plan["venueId"], "venue-demo-quad")
        self.assertEqual(plan["memberVersions"], fx.proposal(fx.participants())["memberVersions"])
        self.assertIn("photography", plan["publicRationale"])
        self.assertIn("is free", plan["publicRationale"])
        self.assertEqual(plan["evidence"]["source"], "replay")
        self.assertEqual(records[-1]["outcome"], "proposed")

    async def test_model_payload_is_minimized_group_level_data(self):
        planner, transport, _ = make("plan", fx.good_plan_output())
        await planner.plan(fx.plan_input())
        payload = sent_payload(transport)
        blob = json.dumps(payload)
        for private in ("p-ava", "p-ben", "Ava", "Ben", "meet new people", "confirmedAt", "1000"):
            self.assertNotIn(private, blob)
        self.assertEqual(payload["constraints"]["maxCostPerPersonMinor"], 0)  # min over members
        self.assertEqual(payload["constraints"]["maxDurationMinutes"], 60)
        # Options are only feasible slots: shared 22:00Z-00:00Z within venue hours.
        quad = next(o for o in payload["options"] if o["venueId"] == "venue-demo-quad")
        self.assertEqual(quad["slots"], [{"start": "2026-11-14T22:00:00Z", "end": "2026-11-15T00:00:00Z"}])
        self.assertTrue(all(o["venueId"] != "venue-demo-plaza" for o in payload["options"]))  # other area

    async def test_unknown_venue_rejected_then_corrected(self):
        planner, transport, records = make("plan", fx.good_plan_output(venueId="venue-hallucinated"), fx.good_plan_output())
        res = await planner.plan(fx.plan_input())
        self.assertEqual(res["status"], "proposed")
        self.assertIn("venueId: must be one of the provided options", transport.calls[1].developer)
        self.assertEqual(records[-1]["rejections"], ["venueId"])

    async def test_invalid_choices_exhaust_retries_with_retryable_error(self):
        bad = [
            fx.good_plan_output(costPerPersonMinor=500),                                   # over budget cap 0
            fx.good_plan_output(start="2026-11-15T00:30:00Z", end="2026-11-15T01:00:00Z"), # outside shared time
            fx.good_plan_output(start="2026-11-14T22:00:00Z", end="2026-11-14T23:30:00Z"), # 90 min > cap 60
            fx.good_plan_output(opener="Since Ben can't afford anything we chose a free walk, see www.x.com"),
            fx.good_plan_output(start="2026-11-14T22:30:00", end="2026-11-14T23:30:00"),   # no zone
        ]
        for out in bad:
            planner, transport, _ = make("plan", out, out)
            with self.assertRaises(PlanningError) as ctx:
                await planner.plan(fx.plan_input())
            self.assertEqual(ctx.exception.code, "PROVIDER_UNAVAILABLE")
            self.assertTrue(ctx.exception.retryable)
            self.assertEqual(len(transport.calls), 2)

    async def test_no_common_time_needs_input_without_model_call(self):
        parts = fx.participants()
        parts[2]["intent"]["availability"] = [{"start": "2026-11-15T18:00:00Z", "end": "2026-11-15T20:00:00Z"}]
        planner, transport, _ = make()
        res = await planner.plan(fx.plan_input(participants=parts, proposal=fx.proposal(parts)))
        self.assertEqual(res["status"], "needs_input")
        self.assertEqual(res["fields"], ["availability"])
        self.assertEqual(transport.calls, [])

    async def test_no_open_public_venue_is_honest_no_plan(self):
        planner, transport, _ = make()
        venues = [v for v in fx.plan_input()["venues"] if v["areaId"] == "area-downtown"]
        res = await planner.plan(fx.plan_input(venues=venues))
        self.assertEqual(res, {"status": "no_feasible_plan", "reason": "No approved public venue is open during a time that works for the whole group."})
        self.assertEqual(transport.calls, [])

    async def test_stale_member_version_rejected_before_model_call(self):
        parts = fx.participants()
        prop = fx.proposal(parts)
        parts[1]["intent"]["intentVersion"] = 2  # availability changed after matching
        planner, transport, _ = make()
        with self.assertRaises(PlanningError) as ctx:
            await planner.plan(fx.plan_input(participants=parts, proposal=prop))
        self.assertEqual(ctx.exception.code, "STALE_REVISION")
        self.assertEqual(transport.calls, [])

    async def test_participants_must_match_proposal_and_contract(self):
        parts = fx.participants()
        prop = fx.proposal(parts)
        intruder = fx.candidate("p-zed", "Zed (synthetic)", "2026-11-14T21:00:00Z", "2026-11-15T01:00:00Z", 1000, 60)
        planner, transport, _ = make()
        with self.assertRaises(PlanningError) as ctx:
            await planner.plan(fx.plan_input(participants=parts[:2] + [intruder], proposal=prop))
        self.assertEqual(ctx.exception.code, "INVALID_INPUT")
        bad = fx.plan_input()
        bad["participants"][0]["intent"]["homeAddress"] = "x"  # unexpected private field
        with self.assertRaises(PlanningError) as ctx:
            await planner.plan(bad)
        self.assertEqual(ctx.exception.code, "INVALID_INPUT")
        self.assertEqual(transport.calls, [])

    async def test_provider_outage_is_retryable_error_not_fake_plan(self):
        err = ProviderError("unavailable", "down", status=503)
        planner, _, _ = make("plan", err, err)
        with self.assertRaises(PlanningError) as ctx:
            await planner.plan(fx.plan_input())
        self.assertEqual(ctx.exception.code, "PROVIDER_UNAVAILABLE")
        self.assertTrue(ctx.exception.retryable)

    async def test_cancellation_propagates(self):
        planner, _, _ = make("plan", fx.good_plan_output(), delay=5.0)
        task = asyncio.create_task(planner.plan(fx.plan_input()))
        await asyncio.sleep(0.01)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task

    def test_rationale_fact_enum_in_sync(self):
        self.assertEqual(tuple(RATIONALE_FACT_ENUM), public_text.RATIONALE_FACTS)

    def test_rationale_never_states_unverified_free(self):
        text = public_text.render_rationale(["free_activity"], shared_interests=["chess"], cost_per_person_minor=300, duration_minutes=45)
        self.assertNotIn("free", text)
        self.assertEqual(public_text.violations(text), [])


class ReviseTests(unittest.IsolatedAsyncioTestCase):
    async def _previous_plan(self) -> dict:
        planner, _, _ = make("plan", fx.good_plan_output())
        return (await planner.plan(fx.plan_input()))["plan"]

    def _changed_input(self, previous: dict, ben_window=("2026-11-14T23:00:00Z", "2026-11-15T02:00:00Z")) -> dict:
        parts = fx.participants()
        parts[1] = fx.candidate("p-ben", "Ben (synthetic)", *ben_window, 0, 90, version=2)
        windows = [{"start": "2026-11-14T23:00:00Z", "end": "2026-11-15T00:00:00Z"}]
        return fx.plan_input(participants=parts, proposal=fx.proposal(parts, revision=2, windows=windows),
                             previousPlan=previous, changeSummary="A member's availability changed.")

    async def test_changed_availability_produces_new_revision_requiring_reconfirmation(self):
        previous = await self._previous_plan()
        planner, transport, _ = make("revise", fx.good_plan_output(start="2026-11-14T23:00:00Z", end="2026-11-14T23:45:00Z"))
        res = await planner.revise(self._changed_input(previous))
        plan = res["plan"]
        self.assertEqual((plan["revision"], plan["basedOnRevision"]), (2, 1))
        self.assertEqual(plan_changes(previous, plan), ["start", "end"])
        self.assertTrue(requires_reconfirmation(previous, plan))
        self.assertEqual(plan["memberVersions"][1]["intentVersion"], 2)
        payload = sent_payload(transport)
        self.assertEqual(payload["previousPlan"]["start"], previous["start"])
        self.assertEqual(payload["changeSummary"], "A member's availability changed.")

    async def test_old_slot_rejected_after_change(self):
        previous = await self._previous_plan()
        stale_choice = fx.good_plan_output()  # 22:30Z no longer works for Ben
        planner, _, _ = make("revise", stale_choice, stale_choice)
        with self.assertRaises(PlanningError):
            await planner.revise(self._changed_input(previous))

    async def test_impossible_change_needs_input(self):
        previous = await self._previous_plan()
        planner, transport, _ = make()
        res = await planner.revise(self._changed_input(previous, ("2026-11-16T01:00:00Z", "2026-11-16T03:00:00Z")))
        self.assertEqual(res["status"], "needs_input")
        self.assertEqual(transport.calls, [])

    async def test_revise_requires_matching_previous_plan(self):
        previous = await self._previous_plan()
        planner, _, _ = make()
        with self.assertRaises(PlanningError):
            await planner.revise(fx.plan_input())
        other = dict(previous, proposalId="prop-other")
        with self.assertRaises(PlanningError):
            await planner.revise(self._changed_input(other))

    def test_non_material_change_does_not_require_reconfirmation(self):
        a = {"title": "A", "activity": "x", "collaborationTask": "y", "venueId": "v", "start": "s", "end": "e", "costPerPersonMinor": 0}
        self.assertFalse(requires_reconfirmation(a, dict(a, title="B")))


class ContinueTests(unittest.IsolatedAsyncioTestCase):
    async def _prior(self) -> dict:
        planner, _, _ = make("plan", fx.good_plan_output())
        return (await planner.plan(fx.plan_input()))["plan"]

    def _input(self, prior: dict, **kw) -> dict:
        inp = {
            "context": {"requestId": "req-cont-1", "contractVersion": "1.0.0", "mode": "fixture"},
            "questId": "quest-synthetic-1",
            "priorPlan": prior,
            "feedback": [
                {"participantId": "p-ava", "attended": None, "wantsReturn": True},
                {"participantId": "p-ben", "attended": None, "wantsReturn": False},
                {"participantId": "p-cy", "attended": True, "wantsReturn": True},
            ],
            "simulateTimeSkip": True,
        }
        inp.update(kw)
        return inp

    @staticmethod
    def _out(**kw) -> dict:
        out = {"nextActivity": "A golden-hour photo walk where the group builds a five-photo story with a twist ending.",
               "invitationText": "Want to do a part two next week? Let's make a five-photo story at golden hour. Reply if you're in!",
               "proposedHostId": "p-cy"}
        out.update(kw)
        return out

    async def test_willing_host_and_no_attendance_sent(self):
        prior = await self._prior()
        planner, transport, _ = make("continue", self._out())
        res = await getattr(planner, "continue")(self._input(prior))
        wire.continuation(res)
        self.assertEqual(res["proposedHostId"], "p-cy")
        payload = sent_payload(transport)
        self.assertEqual(payload["willingHostIds"], ["p-ava", "p-cy"])
        self.assertTrue(payload["simulatedTimeSkip"])
        self.assertNotIn("attended", json.dumps(payload))

    async def test_unwilling_host_and_attendance_claims_rejected(self):
        prior = await self._prior()
        planner, transport, _ = make("continue", self._out(proposedHostId="p-ben"),
                                     self._out(invitationText="Thanks for coming last week! Let's do it again."))
        with self.assertRaises(PlanningError):
            await getattr(planner, "continue")(self._input(prior))
        self.assertIn("proposedHostId", transport.calls[1].developer)

    async def test_null_host_falls_back_to_willing_member_only(self):
        prior = await self._prior()
        planner, _, _ = make("continue", self._out(proposedHostId=None))
        res = await getattr(planner, "continue")(self._input(prior))
        self.assertEqual(res["proposedHostId"], "p-ava")
        nobody = [dict(f, wantsReturn=False) for f in self._input(prior)["feedback"]]
        planner, _, _ = make("continue", self._out(proposedHostId=None))
        res = await getattr(planner, "continue")(self._input(prior, feedback=nobody))
        self.assertIsNone(res["proposedHostId"])

    async def test_non_member_feedback_forbidden_and_unskipped_early_call_rejected(self):
        prior = await self._prior()
        planner, transport, _ = make()
        with self.assertRaises(PlanningError) as ctx:
            await getattr(planner, "continue")(self._input(prior, feedback=[{"participantId": "p-zed", "attended": None, "wantsReturn": True}]))
        self.assertEqual(ctx.exception.code, "FORBIDDEN")
        with self.assertRaises(PlanningError) as ctx:
            await getattr(planner, "continue")(self._input(prior, simulateTimeSkip=False))
        self.assertEqual(ctx.exception.code, "INVALID_INPUT")
        self.assertEqual(transport.calls, [])


if __name__ == "__main__":
    unittest.main()
