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
_TIME = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
_CONTACT = re.compile(r"(\d[\s.()-]?){7,}|@|https?:|www\.|\.(com|net|org|edu)\b", re.I)

INSTRUCTIONS = " ".join(
    [
        "You help a small group chat plan things. Reply to the latest note only, in one or two short sentences, no emoji. Earlier notes are context. Do not quote anyone.",
        "You never bring, buy, book, hold, reserve or register anything yourself. Never say I'll, I will, or let me. Never say anything is booked, held or confirmed.",
        "Use only the catalog facts. Point at catalog entries by id; the app shows them as cards, so do not list details the card already shows.",
        "task=hangout: pick 1 or 2 eventIds that best fit the chat. Mention the event title. Do not mention items.",
        "task=supplies: pick 1 or 2 itemIds that best fit the chat. Say they are demo listings, not purchases.",
        "task=barter: tell the group to ask Campus Cafe, and say nothing is booked until the cafe agrees. You may pick the coffee set itemId.",
        "task=create: propose one new event as draft {title (3-60 chars), placeId from venues, day (a weekday name), time (24h HH:MM between 08:00 and 22:00), description (under 160 chars)} from what the group wants. Say it is a draft they can create. Do not invent venues.",
    ]
)

_SCHEMA = {
    "type": "object",
    "properties": {
        "text": {"type": "string"},
        "itemIds": {"type": "array", "items": {"type": "string"}},
        "eventIds": {"type": "array", "items": {"type": "string"}},
        "draft": {
            "type": "object",
            "properties": {
                k: {"type": "string"} for k in ("title", "placeId", "day", "time", "description")
            },
        },
    },
    "required": ["text"],
}


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

    def clean_draft(self, value: Any) -> dict[str, str] | None:
        if not isinstance(value, dict):
            return None

        def s(key: str, limit: int) -> str:
            v = value.get(key)
            return v.strip()[:limit] if isinstance(v, str) else ""

        draft = {
            "title": s("title", 60),
            "placeId": s("placeId", 40),
            "day": s("day", 12),
            "time": s("time", 5),
            "description": s("description", 160),
        }
        hour = int(draft["time"][:2]) if _TIME.match(draft["time"]) else -1
        if len(draft["title"]) < 3 or draft["placeId"] not in self._venue_ids:
            return None
        if draft["day"].lower() not in WEEKDAYS or not 8 <= hour <= 22:
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
                "json_schema": {"name": "group_chat_line", "strict": False, "schema": _SCHEMA},
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
            "text": text,
            "source": "live",
            "itemIds": self._ids(parsed.get("itemIds"), self._item_ids)
            if kind in ("supplies", "barter")
            else [],
            "eventIds": self._ids(parsed.get("eventIds"), self._event_ids)
            if kind == "hangout"
            else [],
            "draft": self.clean_draft(parsed.get("draft")) if kind == "create" else None,
        }
