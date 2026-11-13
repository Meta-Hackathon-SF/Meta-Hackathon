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


def seed_synthetic_players(store: PrivacyStore, path: Path = WEEK_SAMPLE) -> list[str]:
    """Inserts the fixture's synthetic players as consenting members. Idempotent."""
    sample = json.loads(path.read_text())
    community = sample["communityId"]
    created_at = "2026-11-09T00:00:00Z"
    ids: list[str] = []
    with store.tx() as conn:
        for p in sample["players"]:
            if p.get("isSynthetic") is not True:
                raise ValueError("fixture players must be labeled isSynthetic=true")
            conn.execute(
                "INSERT OR IGNORE INTO players (player_id, display_name, avatar_color, is_synthetic, created_at)"
                " VALUES (?, ?, ?, 1, ?)",
                (p["playerId"], p["displayName"], p["avatarColor"], created_at),
            )
            conn.execute(
                "INSERT OR IGNORE INTO memberships (community_id, player_id, joined_at) VALUES (?, ?, ?)",
                (community, p["playerId"], created_at),
            )
            conn.execute(
                "INSERT OR IGNORE INTO consents (player_id, community_id, version, match_answers,"
                " anonymous_chat, is_adult, created_at) VALUES (?, ?, 1, 1, 1, 1, ?)",
                (p["playerId"], community, created_at),
            )
            ids.append(p["playerId"])
    return ids


def grant_operator(store: PrivacyStore, player_id: str, community_id: str) -> None:
    """Local setup/test only. Takes effect on the player's next request."""
    with store.tx() as conn:
        cur = conn.execute(
            "UPDATE memberships SET is_operator = 1 WHERE player_id = ? AND community_id = ? AND left_at IS NULL",
            (player_id, community_id),
        )
        if cur.rowcount != 1:
            raise LookupError("no active membership")


__all__ = ["PrivacyService", "grant_operator", "seed_community", "seed_synthetic_players"]
