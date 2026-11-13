"""v3 events list (`EventView`, contracts/protocol.ts 3.0.0; PRD S13).

`GET /events` shows approved events only: the D015 catalog plus custom events an
operator approved. Per viewer it adds two private signals computed elsewhere:

  - `constellationInterestBucket`: Rishi's bucketed count of the viewer's
    constellation peers interested in the event (`3-5 | 6-9 | 10+`, nothing
    under 3, recomputed hourly). Anything else from the port becomes "none".
  - `myInterest`: Patrik's private interest flag for this viewer.

Both arrive through ports so this module never sees ids of other players, and a
failing port degrades to "none" / False rather than inventing a signal.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Awaitable, Callable, Iterable

from .errors import PlanningError
from .venues import VenueCatalog, parse_utc, to_utc

BUCKETS = ("3-5", "6-9", "10+")
WEEK = timedelta(days=7)

# viewer -> [{"eventId", "bucket"}] (Rishi's constellation_interest via Kai).
InterestBuckets = Callable[[Any], Awaitable[Iterable[dict[str, Any]]]]
# (viewer, eventIds) -> set of eventIds the viewer marked interested (Patrik's EventSignals).
MyInterests = Callable[[Any, list[str]], Awaitable[Iterable[str]]]


def catalog_view(event: dict[str, Any]) -> dict[str, Any]:
    """A catalog event as an `EventView` without per-viewer signals."""
    return {"eventId": event["eventId"], "title": event["title"], "placeId": event["placeId"],
            "startsAt": to_utc(parse_utc(event["start"])), "endsAt": to_utc(parse_utc(event["end"])),
            "constellationInterestBucket": "none", "myInterest": False, "kind": "catalog"}


class EventsService:
    def __init__(self, catalog: VenueCatalog, *, interest_buckets: InterestBuckets | None = None,
                 my_interests: MyInterests | None = None,
                 custom_events: Callable[[], Iterable[dict[str, Any]]] | None = None) -> None:
        self._catalog = catalog
        self._buckets = interest_buckets
        self._mine = my_interests
        self._custom = custom_events

    def approved(self) -> list[dict[str, Any]]:
        """Every approved event as a signal-free `EventView` (catalog + approved custom)."""
        views = [catalog_view(e) for e in self._catalog.campus_events]
        if self._custom is not None:
            views += [dict(v) for v in self._custom()]
        return views

    def approved_ids(self) -> frozenset[str]:
        return frozenset(v["eventId"] for v in self.approved())

    async def list(self, viewer: Any, *, now: datetime, window: timedelta = WEEK) -> list[dict[str, Any]]:
        """Upcoming approved events in [now, now + window), with this viewer's signals."""
        views = [v for v in self.approved()
                 if now <= parse_utc(v["startsAt"]) < now + window]
        return await self._with_signals(viewer, views)

    async def get(self, viewer: Any, event_id: str) -> dict[str, Any]:
        for view in self.approved():
            if view["eventId"] == event_id:
                return (await self._with_signals(viewer, [view]))[0]
        raise PlanningError("NOT_FOUND", "no approved event with that id")

    async def _with_signals(self, viewer: Any, views: list[dict[str, Any]]) -> list[dict[str, Any]]:
        ids = {v["eventId"] for v in views}
        buckets: dict[str, str] = {}
        if self._buckets is not None and views:
            try:
                for row in await self._buckets(viewer):
                    if isinstance(row, dict) and row.get("eventId") in ids and row.get("bucket") in BUCKETS:
                        buckets[row["eventId"]] = row["bucket"]
            except Exception:  # a failing signal shows "none", never an invented bucket
                buckets = {}
        mine: set[str] = set()
        if self._mine is not None and views:
            try:
                mine = {e for e in await self._mine(viewer, sorted(ids)) if e in ids}
            except Exception:
                mine = set()
        out = [{**v, "constellationInterestBucket": buckets.get(v["eventId"], "none"),
                "myInterest": v["eventId"] in mine} for v in views]
        return sorted(out, key=lambda v: (v["startsAt"], v["eventId"]))
