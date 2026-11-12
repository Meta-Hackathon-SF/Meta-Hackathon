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


PLAN_PROMPT_VERSION = "plan.v1"
REVISE_PROMPT_VERSION = "revise.v1"
CONTINUE_PROMPT_VERSION = "continue.v1"

# Kept in sync with public_text.RATIONALE_FACTS (asserted in tests).
RATIONALE_FACT_ENUM = [
    "shared_interest", "fits_shared_time", "free_activity", "low_cost",
    "public_venue", "short_activity", "creates_shared_output", "easy_first_meeting",
]

PLAN_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["title", "activity", "collaborationTask", "venueId", "start", "end",
                 "costPerPersonMinor", "rationaleFacts", "opener"],
    "properties": {
        "title": {"type": "string", "minLength": 3, "maxLength": 80},
        "activity": {"type": "string", "minLength": 10, "maxLength": 400},
        "collaborationTask": {"type": "string", "minLength": 10, "maxLength": 400},
        "venueId": {"type": "string", "minLength": 1, "maxLength": 128},
        "start": {"type": "string", "maxLength": 40},
        "end": {"type": "string", "maxLength": 40},
        "costPerPersonMinor": {"type": "integer", "minimum": 0, "maximum": 10000000},
        "rationaleFacts": {"type": "array", "maxItems": 6, "items": {"type": "string", "enum": RATIONALE_FACT_ENUM}},
        "opener": {"type": "string", "minLength": 10, "maxLength": 600},
    },
}

_PLAN_RULES = """\
Hard rules (server code rejects violations):
- venueId MUST be one of options[].venueId. start/end MUST lie inside one of that
  option's slots, as RFC3339 UTC with trailing Z, end after start.
- Duration between constraints.minDurationMinutes and constraints.maxDurationMinutes.
- costPerPersonMinor (integer minor units of constraints.currency) MUST be <=
  constraints.maxCostPerPersonMinor. Prefer free when the cap is 0 or low.
- The activity must make people interact and produce something together
  (collaborationTask), not just do things side by side. Keep it doable by
  newcomers, in public, within the duration. No alcohol, no private homes.
- Public text (title, activity, collaborationTask, opener) is shown to the whole
  group. Never mention budgets, money amounts, anyone's limits or schedule,
  personal details, links, or contact info. You do not know names; address the
  group collectively.
- opener: a warm first message from the assistant in the group's chat that
  explains the plan and invites everyone to say hi.
- rationaleFacts: pick the codes that are true for your plan; the server writes
  the public explanation from them.
"""

PLAN_INSTRUCTIONS = (
    "Task: propose ONE small in-person quest for a newly formed group of 3-5 people "
    "who share interests. Input: group (size, sharedInterests, publicInterests), "
    "constraints (group-level caps already computed by the server), options "
    "(approved public venues with time slots when everyone is free and the venue is open).\n\n"
    + _PLAN_RULES
)

REVISE_INSTRUCTIONS = (
    "Task: REVISE an existing quest plan because the group's circumstances changed. "
    "Input: previousPlan (what members accepted), changeSummary (server-written, "
    "what changed), group, constraints and options recomputed for the CURRENT "
    "situation. Keep what still works (same activity and venue if still feasible); "
    "change only what the new constraints require. If the previous time no longer "
    "fits, choose a new slot from options.\n\n"
    + _PLAN_RULES
)

CONTINUE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["nextActivity", "invitationText", "proposedHostId"],
    "properties": {
        "nextActivity": {"type": "string", "minLength": 10, "maxLength": 400},
        "invitationText": {"type": "string", "minLength": 10, "maxLength": 600},
        "proposedHostId": {"type": ["string", "null"], "maxLength": 128},
    },
}

CONTINUE_INSTRUCTIONS = """\
Task: suggest a NEXT-WEEK follow-up quest for a group and a draft invitation a
volunteer host could send to that same group.
Input: priorPlan (public details of the previous quest), willingHostIds (opaque ids of
members who said they want to return), interest summary, simulatedTimeSkip flag.
Rules:
- nextActivity: a small, public, collaborative activity that builds on the prior
  quest's theme (a natural "part two"), doable in about the same time and cost.
- invitationText: a short, friendly draft written for the host to send to the group.
  It MUST NOT claim or imply that anyone attended, met, or enjoyed the prior quest;
  attendance is unknown. Phrase it as an invitation for next week. No money amounts,
  links, contact details or personal information.
- proposedHostId: exactly one id from willingHostIds, or null if the list is empty.
"""


def register_planning_tasks(registry: TaskRegistry) -> TaskRegistry:
    registry.register(TaskSpec(task="plan", prompt_version=PLAN_PROMPT_VERSION, instructions=PLAN_INSTRUCTIONS,
                               output_schema=PLAN_SCHEMA, schema_name="quest_plan", max_output_tokens=2000, temperature=0.7))
    registry.register(TaskSpec(task="revise", prompt_version=REVISE_PROMPT_VERSION, instructions=REVISE_INSTRUCTIONS,
                               output_schema=PLAN_SCHEMA, schema_name="quest_plan", max_output_tokens=2000, temperature=0.4))
    registry.register(TaskSpec(task="continue", prompt_version=CONTINUE_PROMPT_VERSION, instructions=CONTINUE_INSTRUCTIONS,
                               output_schema=CONTINUE_SCHEMA, schema_name="continuation", max_output_tokens=1200, temperature=0.7))
    _register_extract(registry)
    return registry


def _register_extract(registry: TaskRegistry) -> TaskRegistry:
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
