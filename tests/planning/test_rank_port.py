"""rank_group bridge: matching's real ranking code over the real adapter pipeline.

Imports server.matching only to prove the published contract; no runtime code in
server/providers imports matching internals.
"""
from __future__ import annotations

import asyncio
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

from server.matching import ranking
from server.matching.feasibility import FeasibleGroup
from server.matching.models import MatchingError, ModelEvidence, PublicParticipant, Window
from server.providers.errors import ProviderError
from server.providers.fixture import FixtureMuse, ScriptedTransport
from server.providers.port import TaskRegistry
from server.providers.rank_port import (
    RANK_PROMPT_VERSION,
    RANK_REASON_CODES,
    KeywordMusePort,
    build_live_rank_port,
    build_rank_port,
    register_rank_group_task,
)

T0 = datetime(2026, 11, 14, 21, 0, tzinfo=timezone.utc)


def group(ids, interests):
    return FeasibleGroup(
        member_ids=tuple(ids),
        common_windows=(Window(T0, T0 + timedelta(hours=2)),),
        shared_interests=tuple(interests),
        max_activity_minutes=90,
        budget_cap_minor=1500,
        baseline_score=1.0,
    )


GROUPS = [group(["p1", "p2", "p3"], ["climbing"]), group(["p1", "p4", "p5", "p6"], ["board games", "hiking"])]
PROFILES = {
    pid: PublicParticipant(pid, f"Synthetic {pid}", ("climbing",) if pid in ("p2", "p3") else ("board games", "hiking"), True)
    for pid in ("p1", "p2", "p3", "p4", "p5", "p6")
}


def port_with(transport: ScriptedTransport) -> KeywordMusePort:
    return KeywordMusePort(FixtureMuse(register_rank_group_task(TaskRegistry()), transport))


class ContractConformance(unittest.TestCase):
    def test_spec_mirrors_matching_constants(self):
        self.assertEqual(RANK_PROMPT_VERSION, ranking.PROMPT_VERSION)
        self.assertEqual(frozenset(RANK_REASON_CODES), ranking.REASON_CODES)
        self.assertEqual(ranking.TASK_RANK_GROUP, "rank_group")


class RankPortTests(unittest.IsolatedAsyncioTestCase):
    async def test_rank_with_muse_through_adapter(self):
        seen = {}

        def handler(payload):
            seen.update(payload)
            return {"optionId": "g1", "sharedInterests": ["hiking"], "reasonCodes": ["strong_shared_interest", "balanced_size"]}

        port = port_with(ScriptedTransport().on("rank_group", handler))
        decision, evidence = await ranking.rank_with_muse(port, GROUPS, PROFILES, "p1", "req-1")
        self.assertEqual(decision.option_index, 1)
        self.assertEqual(decision.shared_interests, ("hiking",))
        self.assertIsInstance(evidence, ModelEvidence)
        self.assertEqual(evidence.source, "replay")  # fixtures are never labeled live
        self.assertTrue(evidence.model.startswith("fixture:"))
        # The payload Muse sees carries refs, not participant ids or names.
        self.assertEqual(seen["requester"], "m0")
        self.assertNotIn("p1", str(seen))
        self.assertNotIn("Synthetic", str(seen))

    async def test_schema_violation_retried_then_matching_rejects(self):
        bad = {"optionId": "g0", "sharedInterests": [], "reasonCodes": ["made_up"]}
        transport = ScriptedTransport().on("rank_group", lambda _p: bad)
        with self.assertRaises(MatchingError) as ctx:
            await ranking.rank_with_muse(port_with(transport), GROUPS, PROFILES, "p1", "req-2", attempts=1)
        self.assertEqual(ctx.exception.code, "PROVIDER_UNAVAILABLE")
        self.assertEqual(len(transport.calls), 2)  # adapter retried malformed output once

    async def test_out_of_range_option_rejected_by_matching(self):
        transport = ScriptedTransport().on("rank_group", lambda _p: {"optionId": "g9", "sharedInterests": [], "reasonCodes": ["balanced_size"]})
        with self.assertRaises(MatchingError):
            await ranking.rank_with_muse(port_with(transport), GROUPS, PROFILES, "p1", "req-3", attempts=1)

    async def test_unregistered_prompt_version_fails_closed(self):
        port = port_with(ScriptedTransport())
        with self.assertRaises(ProviderError) as ctx:
            await port.generate(task="rank_group", requestId="r", promptVersion="rank_group.v999", payload={})
        self.assertEqual(ctx.exception.kind, "unknown_task")

    async def test_unknown_task_fails_closed(self):
        with self.assertRaises(ProviderError) as ctx:
            await port_with(ScriptedTransport()).generate(task="send_email", requestId="r", promptVersion="x", payload={})
        self.assertEqual(ctx.exception.kind, "unknown_task")

    async def test_unconfigured_port_fails_closed(self):
        with self.assertRaises(ProviderError) as ctx:
            await build_rank_port(None).generate(task="rank_group", requestId="r", promptVersion=RANK_PROMPT_VERSION, payload={})
        self.assertEqual(ctx.exception.kind, "not_configured")

    async def test_cancellation_propagates(self):
        transport = ScriptedTransport(delay_s=5).on("rank_group", lambda _p: {})
        task = asyncio.create_task(port_with(transport).generate(
            task="rank_group", requestId="r", promptVersion=RANK_PROMPT_VERSION, payload={}))
        await asyncio.sleep(0.01)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task

    def test_live_builder_refuses_without_key(self):
        saved = {k: os.environ.pop(k) for k in ("MUSE_API_KEY", "MODEL_API_KEY") if k in os.environ}
        try:
            with tempfile.TemporaryDirectory() as d:
                with self.assertRaises(RuntimeError):
                    build_live_rank_port(env_file=os.path.join(d, "absent.env"))
        finally:
            os.environ.update(saved)


if __name__ == "__main__":
    unittest.main()
