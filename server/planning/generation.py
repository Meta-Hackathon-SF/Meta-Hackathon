"""M6 question generation behind operator approval (step 7, cuttable).

Muse proposes new daily questions from AGGREGATE signal tags only: the prompt
holds tag names with shares, the category mix wanted and recent question ids.
It never holds an answer, a player id or a theme label.

Nothing Muse writes can reach a player on its own:
  - each proposal must be a valid ``Question`` (10-140 chars, open-ended, known
    category, low or medium sensitivity) and pass OutputGuard, as must its hint
  - a proposal that repeats a bank question or another proposal is dropped
  - survivors are stored as PENDING with ``source: "generated"``, ``active:
    false``, outside the bank, so weekly selection cannot pick them
  - only an operator's ``approve`` adds one to the bank as active
"""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable

from server.providers import MUSE_VOICE, MusePort, MuseRequest, ProviderError, TaskRegistry, contract_spec
from server.providers.contract import QUESTION_CATEGORIES

from .errors import BankError, PlanningError
from .ports import OutputGuardPort, guard_allows
from .questions import question_problems
from .selection import QuestionService

GENERATION_PROMPT_VERSION = "question_generation.v1"
MAX_COUNT = 10
_TAG = re.compile(r"^[a-z][a-z0-9_]{0,39}$")

GENERATION_INSTRUCTIONS = """\
Task: write new daily questions for a weekly game where adults in a community
group each answer one question a day in a sentence or two.
Input: count (how many to write), categoryMix (relative weight per category),
aggregateSignals (topic tags with the share of the community they showed up
for; statistics only, no one's words) and recentQuestionIds (already used).
Rules for every question:
- text: 10 to 140 characters, one open question ending with "?". Not answerable
  with yes or no: start with what, where, when, who, how or which.
- Easy to answer honestly in one or two sentences, about everyday life.
- category: one of the categoryMix keys. Follow the mix roughly.
- sensitivity: "low" for light everyday topics, "medium" for anything about
  belonging, difficulty or change. Never write anything heavier than that.
- Never ask about health, sexuality, religion, money, family trouble, or where
  someone lives. Never ask anyone to name another person.
- signalTags: 1 to 4 lowercase tags (letters, digits, underscore) naming what an
  answer would tell us. Reuse aggregateSignals tags where they fit.
- followUpHint: one short gentle follow-up question ending with "?", or null.
- Do not reword a question whose id appears in recentQuestionIds.

""" + MUSE_VOICE


def register_generation_task(registry: TaskRegistry) -> TaskRegistry:
    registry.register(contract_spec(
        "question_generation", GENERATION_PROMPT_VERSION, GENERATION_INSTRUCTIONS,
        max_output_tokens=6000, temperature=0.8,
    ))
    return registry


@dataclass
class InMemoryPendingQuestions:
    """Process-local queue of generated questions awaiting an operator. Not durable."""

    _pending: dict[str, dict[str, Any]] = field(default_factory=dict)

    def add(self, question: dict[str, Any], evidence: dict[str, Any]) -> None:
        self._pending[question["questionId"]] = {"question": question, "evidence": evidence}

    def list(self) -> list[dict[str, Any]]:
        return [{"question": dict(r["question"]), "evidence": dict(r["evidence"])} for r in self._pending.values()]

    def pop(self, question_id: str) -> dict[str, Any] | None:
        return self._pending.pop(question_id, None)


@dataclass(frozen=True)
class GenerationResult:
    pending: list[dict[str, Any]]      # Question rows, source "generated", active false
    rejected: int                      # proposals dropped by validation or guard
    evidence: dict[str, Any]           # MuseCallEvidence (callType M6)


def normalize_mix(category_mix: Any) -> dict[str, float]:
    """All seven categories, non-negative numbers, at least one positive."""
    if category_mix is None:
        return {c: 1.0 for c in QUESTION_CATEGORIES}
    if not isinstance(category_mix, dict) or set(category_mix) - set(QUESTION_CATEGORIES):
        raise PlanningError("INVALID_INPUT", "categoryMix has unknown categories")
    mix: dict[str, float] = {}
    for c in QUESTION_CATEGORIES:
        value = category_mix.get(c, 0)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
            raise PlanningError("INVALID_INPUT", "categoryMix values must be non-negative numbers")
        mix[c] = float(value)
    if not any(mix.values()):
        raise PlanningError("INVALID_INPUT", "categoryMix needs at least one positive weight")
    return mix


def normalize_signals(signals: Any) -> list[dict[str, Any]]:
    """``[{tag, share}]`` only. Anything shaped like free text is refused."""
    if signals is None:
        return []
    if not isinstance(signals, list) or len(signals) > 50:
        raise PlanningError("INVALID_INPUT", "aggregateSignals must be a list of at most 50 items")
    out = []
    for s in signals:
        if not isinstance(s, dict) or set(s) != {"tag", "share"} or not isinstance(s["tag"], str) or not _TAG.match(s["tag"]):
            raise PlanningError("INVALID_INPUT", "aggregateSignals items must be {tag, share} with a lowercase tag")
        share = s["share"]
        if isinstance(share, bool) or not isinstance(share, (int, float)) or not (0 <= share <= 1):
            raise PlanningError("INVALID_INPUT", "aggregateSignals share must be between 0 and 1")
        out.append({"tag": s["tag"], "share": float(share)})
    return out


class QuestionGenerator:
    def __init__(self, muse: MusePort, guard: OutputGuardPort, questions: QuestionService,
                 pending: InMemoryPendingQuestions | None = None, *,
                 new_id: Callable[[], str] = lambda: uuid.uuid4().hex) -> None:
        self._muse = muse
        self._guard = guard
        self._questions = questions
        self._pending = pending if pending is not None else InMemoryPendingQuestions()
        self._new_id = new_id

    async def generate(self, *, count: int, request_id: str, category_mix: Any = None,
                       aggregate_signals: Any = None, recent_question_ids: list[str] | None = None) -> GenerationResult:
        if isinstance(count, bool) or not isinstance(count, int) or not (1 <= count <= MAX_COUNT):
            raise PlanningError("INVALID_INPUT", "count must be 1-10")
        payload = {
            "recentQuestionIds": list(recent_question_ids or [])[:200],
            "categoryMix": normalize_mix(category_mix),
            "aggregateSignals": normalize_signals(aggregate_signals),
            "count": count,
        }
        try:
            result = await self._muse.run(MuseRequest(
                task="question_generation", request_id=request_id,
                prompt_version=GENERATION_PROMPT_VERSION, payload=payload,
            ))
        except ProviderError as exc:
            raise PlanningError("PROVIDER_UNAVAILABLE", f"question generation failed ({exc.kind})",
                                retryable=exc.retryable) from None
        evidence = dict(result.evidence)
        taken = {q["text"].lower() for q in self._questions.bank.questions}
        taken |= {r["question"]["text"].lower() for r in self._pending.list()}
        kept: list[dict[str, Any]] = []
        rejected = 0
        for proposal in result.output["questions"][:count]:
            row = {
                "questionId": self._fresh_id(),
                **proposal,
                "signalTags": list(dict.fromkeys(proposal["signalTags"])),
                "source": "generated",
                "active": False,
            }
            hint = row["followUpHint"]
            if (question_problems(row) or row["text"].lower() in taken
                    or not guard_allows(self._guard, row["text"], [])
                    or (hint is not None and not guard_allows(self._guard, hint, []))):
                rejected += 1
                continue
            taken.add(row["text"].lower())
            self._pending.add(row, evidence)
            kept.append(dict(row))
        rejected += max(0, len(result.output["questions"]) - count)
        return GenerationResult(kept, rejected, evidence)

    def _fresh_id(self) -> str:
        used = {r["question"]["questionId"] for r in self._pending.list()}
        for _ in range(8):
            candidate = f"q-gen-{self._new_id()[:10]}"
            if candidate not in used and self._questions.bank.get(candidate) is None:
                return candidate
        raise PlanningError("PROVIDER_UNAVAILABLE", "could not allocate a question id", retryable=True)

    def pending(self) -> list[dict[str, Any]]:
        """Operator view of proposals awaiting approval: ``[{question, evidence}]``."""
        return self._pending.list()

    def approve(self, question_id: str) -> dict[str, Any]:
        """Operator approval: the question joins the bank as active. Re-guarded first."""
        record = self._pending.pop(question_id)
        if record is None:
            raise PlanningError("NOT_FOUND", "no pending question with that id")
        row = {**record["question"], "active": True}
        hint = row["followUpHint"]
        if not guard_allows(self._guard, row["text"], []) or (hint is not None and not guard_allows(self._guard, hint, [])):
            raise PlanningError("INVALID_INPUT", "question no longer passes the output guard")
        try:
            self._questions.replace_bank(self._questions.bank.with_questions([row]))
        except BankError:
            raise PlanningError("INVALID_INPUT", "question is not valid for the bank") from None
        return row

    def reject(self, question_id: str) -> None:
        if self._pending.pop(question_id) is None:
            raise PlanningError("NOT_FOUND", "no pending question with that id")
