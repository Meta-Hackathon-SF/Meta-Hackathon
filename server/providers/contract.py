"""Runtime validators for the Muse job I/O in contracts/protocol.ts 2.2.0 (M1-M10).

TypeScript declarations are not runtime validation, so each ``MxIn`` / ``MxOut``
is mirrored here as a schema in the subset enforced by ``schema.py``. Field
names are the contract's camelCase keys. The adapter validates the payload
against ``IN_SCHEMAS[task]`` before any provider call and the model's answer
against ``OUT_SCHEMAS[task]`` after it.

Input schemas set ``additionalProperties: false`` everywhere. That is the
"random per-call ids and text only" rule made mechanical: a payload carrying a
name, email, session token or playerId field is rejected before it is sent.

Length and count bounds are not in protocol.ts; they are defensive ceilings
chosen here (generous relative to the contract's 400-char answers, 500-char chat
messages and 140-char questions). ``tests/providers/test_contract_schemas.py``
fails if the task list or key sets drift from protocol.ts.
"""
from __future__ import annotations

from typing import Any

from .port import TASKS, Task, TaskSpec

QUESTION_CATEGORIES = (
    "routine", "belonging", "interests", "values", "hopes", "small_joys", "challenges",
)
SENSITIVITIES = ("low", "medium")  # "high" questions are never stored in the bank
SAFETY_LEVELS = ("none", "distress", "harm")
VENUE_KINDS = ("cafe", "dining_hall", "library", "park", "rec_center", "campus_event")
QUESTION_TEXT_MIN, QUESTION_TEXT_MAX = 10, 140

MAX_ANSWERS = 400        # 5 days x 80 players
MAX_GROUPS = 80


def _obj(props: dict[str, Any], optional: tuple[str, ...] = ()) -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [k for k in props if k not in optional],
        "properties": props,
    }


def _str(max_len: int, min_len: int = 1) -> dict[str, Any]:
    return {"type": "string", "minLength": min_len, "maxLength": max_len}


def _arr(items: dict[str, Any], max_items: int, min_items: int = 0) -> dict[str, Any]:
    return {"type": "array", "minItems": min_items, "maxItems": max_items, "items": items}


_ID = _str(64)
_ISO_TIME = _str(40, 10)
_PERCENT = {"type": "number", "minimum": 0, "maximum": 100}

PROMPT_TEXT = _obj(
    {"id": _ID, "text": _str(500), "weight": {"type": "number", "minimum": 0, "maximum": 1.1}},
    optional=("weight",),
)
# D014: answers to M3/M4 may say which question they reply to.
ANSWER_TEXT = _obj(
    {"id": _ID, "text": _str(500), "weight": {"type": "number", "minimum": 0, "maximum": 1.1},
     "questionId": _ID},
    optional=("weight", "questionId"),
)
_QUESTIONS = _arr(_obj({"questionId": _ID, "text": _str(300)}), 10)
TIME_WINDOW = _obj({"start": _ISO_TIME, "end": _ISO_TIME})
VENUE = _obj({
    "placeId": _ID,
    "name": _str(80),
    "kind": {"type": "string", "enum": list(VENUE_KINDS)},
    "isPublic": {"type": "boolean", "enum": [True]},
})
_THEMES = _arr(_obj({
    "id": _ID,
    "label": _str(120),
    "description": _str(400),
    "memberIds": _arr(_ID, MAX_ANSWERS),
}), MAX_GROUPS)

M1_IN = _obj({
    "text": PROMPT_TEXT,
    "subjectType": {"type": "string", "enum": ["answer", "chat_message"]},
})
M1_OUT = _obj({
    "flag": {"type": "string", "enum": list(SAFETY_LEVELS)},
    "reason": _str(300, 0),
})

M2_IN = _obj({"question": _str(300), "answer": PROMPT_TEXT})
M2_OUT = _obj({
    "needsFollowup": {"type": "boolean"},
    "question": _str(200, 0),  # empty when needsFollowup is false
})

M3_IN = _obj({
    "answers": _arr(ANSWER_TEXT, MAX_ANSWERS, 1),
    "questions": _QUESTIONS,
})
M3_OUT = _obj({"themes": _THEMES})

M4_IN = _obj({
    "themes": _THEMES,
    "answers": _arr(ANSWER_TEXT, MAX_ANSWERS, 1),
    "blockedPairs": _arr(_arr(_ID, 2, 2), 2000),
    "questions": _QUESTIONS,
    # D010 opt-in soft hints, server-computed: pairs of refs and a small count only.
    "affinity": _arr(_obj({
        "memberIds": _arr(_ID, 2, 2),
        "shared": {"type": "integer", "minimum": 1, "maximum": 50},
    }), 4000),
}, optional=("questions", "affinity"))
M4_OUT = _obj({
    "constellations": _arr(_obj({
        "memberIds": _arr(_ID, MAX_ANSWERS, 1),
        "sharedMeaning": _str(400),
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
    }), MAX_GROUPS),
})

M5_IN = _obj({
    "sharedMeaning": _str(400),
    "size": {"type": "integer", "minimum": 3, "maximum": MAX_ANSWERS},  # D016: no max; the 5+ rule is enforced by matching
})
M5_OUT = _obj({"name": _str(60), "shapeId": _ID, "colorId": _ID})

M6_IN = _obj({
    "recentQuestionIds": _arr(_ID, 200),
    "categoryMix": _obj({c: {"type": "number", "minimum": 0} for c in QUESTION_CATEGORIES}),
    "aggregateSignals": _arr(_obj({
        "tag": _str(40),
        "share": {"type": "number", "minimum": 0, "maximum": 1},
    }), 50),
    "count": {"type": "integer", "minimum": 1, "maximum": 10},
})
M6_OUT = _obj({
    "questions": _arr(_obj({
        "text": _str(QUESTION_TEXT_MAX, QUESTION_TEXT_MIN),
        "category": {"type": "string", "enum": list(QUESTION_CATEGORIES)},
        "sensitivity": {"type": "string", "enum": list(SENSITIVITIES)},
        "signalTags": _arr(_str(40), 6, 1),
        "followUpHint": {"type": ["string", "null"], "maxLength": 140},
    }), 10),
})

M7_IN = _obj({
    "sharedMeaning": _str(400),
    "venues": _arr(VENUE, 50, 1),
    "window": TIME_WINDOW,
    "campusEvents": _arr(_obj({"title": _str(80), "placeId": _ID, "start": _ISO_TIME}), 50),
})
M7_OUT = _obj({
    "title": _str(80),
    "placeId": _ID,
    "timeWindow": TIME_WINDOW,
    "why": _str(240),
})

M8_IN = _obj({
    "eligiblePlayers": {"type": "integer", "minimum": 0},
    "constellations": {"type": "integer", "minimum": 0},
    "themes": _arr(_obj({
        "label": _str(120),
        "count": {"type": "integer", "minimum": 0},
        "actualPercent": _PERCENT,
        "guessedPercentMedian": _PERCENT,
    }), MAX_GROUPS),
})
M8_OUT = _obj({"headlines": _arr(_str(200), 6)})

# D014 M9: activity topics. Values from the live eval (scratch B-topics, 2026-11-13).
ACTIVITY_TOPICS = ("ai", "coding", "design", "music", "gaming", "vr", "study", "coffee",
                   "food", "outdoors", "sports", "film", "art", "books")
STANCES = ("positive", "neutral", "negative")
_SHORT_ID = _str(16)
M9_IN = _obj({"texts": _arr(_obj({"id": _SHORT_ID, "text": _str(2000)}), 10, 1)})
M9_OUT = _obj({"results": _arr(_obj({
    "id": _SHORT_ID,
    "sensitive": {"type": "boolean"},
    "labels": _arr(_obj({
        "topic": {"type": "string", "enum": list(ACTIVITY_TOPICS)},
        "stance": {"type": "string", "enum": list(STANCES)},
    }), 3),
}), 10)})

# D014 M10: sensitivity of public game text. Code blocks anything but "none".
SENSITIVITY_CATEGORIES = ("none", "health", "mental_health", "sexuality", "religion", "money",
                          "family", "location", "identity", "substance", "violence")
M10_IN = _obj({"items": _arr(_obj({"id": _SHORT_ID, "text": _str(300)}), 40, 1)})
M10_OUT = _obj({"results": _arr(_obj({
    "id": _SHORT_ID,
    "category": {"type": "string", "enum": list(SENSITIVITY_CATEGORIES)},
}), 40)})

IN_SCHEMAS: dict[str, dict[str, Any]] = {
    "safety_screen": M1_IN, "clarify": M2_IN, "theme_discovery": M3_IN,
    "constellation_formation": M4_IN, "constellation_naming": M5_IN,
    "question_generation": M6_IN, "event_nudge": M7_IN, "sky_narration": M8_IN,
    "activity_classification": M9_IN, "sensitivity_screen": M10_IN,
}
OUT_SCHEMAS: dict[str, dict[str, Any]] = {
    "safety_screen": M1_OUT, "clarify": M2_OUT, "theme_discovery": M3_OUT,
    "constellation_formation": M4_OUT, "constellation_naming": M5_OUT,
    "question_generation": M6_OUT, "event_nudge": M7_OUT, "sky_narration": M8_OUT,
    "activity_classification": M9_OUT, "sensitivity_screen": M10_OUT,
}
assert set(IN_SCHEMAS) == set(OUT_SCHEMAS) == set(TASKS)


def contract_spec(task: Task, prompt_version: str, instructions: str, *,
                  max_output_tokens: int = 8000, temperature: float | None = 0.4) -> TaskSpec:
    """TaskSpec for ``task`` using the contract's own input and output shapes.

    Prompt owners (Patrik M1; Rishi M3/M4/M5/M8) call this with their own
    instructions so every job is validated against protocol.ts on both sides.
    """
    return TaskSpec(
        task=task,
        prompt_version=prompt_version,
        instructions=instructions,
        output_schema=OUT_SCHEMAS[task],
        input_schema=IN_SCHEMAS[task],
        schema_name=task,
        max_output_tokens=max_output_tokens,
        temperature=temperature,
    )
