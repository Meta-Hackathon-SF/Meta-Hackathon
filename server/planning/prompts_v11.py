"""Planning-owned Muse task specs for PROPOSED contract 1.1.0 (D008).

Bump a prompt version on any wording or schema change. Every task receives
code-computed options or briefs; Muse chooses and writes, code validates.
"""
from __future__ import annotations

from typing import Any

from server.providers.port import TaskRegistry, TaskSpec

from .prompts import RATIONALE_FACT_ENUM, REASONING_BUDGET, _quoted

PREFERENCES_PROMPT_VERSION = "extract-preferences.v1"
CREATE_EVENT_PROMPT_VERSION = "create-event.v1"
NEGOTIATE_PROMPT_VERSION = "negotiate.v1"
VENUE_PERSONA_PROMPT_VERSION = "venue-persona.v1"
CHALLENGE_PROMPT_VERSION = "challenge.v1"

_QUOTED_ITEMS = {
    "type": "array",
    "items": {
        "type": "object",
        "additionalProperties": False,
        "required": ["value", "quote"],
        "properties": {
            "value": {"type": "string", "minLength": 1, "maxLength": 40},
            "quote": {"type": "string", "minLength": 1, "maxLength": 300},
        },
    },
}

PREFERENCES_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["availability", "maxBudgetMinor", "areaId", "interests", "avoid",
                 "energy", "socialComfort", "openToNew"],
    "properties": {
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
        "areaId": _quoted({"type": ["string", "null"], "maxLength": 128}),
        "interests": {**_QUOTED_ITEMS, "maxItems": 8},
        "avoid": {**_QUOTED_ITEMS, "maxItems": 5},
        "energy": _quoted({"type": ["string", "null"], "enum": ["low", "medium", "high", None]}),
        "socialComfort": _quoted({"type": ["string", "null"], "enum": ["quiet", "balanced", "outgoing", None]}),
        "openToNew": _quoted({"type": ["boolean", "null"]}),
    },
}

PREFERENCES_INSTRUCTIONS = """\
Task: turn one person's short voice/text note into PRIVATE meetup preferences they
will review before anything is saved. They describe what they are comfortable
with, NOT an activity to organize; never invent an activity for them.

Input: mode ("initial" or "follow_up"), transcript (their words; in follow_up mode
it is their answer to `question` about `field`), referenceTimeUtc,
referenceTimeLocal, timeZone (IANA), currency (ISO 4217; amounts are integer minor
units, e.g. cents), areas (the only valid areaId values).

Rules:
- Extract ONLY what the words state. Unstated -> value null (or []) and quote null.
  Never guess. Missing information is expected and fine.
- Every non-null value MUST include an exact verbatim "quote" from the transcript.
  Values without a verbatim supporting quote are discarded by the server.
- availability: windows within 14 days after referenceTime, converted from timeZone
  to RFC3339 UTC with trailing Z. "Saturday afternoon" may be read as 13:00-17:00 local.
- maxBudgetMinor: the most they will spend on one meetup; "under $15" = 1500;
  "free"/"no money" = 0.
- areaId: only a provided areaId, when the words name that area.
- interests: short lowercase things they enjoy or want to try ("climbing", "board games").
- avoid: short lowercase things they do not want ("bars", "loud places").
- energy: "low" (chill, low-key), "medium", or "high" (active, energetic).
- socialComfort: "quiet" (prefers calm, small talk is hard), "balanced", or
  "outgoing" (wants to meet lots of people).
- openToNew: true when they want to try something new; false when they want familiar.
- In follow_up mode, focus on `field`; other values may stay null.
- Never output identity, contact details, consent, or fields outside the schema.
"""

CREATE_EVENT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["optionId", "start", "end", "title", "activity", "collaborationTask",
                 "costPerPersonMinor", "interestsUsed", "rationaleFacts"],
    "properties": {
        "optionId": {"type": "string", "minLength": 2, "maxLength": 12},
        "start": {"type": "string", "maxLength": 40},
        "end": {"type": "string", "maxLength": 40},
        "title": {"type": "string", "minLength": 3, "maxLength": 80},
        "activity": {"type": "string", "minLength": 10, "maxLength": 400},
        "collaborationTask": {"type": "string", "minLength": 10, "maxLength": 400},
        "costPerPersonMinor": {"type": "integer", "minimum": 0, "maximum": 10000000},
        "interestsUsed": {"type": "array", "maxItems": 3, "items": {"type": "string", "maxLength": 60}},
        "rationaleFacts": {"type": "array", "maxItems": 6, "items": {"type": "string", "enum": RATIONALE_FACT_ENUM}},
    },
}

CREATE_EVENT_INSTRUCTIONS = """\
Task: nothing that already exists fits this community, so CREATE one small
in-person meetup that a group of 3-5 members would enjoy together. Members did not
ask for the same thing; find what fits their combined preferences.

Input: pool (how many members are eligible, interestCounts from public interests,
avoid terms nobody should be pushed into, energyMix, comfortMix), constraints, and
options. Each option is an approved public venue with ONE time slot and
freeCount/maxCostPerPersonMinor/maxDurationMinutes computed by the server.

Hard rules (server code rejects violations):
- optionId MUST be one of options[].optionId. start/end MUST lie inside that
  option's slot, RFC3339 UTC with trailing Z; duration between
  constraints.minDurationMinutes and the option's maxDurationMinutes.
- costPerPersonMinor <= that option's maxCostPerPersonMinor. Prefer free or cheap.
- Nothing from `avoid` may appear in title, activity or collaborationTask.
- The activity must make people interact and produce something together, be
  newcomer-friendly, public and doable in the time. No alcohol, no private homes.
- interestsUsed: 0-3 interests copied verbatim from pool.interestCounts.
- Public text is shown to members: no money amounts, budgets, anyone's limits or
  schedule, personal details, links or contact info.
- rationaleFacts: codes that are true; the server writes the explanation.
"""

NEGOTIATE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["action", "totalPriceMinor", "message"],
    "properties": {
        "action": {"type": "string", "enum": ["counter", "accept", "walk_away"]},
        "totalPriceMinor": {"type": "integer", "minimum": 0, "maximum": 10000000},
        "message": {"type": "string", "minLength": 3, "maxLength": 300},
    },
}

NEGOTIATE_INSTRUCTIONS = """\
Task: you are the GROUP'S agent negotiating with a venue's business assistant for a
small group meetup. Get a fair group price within the group's limit.

Input: brief (activity, groupSize, window, totalBudgetMinor = the most the group
will pay in total, currency), round, maxRounds, venueOffer (the venue's latest
action, totalPriceMinor and terms) and history (earlier prices).

Rules (server code enforces them and rejects violations):
- accept: only when venueOffer.totalPriceMinor <= brief.totalBudgetMinor;
  totalPriceMinor must equal venueOffer.totalPriceMinor.
- counter: totalPriceMinor < venueOffer.totalPriceMinor and <= brief.totalBudgetMinor.
  Counter reasonably (off-peak time, group size, first visit); do not lowball absurdly.
- walk_away: when the venue will not come within the limit.
- message: short and polite, sent to the venue. Put NO money amounts in it (prices
  go in totalPriceMinor). Never reveal or hint at any individual's budget, names,
  schedule or personal details; you only know group totals.
"""

VENUE_PERSONA_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["action", "totalPriceMinor", "terms"],
    "properties": {
        "action": {"type": "string", "enum": ["offer", "final_offer", "decline"]},
        "totalPriceMinor": {"type": "integer", "minimum": 0, "maximum": 10000000},
        "terms": {"type": "string", "minLength": 3, "maxLength": 300},
    },
}

VENUE_PERSONA_INSTRUCTIONS = """\
Task: role-play a SIMULATED local venue's business assistant (a labeled demo
persona, not a real business) replying to a group booking request.

Input: persona (venue name, style, listPricePerPersonMinor, floorPricePerPersonMinor
= the lowest per-person price this venue accepts), request (activity, groupSize,
window, totalBudgetMinor, currency), round, maxRounds, groupCounter (the group's
latest counter price and message, or null on the first round).

Rules (server code enforces them):
- totalPriceMinor is for the whole group and must be >= floorPricePerPersonMinor x groupSize.
- Open near list price, move toward the group if it is reasonable, and use
  final_offer when you will not go lower. decline only if the request cannot work.
- terms: one short sentence about what is included (for example off-peak slot,
  gear rental, intro session). No money amounts, links or contact details.
"""

CHALLENGE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["title", "description", "target", "dueInDays", "rewardOptionId"],
    "properties": {
        "title": {"type": "string", "minLength": 3, "maxLength": 80},
        "description": {"type": "string", "minLength": 10, "maxLength": 400},
        "target": {"type": "integer", "minimum": 2, "maximum": 6},
        "dueInDays": {"type": "integer", "minimum": 7, "maximum": 60},
        "rewardOptionId": {"type": ["string", "null"], "maxLength": 128},
    },
}

CHALLENGE_INSTRUCTIONS = """\
Task: give a small group a personalized challenge that is a reason to meet AGAIN,
building on their quest.

Input: priorPlan (public title, activity and collaborationTask), returningCount (how
many members said they want to return), rewardOptions (approved, simulated rewards;
pick one id or null), simulatedTimeSkip.

Rules (server code enforces them):
- The goal is counted as sessions_together: target = number of future meetups
  (2-6) the group completes together within dueInDays (7-60).
- title/description: specific to the activity and a natural progression (for
  climbing: "send your first V2 together within three sessions"). Doable by beginners.
- Do NOT claim or imply that anyone attended, met or enjoyed anything; attendance
  is unknown. No money amounts, links, contact details or personal information.
- rewardOptionId: one id from rewardOptions, or null.
"""


def register_v11_tasks(registry: TaskRegistry) -> TaskRegistry:
    for task, version, instructions, schema, name, temperature in (
        ("extract_preferences", PREFERENCES_PROMPT_VERSION, PREFERENCES_INSTRUCTIONS, PREFERENCES_SCHEMA, "preference_extraction", 0.0),
        ("create_event", CREATE_EVENT_PROMPT_VERSION, CREATE_EVENT_INSTRUCTIONS, CREATE_EVENT_SCHEMA, "created_event", 0.7),
        ("negotiate", NEGOTIATE_PROMPT_VERSION, NEGOTIATE_INSTRUCTIONS, NEGOTIATE_SCHEMA, "group_counter", 0.3),
        ("venue_persona", VENUE_PERSONA_PROMPT_VERSION, VENUE_PERSONA_INSTRUCTIONS, VENUE_PERSONA_SCHEMA, "venue_offer", 0.5),
        ("challenge", CHALLENGE_PROMPT_VERSION, CHALLENGE_INSTRUCTIONS, CHALLENGE_SCHEMA, "group_challenge", 0.7),
    ):
        registry.register(TaskSpec(task=task, prompt_version=version, instructions=instructions,
                                   output_schema=schema, schema_name=name,
                                   max_output_tokens=REASONING_BUDGET, temperature=temperature))
    return registry
