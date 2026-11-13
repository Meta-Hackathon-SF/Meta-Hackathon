"""SYNTHETIC demo/test data loader. Not real people; every player is isSynthetic.

Reads players from contracts/fixtures/week-sample.json into the privacy store
with full consent so formation has a labeled synthetic population. Synthetic
players can never hold a session (``require_session`` filters them), so they
can be grouped with but never impersonated.

Also ``grant_operator``: the operator role is never granted through an HTTP
route. Call it from a local setup script or a test only.
"""

from __future__ import annotations

import json
from pathlib import Path

from .service import PrivacyService
from .store import PrivacyStore

WEEK_SAMPLE = Path(__file__).resolve().parents[2] / "contracts" / "fixtures" / "week-sample.json"


def seed_community(store: PrivacyStore, community_id: str, name: str, time_zone: str = "America/Los_Angeles") -> None:
    with store.tx() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO communities (community_id, name, time_zone, is_demo) VALUES (?, ?, ?, 1)",
            (community_id, name, time_zone),
        )


def seed_players(store: PrivacyStore, community_id: str, players: list[dict]) -> list[str]:
    """Will's proposed ``SyntheticSeeder``: ensure labeled synthetic players are
    consenting members of ``community_id``. Refuses any player not labeled
    ``isSynthetic: true``. Idempotent."""
    created_at = "2026-11-09T00:00:00Z"
    ids: list[str] = []
    with store.tx() as conn:
        if conn.execute("SELECT 1 FROM communities WHERE community_id = ?", (community_id,)).fetchone() is None:
            raise LookupError("unknown community")
        for p in players:
            if p.get("isSynthetic") is not True:
                raise ValueError("fixture players must be labeled isSynthetic=true")
            conn.execute(
                "INSERT OR IGNORE INTO players (player_id, display_name, avatar_color, is_synthetic, created_at)"
                " VALUES (?, ?, ?, 1, ?)",
                (p["playerId"], p["displayName"], p["avatarColor"], created_at),
            )
            if conn.execute("SELECT is_synthetic FROM players WHERE player_id = ?", (p["playerId"],)).fetchone()[0] != 1:
                raise ValueError("a real player id cannot be reused as a synthetic fixture")
            conn.execute(
                "INSERT OR IGNORE INTO memberships (community_id, player_id, joined_at) VALUES (?, ?, ?)",
                (community_id, p["playerId"], created_at),
            )
            conn.execute(
                "INSERT OR IGNORE INTO consents (player_id, community_id, version, match_answers,"
                " anonymous_chat, is_adult, created_at) VALUES (?, ?, 1, 1, 1, 1, ?)",
                (p["playerId"], community_id, created_at),
            )
            ids.append(p["playerId"])
    return ids


def seed_synthetic_players(store: PrivacyStore, path: Path = WEEK_SAMPLE) -> list[str]:
    """The 8 synthetic players of contracts/fixtures/week-sample.json."""
    sample = json.loads(path.read_text())
    return seed_players(store, sample["communityId"], sample["players"])


def grant_operator(store: PrivacyStore, player_id: str, community_id: str) -> None:
    """Local setup/test only. Takes effect on the player's next request."""
    with store.tx() as conn:
        cur = conn.execute(
            "UPDATE memberships SET is_operator = 1 WHERE player_id = ? AND community_id = ? AND left_at IS NULL",
            (player_id, community_id),
        )
        if cur.rowcount != 1:
            raise LookupError("no active membership")


__all__ = ["PrivacyService", "grant_operator", "seed_community", "seed_players", "seed_synthetic_players"]
