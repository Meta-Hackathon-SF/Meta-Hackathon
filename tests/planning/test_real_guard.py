"""Planning services against Patrik's REAL OutputGuard (server.privacy), offline.

Integration evidence for the guard boundary only: Muse output is still scripted
(FixtureMuse, labeled replay) and chat / constellation context are test-only doubles.
Skipped when server.privacy's dependencies are not installed.
"""
from __future__ import annotations

import asyncio
import json
import unittest

from server.planning import (
    ClarifyService, InMemorySelectionStore, NudgeService, QuestionGenerator, QuestionService,
    VenueCatalog, load_default_bank, register_planning_tasks,
)
from server.providers import TaskRegistry
from server.providers.fixture import FixtureMuse, ScriptedTransport

from .doubles import FIXTURES, TestOnlyChat, TestOnlyWeekStart
from .test_generation import PROPOSALS, proposal
from .test_nudges import GOOD, MEANING, NOW, Context, changed

try:
    from server.privacy import OutputGuard
except ImportError:  # pragma: no cover
    OutputGuard = None

WEEK = json.loads((FIXTURES / "week-sample.json").read_text())
# Text Muse actually returned in the 2026-11-13 live checks (synthetic inputs).
LIVE_TEXT = [
    "What does that cozy pause in your day usually look like?",
    "Drop in for board games",
    "Simple games are out on tables and you can join in or watch for a while if you like.",
    "Drop in for board games at Library Commons, Thursday 5pm-6:30pm. Simple games are out on tables "
    "and you can join in or watch for a while if you like. Go if 3 of you are in.",
    "What small moment helps you feel part of things here?",
    "How do you usually ease into your mornings?",
    "What little thing made an ordinary day feel lighter lately?",
]


def run(coro):
    return asyncio.run(coro)


def muse(task, *steps):
    return FixtureMuse(register_planning_tasks(TaskRegistry()), ScriptedTransport().queue(task, *steps))


@unittest.skipIf(OutputGuard is None, "server.privacy not importable")
class RealGuardTests(unittest.TestCase):
    def setUp(self):
        self.guard = OutputGuard()

    def test_curated_bank_and_hints_pass(self):
        for q in load_default_bank().questions:
            for text in (q["text"], q["followUpHint"]):
                if text is not None:
                    self.assertEqual(self.guard.check(text, []), {"ok": True, "reasons": []}, text)

    def test_saved_live_muse_text_passes_against_fixture_answers(self):
        against = [a["text"] for a in WEEK["answers"]] + [MEANING]
        for text in LIVE_TEXT:
            self.assertTrue(self.guard.check(text, against)["ok"], text)

    def test_clarify_accepts_clean_and_falls_back_on_rejected(self):
        question = load_default_bank().get("q-routine-meals")
        ok = {"needsFollowup": True, "question": "What do you like about that corner?"}
        res = run(ClarifyService(muse("clarify", ok), self.guard).follow_up(
            answer_id="a1", question=question, answer_text="Mostly the dining hall", request_id="r"))
        self.assertEqual((res.source, res.output), ("muse", ok))
        for bad in ("What did your therapist say about that?", "What number can I text you on, 555-0100?"):
            res = run(ClarifyService(muse("clarify", {"needsFollowup": True, "question": bad}), self.guard).follow_up(
                answer_id="a2", question=question, answer_text="Mostly the dining hall", request_id="r"))
            self.assertEqual(res.source, "fallback", bad)
            self.assertEqual(res.output["question"], question["followUpHint"])

    def nudges(self, step):
        chat = TestOnlyChat()
        return NudgeService(muse("event_nudge", step), self.guard, VenueCatalog.load(), Context(), chat, now=lambda: NOW), chat

    def test_nudge_posts_clean_text_and_rejects_quotes_and_sensitive_terms(self):
        svc, chat = self.nudges(GOOD)
        posted = run(svc.propose_and_post("c-1"))
        self.assertEqual(posted["message"]["kind"], "muse_nudge")
        self.assertEqual(len(chat.posted), 1)
        quoting = "Come along, since you eat in my room so no one sees me alone anyway."
        for why in (quoting, "Good for people having most meals on their own and lonely.",
                    "Easier than therapy, and it is free."):
            svc, chat = self.nudges(changed(why=why))
            outcome = run(svc.propose_detailed("c-1"))
            self.assertIsNone(outcome.nudge, why)
            self.assertEqual(outcome.reason, "guard_rejected_text")
        svc, _ = self.nudges(changed(title="Text 555-0100 to join"))
        self.assertIsNone(run(svc.propose("c-1")))

    def test_generation_keeps_clean_and_drops_guarded(self):
        questions = QuestionService(load_default_bank(), InMemorySelectionStore(), TestOnlyWeekStart())
        proposals = [*PROPOSALS,
                     proposal("What has your therapist said about your week so far?"),
                     proposal("Where do you go to think things over on a slow day?", followUpHint="Text me at 555-0100?")]
        gen = QuestionGenerator(muse("question_generation", {"questions": proposals}), self.guard, questions)
        res = run(gen.generate(count=5, request_id="r"))
        self.assertEqual([q["text"] for q in res.pending], [p["text"] for p in PROPOSALS])
        self.assertEqual(res.rejected, 2)
        approved = gen.approve(res.pending[0]["questionId"])
        self.assertTrue(approved["active"])


if __name__ == "__main__":
    unittest.main()
