"""v3 event nudges (`EventNudgeView`, contracts/protocol.ts 3.0.0; PRD S13).

A nudge tells one viewer that people from their constellations are interested in
an approved event. Who is eligible comes from Rishi (`nudge_eligible` rows of
`{eventId, bucket}`); Kai's job calls `propose_for` and delivers with the R3
delay. This module owns the copy and the cadence:

Copy (M7, task `event_nudge`, prompt `event_nudge_copy.v1`): Muse writes one line
from aggregate input only (event title, venue name, start, bucket). Code accepts
it only if it is one line of at most 140 chars, mentions the event title or the
venue, contains no digits (no counts, times or numbers), passes OutputGuard and
the M10 sensitivity screen. Otherwise a fixed template is used and labeled
`source: "template"`. The M10 screen is REQUIRED here: without one, Muse copy is
never shown (fail closed to the template). Copy is shared per (event, bucket),
never personal, and cached for an hour, so one Muse call serves every viewer.

Cadence per viewer: at most 2 active, at most 1 new per 48 h, at most 2 per rolling
7 days, never the same event twice, only upcoming events within 7 days, and a
dismissed or expired nudge never comes back. Revoking event consent `forget`s all.
"""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable

from server.providers import MUSE_VOICE, MusePort, MuseRequest, NullTrace, ProviderError, TaskRegistry, TaskSpec
from server.providers.contract import INTEREST_BUCKETS, M7_COPY_IN, M7_COPY_OUT

from .ports import OutputGuardPort, guard_allows, sensitivity_allows
from .venues import VenueCatalog, parse_utc, to_utc

NUDGE_COPY_PROMPT_VERSION = "event_nudge_copy.v1"
MAX_COPY = 140
MAX_ACTIVE = 2
MIN_GAP = timedelta(hours=48)
WEEK = timedelta(days=7)
COPY_TTL = timedelta(hours=1)  # buckets are recomputed hourly (R3)
BUCKET_WORDS = {"3-5": "A few", "6-9": "Several", "10+": "Lots of"}

NUDGE_COPY_INSTRUCTIONS = """\
Task: write one short line telling a player that some people from their
constellations (small groups they were matched into this week) are interested in
a public campus event, so they might want to go too.
Input: event (title, venueName, startsAt) and interestBucket ("3-5", "6-9" or
"10+": how many, as a range).
Rules:
- One sentence, at most 120 characters. Mention the event title or the venue.
- Never write a number, a count, a time or a date: say "a few", "several" or
  "lots of" for the bucket. Never name or describe anyone.
- An easy invitation, never pressure. No exclamation marks, no emoji.

""" + MUSE_VOICE

_DIGIT = re.compile(r"\d")
_URL = re.compile(r"https?://|www\.|@", re.I)


def register_nudge_copy_task(registry: TaskRegistry) -> TaskRegistry:
    registry.register(TaskSpec(
        task="event_nudge", prompt_version=NUDGE_COPY_PROMPT_VERSION, instructions=NUDGE_COPY_INSTRUCTIONS,
        output_schema=M7_COPY_OUT, input_schema=M7_COPY_IN, schema_name="event_nudge_copy",
        max_output_tokens=3000, temperature=0.6,
    ))
    return registry


def template_copy(bucket: str, title: str, venue: str) -> str:
    return f"{BUCKET_WORDS[bucket]} people from your constellations are interested in {title} at {venue}."


def copy_problems(copy: Any, title: str, venue: str) -> list[str]:
    if not isinstance(copy, str) or not copy.strip():
        return ["empty"]
    problems = []
    if len(copy) > MAX_COPY or "\n" in copy or copy != copy.strip():
        problems.append("shape")
    if _DIGIT.search(copy):
        problems.append("digits")
    if _URL.search(copy):
        problems.append("link_or_handle")
    if title.lower() not in copy.lower() and venue.lower() not in copy.lower():
        problems.append("off_topic")
    return problems


@dataclass
class InMemoryNudgeLedger:
    """Per-viewer nudges (process-local; Kai provides the durable one)."""

    _rows: dict[str, list[dict[str, Any]]] = field(default_factory=dict)

    def rows(self, viewer_id: str) -> list[dict[str, Any]]:
        return [dict(r) for r in self._rows.get(viewer_id, [])]

    def add(self, viewer_id: str, row: dict[str, Any]) -> None:
        self._rows.setdefault(viewer_id, []).append(dict(row))

    def dismiss(self, viewer_id: str, nudge_id: str) -> bool:
        for r in self._rows.get(viewer_id, []):
            if r["nudgeId"] == nudge_id:
                r["dismissed"] = True
                return True
        return False

    def forget(self, viewer_id: str) -> None:
        self._rows.pop(viewer_id, None)


class EventNudgeService:
    def __init__(self, muse: MusePort, guard: OutputGuardPort, catalog: VenueCatalog, *,
                 sensitivity: Any = None, approved_events: Callable[[], list[dict[str, Any]]] | None = None,
                 ledger: InMemoryNudgeLedger | None = None, trace: Any = None,
                 new_id: Callable[[], str] = lambda: uuid.uuid4().hex) -> None:
        self._muse = muse
        self._guard = guard
        self._catalog = catalog
        self._sensitivity = sensitivity
        self._approved = approved_events
        self._ledger = ledger if ledger is not None else InMemoryNudgeLedger()
        self._trace = trace if trace is not None else NullTrace()
        self._new_id = new_id
        self._copy_cache: dict[tuple[str, str], tuple[datetime, str, str]] = {}

    def _events(self) -> dict[str, dict[str, Any]]:
        from .events import catalog_view

        views = [catalog_view(e) for e in self._catalog.campus_events]
        if self._approved is not None:
            views += list(self._approved())
        return {v["eventId"]: v for v in views}

    def _venue_name(self, place_id: str) -> str | None:
        venue = self._catalog.get(place_id)
        return venue["name"] if venue else None

    async def copy_for(self, event: dict[str, Any], bucket: str, *, now: datetime,
                       request_id: str | None = None) -> tuple[str, str]:
        """(copy, source) with source "muse" or "template". Shared per (event, bucket)."""
        venue = self._venue_name(event["placeId"])
        if venue is None or bucket not in INTEREST_BUCKETS:
            raise ValueError("event must be at an approved venue with a visible bucket")
        key = (event["eventId"], bucket)
        cached = self._copy_cache.get(key)
        if cached is not None and now - cached[0] < COPY_TTL:
            return cached[1], cached[2]
        fallback = template_copy(bucket, event["title"], venue)
        copy, source = fallback, "template"
        rid = request_id or f"nudge-copy-{self._new_id()[:12]}"
        try:
            result = await self._muse.run(MuseRequest(
                task="event_nudge", request_id=rid, prompt_version=NUDGE_COPY_PROMPT_VERSION,
                payload={"event": {"title": event["title"], "venueName": venue, "startsAt": event["startsAt"]},
                         "interestBucket": bucket}))
            proposed = result.output["copy"]
            problems = copy_problems(proposed, event["title"], venue)
            if problems:
                for code in problems:
                    self._trace.note(rid, "validate", code)
            elif not guard_allows(self._guard, proposed, []):
                self._trace.note(rid, "guard", "rejected")
            elif not await sensitivity_allows(self._sensitivity, [proposed], required=True):
                self._trace.note(rid, "refused", "sensitive_or_unscreened")
            else:
                copy, source = proposed, "muse"
        except ProviderError:
            self._trace.note(rid, "fallback", "provider_failed")
        if source == "template":
            self._trace.note(rid, "fallback", "template")
        self._copy_cache[key] = (now, copy, source)
        return copy, source

    def active(self, viewer_id: str, *, now: datetime) -> list[dict[str, Any]]:
        """`EventNudgeView[]`, at most 2: not dismissed, not expired."""
        rows = [r for r in self._ledger.rows(viewer_id)
                if not r.get("dismissed") and parse_utc(r["expiresAt"]) > now]
        rows.sort(key=lambda r: r["createdAt"], reverse=True)
        return [{k: r[k] for k in ("nudgeId", "eventId", "copy", "interestBucket", "expiresAt")}
                for r in rows[:MAX_ACTIVE]]

    def dismiss(self, viewer_id: str, nudge_id: str) -> bool:
        return self._ledger.dismiss(viewer_id, nudge_id)

    def forget(self, viewer_id: str) -> None:
        """Event-signal consent revoked: drop every queued and active nudge."""
        self._ledger.forget(viewer_id)

    async def propose_for(self, viewer_id: str, eligible: list[dict[str, Any]], *,
                          now: datetime) -> dict[str, Any] | None:
        """Create at most one nudge for the viewer from Rishi's eligible rows, or None."""
        rows = self._ledger.rows(viewer_id)
        created = [parse_utc(r["createdAt"]) for r in rows]
        if any(now - c < MIN_GAP for c in created) or sum(now - c < WEEK for c in created) >= 2:
            return None
        if len(self.active(viewer_id, now=now)) >= MAX_ACTIVE:
            return None
        seen = {r["eventId"] for r in rows}
        events = self._events()
        rank = {b: i for i, b in enumerate(reversed(INTEREST_BUCKETS))}  # 10+ first
        candidates = []
        for row in eligible:
            event = events.get(row.get("eventId"))
            bucket = row.get("bucket")
            if event is None or bucket not in INTEREST_BUCKETS or event["eventId"] in seen:
                continue
            starts = parse_utc(event["startsAt"])
            if not (now < starts <= now + WEEK):
                continue
            candidates.append((rank[bucket], starts, event, bucket))
        if not candidates:
            return None
        _, starts, event, bucket = min(candidates, key=lambda c: (c[0], c[1], c[2]["eventId"]))
        copy, source = await self.copy_for(event, bucket, now=now)
        row = {"nudgeId": f"nd-{self._new_id()[:16]}", "eventId": event["eventId"], "copy": copy,
               "interestBucket": bucket, "expiresAt": to_utc(starts), "createdAt": to_utc(now),
               "copySource": source, "dismissed": False}
        self._ledger.add(viewer_id, row)
        return {k: row[k] for k in ("nudgeId", "eventId", "copy", "interestBucket", "expiresAt")}

    async def preview(self, event_id: str, bucket: str, *, now: datetime) -> dict[str, Any]:
        """Operator preview: copy, its source and the guard verdict. No player ids."""
        event = self._events().get(event_id)
        if event is None:
            raise ValueError("not an approved event")
        copy, source = await self.copy_for(event, bucket, now=now)
        return {"eventId": event_id, "interestBucket": bucket, "copy": copy, "source": source,
                "guardOk": guard_allows(self._guard, copy, [])}

    def bucket_counts(self, *, now: datetime) -> dict[str, int]:
        """Operator panel: active nudges per bucket across viewers (counts only)."""
        out = {b: 0 for b in INTEREST_BUCKETS}
        for viewer in list(self._ledger._rows):
            for n in self.active(viewer, now=now):
                out[n["interestBucket"]] += 1
        return out
