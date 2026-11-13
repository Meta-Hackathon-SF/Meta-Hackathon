"""M2 clarify over the fixture Muse (scripted transport; no network, no paid calls)."""
from __future__ import annotations

import asyncio
import json
import unittest

from server.planning import ClarifyService, PlanningError, register_planning_tasks
from server.planning.clarify import CLARIFY_INSTRUCTIONS, CLARIFY_PROMPT_VERSION
from server.providers import MUSE_VOICE, ProviderError, TaskRegistry
from server.providers.fixture import FIXTURE_MODEL, FixtureMuse, ScriptedTransport, decode_user_message

from .doubles import FIXTURES, TestOnlyOutputGuard

BANK = {q["questionId"]: q for q in json.loads((FIXTURES / "question-bank.json").read_text())["questions"]}
WITH_HINT = BANK["q-routine-meals"]        # followUpHint: "Was that by choice?"
NO_HINT = BANK["q-belonging-pretend"]      # followUpHint: null
WEEK = json.loads((FIXTURES / "week-sample.json").read_text())
ANSWER = "Mostly the dining hall corner table with headphones in"
ASK = {"needsFollowup": True, "question": "What do you like about that corner?"}


def run(coro):
    return asyncio.run(coro)


def make(*steps):
    transport = ScriptedTransport()
    if steps:
        transport.queue("clarify", *steps)
    muse = FixtureMuse(register_planning_tasks(TaskRegistry()), transport)
    guard = TestOnlyOutputGuard()
    ids = iter(f"rand-{i}" for i in range(100))
    return ClarifyService(muse, guard, new_id=lambda: next(ids)), transport, guard


def ask(svc, **kw):
    base = dict(answer_id="ans-1", question=WITH_HINT, answer_text=ANSWER, request_id="req-1")
    base.update(kw)
    return run(svc.follow_up(**base))


class ClarifyTests(unittest.TestCase):
    def test_muse_follow_up_is_returned_with_replay_evidence(self):
        svc, transport, guard = make(ASK)
        res = ask(svc)
        self.assertEqual(res.output, ASK)
        self.assertEqual(set(res.output), {"needsFollowup", "question"})
        self.assertEqual(res.source, "muse")
        self.assertEqual(res.evidence["callType"], "M2")
        self.assertEqual(res.evidence["source"], "replay")  # fixture is never labeled live
        self.assertEqual(res.evidence["model"], FIXTURE_MODEL)
        self.assertEqual(guard.calls, [(ASK["question"], [])])
        self.assertEqual(len(transport.calls), 1)

    def test_prompt_carries_only_question_text_random_id_and_answer_text(self):
        svc, transport, _ = make(ASK)
        ask(svc, answer_id="ans-secret-77")
        sent = transport.calls[0]
        message = decode_user_message(sent.user)
        self.assertEqual(message, {"task": "clarify", "input": {
            "question": WITH_HINT["text"], "answer": {"id": "rand-0", "text": ANSWER}}})
        self.assertNotIn("ans-secret-77", sent.user + sent.developer)
        self.assertNotIn(ANSWER, sent.developer)
        self.assertNotIn(WITH_HINT["followUpHint"], sent.user)
        self.assertIn(MUSE_VOICE, sent.developer)

    def test_one_follow_up_max_per_answer(self):
        svc, transport, _ = make(ASK, {"needsFollowup": True, "question": "A second, different question?"})
        first = ask(svc)
        again = ask(svc, request_id="req-2")
        self.assertEqual(again, first)
        self.assertEqual(len(transport.calls), 1)
        used = ask(svc, follow_up_used=True)
        self.assertEqual(used.output, {"needsFollowup": False, "question": ""})
        self.assertEqual(len(transport.calls), 1)
        other = ask(svc, answer_id="ans-2")
        self.assertEqual(other.output["question"], "A second, different question?")

    def test_a_no_follow_up_decision_is_also_final(self):
        svc, transport, _ = make({"needsFollowup": False, "question": ""}, ASK)
        self.assertFalse(ask(svc).output["needsFollowup"])
        self.assertFalse(ask(svc).output["needsFollowup"])
        self.assertEqual(len(transport.calls), 1)

    def test_flagged_answer_never_reaches_muse(self):
        distress = WEEK["distressFixture"]
        for flag in ("distress", "harm"):
            svc, transport, guard = make(ASK)
            res = ask(svc, answer_text=distress["text"], safety_flag=flag)
            self.assertEqual(res.output, {"needsFollowup": False, "question": ""})
            self.assertEqual(res.source, "none")
            self.assertIsNone(res.evidence)
            self.assertEqual(transport.calls, [])
            self.assertEqual(guard.calls, [])

    def test_prompt_injection_stays_data(self):
        injection = WEEK["injectionFixture"]["text"]
        svc, transport, _ = make({"needsFollowup": False, "question": ""})
        ask(svc, answer_text=injection)
        sent = transport.calls[0]
        self.assertNotIn(injection, sent.developer)
        self.assertEqual(sent.developer.count(CLARIFY_INSTRUCTIONS), 1)
        self.assertTrue(sent.user.startswith("UNTRUSTED_INPUT_JSON"))

    def test_invalid_json_one_retry_then_labeled_fallback(self):
        svc, transport, _ = make("not json", "{still not json", ASK)
        res = ask(svc)
        self.assertEqual(len(transport.calls), 2)  # exactly one retry
        self.assertEqual(res.source, "fallback")
        self.assertTrue(res.is_fallback)
        self.assertIsNone(res.evidence)
        self.assertEqual(res.output, {"needsFollowup": True, "question": WITH_HINT["followUpHint"]})

    def test_invalid_json_then_valid_retry_succeeds(self):
        svc, transport, _ = make("not json", ASK)
        res = ask(svc)
        self.assertEqual(res.source, "muse")
        self.assertEqual(len(transport.calls), 2)

    def test_provider_down_without_hint_means_no_follow_up(self):
        svc, _, _ = make(ProviderError("auth", "x", status=401))
        res = ask(svc, question=NO_HINT)
        self.assertEqual(res.output, {"needsFollowup": False, "question": ""})
        self.assertEqual(res.source, "fallback")

    def test_guard_rejection_falls_back_and_never_shows_the_proposal(self):
        cases = [
            "Have you talked to a therapist about that?",   # sensitive_term
            "Want to text me at 555-0100?",                 # contact_info
            "Why? And who with?",                           # two questions
            "Is there a small moment you would like to share more about?",  # yes/no (seen live)
            "Tell me more about the corner table.",         # not a question
            "What " + "really " * 30 + "happened?",         # too long
            "   ",
        ]
        for proposed in cases:
            svc, _, _ = make({"needsFollowup": True, "question": proposed})
            res = ask(svc)
            self.assertEqual(res.source, "fallback", proposed)
            self.assertEqual(res.output["question"], WITH_HINT["followUpHint"])
            svc, _, _ = make({"needsFollowup": True, "question": proposed})
            self.assertEqual(ask(svc, question=NO_HINT).output, {"needsFollowup": False, "question": ""})

    def test_broken_guard_fails_closed(self):
        class Broken:
            def check(self, text, against_answers):
                return {"ok": "yes"}

        class Raising:
            def check(self, text, against_answers):
                raise RuntimeError("guard offline")

        for guard in (Broken(), Raising()):
            muse = FixtureMuse(register_planning_tasks(TaskRegistry()), ScriptedTransport().queue("clarify", ASK))
            res = run(ClarifyService(muse, guard).follow_up(
                answer_id="a", question=WITH_HINT, answer_text=ANSWER, request_id="r"))
            self.assertEqual(res.output, {"needsFollowup": False, "question": ""})

    def test_answer_length_is_validated(self):
        svc, transport, _ = make(ASK)
        for bad in ("", "x" * 401, None):
            with self.assertRaises(PlanningError) as ctx:
                ask(svc, answer_text=bad)
            self.assertEqual(ctx.exception.code, "INVALID_INPUT")
        self.assertEqual(transport.calls, [])

    def test_registered_under_the_contract_task_and_version(self):
        registry = register_planning_tasks(TaskRegistry())
        self.assertIn(("clarify", CLARIFY_PROMPT_VERSION), registry.keys())


if __name__ == "__main__":
    unittest.main()
