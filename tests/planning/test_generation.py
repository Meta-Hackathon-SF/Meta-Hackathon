"""M6 question generation behind operator approval (fixture Muse; offline)."""
from __future__ import annotations

import asyncio
import json
import unittest

from server.planning import (
    InMemorySelectionStore, PlanningError, QuestionGenerator, QuestionService,
    load_default_bank, pick_week, register_planning_tasks,
)
from server.providers import MUSE_VOICE, ProviderError, TaskRegistry
from server.providers.fixture import FixtureMuse, ScriptedTransport, decode_user_message

from .doubles import FIXTURES, TestOnlyOutputGuard, TestOnlyWeekStart

WEEK = json.loads((FIXTURES / "week-sample.json").read_text())


def proposal(text, **over):
    base = {"text": text, "category": "routine", "sensitivity": "low", "signalTags": ["routine"], "followUpHint": None}
    base.update(over)
    return base


PROPOSALS = [
    proposal("What part of your walk across campus do you look forward to?", signalTags=["routine", "places"]),
    proposal("Who did you end up talking to longer than you expected this week?", category="belonging",
             sensitivity="medium", followUpHint="What kept the conversation going?"),
    proposal("What would you put on a shared playlist for this group?", category="interests"),
]
SIGNALS = [{"tag": "solitude", "share": 0.43}, {"tag": "meals", "share": 0.57}]


def run(coro):
    return asyncio.run(coro)


def make(*steps):
    transport = ScriptedTransport()
    if steps:
        transport.queue("question_generation", *steps)
    muse = FixtureMuse(register_planning_tasks(TaskRegistry()), transport)
    questions = QuestionService(load_default_bank(), InMemorySelectionStore(), TestOnlyWeekStart())
    ids = iter(f"{i:010x}" + "0" * 22 for i in range(1, 100))
    return QuestionGenerator(muse, TestOnlyOutputGuard(), questions, new_id=lambda: next(ids)), transport, questions


def gen(g, **kw):
    base = dict(count=3, request_id="req-gen", aggregate_signals=SIGNALS)
    base.update(kw)
    return run(g.generate(**base))


class GenerationTests(unittest.TestCase):
    def test_valid_proposals_become_pending_not_active(self):
        g, _, questions = make({"questions": PROPOSALS})
        before = len(questions.bank.questions)
        res = gen(g)
        self.assertEqual(len(res.pending), 3)
        self.assertEqual(res.rejected, 0)
        self.assertEqual(res.evidence["callType"], "M6")
        self.assertEqual(res.evidence["source"], "replay")
        for q in res.pending:
            self.assertEqual((q["source"], q["active"]), ("generated", False))
            self.assertTrue(q["questionId"].startswith("q-gen-"))
        self.assertEqual(len(questions.bank.questions), before)
        self.assertEqual(len(g.pending()), 3)

    def test_pending_questions_can_never_be_selected(self):
        g, _, questions = make({"questions": PROPOSALS})
        pending_ids = {q["questionId"] for q in gen(g).pending}
        for seed in range(100):
            self.assertFalse(pending_ids & {q["questionId"] for q in pick_week(questions.bank, set(), seed)})

    def test_prompt_holds_aggregates_only(self):
        g, transport, _ = make({"questions": PROPOSALS})
        gen(g, category_mix={"routine": 2, "belonging": 1}, recent_question_ids=["q-routine-meals"])
        sent = transport.calls[0]
        payload = decode_user_message(sent.user)["input"]
        self.assertEqual(set(payload), {"recentQuestionIds", "categoryMix", "aggregateSignals", "count"})
        self.assertEqual(payload["aggregateSignals"], SIGNALS)
        self.assertEqual(len(payload["categoryMix"]), 7)
        self.assertEqual(payload["categoryMix"]["hopes"], 0.0)
        for answer in WEEK["answers"]:
            self.assertNotIn(answer["text"], sent.user + sent.developer)
        for player in WEEK["players"]:
            self.assertNotIn(player["playerId"], sent.user)
        self.assertIn(MUSE_VOICE, sent.developer)

    def test_answer_text_cannot_be_smuggled_in_as_a_signal(self):
        g, transport, _ = make({"questions": PROPOSALS})
        bad_signals = [
            [{"tag": "I eat in my room so no one sees me alone", "share": 0.2}],
            [{"tag": "solitude", "share": 0.2, "example": "cooking for one"}],
            [{"tag": "solitude", "share": 4}],
            ["solitude"],
            "solitude",
        ]
        for signals in bad_signals:
            with self.assertRaises(PlanningError) as ctx:
                gen(g, aggregate_signals=signals)
            self.assertEqual(ctx.exception.code, "INVALID_INPUT")
        for mix in ({"dating": 1}, {"routine": -1}, {"routine": 0}, ["routine"]):
            with self.assertRaises(PlanningError):
                gen(g, category_mix=mix)
        for count in (0, 11, True, "3", None):
            with self.assertRaises(PlanningError):
                gen(g, count=count)
        self.assertEqual(transport.calls, [])

    def test_bad_proposals_are_dropped_and_counted(self):
        existing = load_default_bank().questions[0]["text"]
        proposals = [
            PROPOSALS[0],
            proposal("Do you eat alone in the dining hall most days?"),              # yes/no
            proposal("What has your therapist said about your week so far?"),         # guard: sensitive
            proposal(existing),                                                        # duplicate of the bank
            proposal(PROPOSALS[0]["text"].upper().replace("?", "") + "?"),             # duplicate of a proposal
            proposal("What made you smile today, and who was there with you?", signalTags=["Joy!"]),
            proposal("Where do you go to think things over on a slow day?", followUpHint="Text me at 555-0100?"),
        ]
        g, _, _ = make({"questions": proposals})
        res = gen(g, count=7)
        self.assertEqual([q["text"] for q in res.pending], [PROPOSALS[0]["text"]])
        self.assertEqual(res.rejected, 6)

    def test_extra_proposals_beyond_count_are_ignored(self):
        g, _, _ = make({"questions": PROPOSALS})
        res = gen(g, count=1)
        self.assertEqual(len(res.pending), 1)
        self.assertEqual(res.rejected, 2)

    def test_high_sensitivity_is_rejected_by_the_adapter_schema(self):
        bad = {"questions": [proposal("What scares you most about being here?", sensitivity="high")]}
        g, transport, _ = make(bad, bad)
        with self.assertRaises(PlanningError) as ctx:
            gen(g)
        self.assertEqual(ctx.exception.code, "PROVIDER_UNAVAILABLE")
        self.assertTrue(ctx.exception.retryable)
        self.assertEqual(len(transport.calls), 2)  # exactly one retry
        self.assertEqual(g.pending(), [])

    def test_provider_failure_creates_nothing(self):
        g, _, questions = make(ProviderError("auth", "x", status=401))
        before = len(questions.bank.questions)
        with self.assertRaises(PlanningError) as ctx:
            gen(g)
        self.assertFalse(ctx.exception.retryable)
        self.assertEqual((g.pending(), len(questions.bank.questions)), ([], before))

    def test_approve_activates_and_reject_discards(self):
        g, _, questions = make({"questions": PROPOSALS})
        first, second, _third = gen(g).pending
        approved = g.approve(first["questionId"])
        self.assertEqual((approved["active"], approved["source"]), (True, "generated"))
        self.assertEqual(questions.bank.get(first["questionId"]), approved)
        g.reject(second["questionId"])
        self.assertIsNone(questions.bank.get(second["questionId"]))
        self.assertEqual(len(g.pending()), 1)
        for gone in (first["questionId"], second["questionId"], "q-gen-unknown"):
            with self.assertRaises(PlanningError) as ctx:
                g.approve(gone)
            self.assertEqual(ctx.exception.code, "NOT_FOUND")
        with self.assertRaises(PlanningError):
            g.reject("q-gen-unknown")
        picked = {q["questionId"] for seed in range(300) for q in pick_week(questions.bank, set(), seed)}
        self.assertIn(first["questionId"], picked)


if __name__ == "__main__":
    unittest.main()
