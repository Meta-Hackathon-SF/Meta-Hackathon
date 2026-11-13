"""Demo population: about 100 SYNTHETIC young-adult players with answers, posts,
comments, likes, Groups and event RSVPs.

Every player is labeled synthetic (``is_synthetic=1`` and "(synthetic)" in the
name) and is never counted as a real participant. All text was written for the
demo (``data/demo_population.json``); none of it comes from real people.

What makes it read like a real community rather than a fixture:
- 20 loose "meaning clusters" of 5 people. A cluster is what someone's answers
  tend to mean, not shared wording, and one person per cluster leans toward a
  neighbouring cluster. Nothing in the data tells matching which cluster a
  player is in: ``theme`` is used only for the feed and for tests.
- Each person answers all 12 bank questions in their own voice, but does not
  answer every day. ``engagement`` decides which days they show up, which they
  catch up later, and who drifts off after Monday.
- About one in five never posts. Likes follow shared Groups and interests, so
  a few posts get most of the reactions.

    from server.privacy.demo_population import players, topup_rows, guesses

    # feed copy for the web shell
    python -m server.privacy.demo_population --export-feed web/src/data/population.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Iterable, Mapping
from functools import lru_cache
from pathlib import Path

from .answers import AnswerStore
from .fixtures import seed_players
from .store import PrivacyStore

DATA = Path(__file__).with_name("data") / "demo_population.json"
COLORS = ["#4c6ef5", "#12b886", "#f59f00", "#e64980", "#7950f2", "#15aabf", "#fa5252", "#40c057"]
GROUP_NAMES = {
    "g-hackathon-builders": "Hackathon Builders",
    "g-xr-student-collective": "XR Student Collective",
    "g-campus-cooks": "Campus Cooks",
    "g-campus-outdoors": "Campus Outdoors",
    "g-campus-music": "Campus Music",
    "g-intramurals": "Intramurals",
    "g-film-club": "Film Club",
    "g-board-game-night": "Board Game Night",
    "g-book-nook": "Book Nook",
    "g-campus-gamers": "Campus Gamers",
    "g-international-students": "International Students",
    "g-transfer-commuter": "Transfers and Commuters",
    "g-art-and-thrift": "Art and Thrift",
    "g-dance-theater": "Dance and Theater",
    "g-career-prep": "Career Prep",
    "g-volunteer-garden": "Volunteers and Garden",
}
EVENT_IDS = ("ev-open-mic", "ev-volleyball", "ev-board-games", "ev-film-club")  # contracts/fixtures/venues.json
ENGAGEMENTS = ("daily", "regular", "casual", "drifter")
DAYS = (1, 2, 3, 4, 5)


def _hash(*parts: object) -> int:
    """Stable across processes (unlike ``hash``), so every run seeds the same week."""
    return int.from_bytes(hashlib.sha256("|".join(map(str, parts)).encode()).digest()[:8], "big")


def _slug(name: str) -> str:
    return "".join(c if c.isalnum() else "-" for c in name.lower()).strip("-")


@lru_cache(maxsize=1)
def personas() -> tuple[dict, ...]:
    """The authored personas, validated. Raises on any malformed entry."""
    raw = json.loads(DATA.read_text(encoding="utf-8"))["personas"]
    names = set()
    for p in raw:
        if p["name"] in names:
            raise ValueError("duplicate persona name")
        names.add(p["name"])
        if p["engagement"] not in ENGAGEMENTS:
            raise ValueError("unknown engagement")
        if not set(p["groups"]) <= set(GROUP_NAMES) or not set(p["events"]) <= set(EVENT_IDS):
            raise ValueError("unknown group or event id")
    return tuple(raw)


def player_id(name: str) -> str:
    return f"p-demo-{_slug(name)}"


def answer_days(persona: Mapping) -> dict[int, bool]:
    """``{day: isCatchUp}`` for the days this person answers. Not everyone
    shows up every day: daily people answer all five (sometimes one late),
    regulars miss one, casual players answer two or three, drifters stop after
    Monday or Tuesday."""
    pid, level = player_id(persona["name"]), persona["engagement"]
    h = _hash(pid, "days")
    if level == "daily":
        late = {h % 5 + 1} if h % 4 == 0 else set()
        return {d: d in late for d in DAYS}
    if level == "regular":
        missed = h % 5 + 1
        days = [d for d in DAYS if d != missed]
        late = {days[(h >> 8) % 4]} if h % 3 == 0 else set()
        return {d: d in late for d in days}
    if level == "casual":
        count = 2 + (h >> 4) % 2
        days = sorted({(h + i * 2) % 5 + 1 for i in range(count)})
        return {d: i == 0 and h % 2 == 0 for i, d in enumerate(days)}
    return {d: False for d in DAYS[: 1 + h % 2]}  # drifter


def players() -> list[dict]:
    out = []
    for i, p in enumerate(personas()):
        out.append({
            "playerId": player_id(p["name"]),
            "displayName": f"{p['name']} (synthetic)",
            "avatarColor": COLORS[_hash(p["name"], "color") % len(COLORS)],
            "isSynthetic": True,
            "theme": p["cluster"],
            "engagement": p["engagement"],
            "groupIds": list(p["groups"]),
            "eventIds": list(p["events"]),
            "texts": [post["text"] for post in p["posts"]] + [c["text"] for c in p["comments"]],
            "order": i,
        })
    return out


def topup_rows(question_by_day: Mapping[int, str]) -> list[dict]:
    """Answer rows ``{playerId, day, text, isCatchUp, ownTiming}`` for the
    cycle's questions, in the shape ``CycleService.synthetic_topup`` saves."""
    rows = []
    for p in personas():
        days = answer_days(p)
        for day, qid in sorted(question_by_day.items()):
            text = p["answers"].get(qid)
            if text and day in days:
                rows.append({"playerId": player_id(p["name"]), "day": day, "text": text,
                             "isCatchUp": days[day], "ownTiming": True})
    return rows


def guesses() -> list[dict]:
    """Each person's prevalence guess ("how many people feel like I do?")."""
    return [{"playerId": player_id(p["name"]), "percent": int(p["guess"])} for p in personas()]


# ------------------------------------------------------------------ the feed
def _likes(author: Mapping, others: Iterable[Mapping], post_key: str) -> int:
    """How many of the cast liked a post. People like what their own circle
    posts: same cluster most, a shared Group sometimes, strangers rarely. A
    per-author factor makes a few people reliably popular and a few ignored."""
    reach = 0.55 + (_hash(author["name"], "reach") % 100) / 80  # 0.55 .. 1.8
    # Most posts land quietly and a few take off, like any real feed.
    reach *= (0.08, 0.15, 0.3, 0.45, 0.6, 0.8, 1.0, 1.3, 1.9, 2.8)[_hash(post_key, "luck") % 10]
    count = 0
    for other in others:
        if other["name"] == author["name"]:
            continue
        chance = 0.03
        if set(other["groups"]) & set(author["groups"]):
            chance = 0.3
        if other["cluster"] == author["cluster"]:
            chance = 0.7
        if other["engagement"] == "drifter":
            chance *= 0.4
        if (_hash(other["name"], post_key) % 1000) / 1000 < min(0.95, chance * reach):
            count += 1
    return count


def feed() -> list[dict]:
    """Feed posts for the web shell, newest first, with the comments other
    cast members wrote on them and a like count from ``_likes``."""
    cast = personas()
    by_name = {p["name"]: p for p in cast}
    color = {p["name"]: COLORS[_hash(p["name"], "color") % len(COLORS)] for p in cast}
    posts = []
    index: dict[str, list[dict]] = {}
    for p in cast:
        for i, post in enumerate(p["posts"]):
            pid = player_id(p["name"])
            entry = {
                "id": f"post-{pid}-{i}",
                "authorName": f"{p['name']} (synthetic)",
                "authorColor": color[p["name"]],
                "theme": p["cluster"],
                "groupName": GROUP_NAMES[p["groups"][_hash(pid, i, "group") % len(p["groups"])]],
                "text": post["text"],
                "comments": [],
                "reactionCount": _likes(p, cast, f"{pid}-{i}"),
                "minutesAgo": int(post["minutesAgo"]),
            }
            posts.append(entry)
            index.setdefault(p["name"], []).append(entry)
    for p in cast:
        for k, comment in enumerate(p["comments"]):
            targets = index.get(comment["on"])
            if not targets or comment["on"] not in by_name:
                continue
            # ``post`` says which of the author's posts the comment answers.
            chosen = comment.get("post")
            target = targets[chosen if isinstance(chosen, int) and 0 <= chosen < len(targets) else 0]
            target["comments"].append({
                "id": f"c-{player_id(p['name'])}-{k}",
                "authorName": f"{p['name']} (synthetic)",
                "authorColor": color[p["name"]],
                "text": comment["text"],
            })
    posts.sort(key=lambda x: x["minutesAgo"])
    return posts


# ------------------------------------------------------------------ seeding
def seed_activity(store: PrivacyStore, community_id: str, now: str = "2026-11-09T18:00:00Z") -> int:
    """Store each synthetic player's Groups, approved event RSVPs and post
    topics as activity signals. Topics come from the offline keyword list (no
    model call); post text itself is never stored. Idempotent."""
    from .activity import ActivityRequest, ActivityStore, derive_topics

    activity = ActivityStore(store, approved_event_ids=lambda: EVENT_IDS)
    for p in players():
        request = ActivityRequest.model_validate({
            "useActivity": True, "groupIds": p["groupIds"], "eventIds": p["eventIds"], "texts": p["texts"],
        })
        activity.put(p["playerId"], community_id, request, now, topics=derive_topics(p["texts"]))
    return len(players())


def seed_demo_population(
    store: PrivacyStore,
    answers: AnswerStore,
    community_id: str,
    cycle_id: str,
    question_by_day: Mapping[int, str],
    days: Iterable[int] = DAYS,
    *,
    with_activity: bool = False,
    now: str = "2026-11-09T18:00:00Z",
) -> list[str]:
    """Seed the synthetic cast as consenting members with their answers for the
    given days (using the cycle's questionId for each day). Idempotent."""
    ids = seed_players(store, community_id, players())
    wanted = set(days)
    for row in topup_rows(question_by_day):
        if row["day"] not in wanted:
            continue
        answers.save({
            "answerId": f"a-{row['playerId']}-{cycle_id}-{row['day']}", "cycleId": cycle_id, "day": row["day"],
            "questionId": question_by_day[row["day"]], "playerId": row["playerId"], "text": row["text"],
            "source": "text", "isCatchUp": row["isCatchUp"], "weight": 0.5 if row["isCatchUp"] else 1.0,
            "followUpUsed": False, "createdAt": now, "editedAt": None, "deletedAt": None,
        }, "none")
    if with_activity:
        seed_activity(store, community_id, now)
    return ids


def _main() -> None:
    ap = argparse.ArgumentParser(description="Export the synthetic demo feed for the web shell.")
    ap.add_argument("--export-feed", type=Path, required=True)
    args = ap.parse_args()
    posts = feed()
    args.export_feed.write_text(
        json.dumps({"label": "Synthetic demo population. Not real people.", "posts": posts}, indent=1, ensure_ascii=False)
        + "\n"
    )
    print(f"wrote {len(posts)} posts to {args.export_feed}")


if __name__ == "__main__":
    _main()
