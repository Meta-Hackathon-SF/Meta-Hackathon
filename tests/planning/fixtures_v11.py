"""SYNTHETIC fixtures for PROPOSED contract 1.1.0 (D008). No real people.

Scenario mirrors the README example: four transfer students in area-north,
none of whom asked for climbing. Reference time Thu 2026-11-12 20:00Z
(12:00 PT); everyone overlaps Sat 2026-11-14 22:00Z-00:00Z (14:00-16:00 PT).
"""
from __future__ import annotations

from server.planning.catalog import demo_venues_with_gym
from server.planning.extraction import Area, CommunityContext

from .fixtures import EVIDENCE, REF, TZ, intent

COMMUNITY = CommunityContext("c-synthetic", [Area("area-north", "North Campus"), Area("area-downtown", "Downtown")], "USD", TZ)
CONSENT = {"communityId": "c-synthetic", "modelProcessing": True, "revokedAt": None}
CTX = {"requestId": "req-v11", "contractVersion": "1.0.0", "mode": "fixture"}

#   pid       start                   end                     ceiling interests        avoid     energy    comfort
MEMBERS = (
    ("p-ana", "2026-11-14T21:00:00Z", "2026-11-15T01:00:00Z", 1500, ["coffee"], [], "low", "quiet"),
    ("p-bo", "2026-11-14T21:00:00Z", "2026-11-15T00:00:00Z", 2000, ["art"], ["bars"], "medium", "balanced"),
    ("p-cy", "2026-11-14T22:00:00Z", "2026-11-15T01:00:00Z", 2500, ["climbing"], [], "high", "balanced"),
    ("p-dee", "2026-11-14T21:00:00Z", "2026-11-15T01:00:00Z", 3000, ["music"], [], None, "outgoing"),
)


def member(pid, start, end, ceiling, interests, avoid, energy, comfort, area="area-north") -> dict:
    i = intent(pid, start, end, ceiling, 120)
    i["areaId"] = area
    i["interests"] = list(interests)
    return {
        "intent": i,
        "publicProfile": {"participantId": pid, "displayName": f"{pid[2:].title()} (synthetic)",
                          "publicInterests": list(interests), "isSynthetic": True},
        "preferences": {"energy": energy, "socialComfort": comfort, "avoid": list(avoid), "openToNew": True},
    }


def members() -> list[dict]:
    return [member(*m) for m in MEMBERS]


def venues() -> list[dict]:
    return demo_venues_with_gym(time_zone=TZ, start=REF)


def create_input(**overrides) -> dict:
    inp = {"context": dict(CTX), "communityId": "c-synthetic", "candidates": members(), "venues": venues()}
    inp.update(overrides)
    return inp


def good_create_output(**overrides) -> dict:
    out = {
        "optionId": "o0",
        "start": "2026-11-14T22:00:00Z",
        "end": "2026-11-14T23:30:00Z",
        "title": "First Bouldering Session",
        "activity": "An intro bouldering session on the beginner wall, taking turns spotting and cheering each other on.",
        "collaborationTask": "As a team, pick one beginner route and work out the moves together until everyone has tried it.",
        "costPerPersonMinor": 1500,
        "interestsUsed": ["climbing"],
        "rationaleFacts": ["shared_interest", "easy_first_meeting"],
    }
    out.update(overrides)
    return out


def opportunity(**overrides) -> dict:
    opp = {
        "opportunityId": "opp-synthetic-1", "communityId": "c-synthetic", "source": "muse_created",
        "title": "First Bouldering Session",
        "activity": "An intro bouldering session on the beginner wall, taking turns spotting and cheering each other on.",
        "collaborationTask": "As a team, pick one beginner route and work out the moves together until everyone has tried it.",
        "venueId": "venue-demo-boulder",
        "window": {"start": "2026-11-14T22:00:00Z", "end": "2026-11-14T23:30:00Z"},
        "timeZone": TZ, "costPerPersonMinor": 1500, "currency": "USD", "minimumSize": 3, "maximumSize": 5,
        "publicRationale": "This quest fits a time when enough members are free, and happens at an approved public venue.",
        "isSimulated": False, "evidence": dict(EVIDENCE),
    }
    opp.update(overrides)
    return opp


def negotiation_input(**overrides) -> dict:
    inp = {"context": dict(CTX), "negotiationId": "neg-synthetic-1", "opportunity": opportunity(),
           "participants": members(), "maxRounds": 3}
    inp.update(overrides)
    return inp


def prior_plan() -> dict:
    return {
        "planId": "plan-synthetic-1", "proposalId": "prop-synthetic-1", "revision": 1, "basedOnRevision": None,
        "memberVersions": [{"participantId": m[0], "intentVersion": 1, "consentVersion": 1} for m in MEMBERS],
        "title": "First Bouldering Session",
        "activity": "An intro bouldering session on the beginner wall, taking turns spotting each other.",
        "collaborationTask": "Pick one beginner route and work out the moves together.",
        "venueId": "venue-demo-boulder", "start": "2026-11-14T22:00:00Z", "end": "2026-11-14T23:30:00Z",
        "timeZone": TZ, "costPerPersonMinor": 1500, "currency": "USD", "minimumSize": 3, "maximumSize": 5,
        "publicRationale": "This quest fits a time that works for everyone, and happens at an approved public venue.",
        "opener": "Hi everyone, welcome to your first bouldering session. Say hi!",
        "evidence": dict(EVIDENCE),
    }


def event() -> dict:
    return {
        "eventId": "evt-synthetic-1", "questId": "quest-synthetic-1", "planId": "plan-synthetic-1", "revision": 1,
        "status": "completed", "title": "First Bouldering Session", "venueId": "venue-demo-boulder",
        "start": "2026-11-14T22:00:00Z", "end": "2026-11-14T23:30:00Z",
        "acceptedMemberIds": [m[0] for m in MEMBERS], "conversationId": "conv-synthetic-1",
    }


REWARD_OPTIONS = [
    {"rewardOptionId": "rw-gym-pass", "label": "Free shoe rental on your next visit (simulated reward)",
     "sponsor": "venue", "venueId": "venue-demo-boulder", "isSimulated": True},
    {"rewardOptionId": "rw-cafe", "label": "Cafe group snack (simulated reward)",
     "sponsor": "venue", "venueId": "venue-demo-cafe", "isSimulated": True},
    {"rewardOptionId": "rw-badge", "label": "Group Quests streak badge (simulated reward)",
     "sponsor": "group_quests", "venueId": None, "isSimulated": True},
]


def challenge_input(**overrides) -> dict:
    inp = {
        "context": dict(CTX), "questId": "quest-synthetic-1", "event": event(), "priorPlan": prior_plan(),
        "feedback": [{"participantId": m[0], "attended": None, "wantsReturn": m[0] != "p-dee"} for m in MEMBERS],
        "rewardOptions": [dict(r) for r in REWARD_OPTIONS], "simulateTimeSkip": True,
    }
    inp.update(overrides)
    return inp


def good_challenge_output(**overrides) -> dict:
    out = {"title": "First V2 Together",
           "description": "Send your first V2 as a team within three sessions: everyone tries it, everyone spots.",
           "target": 3, "dueInDays": 21, "rewardOptionId": "rw-gym-pass"}
    out.update(overrides)
    return out
