"""Synthetic wire-shaped fixtures for the matching engine tests.

Every profile here is synthetic (isSynthetic true, "Synthetic <Name>" display names).
No real participant data, no network, no live model calls. Builders return new dicts
on every call so tests cannot leak state into each other.
"""
import asyncio
import copy
from typing import Any, Mapping, Optional, Sequence, Union

DEMO_COMMUNITY_ID = "comm_demo"
DEFAULT_AREA_ID = "area_campus"
DOWNTOWN_AREA_ID = "area_downtown"
DEFAULT_TIME_ZONE = "America/Los_Angeles"
DEFAULT_CURRENCY = "USD"
DEFAULT_CONFIRMED_AT = "2026-11-12T20:00:00Z"
DEFAULT_WINDOW_START = "2026-11-14T18:00:00Z"
DEFAULT_WINDOW_END = "2026-11-14T21:00:00Z"
OTHER_DAY_WINDOW_START = "2026-11-15T18:00:00Z"
OTHER_DAY_WINDOW_END = "2026-11-15T21:00:00Z"
DEFAULT_MAX_BUDGET_MINOR = 1500
DEFAULT_MAX_DURATION_MINUTES = 120
DEFAULT_INTENT_VERSION = 1
DEFAULT_CONSENT_VERSION = 1
DEFAULT_MINIMUM_SIZE = 3
DEFAULT_MAXIMUM_SIZE = 5
CONTRACT_VERSION = "1.0.0"
DEFAULT_REQUEST_ID = "req_test"
DEFAULT_MODE = "fixture"
FAKE_MODEL_NAME = "fake-muse"
FAKE_GENERATED_AT = "2026-11-12T20:00:00Z"
FAKE_LATENCY_MS = 1
HANG_SECONDS = 3600
HANG_SENTINEL = "hang"
DEFAULT_OPTION_ID = "g0"
DEFAULT_REASON_CODE = "strong_shared_interest"

FAKE_EVIDENCE: Mapping[str, Any] = {
    "model": FAKE_MODEL_NAME,
    "source": "replay",
    "generatedAt": FAKE_GENERATED_AT,
    "latencyMs": FAKE_LATENCY_MS,
}

DEFAULT_MUSE_OUTPUT: Mapping[str, Any] = {
    "optionId": DEFAULT_OPTION_ID,
    "sharedInterests": [],
    "reasonCodes": [DEFAULT_REASON_CODE],
}

MuseResponse = Union[Mapping[str, Any], str, BaseException]


def _default_availability() -> list[dict[str, str]]:
    return [{"start": DEFAULT_WINDOW_START, "end": DEFAULT_WINDOW_END}]


def make_intent(pid: str, **overrides: Any) -> dict[str, Any]:
    """Return a wire PrivateIntent dict for participant ``pid``. Overrides use wire (camelCase) keys."""
    defaults: dict[str, Any] = {
        "participantId": pid,
        "communityId": DEMO_COMMUNITY_ID,
        "intentVersion": DEFAULT_INTENT_VERSION,
        "goal": "meet people",
        "interests": [],
        "areaId": DEFAULT_AREA_ID,
        "timeZone": DEFAULT_TIME_ZONE,
        "availability": _default_availability(),
        "maxBudgetMinor": DEFAULT_MAX_BUDGET_MINOR,
        "currency": DEFAULT_CURRENCY,
        "maxDurationMinutes": DEFAULT_MAX_DURATION_MINUTES,
        "groupPreference": "small",
        "consentVersion": DEFAULT_CONSENT_VERSION,
        "confirmedAt": DEFAULT_CONFIRMED_AT,
    }
    return {**defaults, **copy.deepcopy(dict(overrides))}


def make_candidate(pid: str, name: str, public_interests: Sequence[str],
                   **intent_overrides: Any) -> dict[str, Any]:
    """Return a wire Candidate dict. ``name`` is the bare first name; display is "Synthetic <name>"."""
    intent = make_intent(pid, interests=list(public_interests), **intent_overrides)
    profile = {
        "participantId": pid,
        "displayName": f"Synthetic {name}",
        "publicInterests": list(public_interests),
        "isSynthetic": True,
    }
    return {"intent": intent, "publicProfile": profile}


def make_match_input(candidates: Sequence[Mapping[str, Any]], requester_id: str,
                     mode: str = DEFAULT_MODE,
                     request_id: str = DEFAULT_REQUEST_ID) -> dict[str, Any]:
    """Return a wire MatchInput dict wrapping deep copies of ``candidates``."""
    return {
        "context": {
            "requestId": request_id,
            "contractVersion": CONTRACT_VERSION,
            "mode": mode,
        },
        "communityId": DEMO_COMMUNITY_ID,
        "requesterId": requester_id,
        "candidates": [copy.deepcopy(dict(c)) for c in candidates],
        "minimumSize": DEFAULT_MINIMUM_SIZE,
        "maximumSize": DEFAULT_MAXIMUM_SIZE,
    }


DEMO_POOL: list[dict[str, Any]] = [
    # Requester: shares photography + coffee with several members, same day and area.
    make_candidate("p_ava", "Ava", ["photography", "coffee", "hiking"]),
    make_candidate("p_ben", "Ben", ["photography", "board games"]),
    make_candidate("p_cy", "Cy", ["coffee", "board games"]),
    make_candidate("p_dee", "Dee", ["hiking", "photography"]),
    make_candidate("p_eli", "Eli", ["coffee", "hiking", "board games"]),
    # No time overlap with the requester (different day).
    make_candidate("p_fay", "Fay", ["photography", "coffee"],
                   availability=[{"start": OTHER_DAY_WINDOW_START, "end": OTHER_DAY_WINDOW_END}]),
    make_candidate("p_gus", "Gus", ["hiking", "board games"],
                   availability=[{"start": OTHER_DAY_WINDOW_START, "end": OTHER_DAY_WINDOW_END}]),
    # Different area from the requester (area_campus).
    make_candidate("p_hal", "Hal", ["photography", "hiking"], areaId=DOWNTOWN_AREA_ID),
]


class FakeMusePort:
    """Scripted MusePort double. Never labeled live; evidence source is always "replay".

    ``responses`` is consumed in order, one per call:
      - Mapping: returned as the ``output`` field.
      - str: returned as the raw ``output`` value.
      - BaseException instance: raised.
      - "hang": sleeps for an hour (exercises timeouts and cancellation).
    When the script is exhausted, the default ranking output is returned.
    """

    def __init__(self, responses: Optional[Sequence[MuseResponse]] = None) -> None:
        self._responses: list[MuseResponse] = list(responses or [])
        self._calls: list[dict[str, Any]] = []

    @property
    def calls(self) -> tuple[dict[str, Any], ...]:
        """Recorded calls in order. Each entry has task, requestId, promptVersion, payload."""
        return tuple(copy.deepcopy(c) for c in self._calls)

    async def generate(self, *, task: str, requestId: str, promptVersion: str,
                       payload: Any, signal: Any = None) -> dict[str, Any]:
        self._calls.append({
            "task": task,
            "requestId": requestId,
            "promptVersion": promptVersion,
            "payload": copy.deepcopy(payload),
        })
        output = await self._next_output()
        return {"output": output, "evidence": copy.deepcopy(dict(FAKE_EVIDENCE))}

    async def _next_output(self) -> Any:
        if not self._responses:
            return copy.deepcopy(dict(DEFAULT_MUSE_OUTPUT))
        item = self._responses.pop(0)
        if isinstance(item, BaseException):
            raise item
        if item == HANG_SENTINEL:
            await asyncio.sleep(HANG_SECONDS)
            return None
        if isinstance(item, Mapping):
            return copy.deepcopy(dict(item))
        return item
