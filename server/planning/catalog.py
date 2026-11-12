"""Venue catalog helpers + a SYNTHETIC demo catalog.

The contract's Venue carries absolute openingWindows, so weekly hours are
expanded over a horizon in the venue's local time zone. The demo catalog is
labeled synthetic: its names and addresses are placeholders, not real places,
until the team agrees on an approved catalog source (see handoff).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Mapping, Sequence
from zoneinfo import ZoneInfo

from . import wire
from .timeutil import fmt_utc

Hours = Mapping[int, Sequence[tuple[str, str]]]  # weekday (0=Mon) -> [("09:00", "21:00")]


@dataclass(frozen=True)
class CatalogVenue:
    venue_id: str
    name: str
    area_id: str
    public_address: str
    weekly_hours: Hours


def expand_venue(v: CatalogVenue, *, time_zone: str, start: datetime, days: int = 14) -> dict:
    tz = ZoneInfo(time_zone)
    local_start: date = start.astimezone(tz).date()
    windows: list[dict] = []
    for offset in range(days + 1):
        day = local_start + timedelta(days=offset)
        for open_s, close_s in v.weekly_hours.get(day.weekday(), ()):
            o = datetime.combine(day, time.fromisoformat(open_s), tz).astimezone(timezone.utc)
            c = datetime.combine(day, time.fromisoformat(close_s), tz).astimezone(timezone.utc)
            if c > o:
                windows.append({"start": fmt_utc(o), "end": fmt_utc(c)})
    venue = {
        "venueId": v.venue_id,
        "name": v.name,
        "areaId": v.area_id,
        "publicAddress": v.public_address,
        "isPublic": True,
        "openingWindows": windows,
    }
    return wire.venue(venue)


_DAILY = {d: [("08:00", "21:00")] for d in range(7)}
_CAFE = {d: [("07:00", "19:00")] for d in range(7)}

SYNTHETIC_DEMO_CATALOG: tuple[CatalogVenue, ...] = (
    CatalogVenue("venue-demo-quad", "Main Quad (synthetic demo venue)", "area-north", "Demo address withheld: Main Quad", _DAILY),
    CatalogVenue("venue-demo-library-lawn", "Library Lawn (synthetic demo venue)", "area-north", "Demo address withheld: Library Lawn", _DAILY),
    CatalogVenue("venue-demo-cafe", "Student Union Cafe (synthetic demo venue)", "area-north", "Demo address withheld: Student Union", _CAFE),
    CatalogVenue("venue-demo-plaza", "Downtown Plaza (synthetic demo venue)", "area-downtown", "Demo address withheld: Downtown Plaza", _DAILY),
)


def demo_venues(*, time_zone: str, start: datetime, days: int = 14) -> list[dict]:
    return [expand_venue(v, time_zone=time_zone, start=start, days=days) for v in SYNTHETIC_DEMO_CATALOG]
