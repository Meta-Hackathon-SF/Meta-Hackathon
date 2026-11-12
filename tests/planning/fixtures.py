"""SYNTHETIC planning fixtures (no real people). Times are around a fixed
reference: Thu 2026-11-12 12:00 America/Los_Angeles (20:00Z). The group's only
shared time is Sat 2026-11-14 14:00-16:00 PT (22:00Z-00:00Z)."""
from __future__ import annotations

import copy
from datetime import datetime, timezone

from server.planning.catalog import demo_venues

REF = datetime(2026, 11, 12, 20, 0, tzinfo=timezone.utc)
TZ = "America/Los_Angeles"
EVIDENCE = {"model": "fixture:scripted-muse", "source": "replay", "generatedAt": "2026-11-12T20:00:00.000Z", "latencyMs": 5}


def intent(pid: str, start: str, end: str, budget: int, duration: int, version: int = 1) -> dict:
    return {
        "participantId": pid, "communityId": "c-synthetic", "intentVersion": version,
        "goal": "meet new people", "interests": ["photography"], "areaId": "area-north",
        "timeZone": TZ, "availability": [{"start": start, "end": end}],
        "maxBudgetMinor": budget, "currency": "USD", "maxDurationMinutes": duration,
        "groupPreference": "small", "consentVersion": 1, "confirmedAt": "2026-11-12T19:00:00Z",
    }


def candidate(pid: str, name: str, *args, **kw) -> dict:
    return {
        "intent": intent(pid, *args, **kw),
        "publicProfile": {"participantId": pid, "displayName": name, "publicInterests": ["photography", "coffee"], "isSynthetic": True},
    }


def participants() -> list[dict]:
    return [
        candidate("p-ava", "Ava (synthetic)", "2026-11-14T21:00:00Z", "2026-11-15T01:00:00Z", 1000, 60),
        candidate("p-ben", "Ben (synthetic)", "2026-11-14T22:00:00Z", "2026-11-15T02:00:00Z", 0, 90),
        candidate("p-cy", "Cy (synthetic)", "2026-11-14T21:30:00Z", "2026-11-15T00:00:00Z", 500, 120),
    ]


def proposal(parts: list[dict], revision: int = 1, windows: list[dict] | None = None) -> dict:
    return {
        "proposalId": "prop-synthetic-1", "communityId": "c-synthetic", "revision": revision,
        "memberIds": [p["intent"]["participantId"] for p in parts],
        "memberVersions": [
            {"participantId": p["intent"]["participantId"], "intentVersion": p["intent"]["intentVersion"],
             "consentVersion": p["intent"]["consentVersion"]} for p in parts
        ],
        "feasibleWindows": windows or [{"start": "2026-11-14T22:00:00Z", "end": "2026-11-15T00:00:00Z"}],
        "sharedInterests": ["photography"],
        "publicRationale": "Everyone is into photography.",
        "evidence": EVIDENCE,
    }


def plan_input(**overrides) -> dict:
    parts = overrides.pop("participants", None) or participants()
    inp = {
        "context": {"requestId": "req-plan-1", "contractVersion": "1.0.0", "mode": "fixture"},
        "proposal": overrides.pop("proposal", None) or proposal(parts),
        "participants": parts,
        "venues": overrides.pop("venues", None) or demo_venues(time_zone=TZ, start=REF),
    }
    inp.update(overrides)
    return inp


def good_plan_output(**overrides) -> dict:
    out = {
        "title": "Three-Photo Story Walk",
        "activity": "Take a slow loop around the quad and each spot one scene that could open, middle or end a story.",
        "collaborationTask": "Together pick three photos, put them in order and agree on a one-line caption for the story.",
        "venueId": "venue-demo-quad",
        "start": "2026-11-14T22:30:00Z",
        "end": "2026-11-14T23:30:00Z",
        "costPerPersonMinor": 0,
        "rationaleFacts": ["shared_interest", "free_activity", "short_activity", "creates_shared_output"],
        "opener": "Hi everyone! You're set for a three-photo story walk on the Main Quad. Say hi and share one thing you love to photograph.",
    }
    out.update(overrides)
    return out


def clone(x):
    return copy.deepcopy(x)
