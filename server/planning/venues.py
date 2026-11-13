"""Approved public venue allowlist (``Venue`` in contracts/protocol.ts 2.0.0).

M7 may only pick a ``placeId`` from this catalog. The file is validated on
load; a venue that is not marked public, or an event at an unknown place,
stops the load. Addresses are not stored: a nudge names a venue, never a route
to anyone's home.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from server.providers.contract import VENUE
from server.providers.schema import SchemaViolation, validate

from .errors import BankError

_EVENT_ID = re.compile(r"^ev-[a-z0-9-]{1,60}$")
# What M7 sees of an event (M7In.campusEvents in contracts/protocol.ts): no id.
M7_EVENT_FIELDS = ("title", "placeId", "start")
DEFAULT_VENUES_PATH = Path(__file__).resolve().parent / "data" / "venues.json"

_EVENT = {
    "type": "object", "additionalProperties": False, "required": ["eventId", "title", "placeId", "start", "end"],
    "properties": {
        # Stable approved id: activity signals and event heat may count only these.
        "eventId": {"type": "string", "minLength": 4, "maxLength": 64},
        "title": {"type": "string", "minLength": 1, "maxLength": 80},
        "placeId": {"type": "string", "minLength": 1, "maxLength": 64},
        "start": {"type": "string", "minLength": 10, "maxLength": 40},
        # D015 addendum: explicit end so EventView.endsAt (3.0.0) is never guessed.
        "end": {"type": "string", "minLength": 10, "maxLength": 40},
    },
}
MAX_EVENT_HOURS = 3


def parse_utc(value: Any) -> datetime:
    """RFC3339 UTC instant -> aware datetime. Raises ValueError otherwise."""
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError("time must be RFC3339 UTC ending in Z")
    parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    return parsed.astimezone(timezone.utc)


def to_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass(frozen=True)
class VenueCatalog:
    venues: tuple[dict[str, Any], ...]
    campus_events: tuple[dict[str, Any], ...]

    @classmethod
    def from_doc(cls, doc: Any) -> "VenueCatalog":
        if not isinstance(doc, dict) or doc.get("contractVersion") != "2.0.0":
            raise BankError("venue file must declare contractVersion 2.0.0")
        venues, events = doc.get("venues"), doc.get("campusEvents", [])
        if not isinstance(venues, list) or not venues or not isinstance(events, list):
            raise BankError("venue file needs a non-empty venues list")
        ids: set[str] = set()
        for i, v in enumerate(venues):
            try:
                validate(v, VENUE)
            except SchemaViolation as exc:
                raise BankError(f"venues[{i}]: {exc}") from None
            if v["placeId"] in ids:
                raise BankError(f"venues[{i}]: duplicate placeId")
            ids.add(v["placeId"])
        event_ids: set[str] = set()
        for i, e in enumerate(events):
            try:
                validate(e, _EVENT)
                begins, ends = parse_utc(e["start"]), parse_utc(e["end"])
                if not (begins < ends <= begins + timedelta(hours=MAX_EVENT_HOURS)):
                    raise ValueError(f"end must be after start and within {MAX_EVENT_HOURS} h")
            except (SchemaViolation, ValueError) as exc:
                raise BankError(f"campusEvents[{i}]: {exc}") from None
            if not _EVENT_ID.match(e["eventId"]) or e["eventId"] in event_ids:
                raise BankError(f"campusEvents[{i}]: eventId must be unique and look like ev-name")
            event_ids.add(e["eventId"])
            if e["placeId"] not in ids:
                raise BankError(f"campusEvents[{i}]: placeId is not an approved venue")
        return cls(tuple(dict(v) for v in venues), tuple(dict(e) for e in events))

    @classmethod
    def load(cls, path: str | Path = DEFAULT_VENUES_PATH) -> "VenueCatalog":
        try:
            doc = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            raise BankError("venue file is missing or not JSON") from None
        return cls.from_doc(doc)

    def get(self, place_id: Any) -> dict[str, Any] | None:
        for v in self.venues:
            if v["placeId"] == place_id:
                return dict(v)
        return None

    def events_between(self, start: datetime, end: datetime) -> list[dict[str, Any]]:
        """Events in [start, end) shaped for M7In (title, placeId, start; no id)."""
        return [{k: e[k] for k in M7_EVENT_FIELDS} for e in self.campus_events
                if start <= parse_utc(e["start"]) < end]

    def event_ids(self) -> frozenset[str]:
        """Approved event ids: the only ids activity signals and event heat may count."""
        return frozenset(e["eventId"] for e in self.campus_events)

    def event(self, event_id: Any) -> dict[str, Any] | None:
        for e in self.campus_events:
            if e["eventId"] == event_id:
                return dict(e)
        return None
