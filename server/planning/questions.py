"""Question bank: load and validate ``Question`` rows (contracts/protocol.ts 2.0.0).

A row that fails validation stops the load: a half-valid bank is never served.
The same ``validate_question`` gates M6 output before it can enter the bank.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from server.providers.contract import QUESTION_CATEGORIES, QUESTION_TEXT_MAX, QUESTION_TEXT_MIN, SENSITIVITIES
from server.providers.schema import SchemaViolation, validate

from .errors import BankError

CONTRACT_VERSION = "2.0.0"
SOURCES = ("curated", "generated")

QUESTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["questionId", "text", "category", "sensitivity", "signalTags", "followUpHint", "source", "active"],
    "properties": {
        "questionId": {"type": "string", "minLength": 1, "maxLength": 64},
        "text": {"type": "string", "minLength": QUESTION_TEXT_MIN, "maxLength": QUESTION_TEXT_MAX},
        "category": {"type": "string", "enum": list(QUESTION_CATEGORIES)},
        "sensitivity": {"type": "string", "enum": list(SENSITIVITIES)},
        "signalTags": {"type": "array", "minItems": 1, "maxItems": 6,
                       "items": {"type": "string", "minLength": 1, "maxLength": 40}},
        "followUpHint": {"type": ["string", "null"], "maxLength": 140},
        "source": {"type": "string", "enum": list(SOURCES)},
        "active": {"type": "boolean"},
    },
}

_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
_TAG = re.compile(r"^[a-z][a-z0-9_]{0,39}$")
# The contract asks for open-ended questions. A question that opens with an
# auxiliary verb invites a yes/no answer.
YES_NO_OPENING = re.compile(
    r"^(do|does|did|is|are|was|were|am|have|has|had|can|could|will|would|should|shall|may|might)\b",
    re.IGNORECASE,
)


def question_problems(row: Any) -> list[str]:
    """Reasons a row is not a valid ``Question``; empty when valid."""
    try:
        validate(row, QUESTION_SCHEMA)
    except SchemaViolation as exc:
        return [f"schema {exc}"]
    problems: list[str] = []
    text = row["text"]
    if text != text.strip() or "\n" in text:
        problems.append("text has surrounding whitespace or a line break")
    if not text.endswith("?"):
        problems.append("text must end with a question mark")
    if YES_NO_OPENING.match(text):
        problems.append("text reads as a yes/no question")
    if not _ID.match(row["questionId"]):
        problems.append("questionId must be lowercase letters, digits and hyphens")
    if any(not _TAG.match(t) for t in row["signalTags"]) or len(set(row["signalTags"])) != len(row["signalTags"]):
        problems.append("signalTags must be unique lowercase tags")
    hint = row["followUpHint"]
    if hint is not None and (not hint.strip() or not hint.endswith("?")):
        problems.append("followUpHint must be a question or null")
    return problems


def validate_question(row: Any) -> dict[str, Any]:
    problems = question_problems(row)
    if problems:
        raise BankError("; ".join(problems))
    return dict(row)


@dataclass(frozen=True)
class QuestionBank:
    """Immutable validated bank. ``questions`` keeps file order."""

    questions: tuple[dict[str, Any], ...]
    label: str = ""

    @classmethod
    def from_doc(cls, doc: Any) -> "QuestionBank":
        if not isinstance(doc, dict) or doc.get("contractVersion") != CONTRACT_VERSION:
            raise BankError(f"question bank must declare contractVersion {CONTRACT_VERSION}")
        rows = doc.get("questions")
        if not isinstance(rows, list) or not rows:
            raise BankError("question bank has no questions")
        seen: set[str] = set()
        texts: set[str] = set()
        out: list[dict[str, Any]] = []
        for i, row in enumerate(rows):
            problems = question_problems(row)
            if problems:
                raise BankError(f"questions[{i}]: " + "; ".join(problems))
            if row["questionId"] in seen:
                raise BankError(f"questions[{i}]: duplicate questionId")
            if row["text"].lower() in texts:
                raise BankError(f"questions[{i}]: duplicate text")
            seen.add(row["questionId"])
            texts.add(row["text"].lower())
            out.append(dict(row))
        label = doc.get("label")
        return cls(tuple(out), label if isinstance(label, str) else "")

    @classmethod
    def load(cls, path: str | Path) -> "QuestionBank":
        try:
            doc = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            raise BankError("question bank file is missing or not JSON") from None
        return cls.from_doc(doc)

    def get(self, question_id: str) -> dict[str, Any] | None:
        for q in self.questions:
            if q["questionId"] == question_id:
                return dict(q)
        return None

    def list(self, *, active: bool | None = None, category: str | None = None,
             source: str | None = None) -> list[dict[str, Any]]:
        """Operator view (GET /operator/questions). Not a player route."""
        return [
            dict(q) for q in self.questions
            if (active is None or q["active"] is active)
            and (category is None or q["category"] == category)
            and (source is None or q["source"] == source)
        ]

    def with_questions(self, extra: Iterable[dict[str, Any]]) -> "QuestionBank":
        """New bank including ``extra`` rows, re-validated as a whole."""
        return QuestionBank.from_doc({
            "contractVersion": CONTRACT_VERSION, "label": self.label,
            "questions": [*self.questions, *extra],
        })


DEFAULT_BANK_PATH = Path(__file__).resolve().parent / "data" / "question-bank.json"


def load_default_bank() -> QuestionBank:
    """The curated bank shipped with planning (a superset of the shared fixture)."""
    return QuestionBank.load(DEFAULT_BANK_PATH)
