"""M7 event nudges: NudgePort.propose (contracts/protocol.ts 2.0.0). Step 6, cuttable.

Muse proposes one public get-together for a constellation; this module decides
whether it is real enough to show:
  - the constellation must have at least 3 members and an open room
  - ``placeId`` must be in the approved venue catalog (never a free-text place)
  - the time window must be well-formed, inside the requested window, in the
    future and at most MAX_EVENT_HOURS long
  - title, why and the final chat text each pass OutputGuard against the
    members' answers and the private sharedMeaning
  - ``minAttendees`` is always 3
A rejected or failed proposal yields no nudge. There is no invented fallback:
``EventNudge.evidence`` must be a real Muse call. One nudge per constellation;
asking again returns the stored one.

The chat line is written by code from validated fields, not by the model.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Awaitable, Callable, Protocol
from zoneinfo import ZoneInfo

from server.providers import MUSE_VOICE, MusePort, NullTrace, MuseRequest, ProviderError, TaskRegistry, contract_spec

from .errors import PlanningError
from .ports import ChatPostPort, OutputGuardPort, guard_allows, sensitivity_allows
from .venues import VenueCatalog, parse_utc, to_utc

NUDGE_PROMPT_VERSION = "event_nudge.v1"
MIN_ATTENDEES = 3
MAX_EVENT_HOURS = 3
DEFAULT_WINDOW = timedelta(hours=72)
MUSE_HANDLE = "Muse"

NUDGE_INSTRUCTIONS = """\
Task: suggest ONE easy, public get-together for a small group of 3 to 5 people
who do not know each other's names yet.
Input: sharedMeaning (a private note on what this group has in common), venues
(the only places allowed), window (the only time range allowed) and campusEvents
(things already happening at those venues).
Rules:
- placeId must be copied exactly from venues. Never invent a place.
- Prefer a campusEvents entry inside the window: use its placeId and start, and
  end one to two hours later. Otherwise pick a venue and a daytime or early
  evening slot of one to two hours inside the window.
- timeWindow start and end are RFC3339 UTC ending in "Z".
- title: at most 60 characters, what is happening, no venue name needed.
- why: one sentence, at most 160 characters, on why this is an easy thing to
  show up to. Talk about the activity, not about the people. Never state or
  hint at what the group has in common, never repeat words from sharedMeaning,
  never suggest a private place, food budget, or exchanging contact details.

""" + MUSE_VOICE


def register_nudge_task(registry: TaskRegistry) -> TaskRegistry:
    registry.register(contract_spec(
        "event_nudge", NUDGE_PROMPT_VERSION, NUDGE_INSTRUCTIONS, max_output_tokens=4000, temperature=0.6,
    ))
    return registry


class ConstellationContext(Protocol):
    """Orchestration (Kai) supplies this server-side view. None when unknown.

    Returns ``{constellationId, roomId, sharedMeaning, memberCount, roomOpen,
    againstAnswers}``. ``againstAnswers`` are the members' answer texts for the
    no-quote guard; they are never sent to Muse and never logged here.
    """

    def __call__(self, constellation_id: str) -> Awaitable[dict[str, Any] | None]: ...


@dataclass(frozen=True)
class NudgeOutcome:
    nudge: dict[str, Any] | None   # EventNudge
    reason: str                    # "ok", "stored", or why there is no nudge (code-generated)


@dataclass
class InMemoryNudgeStore:
    """Process-local. Durable storage belongs to orchestration."""

    _nudges: dict[str, dict[str, Any]] = field(default_factory=dict)
    _posted: dict[str, dict[str, Any]] = field(default_factory=dict)

    def get(self, constellation_id: str) -> dict[str, Any] | None:
        return self._nudges.get(constellation_id)

    def put(self, constellation_id: str, nudge: dict[str, Any]) -> None:
        self._nudges[constellation_id] = nudge

    def posted(self, constellation_id: str) -> dict[str, Any] | None:
        return self._posted.get(constellation_id)

    def mark_posted(self, constellation_id: str, message: dict[str, Any]) -> None:
        self._posted[constellation_id] = message


def _clean_line(text: Any, max_len: int) -> bool:
    return isinstance(text, str) and 0 < len(text) <= max_len and text == text.strip() and "\n" not in text


class NudgeService:
    def __init__(self, muse: MusePort, guard: OutputGuardPort, catalog: VenueCatalog,
                 context: ConstellationContext, chat: ChatPostPort, *,
                 store: InMemoryNudgeStore | None = None,
                 now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
                 time_zone: str = "America/Los_Angeles",
                 new_id: Callable[[], str] = lambda: uuid.uuid4().hex, trace: Any = None,
                 sensitivity: Any = None) -> None:
        self._muse = muse
        self._trace = trace if trace is not None else NullTrace()
        self._sensitivity = sensitivity  # D014 M10 port, optional; runs after OutputGuard
        self._guard = guard
        self._catalog = catalog
        self._context = context
        self._chat = chat
        self._store = store if store is not None else InMemoryNudgeStore()
        self._now = now
        self._tz = ZoneInfo(time_zone)
        self._new_id = new_id

    async def propose(self, constellation_id: str, *, request_id: str | None = None) -> dict[str, Any] | None:
        """NudgePort.propose: an ``EventNudge`` or None."""
        return (await self.propose_detailed(constellation_id, request_id=request_id)).nudge

    async def propose_detailed(self, constellation_id: str, *, request_id: str | None = None,
                               window: tuple[datetime, datetime] | None = None) -> NudgeOutcome:
        stored = self._store.get(constellation_id)
        if stored is not None:
            return NudgeOutcome(dict(stored), "stored")
        ctx = await self._context(constellation_id)
        if ctx is None:
            return NudgeOutcome(None, "unknown_constellation")
        if not ctx.get("roomOpen") or int(ctx.get("memberCount", 0)) < MIN_ATTENDEES:
            return NudgeOutcome(None, "room_closed_or_too_small")
        start, end = window if window is not None else (self._now(), self._now() + DEFAULT_WINDOW)
        payload = {
            "sharedMeaning": ctx["sharedMeaning"],
            "venues": [dict(v) for v in self._catalog.venues],
            "window": {"start": to_utc(start), "end": to_utc(end)},
            "campusEvents": self._catalog.events_between(start, end),
        }
        rid = request_id or f"nudge-{self._new_id()[:12]}"
        try:
            result = await self._muse.run(MuseRequest(
                task="event_nudge", request_id=rid,
                prompt_version=NUDGE_PROMPT_VERSION, payload=payload,
            ))
        except ProviderError as exc:
            return NudgeOutcome(None, f"provider_{exc.kind}")
        self._trace.note(rid, "input", "approved_venues", len(payload["venues"]))
        against = [*ctx.get("againstAnswers", []), ctx["sharedMeaning"]]
        reason = self._reject_reason(result.output, start, end, against)
        if reason is not None:
            self._trace.note(rid, "refused", reason)
            return NudgeOutcome(None, reason)
        out = result.output
        nudge = {
            "nudgeId": f"nudge-{self._new_id()}",
            "constellationId": constellation_id,
            "title": out["title"],
            "placeId": out["placeId"],
            "timeWindow": {"start": to_utc(parse_utc(out["timeWindow"]["start"])),
                           "end": to_utc(parse_utc(out["timeWindow"]["end"]))},
            "why": out["why"],
            "minAttendees": MIN_ATTENDEES,
            "evidence": dict(result.evidence),
        }
        if not guard_allows(self._guard, self.chat_text(nudge), against):
            self._trace.note(rid, "refused", "guard_rejected_text")
            return NudgeOutcome(None, "guard_rejected_text")
        if not await sensitivity_allows(self._sensitivity, [out["title"], out["why"]]):
            self._trace.note(rid, "refused", "sensitive_text")
            return NudgeOutcome(None, "sensitive_text")
        self._trace.note(rid, "checked", "venue_time_text_ok")
        self._store.put(constellation_id, nudge)
        return NudgeOutcome(dict(nudge), "ok")

    def _reject_reason(self, out: dict[str, Any], start: datetime, end: datetime, against: list[str]) -> str | None:
        if self._catalog.get(out["placeId"]) is None:
            return "place_not_allowlisted"
        try:
            begins, ends = parse_utc(out["timeWindow"]["start"]), parse_utc(out["timeWindow"]["end"])
        except ValueError:
            return "time_malformed"
        if not (begins < ends <= begins + timedelta(hours=MAX_EVENT_HOURS)):
            return "time_length"
        if begins < start or ends > end or begins <= self._now():
            return "time_outside_window"
        if not _clean_line(out["title"], 80) or not _clean_line(out["why"], 240):
            return "text_shape"
        if not guard_allows(self._guard, out["title"], against) or not guard_allows(self._guard, out["why"], against):
            return "guard_rejected_text"
        return None

    def chat_text(self, nudge: dict[str, Any]) -> str:
        """The single line posted to the room, built by code from validated fields."""
        venue = self._catalog.get(nudge["placeId"])
        if venue is None:  # catalog changed since the nudge was stored
            raise PlanningError("INVALID_INPUT", "nudge venue is no longer approved")
        begins = parse_utc(nudge["timeWindow"]["start"]).astimezone(self._tz)
        ends = parse_utc(nudge["timeWindow"]["end"]).astimezone(self._tz)
        when = f"{begins.strftime('%A')} {_clock(begins)}-{_clock(ends)}"
        return (f"{nudge['title']} at {venue['name']}, {when}. {nudge['why']} "
                f"Go if {nudge['minAttendees']} of you are in.")

    async def propose_and_post(self, constellation_id: str, *, request_id: str | None = None) -> dict[str, Any]:
        """Operator button / mid-week job: propose, then post once as ``muse_nudge``.

        Returns ``{"nudge": EventNudge, "message": ChatMessage}``. Raises
        PlanningError when there is nothing safe to post.
        """
        outcome = await self.propose_detailed(constellation_id, request_id=request_id)
        if outcome.nudge is None:
            if outcome.reason in ("unknown_constellation", "room_closed_or_too_small"):
                raise PlanningError("NOT_FOUND", "no open room for this constellation")
            raise PlanningError("PROVIDER_UNAVAILABLE", f"no nudge available ({outcome.reason})", retryable=True)
        already = self._store.posted(constellation_id)
        if already is not None:
            return {"nudge": outcome.nudge, "message": dict(already)}
        # Recheck at execution time: the room may have expired since the proposal.
        ctx = await self._context(constellation_id)
        if ctx is None or not ctx.get("roomOpen") or int(ctx.get("memberCount", 0)) < MIN_ATTENDEES:
            raise PlanningError("NOT_FOUND", "no open room for this constellation")
        text = self.chat_text(outcome.nudge)
        if not guard_allows(self._guard, text, [*ctx.get("againstAnswers", []), ctx["sharedMeaning"]]):
            raise PlanningError("PROVIDER_UNAVAILABLE", "no nudge available (guard_rejected_text)", retryable=True)
        message = await self._chat.post_system(ctx["roomId"], {
            "roomId": ctx["roomId"], "handle": MUSE_HANDLE, "text": text, "kind": "muse_nudge",
        })
        self._store.mark_posted(constellation_id, dict(message))
        return {"nudge": outcome.nudge, "message": dict(message)}


def _clock(t: datetime) -> str:
    hour = t.hour % 12 or 12
    minutes = f":{t.minute:02d}" if t.minute else ""
    return f"{hour}{minutes}{'am' if t.hour < 12 else 'pm'}"
