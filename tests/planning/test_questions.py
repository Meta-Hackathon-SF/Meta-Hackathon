"""Question bank validation and weekly selection (offline; no model call)."""
from __future__ import annotations

import asyncio
import copy
import json
import unittest
from datetime import date, timedelta

from server.planning import (
    BankError, InMemorySelectionStore, PlanningError, QuestionBank, QuestionService,
    load_default_bank, pick_week, question_problems,
)
from server.planning.selection import MAX_MEDIUM, NO_REPEAT_CYCLES

from .doubles import FIXTURES, TestOnlyWeekStart

FIXTURE_DOC = json.loads((FIXTURES / "question-bank.json").read_text())
WEEK = json.loads((FIXTURES / "week-sample.json").read_text())
CYCLE = WEEK["cycle"]["cycleId"]
COMMUNITY = WEEK["communityId"]
DAILY_KEYS = {"cycleId", "day", "date", "question"}
QUESTION_KEYS = {"questionId", "text", "category", "sensitivity", "signalTags", "followUpHint", "source", "active"}


def run(coro):
    return asyncio.run(coro)


def row(**kw):
    base = copy.deepcopy(FIXTURE_DOC["questions"][0])
    base.update(kw)
    return base


def week_rules_hold(test: unittest.TestCase, week: list[dict]) -> None:
    qs = [d["question"] for d in week]
    test.assertEqual([d["day"] for d in week], [1, 2, 3, 4, 5])
    test.assertEqual(qs[0]["sensitivity"], "low")
    medium = [q["sensitivity"] == "medium" for q in qs]
    test.assertLessEqual(sum(medium), MAX_MEDIUM)
    test.assertFalse(any(a and b for a, b in zip(medium, medium[1:])))
    test.assertEqual(len({q["questionId"] for q in qs}), 5)
    test.assertTrue(all(q["active"] for q in qs))


class BankValidationTests(unittest.TestCase):
    def test_shared_fixture_and_default_bank_load(self):
        fixture = QuestionBank.from_doc(FIXTURE_DOC)
        self.assertEqual(len(fixture.questions), len(FIXTURE_DOC["questions"]))
        default = load_default_bank()
        self.assertGreaterEqual(len([q for q in default.questions if q["active"]]), 5 * (NO_REPEAT_CYCLES + 1))
        # The default bank is a superset of the shared fixture, row for row.
        for q in fixture.questions:
            self.assertEqual(default.get(q["questionId"]), q)
        self.assertTrue(all(set(q) == QUESTION_KEYS for q in default.questions))

    def test_bad_rows_are_rejected(self):
        bad = [
            row(text="Too short"),
            row(text="x" * 141 + "?"),
            row(text="Do you like the dining hall?"),
            row(text="Tell me about your week."),
            row(category="dating"),
            row(sensitivity="high"),
            row(signalTags=[]),
            row(signalTags=["Meals"]),
            row(followUpHint="Say more."),
            row(source="scraped"),
            row(active="yes"),
            row(questionId="Q 1"),
            {k: v for k, v in row().items() if k != "followUpHint"},
            {**row(), "authorId": "p-maya"},
        ]
        for r in bad:
            self.assertTrue(question_problems(r), r)
        self.assertEqual(question_problems(row()), [])

    def test_bank_level_rules(self):
        with self.assertRaises(BankError):
            QuestionBank.from_doc({"contractVersion": "1.0.0", "questions": [row()]})
        with self.assertRaises(BankError):
            QuestionBank.from_doc({"contractVersion": "2.0.0", "questions": []})
        with self.assertRaises(BankError):
            QuestionBank.from_doc({"contractVersion": "2.0.0", "questions": [row(), row()]})
        with self.assertRaises(BankError) as ctx:
            QuestionBank.from_doc({"contractVersion": "2.0.0", "questions": [row(), row(questionId="q-2", category="x")]})
        self.assertIn("questions[1]", str(ctx.exception))
        with self.assertRaises(BankError):
            QuestionBank.load(FIXTURES / "does-not-exist.json")

    def test_operator_list_filters(self):
        bank = QuestionBank.from_doc(FIXTURE_DOC)
        self.assertTrue(all(q["category"] == "routine" for q in bank.list(category="routine")))
        self.assertEqual(bank.list(active=False), [])
        self.assertIsNone(bank.get("q-missing"))


class SelectionTests(unittest.TestCase):
    def service(self, bank=None, starts=None):
        store = InMemorySelectionStore()
        return QuestionService(bank or load_default_bank(), store, TestOnlyWeekStart(starts)), store

    def test_shape_dates_and_rules(self):
        svc, _ = self.service()
        week = run(svc.select_week(CYCLE, COMMUNITY))
        week_rules_hold(self, week)
        for d in week:
            self.assertEqual(set(d), DAILY_KEYS)
            self.assertEqual(set(d["question"]), QUESTION_KEYS)
            self.assertEqual(d["cycleId"], CYCLE)
        monday = date.fromisoformat(WEEK["cycle"]["weekStart"])
        self.assertEqual([d["date"] for d in week], [(monday + timedelta(days=i)).isoformat() for i in range(5)])
        self.assertEqual(len({d["question"]["category"] for d in week}), 5)

    def test_deterministic_with_seed_and_varies_across_seeds(self):
        bank = load_default_bank()
        a = [q["questionId"] for q in pick_week(bank, set(), seed=7)]
        b = [q["questionId"] for q in pick_week(bank, set(), seed=7)]
        self.assertEqual(a, b)
        others = {tuple(q["questionId"] for q in pick_week(bank, set(), seed=s)) for s in range(20)}
        self.assertGreater(len(others), 1)
        one, _ = self.service()
        two, _ = self.service()
        self.assertEqual(run(one.select_week(CYCLE, COMMUNITY)), run(two.select_week(CYCLE, COMMUNITY)))
        self.assertEqual(run(one.select_week(CYCLE, COMMUNITY, seed=3)), run(two.select_week(CYCLE, COMMUNITY)))

    def test_rules_hold_for_many_seeds(self):
        bank = load_default_bank()
        for seed in range(200):
            qs = pick_week(bank, set(), seed)
            week_rules_hold(self, [{"day": i + 1, "question": q} for i, q in enumerate(qs)])
            self.assertEqual(len({q["category"] for q in qs}), 5)

    def test_selection_is_stable_once_made(self):
        svc, _ = self.service()
        first = run(svc.select_week(CYCLE, COMMUNITY))
        svc.replace_bank(QuestionBank.from_doc(FIXTURE_DOC))
        self.assertEqual(run(svc.select_week(CYCLE, COMMUNITY, seed=99)), first)
        with self.assertRaises(PlanningError) as ctx:
            run(svc.select_week(CYCLE, "community-other"))
        self.assertEqual(ctx.exception.code, "NOT_FOUND")

    def test_no_repeat_within_four_weeks(self):
        monday = date(2026, 11, 9)
        starts = {f"cycle-{i}": (monday + timedelta(weeks=i)).isoformat() for i in range(8)}
        svc, _ = self.service(starts=starts)
        weeks = [[d["question"]["questionId"] for d in run(svc.select_week(f"cycle-{i}", COMMUNITY))] for i in range(8)]
        for i, ids in enumerate(weeks):
            previous = {q for w in weeks[max(0, i - NO_REPEAT_CYCLES):i] for q in w}
            self.assertFalse(previous & set(ids), f"cycle {i} repeats a recent question")

    def test_default_bank_can_always_fill_the_next_week(self):
        # Worst case for the rules: four weeks of history hold 20 low questions.
        bank = load_default_bank()
        low = [q for q in bank.questions if q["sensitivity"] == "low" and q["active"]]
        self.assertGreaterEqual(len(low), 5 * NO_REPEAT_CYCLES + 3)
        for seed in range(30):
            store = InMemorySelectionStore()
            starts = {f"c-{i}": (date(2026, 11, 9) + timedelta(weeks=i)).isoformat() for i in range(12)}
            svc = QuestionService(bank, store, TestOnlyWeekStart(starts))
            for i in range(12):
                week_rules_hold(self, run(svc.select_week(f"c-{i}", COMMUNITY, seed=seed * 100 + i)))

    def test_history_is_per_community(self):
        starts = {"c-a": "2026-11-09", "c-b": "2026-11-09"}
        svc, _ = self.service(starts=starts)
        a = run(svc.select_week("c-a", "community-a", seed=5))
        b = run(svc.select_week("c-b", "community-b", seed=5))
        self.assertEqual([d["question"]["questionId"] for d in a], [d["question"]["questionId"] for d in b])

    def test_bank_too_small_is_an_error_not_a_weaker_week(self):
        starts = {f"cycle-{i}": (date(2026, 11, 9) + timedelta(weeks=i)).isoformat() for i in range(3)}
        svc, _ = self.service(bank=QuestionBank.from_doc(FIXTURE_DOC), starts=starts)
        run(svc.select_week("cycle-0", COMMUNITY))
        run(svc.select_week("cycle-1", COMMUNITY))
        with self.assertRaises(PlanningError) as ctx:
            run(svc.select_week("cycle-2", COMMUNITY))  # 12 questions cannot cover a third week
        self.assertEqual(ctx.exception.code, "INVALID_INPUT")
        medium_only = QuestionBank.from_doc({"contractVersion": "2.0.0", "questions": [
            row(questionId=f"q-{i}", text=f"What is hard about week number {i} here?", sensitivity="medium")
            for i in range(6)]})
        with self.assertRaises(PlanningError):
            pick_week(medium_only, set(), seed=1)

    def test_inactive_questions_never_selected(self):
        doc = copy.deepcopy(FIXTURE_DOC)
        doc["questions"][0]["active"] = False
        bank = QuestionBank.from_doc(doc)
        for seed in range(50):
            self.assertNotIn(doc["questions"][0]["questionId"], [q["questionId"] for q in pick_week(bank, set(), seed)])

    def test_week_start_must_be_a_monday(self):
        svc, _ = self.service(starts={"c-tue": "2026-11-10", "c-bad": "next week"})
        for cycle in ("c-tue", "c-bad"):
            with self.assertRaises(PlanningError) as ctx:
                run(svc.select_week(cycle, COMMUNITY))
            self.assertEqual(ctx.exception.code, "INVALID_INPUT")


class FutureDayLeakTests(unittest.TestCase):
    def setUp(self):
        self.svc = QuestionService(load_default_bank(), InMemorySelectionStore(), TestOnlyWeekStart())
        self.week = run(self.svc.select_week(CYCLE, COMMUNITY))

    def test_released_never_includes_a_future_day(self):
        for current in range(1, 6):
            released = self.svc.released(CYCLE, current)
            self.assertEqual([d["day"] for d in released], list(range(1, current + 1)))
            blob = json.dumps(released)
            for future in self.week[current:]:
                self.assertNotIn(future["question"]["questionId"], blob)
                self.assertNotIn(future["question"]["text"], blob)

    def test_future_day_lookup_is_indistinguishable_from_missing(self):
        self.assertEqual(self.svc.question_for_day(CYCLE, 2, current_day=3), self.week[1])
        for day in (4, 5, 6, 0):
            with self.assertRaises(PlanningError) as ctx:
                self.svc.question_for_day(CYCLE, day, current_day=3)
            self.assertEqual(ctx.exception.code, "NOT_FOUND")

    def test_bad_current_day_and_unknown_cycle(self):
        for bad in (0, 6, True, "5", 2.0, None):
            with self.assertRaises(PlanningError):
                self.svc.released(CYCLE, bad)
        with self.assertRaises(PlanningError) as ctx:
            self.svc.released("cycle-unknown", 1)
        self.assertEqual(ctx.exception.code, "NOT_FOUND")

    def test_all_days_after_lock(self):
        self.assertEqual(len(self.svc.released(CYCLE, 3, cycle_open=False)), 5)


if __name__ == "__main__":
    unittest.main()


class QuestionTextsTests(unittest.TestCase):
    def test_formation_reader_returns_the_selected_week_for_that_community_only(self):
        svc = QuestionService(load_default_bank(), InMemorySelectionStore(), TestOnlyWeekStart())
        week = run(svc.select_week(CYCLE, COMMUNITY))
        texts = svc.question_texts(CYCLE, COMMUNITY)
        self.assertEqual(texts, {d["question"]["questionId"]: d["question"]["text"] for d in week})
        self.assertEqual(len(texts), 5)
        for bad in ((CYCLE, "another-group"), ("cycle-unknown", COMMUNITY)):
            with self.assertRaises(PlanningError) as ctx:
                svc.question_texts(*bad)
            self.assertEqual(ctx.exception.code, "NOT_FOUND")

    def test_formation_snapshot_shape_matches_the_contract(self):
        from server.providers.contract import M4_IN
        from server.providers.schema import validate

        svc = QuestionService(load_default_bank(), InMemorySelectionStore(), TestOnlyWeekStart())
        run(svc.select_week(CYCLE, COMMUNITY))
        questions = [{"questionId": k, "text": v} for k, v in svc.question_texts(CYCLE, COMMUNITY).items()]
        qid = questions[0]["questionId"]
        validate({"themes": [], "answers": [{"id": "r1", "text": "nobody", "questionId": qid}],
                  "blockedPairs": [], "questions": questions}, M4_IN)
