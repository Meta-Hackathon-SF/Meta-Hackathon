"""SYNTHETIC demo/test data. Not real people; every profile has isSynthetic=true.

Seeding needs the migration-owner connection (it bypasses RLS on purpose to
create fixture rows). Never call this from a request path or with a live
participant's identity. Synthetic participants cannot hold sessions
(privacy.resolve_session filters them out), so they can be matched with but
never impersonated.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import psycopg
from psycopg.types.json import Jsonb

DEMO_COMMUNITY = {
    "community_id": "demo-campus",
    "name": "Demo Campus (synthetic)",
    "area_ids": ["demo-campus-central"],
    "currency": "USD",
}

# Interests and goals are invented for the demo; display names say "(demo)".
SYNTHETIC_PROFILES = [
    ("Sam (demo)", "meet people who like board games", ["board games", "coffee"], 1500, 120),
    ("Riley (demo)", "find a weekly creative group", ["sketching", "board games"], 0, 90),
    ("Jo (demo)", "try something new after class", ["coffee", "trivia"], 1000, 120),
    ("Ari (demo)", "low-key social plans", ["trivia", "board games"], 500, 60),
]


def seed_community(admin: psycopg.Connection, community: dict = DEMO_COMMUNITY, *, is_demo: bool = True) -> None:
    admin.execute(
        """
        INSERT INTO privacy.communities (community_id, name, area_ids, currency, is_demo)
        VALUES (%s, %s, %s, %s, %s) ON CONFLICT (community_id) DO NOTHING
        """,
        (community["community_id"], community["name"], community["area_ids"],
         community["currency"], is_demo),
    )


def seed_synthetic_profiles(
    admin: psycopg.Connection,
    community: dict = DEMO_COMMUNITY,
    *,
    start: datetime | None = None,
) -> list[str]:
    """Creates consenting synthetic members with confirmed intents. Returns ids."""
    base = (start or datetime.now(timezone.utc)).replace(minute=0, second=0, microsecond=0)
    ids: list[str] = []
    for index, (name, goal, interests, budget, duration) in enumerate(SYNTHETIC_PROFILES):
        pid = admin.execute(
            "INSERT INTO privacy.participants (is_synthetic) VALUES (true) RETURNING participant_id"
        ).fetchone()[0]
        admin.execute(
            "INSERT INTO privacy.memberships (community_id, participant_id, display_name)"
            " VALUES (%s, %s, %s)",
            (community["community_id"], pid, name),
        )
        admin.execute(
            "INSERT INTO privacy.consents (participant_id, community_id, version, matching,"
            " model_processing, public_interests) VALUES (%s, %s, 1, true, true, true)",
            (pid, community["community_id"]),
        )
        day = base + timedelta(days=1)
        window = {
            "start": _z(day + timedelta(hours=index % 2)),
            "end": _z(day + timedelta(hours=4 + index % 2)),
        }
        admin.execute(
            """
            INSERT INTO privacy.private_intents
              (participant_id, community_id, intent_version, goal, interests, area_id, time_zone,
               availability, max_budget_minor, currency, max_duration_minutes, consent_version,
               confirmed_at)
            VALUES (%s, %s, 1, %s, %s, %s, 'America/Los_Angeles', %s, %s, %s, %s, 1, now())
            """,
            (pid, community["community_id"], goal, interests, community["area_ids"][0],
             Jsonb([window]), budget, community["currency"], duration),
        )
        ids.append(pid)
    return ids


def _z(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
