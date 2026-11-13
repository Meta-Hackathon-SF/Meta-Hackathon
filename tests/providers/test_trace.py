"""ReasoningTrace: call records plus code verdicts, never text."""
from __future__ import annotations

import asyncio
import json
import unittest

from server.providers import ReasoningTrace, TaskRegistry
from server.providers.fixture import FixtureMuse, ScriptedTransport
from server.providers.port import MuseRequest


class TraceTests(unittest.TestCase):
    def test_notes_accept_codes_and_counts_only(self):
        t = ReasoningTrace()
        self.assertTrue(t.note("req-1", "refused", "near_duplicate", 2))
        for stage, code, count in [("refused", "I eat alone in my room", 1), ("Guard", "rejected", 1),
                                   ("guard", "rejected", -1), ("guard", "rejected", True),
                                   ("guard", "x" * 41, 1), ("guard", "rejected", 10**6)]:
            self.assertFalse(t.note("req-1", stage, code, count))
        self.assertFalse(t.note("bad id with spaces", "guard", "rejected"))
        self.assertEqual(t.list()[0]["checks"], [{"stage": "refused", "code": "near_duplicate", "count": 2}])

    def test_bounded_newest_first_and_task_filter(self):
        t = ReasoningTrace(maxlen=3)
        for i in range(5):
            t.record_call({"requestId": f"r{i}", "task": "clarify" if i % 2 else "event_nudge", "outcome": "ok"})
        self.assertEqual([e["requestId"] for e in t.list()], ["r4", "r3", "r2"])
        self.assertEqual([e["requestId"] for e in t.list(task="clarify")], ["r3"])

    def test_record_call_copies_only_scalar_call_fields(self):
        t = ReasoningTrace()
        t.record_call({"requestId": "r1", "task": "clarify", "outcome": "ok", "payload": {"text": "secret"},
                       "model": {"nested": "secret"}})
        entry = t.list()[0]
        self.assertNotIn("payload", entry)
        self.assertNotIn("secret", json.dumps(entry))

    def test_fixture_calls_are_traced_as_replay(self):
        from server.planning import register_planning_tasks

        transport = ScriptedTransport().queue("clarify", {"needsFollowup": False, "question": ""})
        muse = FixtureMuse(register_planning_tasks(TaskRegistry()), transport)
        asyncio.run(muse.run(MuseRequest(task="clarify", request_id="r-fx", prompt_version="clarify.v2",
                                         payload={"question": "Where did you eat?", "answer": {"id": "a1", "text": "hall"}})))
        entry = muse.reasoning_trace.list()[0]
        self.assertEqual((entry["source"], entry["callType"], entry["outcome"]), ("replay", "M2", "ok"))


if __name__ == "__main__":
    unittest.main()
