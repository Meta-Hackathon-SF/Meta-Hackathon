"""Muse suggestions for the Sunday Messenger group (owner: Will).

``POST /api/v1/muse-chat`` on the cycle router. The hosted web app calls it so the
Muse key stays on the API host (Railway); see server/app/VERCEL.md. The local
dev server has a TypeScript twin (web/museChat.ts) for fixture mode. Keep both
in step: same catalog (data/catalog.json), same instructions, same checks.

Muse proposes, code checks:
* the request carries only a task kind and the last few chat lines, with members
  already renamed to "You" / "Member N" / "Muse"; any other sender is dropped;
* facts come from the demo catalog, never from the request;
* Muse may only point at catalog ids or propose an event draft on an approved
  venue between 08:00 and 22:00; unknown ids and bad drafts are removed here,
  and the browser checks again before showing anything.
Nothing is booked, bought or posted by this route. Prompts and chat text are
never logged. This is a direct HTTPS call, like server/voice/muse_stt.py; it
does not go through the providers adapter, so it records no Muse evidence.
"""

from __future__ import annotations

import json
import logging
import os
import re
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

CATALOG_PATH = Path(__file__).resolve().parent / "data" / "catalog.json"
KINDS = ("hangout", "supplies", "barter", "create")
WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
_SENDER = re.compile(r"^(You|Muse|Member [1-9])$")
_ID = re.compile(r"\b(?:mk|ev|v)-[a-z0-9-]+\b")
_CLOCK = re.compile(r"^(\d{1,2})(?::(\d{2}))?(?::\d{2})?\s*(am|pm|a\.m\.|p\.m\.)?$")
_CONTACT = re.compile(r"(\d[\s.()-]?){7,}|@|https?:|www\.|\.(com|net|org|edu)\b", re.I)

INSTRUCTIONS = " ".join(
    [
        "You help a small group chat plan things. Reply to the latest note only, in one or two short sentences, no emoji. Earlier notes are context. Do not quote anyone.",
        "You never bring, buy, book, hold, reserve or register anything yourself. Never say I'll, I will, or let me. Never say anything is booked, held or confirmed.",
        "Use only the catalog facts. Point at catalog entries by id; the app shows them as cards, so do not list details the card already shows.",
        "task=hangout: pick 1 or 2 eventIds that best fit the chat. Mention the event title. Do not mention items.",
        "task=supplies: pick 1 or 2 itemIds that best fit the chat. Say they are demo listings, not purchases.",
        "task=barter: tell the group to ask Campus Cafe, and say nothing is booked until the cafe agrees. You may pick the coffee set itemId.",
        "task=create: you must fill draftTitle (3-60 chars), draftPlaceId (one venue placeId from the catalog), draftDay (full weekday name), draftTime (24-hour HH:MM between 08:00 and 22:00) and draftDescription (under 160 chars) from what the group wants. If they name no place, pick the best venue. In text, say it is a draft they can create.",
        "Never write any id in text; ids go only in itemIds, eventIds and draftPlaceId. In text use the names.",
    ]
)

_SCHEMA = {
    "type": "object",
    "properties": {
        "text": {"type": "string"},
        "itemIds": {"type": "array", "items": {"type": "string"}},
        "eventIds": {"type": "array", "items": {"type": "string"}},
        # Flat draft fields: models fill these more reliably than a nested object.
        **{
            f"draft{k}": {"type": "string"}
            for k in ("Title", "PlaceId", "Day", "Time", "Description")
        },
    },
    "required": ["text"],
}


_DRAFT_FIELDS = ("draftTitle", "draftPlaceId", "draftDay", "draftTime", "draftDescription")


def _schema(kind: str) -> dict[str, Any]:
    """For create, every draft field is required: live tests showed optional ones were skipped."""
    if kind != "create":
        return _SCHEMA
    return {**_SCHEMA, "required": ["text", *_DRAFT_FIELDS]}


class MuseChatError(Exception):
    """Carries one of the cycle API error codes; never the request or provider body."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class MuseChatConfig:
    key: str
    model: str = "muse-spark-1.3"
    base_url: str = "https://api.meta.ai/v1"
    timeout_s: float = 20.0

    def __post_init__(self) -> None:
        if not self.base_url.startswith("https://"):
            raise ValueError("Muse base URL must be https")

    def __repr__(self) -> str:  # never print the key
        return f"MuseChatConfig(model={self.model!r}, base_url={self.base_url!r})"


def load_config(env: Mapping[str, str] | None = None) -> MuseChatConfig | None:
    """Same variable names as server/providers/config.py, so Railway's existing key works."""
    env = os.environ if env is None else env
    key = env.get("MUSE_API_KEY") or env.get("MODEL_API_KEY") or ""
    if not key or key == "replace-me":
        return None
    return MuseChatConfig(
        key=key,
        model=env.get("MUSE_MODEL") or "muse-spark-1.3",
        base_url=(env.get("MUSE_BASE_URL") or "https://api.meta.ai/v1").rstrip("/"),
    )


Sender = Callable[[str, dict[str, str], bytes, float], tuple[int, bytes]]


def _urllib_send(
    url: str, headers: dict[str, str], body: bytes, timeout_s: float
) -> tuple[int, bytes]:
    request = urllib.request.Request(url, data=body, method="POST", headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as response:  # noqa: S310 - https enforced
            return response.status, response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, b""


def load_catalog(path: Path = CATALOG_PATH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


class MuseChat:
    """One short, checked Muse line for the group chat. Thread-safe rate limit per player."""

    def __init__(
        self,
        config: MuseChatConfig | None,
        *,
        catalog: Mapping[str, Any] | None = None,
        send: Sender = _urllib_send,
        clock: Callable[[], float] = time.monotonic,
        limit: int = 12,
        window_s: float = 60.0,
    ) -> None:
        self._config = config
        self._send = send
        self._clock = clock
        self._limit = limit
        self._window = window_s
        self._hits: dict[str, list[float]] = {}
        self._lock = threading.Lock()
        data = catalog if catalog is not None else load_catalog()
        self._venue_ids = {v["placeId"] for v in data["venues"]}
        self._item_ids = {i["itemId"] for i in data["items"]}
        self._event_ids = {e["eventId"] for e in data["events"]}
        venues = {v["placeId"]: v["name"] for v in data["venues"]}
        self._venue_names = venues
        self._id_names = {
            **venues,
            **{i["itemId"]: i["title"] for i in data["items"]},
            **{e["eventId"]: e["title"] for e in data["events"]},
        }
        self._facts = {
            "events": [
                {
                    "eventId": e["eventId"],
                    "title": e["title"],
                    "venue": venues.get(e["placeId"]),
                    "when": e["when"],
                    "about": e["description"],
                }
                for e in data["events"]
            ],
            "items": [
                {
                    "itemId": i["itemId"],
                    "title": i["title"],
                    "price": i["price"],
                    "about": i["description"],
                }
                for i in data["items"]
            ],
            "venues": list(data["venues"]),
            "vendor": {
                "name": "Campus Cafe",
                "ask": "a table for the group",
                "offer": "bring the coffee set from Marketplace and split the check",
            },
        }

    @classmethod
    def from_env(cls) -> MuseChat:
        return cls(load_config())

    @property
    def configured(self) -> bool:
        return self._config is not None

    # ---- input checks ----------------------------------------------------------
    @staticmethod
    def clean_context(value: Any) -> list[dict[str, str]]:
        if not isinstance(value, list):
            return []
        notes = []
        for note in value:
            if not isinstance(note, dict):
                continue
            sender = note.get("sender")
            text = note.get("text")
            if not isinstance(sender, str) or not isinstance(text, str):
                continue
            sender, text = sender[:20], text.strip()[:200]
            if _SENDER.match(sender) and text:  # only anonymous labels reach the model
                notes.append({"sender": sender, "text": text})
        return notes[-6:]

    def _limited(self, player_id: str) -> bool:
        now = self._clock()
        with self._lock:
            recent = [t for t in self._hits.get(player_id, []) if now - t < self._window]
            recent.append(now)
            self._hits[player_id] = recent
            if len(self._hits) > 5000:
                self._hits = {player_id: recent}
            return len(recent) > self._limit

    # ---- output checks ---------------------------------------------------------
    @staticmethod
    def _ids(value: Any, allowed: set[str]) -> list[str]:
        if not isinstance(value, list):
            return []
        out: list[str] = []
        for v in value:
            if isinstance(v, str) and v in allowed and v not in out:
                out.append(v)
        return out[:2]

    def _venue(self, value: str) -> str:
        """An approved placeId, given the id or the venue's name ("Main Quad", "the quad")."""
        v = value.strip()
        if v in self._venue_ids:
            return v
        key = re.sub(r"^the\s+", "", v.lower())
        for place_id, name in self._venue_names.items():
            if key in (name.lower(), place_id.lower()):
                return place_id
        return ""

    @staticmethod
    def _hhmm(value: str) -> str:
        """24-hour HH:MM from "14:00", "14:00:00", "2:00 PM", "2pm"; "" if unreadable."""
        m = _CLOCK.match(value.strip().lower())
        if not m:
            return ""
        hour, minute, half = int(m.group(1)), int(m.group(2) or 0), m.group(3)
        if half:
            if not 1 <= hour <= 12:
                return ""
            hour = hour % 12 + (12 if half.startswith("p") else 0)
        if hour > 23 or minute > 59:
            return ""
        return f"{hour:02d}:{minute:02d}"

    @staticmethod
    def _weekday(value: str) -> str:
        v = value.strip().lower()
        for day in WEEKDAYS:
            if len(v) >= 3 and day.startswith(v):
                return day.capitalize()
        return ""

    @staticmethod
    def _draft_fields(parsed: Mapping[str, Any]) -> dict[str, Any] | None:
        """The draft from flat draftX fields, or a nested draft object (possibly a JSON string)."""
        flat = {
            k: parsed.get("draft" + k[0].upper() + k[1:])
            for k in ("title", "placeId", "day", "time", "description")
        }
        if any(isinstance(v, str) and v.strip() for v in flat.values()):
            return flat
        nested = parsed.get("draft") or parsed.get("event")
        if isinstance(nested, str):
            try:
                nested = json.loads(nested)
            except ValueError:
                return None
        return nested if isinstance(nested, dict) else None

    def _names_for_ids(self, text: str) -> str:
        """Safety net: any catalog id that slips into the reply is shown by its name."""
        return _ID.sub(lambda m: self._id_names.get(m.group(0), m.group(0)), text)

    def clean_draft(self, value: Any) -> dict[str, str] | None:
        """Normalizes common variants, then applies the same hard limits: approved
        venue, a weekday, 08:00-22:00, title 3-60 chars, no contact details."""
        if not isinstance(value, dict):
            return None

        def s(key: str, limit: int) -> str:
            v = value.get(key)
            return v.strip()[:limit] if isinstance(v, str) else ""

        draft = {
            "title": s("title", 60),
            "placeId": self._venue(s("placeId", 60) or s("venue", 60)),
            "day": self._weekday(s("day", 12)),
            "time": self._hhmm(s("time", 12)),
            "description": s("description", 160),
        }
        hour = int(draft["time"][:2]) if draft["time"] else -1
        if len(draft["title"]) < 3 or not draft["placeId"] or not draft["day"]:
            return None
        if not 8 <= hour <= 22:
            return None
        if _CONTACT.search(draft["title"]) or _CONTACT.search(draft["description"]):
            return None
        return draft

    # ---- the call --------------------------------------------------------------
    def reply(self, body: Any, player_id: str) -> dict[str, Any]:
        """Returns the reply body or raises MuseChatError(INVALID_INPUT | RATE_LIMITED | PROVIDER_UNAVAILABLE)."""
        record = body if isinstance(body, dict) else {}
        kind = record.get("kind")
        context = self.clean_context(record.get("context"))
        if kind not in KINDS or not context:
            raise MuseChatError("INVALID_INPUT")
        if self._config is None:
            raise MuseChatError("PROVIDER_UNAVAILABLE")
        if self._limited(player_id):
            raise MuseChatError("RATE_LIMITED")
        config = self._config
        payload = {
            "model": config.model,
            "reasoning_effort": "low",
            "max_completion_tokens": 900,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "group_chat_line",
                    "strict": False,
                    "schema": _schema(kind),
                },
            },
            "messages": [
                {"role": "developer", "content": INSTRUCTIONS},
                {
                    "role": "user",
                    "content": json.dumps(
                        {"task": kind, "context": context, "catalog": self._facts}
                    ),
                },
            ],
        }
        headers = {
            "authorization": f"Bearer {config.key}",
            "content-type": "application/json",
            "accept": "application/json",
        }
        try:
            status, raw = self._send(
                f"{config.base_url}/chat/completions",
                headers,
                json.dumps(payload).encode(),
                config.timeout_s,
            )
        except Exception as exc:  # noqa: BLE001 - network failures become one code
            log.warning("muse-chat transport failed: %s", type(exc).__name__)
            raise MuseChatError("PROVIDER_UNAVAILABLE") from None
        if status != 200:
            log.warning("muse-chat provider status %s", status)
            raise MuseChatError("PROVIDER_UNAVAILABLE")
        try:
            content = json.loads(raw)["choices"][0]["message"]["content"]
            parsed = json.loads(content)
            text = parsed["text"].strip()[:400]
        except (ValueError, KeyError, IndexError, TypeError, AttributeError):
            raise MuseChatError("PROVIDER_UNAVAILABLE") from None
        if not text:
            raise MuseChatError("PROVIDER_UNAVAILABLE")
        return {
            "text": self._names_for_ids(text),
            "source": "live",
            "itemIds": self._ids(parsed.get("itemIds"), self._item_ids)
            if kind in ("supplies", "barter")
            else [],
            "eventIds": self._ids(parsed.get("eventIds"), self._event_ids)
            if kind == "hangout"
            else [],
            "draft": self.clean_draft(self._draft_fields(parsed)) if kind == "create" else None,
        }
