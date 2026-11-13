"""v3 custom events (`CustomEventProposal`, contracts/protocol.ts 3.0.0; PRD S14).

Every few weeks Rishi's cluster finder spots players who keep landing in the same
constellations. Muse proposes one public event for them (M7, task `event_nudge`,
prompt `custom_event.v1`) from AGGREGATE input only: cluster size, allowlisted
interest tags, a city-level area from community config, candidate windows and
the approved venues. Never player ids, answers or names.

Code decides what an operator ever sees:
  - `placeId` must be an approved public venue,
  - `timeWindow` must sit inside one of the offered windows, last at most 3 h,
  - `title` and `why` must be one line, contain no digits or links, pass
    OutputGuard and the M10 sensitivity screen (REQUIRED: no screen, no proposal).
Survivors are stored `pending`. Nothing reaches a player until an operator
approves; then it becomes an `EventView` of kind "custom" (`ev-custom-<id>`) and
`on_approved` lets Patrik's invites module issue invites.
"""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any, Callable

from server.providers import MUSE_VOICE, MusePort, MuseRequest, NullTrace, ProviderError, TaskRegistry, TaskSpec
from server.providers.contract import ACTIVITY_TOPICS, CUSTOM_EVENT_IN, CUSTOM_EVENT_OUT

from .errors import PlanningError
from .ports import OutputGuardPort, guard_allows, sensitivity_allows
from .venues import VenueCatalog, parse_utc, to_utc

CUSTOM_EVENT_PROMPT_VERSION = "custom_event.v1"
MAX_HOURS = 3
_DIGIT = re.compile(r"\d")
_URL = re.compile(r"https?://|www\.|@", re.I)

CUSTOM_EVENT_INSTRUCTIONS = """\
Task: propose one small, public, low-pressure meetup for a group of people who
keep being matched together in a weekly game, so they can meet in person.
Input: clusterSize, interestTags (what the group tends to enjoy), area (city),
windows (allowed time windows) and venues (the only places allowed).
Rules:
- placeId: exactly one placeId from venues. timeWindow: inside one of windows,
  one to three hours long.
- title: at most 60 characters, plain and inviting, about an activity that fits
  the interestTags and the venue.
- why: one sentence, at most 160 characters, naming the shared interests only.
  Never describe people, feelings or anything personal, never write numbers.
- Easy to decline, never pressure. No exclamation marks, no emoji.

""" + MUSE_VOICE


def register_custom_event_task(registry: TaskRegistry) -> TaskRegistry:
    registry.register(TaskSpec(
        task="event_nudge", prompt_version=CUSTOM_EVENT_PROMPT_VERSION, instructions=CUSTOM_EVENT_INSTRUCTIONS,
        output_schema=CUSTOM_EVENT_OUT, input_schema=CUSTOM_EVENT_IN, schema_name="custom_event",
        max_output_tokens=4000, temperature=0.6,
    ))
    return registry


@dataclass
class InMemoryCustomEventStore:
    """Process-local proposals (Kai provides the durable one)."""

    _rows: dict[str, dict[str, Any]] = field(default_factory=dict)

    def put(self, row: dict[str, Any]) -> None:
        self._rows[row["proposalId"]] = dict(row)

    def get(self, proposal_id: str) -> dict[str, Any] | None:
        row = self._rows.get(proposal_id)
        return dict(row) if row else None

    def all(self) -> list[dict[str, Any]]:
        return [dict(r) for r in self._rows.values()]


PUBLIC_KEYS = ("proposalId", "clusterSize", "title", "why", "placeId", "timeWindow", "evidence", "status")


class CustomEventService:
    def __init__(self, muse: MusePort, guard: OutputGuardPort, catalog: VenueCatalog, *,
                 area: str, sensitivity: Any = None, store: InMemoryCustomEventStore | None = None,
                 on_approved: Callable[[dict[str, Any]], Any] | None = None, trace: Any = None,
                 new_id: Callable[[], str] = lambda: uuid.uuid4().hex) -> None:
        if not isinstance(area, str) or not (1 <= len(area) <= 60):
            raise ValueError("area must be a city-level name from community config")
        self._muse = muse
        self._guard = guard
        self._catalog = catalog
        self._area = area
        self._sensitivity = sensitivity
        self._store = store if store is not None else InMemoryCustomEventStore()
        self._on_approved = on_approved
        self._trace = trace if trace is not None else NullTrace()
        self._new_id = new_id

    async def propose(self, cluster: dict[str, Any], windows: list[dict[str, str]], *,
                      request_id: str | None = None) -> dict[str, Any] | None:
        """One pending proposal from Rishi's `cluster_aggregate` output, or None if code refused it."""
        size, tags = cluster.get("clusterSize"), cluster.get("tags", cluster.get("interestTags", []))
        if (isinstance(size, bool) or not isinstance(size, int) or not isinstance(tags, list)
                or set(tags) - set(ACTIVITY_TOPICS)):
            raise PlanningError("INVALID_INPUT", "cluster must be {clusterSize, tags} with allowlisted tags")
        payload = {"clusterSize": size, "interestTags": list(dict.fromkeys(tags))[:5], "area": self._area,
                   "windows": [{"start": w["start"], "end": w["end"]} for w in windows][:5],
                   "venues": [dict(v) for v in self._catalog.venues]}
        rid = request_id or f"custom-{self._new_id()[:12]}"
        try:
            result = await self._muse.run(MuseRequest(task="event_nudge", request_id=rid,
                                                      prompt_version=CUSTOM_EVENT_PROMPT_VERSION, payload=payload))
        except ProviderError as exc:
            self._trace.note(rid, "refused", f"provider_{exc.kind}")
            return None
        out = result.output
        reason = self._refusal(out, payload["windows"])
        if reason is None and not await sensitivity_allows(self._sensitivity, [out["title"], out["why"]], required=True):
            reason = "sensitive_or_unscreened"
        if reason is not None:
            self._trace.note(rid, "refused", reason)
            return None
        row = {"proposalId": f"cp-{self._new_id()[:16]}", "clusterSize": size, "title": out["title"],
               "why": out["why"], "placeId": out["placeId"],
               "timeWindow": {"start": to_utc(parse_utc(out["timeWindow"]["start"])),
                              "end": to_utc(parse_utc(out["timeWindow"]["end"]))},
               "evidence": dict(result.evidence), "status": "pending"}
        self._store.put(row)
        self._trace.note(rid, "kept", "pending_proposal")
        return {k: row[k] for k in PUBLIC_KEYS}

    def _refusal(self, out: dict[str, Any], windows: list[dict[str, str]]) -> str | None:
        if self._catalog.get(out["placeId"]) is None:
            return "place_not_allowlisted"
        try:
            begins, ends = parse_utc(out["timeWindow"]["start"]), parse_utc(out["timeWindow"]["end"])
        except ValueError:
            return "time_malformed"
        if not (begins < ends <= begins + timedelta(hours=MAX_HOURS)):
            return "time_length"
        if not any(parse_utc(w["start"]) <= begins and ends <= parse_utc(w["end"]) for w in windows):
            return "time_outside_window"
        for text in (out["title"], out["why"]):
            if "\n" in text or text != text.strip() or _DIGIT.search(text) or _URL.search(text):
                return "text_shape"
            if not guard_allows(self._guard, text, []):
                return "guard_rejected_text"
        return None

    def pending(self) -> list[dict[str, Any]]:
        return [{k: r[k] for k in PUBLIC_KEYS} for r in self._store.all() if r["status"] == "pending"]

    def decide(self, proposal_id: str, decision: str) -> dict[str, Any]:
        """Operator approve/reject. An approved proposal becomes a custom `EventView`."""
        if decision not in ("approve", "reject"):
            raise PlanningError("INVALID_INPUT", "decision must be approve or reject")
        row = self._store.get(proposal_id)
        if row is None:
            raise PlanningError("NOT_FOUND", "no proposal with that id")
        if row["status"] != "pending":
            raise PlanningError("INVALID_INPUT", "proposal already decided")
        row["status"] = "approved" if decision == "approve" else "rejected"
        self._store.put(row)
        if row["status"] == "approved" and self._on_approved is not None:
            self._on_approved(self.event_view(row))
        return {k: row[k] for k in PUBLIC_KEYS}

    @staticmethod
    def event_view(row: dict[str, Any]) -> dict[str, Any]:
        return {"eventId": f"ev-custom-{row['proposalId']}", "title": row["title"], "placeId": row["placeId"],
                "startsAt": row["timeWindow"]["start"], "endsAt": row["timeWindow"]["end"],
                "constellationInterestBucket": "none", "myInterest": False, "kind": "custom"}

    def approved_events(self) -> list[dict[str, Any]]:
        return [self.event_view(r) for r in self._store.all() if r["status"] == "approved"]
