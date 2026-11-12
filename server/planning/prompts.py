"""Planning-owned Muse task specs. Bump prompt_version on any wording change."""
from __future__ import annotations

from typing import Any

from server.providers.port import TaskRegistry, TaskSpec

EXTRACT_PROMPT_VERSION = "extract-intent.v1"


def _quoted(value_schema: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["value", "quote"],
        "properties": {
            "value": value_schema,
            "quote": {"type": ["string", "null"], "maxLength": 300},
        },
    }


EXTRACT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["goal", "interests", "areaId", "availability", "maxBudgetMinor", "maxDurationMinutes"],
    "properties": {
        "goal": _quoted({"type": ["string", "null"], "maxLength": 280}),
        "interests": {
            "type": "array",
            "maxItems": 8,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["value", "quote"],
                "properties": {
                    "value": {"type": "string", "minLength": 1, "maxLength": 40},
                    "quote": {"type": "string", "minLength": 1, "maxLength": 300},
                },
            },
        },
        "areaId": _quoted({"type": ["string", "null"], "maxLength": 128}),
        "availability": {
            "type": "array",
            "maxItems": 6,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["start", "end", "quote"],
                "properties": {
                    "start": {"type": "string", "maxLength": 40},
                    "end": {"type": "string", "maxLength": 40},
                    "quote": {"type": "string", "minLength": 1, "maxLength": 300},
                },
            },
        },
        "maxBudgetMinor": _quoted({"type": ["integer", "null"], "minimum": 0, "maximum": 10000000}),
        "maxDurationMinutes": _quoted({"type": ["integer", "null"], "minimum": 1, "maximum": 1440}),
    },
}

EXTRACT_INSTRUCTIONS = """\
Task: extract a structured, PRIVATE activity intent from one person's short
voice/text note so they can review and correct it before anything is saved.

Input fields: transcript (the person's words), referenceTimeUtc, referenceTimeLocal,
timeZone (IANA), currency (ISO 4217; amounts are integer minor units, e.g. cents),
areas (the only valid areaId values with their names).

Rules:
- Extract ONLY what the transcript states. If a field is not stated, set value to
  null (or an empty array) and quote to null. Never guess availability, budget,
  duration or area. Missing information is expected and fine.
- Every non-null value MUST include "quote": an exact, verbatim span copied from
  the transcript that supports it. Values without a verbatim supporting quote are
  discarded by the server.
- goal: one short sentence in the person's own terms (what they hope to get).
- interests: short lowercase activity/topic nouns (e.g. "photography", "board games").
- areaId: only one of the provided areaId values, when the transcript names that area.
- availability: concrete windows within the next 14 days after referenceTime,
  converted from timeZone into RFC3339 UTC with a trailing Z (e.g.
  2026-11-14T22:00:00Z). "Saturday afternoon" may be read as 13:00-17:00 local.
- maxBudgetMinor: integer minor units in the given currency; "free"/"no money" = 0.
- maxDurationMinutes: integer minutes the person can spend on one activity.
- Do not output consent, identity, contact details, or any field not in the schema.
"""


def register_planning_tasks(registry: TaskRegistry) -> TaskRegistry:
    registry.register(TaskSpec(
        task="extract_intent",
        prompt_version=EXTRACT_PROMPT_VERSION,
        instructions=EXTRACT_INSTRUCTIONS,
        output_schema=EXTRACT_SCHEMA,
        schema_name="intent_extraction",
        max_output_tokens=1500,
        temperature=0.0,
    ))
    return registry
