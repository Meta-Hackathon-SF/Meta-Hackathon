"""D010: optional activity signals for matching (proposed by Will; forced in by
Will's human ahead of the owners' ACKs, see docs/DECISIONS.md D010).

* Off by default. ``PUT /me/activity`` with ``useActivity: false`` deletes the
  stored row; ``DELETE /me/data`` deletes it too.
* Groups, Events and friends are stored as opaque ids (no names).
* ``eventIds`` not in the approved venue catalog are dropped, never stored
  (D013: only approved events may count as signals or event heat). The
  approved set comes from ``approved_event_ids``; the default reads
  ``server.planning.VenueCatalog.load().event_ids()`` and fails closed (keeps
  no event ids) when the catalog or that method is unavailable.
* Post/comment ``texts`` are reduced by code to labels from ``SAFE_TOPICS`` and
  then discarded: never stored, logged, sent to Muse or shown to anyone. The
  allowlist contains no sensitive categories (health, sexuality, religion,
  finances, family trauma, home location), so those can never become signals.
* Formation reads these only through the privacy snapshot, keyed by the
  per-lease random ref, and only for fully consenting players.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Iterable, Mapping
from typing import Annotated

from pydantic import Field, StrictBool, StrictStr

from .store import PrivacyStore
from .wire import Id, Wire, WireRequest

MAX_IDS = 50
MAX_TEXTS = 50
MAX_TEXT_CHARS = 2000

# label -> keywords (lowercase, whole word). Everyday, non-sensitive interests only.
SAFE_TOPICS: dict[str, tuple[str, ...]] = {
    "ai": ("ai", "llama", "llm", "machine learning", "model", "models"),
    "coding": ("code", "coding", "hackathon", "prototype", "programming", "cs"),
    "design": ("design", "designer", "figma", "ui", "ux"),
    "music": ("music", "song", "songs", "concert", "band", "playlist", "singing"),
    "gaming": ("game", "games", "gaming", "board game", "board games"),
    "vr": ("vr", "ar", "xr", "headset", "virtual reality"),
    "study": ("study", "studying", "library", "exam", "exams", "class"),
    "coffee": ("coffee", "cafe", "café", "espresso"),
    "food": ("cooking", "dinner", "lunch", "breakfast", "recipe", "dining hall"),
    "outdoors": ("hike", "hiking", "outdoors", "walk", "walking", "park", "trail"),
    "sports": ("volleyball", "basketball", "soccer", "gym", "running", "climbing"),
    "film": ("movie", "movies", "film", "films"),
    "art": ("art", "drawing", "painting", "photography", "photo"),
    "books": ("book", "books", "reading", "novel"),
}
_PATTERNS = {label: re.compile(r"\b(" + "|".join(re.escape(k) for k in kws) + r")\b")
             for label, kws in SAFE_TOPICS.items()}

ActivityId = Annotated[StrictStr, Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_.:-]+$")]
ActivityText = Annotated[StrictStr, Field(max_length=MAX_TEXT_CHARS)]


def derive_topics(texts: Iterable[str]) -> list[str]:
    """Allowlisted topic labels found in the player's own texts. Text is not kept."""
    found: set[str] = set()
    for text in texts:
        lowered = text.lower()
        for label, pattern in _PATTERNS.items():
            if pattern.search(lowered):
                found.add(label)
    return sorted(found)


class ActivityRequest(WireRequest):
    use_activity: StrictBool
    profile_id: ActivityId | None = None
    group_ids: list[ActivityId] = Field(default_factory=list, max_length=MAX_IDS)
    event_ids: list[ActivityId] = Field(default_factory=list, max_length=MAX_IDS)
    friend_ids: list[ActivityId] = Field(default_factory=list, max_length=MAX_IDS)
    texts: list[ActivityText] = Field(default_factory=list, max_length=MAX_TEXTS)


class ActivityResult(Wire):
    use_activity: StrictBool
    topics: list[StrictStr]


class ActivitySignals(Wire):
    """contracts/protocol.ts ActivitySignals (PRIVATE)."""

    profile_id: Id | None
    group_ids: list[Id]
    event_ids: list[Id]
    friend_ids: list[Id]
    topics: list[StrictStr]


def _ids(values: Iterable[str]) -> list[str]:
    return sorted(set(values))


ApprovedEventIds = Callable[[], Iterable[str]]


def catalog_event_ids() -> frozenset[str]:
    """Approved event ids from Adam's venue catalog (package-root import only).
    Fails closed: any load problem, or a catalog without ``event_ids()``,
    approves nothing."""
    try:
        from server.planning import VenueCatalog

        event_ids = getattr(VenueCatalog.load(), "event_ids", None)
        return frozenset(event_ids()) if callable(event_ids) else frozenset()
    except Exception:  # noqa: BLE001 - a missing/invalid catalog approves no events
        return frozenset()


class ActivityStore:
    def __init__(self, store: PrivacyStore, *, approved_event_ids: ApprovedEventIds = catalog_event_ids):
        self._store = store
        self._approved_event_ids = approved_event_ids

    def _approved(self, event_ids: Iterable[str]) -> list[str]:
        wanted = _ids(event_ids)
        if not wanted:
            return []
        approved = frozenset(self._approved_event_ids())
        return [e for e in wanted if e in approved]

    def put(self, player_id: str, community_id: str, req: ActivityRequest, now: str) -> ActivityResult:
        with self._store.tx() as conn:
            if not req.use_activity:
                conn.execute("DELETE FROM activity_signals WHERE player_id = ? AND community_id = ?",
                             (player_id, community_id))
                return ActivityResult(use_activity=False, topics=[])
            topics = derive_topics(req.texts)  # req.texts goes out of scope here; never persisted
            event_ids = self._approved(req.event_ids)  # unapproved ids are dropped, not stored
            conn.execute(
                "INSERT INTO activity_signals (player_id, community_id, profile_id, group_ids, event_ids,"
                " friend_ids, topics, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
                " ON CONFLICT (player_id, community_id) DO UPDATE SET profile_id = excluded.profile_id,"
                " group_ids = excluded.group_ids,"
                " event_ids = excluded.event_ids, friend_ids = excluded.friend_ids,"
                " topics = excluded.topics, updated_at = excluded.updated_at",
                (player_id, community_id, req.profile_id, json.dumps(_ids(req.group_ids)), json.dumps(event_ids),
                 json.dumps(_ids(req.friend_ids)), json.dumps(topics), now),
            )
            return ActivityResult(use_activity=True, topics=topics)

    def is_on(self, player_id: str, community_id: str) -> bool:
        with self._store.tx() as conn:
            return conn.execute("SELECT 1 FROM activity_signals WHERE player_id = ? AND community_id = ?",
                                (player_id, community_id)).fetchone() is not None

    def delete_player(self, player_id: str) -> int:
        with self._store.tx() as conn:
            return conn.execute("DELETE FROM activity_signals WHERE player_id = ?", (player_id,)).rowcount

    def for_players(self, community_id: str, player_ids: Iterable[str]) -> Mapping[str, ActivitySignals]:
        wanted = sorted(set(player_ids))
        if not wanted:
            return {}
        marks = ",".join("?" for _ in wanted)
        with self._store.tx() as conn:
            rows = conn.execute(
                f"SELECT * FROM activity_signals WHERE community_id = ? AND player_id IN ({marks})",
                (community_id, *wanted),
            ).fetchall()
        return {r["player_id"]: ActivitySignals(profile_id=r["profile_id"],
                                                 group_ids=json.loads(r["group_ids"]),
                                                 event_ids=json.loads(r["event_ids"]),
                                                 friend_ids=json.loads(r["friend_ids"]),
                                                 topics=json.loads(r["topics"])) for r in rows}
