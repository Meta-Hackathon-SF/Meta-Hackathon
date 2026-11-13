"""M6 question generation behind operator approval (step 7, cuttable).

Muse proposes new daily questions from AGGREGATE signal tags only: the prompt
holds tag names with shares, the category mix wanted and recent question ids.
It never holds an answer, a player id or a theme label.

Where the signals come from: ``signals.aggregate_signals`` turns opted-in
players' allowlisted activity topics (D010, from their posts and comments) or
theme tags into thresholded, rounded community shares. Code then records which
input signals each proposal actually used (``basis.matchedSignals``), so the
operator view can show what grounded every question.

Nothing Muse writes can reach a player on its own:
  - each proposal must be a valid ``Question`` (10-140 chars, open-ended, known
    category, low or medium sensitivity) and pass OutputGuard, as must its hint
  - a proposal that repeats, or nearly repeats, a bank question or another
    proposal is dropped (content-word overlap, not just exact text)
  - categories follow the requested mix: a category with weight 0 is refused
    and none may exceed its share of ``count``
  - every refusal is counted by reason, so the operator sees what code removed
  - survivors are stored as PENDING with ``source: "generated"``, ``active:
    false``, outside the bank, so weekly selection cannot pick them
  - only an operator's ``approve`` adds one to the bank as active
"""
from __future__ import annotations

import math
import re
import uuid
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Callable

from server.providers import MUSE_VOICE, MusePort, MuseRequest, NullTrace, ProviderError, TaskRegistry, contract_spec
from server.providers.contract import QUESTION_CATEGORIES

from .errors import BankError, PlanningError
from .ports import OutputGuardPort, guard_allows
from .clarify import follow_up_problems
from .questions import question_problems
from .selection import QuestionService

GENERATION_PROMPT_VERSION = "question_generation.v2"
MAX_COUNT = 10
_TAG = re.compile(r"^[a-z][a-z0-9_]{0,39}$")
NEAR_DUPLICATE = 0.6  # Jaccard overlap of content words
_WORD = re.compile(r"[a-z0-9']+")
_STOPWORDS = frozenset("""
a an and are at be did do does for from had has have how i in is it its me my of on or our
so that the their them there they this to was we were what when where which who whom why
with you your yours this week today day
""".split())

# Reason codes for refused proposals (fixed vocabulary; never model text).
REASONS = ("invalid_question", "duplicate", "near_duplicate", "guard_text", "guard_hint",
           "category_not_requested", "over_category_quota", "over_count")
# Not refusals: a model-written follow-up hint that is yes/no or badly shaped is
# removed (set to null) and the question kept. Curated bank hints are exempt
# from the yes/no rule because a person wrote them; generated ones are not.

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
  answer would tell us. When aggregateSignals is not empty, ground each question
  in one of those tags and list that tag first; spread questions across
  different tags rather than repeating the most common one.
- Write questions that different people would answer differently, so answers
  reveal what something means to each person, not just facts. Two questions in
  one batch must not ask the same thing in different words.
- followUpHint: one short gentle open follow-up question ending with "?" that
  starts with What, When, Where, Who, How or Which (never yes/no), or null.
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

    def add(self, question: dict[str, Any], evidence: dict[str, Any], basis: dict[str, Any] | None = None) -> None:
        self._pending[question["questionId"]] = {"question": question, "evidence": evidence,
                                                 "basis": dict(basis or {"matchedSignals": []})}

    def list(self) -> list[dict[str, Any]]:
        return [{"question": dict(r["question"]), "evidence": dict(r["evidence"]),
                 "basis": {"matchedSignals": list(r["basis"]["matchedSignals"])}}
                for r in self._pending.values()]

    def pop(self, question_id: str) -> dict[str, Any] | None:
        return self._pending.pop(question_id, None)


@dataclass(frozen=True)
class GenerationResult:
    pending: list[dict[str, Any]]      # Question rows, source "generated", active false
    rejected: int                      # proposals dropped by validation or guard
    evidence: dict[str, Any]           # MuseCallEvidence (callType M6)
    rejections: dict[str, int] = field(default_factory=dict)  # reason code -> count
    basis: list[dict[str, Any]] = field(default_factory=list)  # per pending row: {matchedSignals}


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


def content_words(text: str) -> frozenset[str]:
    return frozenset(w for w in _WORD.findall(text.lower()) if w not in _STOPWORDS)


def is_near_duplicate(a: frozenset[str], b: frozenset[str]) -> bool:
    if not a or not b:
        return a == b
    return len(a & b) / len(a | b) >= NEAR_DUPLICATE


def category_quota(mix: dict[str, float], count: int) -> dict[str, int]:
    """How many of ``count`` questions each category may take (0 for unrequested)."""
    total = sum(mix.values())
    return {c: (max(1, math.ceil(count * w / total)) if w > 0 else 0) for c, w in mix.items()}


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
                 new_id: Callable[[], str] = lambda: uuid.uuid4().hex, trace: Any = None) -> None:
        self._muse = muse
        self._trace = trace if trace is not None else NullTrace()
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
        quota = category_quota(payload["categoryMix"], count)
        input_tags = {sig["tag"] for sig in payload["aggregateSignals"]}
        texts = [q["text"] for q in self._questions.bank.questions] + [r["question"]["text"] for r in self._pending.list()]
        taken = {t.lower() for t in texts}
        seen_words = [content_words(t) for t in texts]
        used: Counter[str] = Counter()
        reasons: Counter[str] = Counter()
        kept: list[dict[str, Any]] = []
        basis: list[dict[str, Any]] = []
        proposals = result.output["questions"]
        hints_dropped = 0
        for proposal in proposals[:count]:
            row = {
                "questionId": self._fresh_id(),
                **proposal,
                "signalTags": list(dict.fromkeys(proposal["signalTags"])),
                "source": "generated",
                "active": False,
            }
            if row["followUpHint"] is not None and follow_up_problems(row["followUpHint"]):
                row["followUpHint"] = None
                hints_dropped += 1
            reason = self._refusal(row, taken, seen_words, quota, used)
            if reason is not None:
                reasons[reason] += 1
                continue
            taken.add(row["text"].lower())
            seen_words.append(content_words(row["text"]))
            used[row["category"]] += 1
            grounds = {"matchedSignals": [t for t in row["signalTags"] if t in input_tags]}
            self._pending.add(row, evidence, grounds)
            kept.append(dict(row))
            basis.append(grounds)
        if len(proposals) > count:
            reasons["over_count"] += len(proposals) - count
        self._trace.note(request_id, "proposed", "questions", len(proposals))
        for code, n in sorted(reasons.items()):
            self._trace.note(request_id, "refused", code, n)
        if hints_dropped:
            self._trace.note(request_id, "repaired", "hint_removed", hints_dropped)
        self._trace.note(request_id, "kept", "pending_questions", len(kept))
        self._trace.note(request_id, "grounded", "questions_with_signal", sum(1 for b in basis if b["matchedSignals"]))
        return GenerationResult(kept, sum(reasons.values()), evidence, dict(reasons), basis)

    def _refusal(self, row: dict[str, Any], taken: set[str], seen_words: list[frozenset[str]],
                 quota: dict[str, int], used: Counter[str]) -> str | None:
        """First code rule the proposal breaks, as a reason code, or None."""
        if question_problems(row):
            return "invalid_question"
        if row["text"].lower() in taken:
            return "duplicate"
        words = content_words(row["text"])
        if any(is_near_duplicate(words, other) for other in seen_words):
            return "near_duplicate"
        if quota.get(row["category"], 0) == 0:
            return "category_not_requested"
        if used[row["category"]] >= quota[row["category"]]:
            return "over_category_quota"
        if not guard_allows(self._guard, row["text"], []):
            return "guard_text"
        hint = row["followUpHint"]
        if hint is not None and not guard_allows(self._guard, hint, []):
            return "guard_hint"
        return None

    def _fresh_id(self) -> str:
        used = {r["question"]["questionId"] for r in self._pending.list()}
        for _ in range(8):
            candidate = f"q-gen-{self._new_id()[:10]}"
            if candidate not in used and self._questions.bank.get(candidate) is None:
                return candidate
        raise PlanningError("PROVIDER_UNAVAILABLE", "could not allocate a question id", retryable=True)

    def pending(self) -> list[dict[str, Any]]:
        """Operator view of proposals awaiting approval: ``[{question, evidence, basis}]``."""
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
