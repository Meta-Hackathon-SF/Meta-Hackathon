"""Privacy test harness.

DB tests need a local Postgres (db/privacy/dev-db.sh up). Each session creates
a fresh database + a random non-owner login role in gq_api, applies the real
migration, and drops both afterwards. Policies are therefore exercised with the
same non-bypass credentials the API uses.

Set GQ_TEST_ADMIN_DSN to point elsewhere (default: the dev-db.sh container).
"""

from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import psycopg  # noqa: E402
from psycopg import sql  # noqa: E402

from server.privacy.db import Database  # noqa: E402
from server.privacy.fixtures import DEMO_COMMUNITY, seed_community  # noqa: E402
from server.privacy.service import PrivacyService  # noqa: E402

ADMIN_DSN = os.environ.get("GQ_TEST_ADMIN_DSN", "postgresql://postgres@127.0.0.1:54329/postgres")
MIGRATION = ROOT / "db" / "privacy" / "001_privacy_foundation.sql"
DEMO_SEED = ROOT / "db" / "privacy" / "002_demo_communities.sql"
OTHER_COMMUNITY = {
    "community_id": "other-campus",
    "name": "Other Campus (synthetic)",
    "area_ids": ["other-central"],
    "currency": "USD",
}


def _dsn_for(dsn: str, *, dbname: str, user: str | None = None) -> str:
    info = psycopg.conninfo.conninfo_to_dict(dsn)
    info["dbname"] = dbname
    if user:
        info["user"] = user
    return psycopg.conninfo.make_conninfo(**info)


@pytest.fixture(scope="session")
def pg():
    try:
        root = psycopg.connect(ADMIN_DSN, autocommit=True, connect_timeout=3)
    except psycopg.OperationalError as exc:
        pytest.skip(f"Postgres not reachable ({exc.__class__.__name__}); run db/privacy/dev-db.sh up")
    suffix = uuid.uuid4().hex[:10]
    dbname, login = f"gq_privacy_test_{suffix}", f"gq_api_test_{suffix}"
    root.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(dbname)))
    admin_dsn = _dsn_for(ADMIN_DSN, dbname=dbname)
    with psycopg.connect(admin_dsn, autocommit=True) as admin:
        admin.execute(MIGRATION.read_text())
        admin.execute(sql.SQL("CREATE ROLE {} LOGIN IN ROLE gq_api").format(sql.Identifier(login)))
    try:
        yield {"admin_dsn": admin_dsn, "api_dsn": _dsn_for(ADMIN_DSN, dbname=dbname, user=login)}
    finally:
        root.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(dbname)))
        root.execute(sql.SQL("DROP ROLE IF EXISTS {}").format(sql.Identifier(login)))
        root.close()


@pytest.fixture
def admin(pg):
    """Migration-owner connection for fixture setup and assertions ONLY."""
    with psycopg.connect(pg["admin_dsn"], autocommit=True) as conn:
        conn.execute(
            "TRUNCATE privacy.private_intents, privacy.consents, privacy.memberships,"
            " privacy.sessions, privacy.participants, privacy.communities CASCADE"
        )
        conn.execute(DEMO_SEED.read_text())
        seed_community(conn, DEMO_COMMUNITY)
        seed_community(conn, OTHER_COMMUNITY)
        yield conn


@pytest.fixture(scope="session")
def database(pg):
    db = Database(pg["api_dsn"], max_size=8)
    yield db
    db.close()


@pytest.fixture
def service(database, admin):
    return PrivacyService(database)


@pytest.fixture
def api_conn(pg, admin):
    """Raw non-owner gq_api connection for direct policy probes."""
    with psycopg.connect(pg["api_dsn"]) as conn:
        yield conn
