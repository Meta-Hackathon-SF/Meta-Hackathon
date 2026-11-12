"""Direct row-level-security probes using the non-owner gq_api login role.

These bypass the Python service entirely: they show the database itself denies
cross-participant access even if an API route forgot a filter.
"""

from __future__ import annotations

import psycopg
import pytest
from psycopg.types.json import Jsonb

from privacy_helpers import COMMUNITY, eligible_member, window
from server.privacy.db import Database


def as_actor(conn, participant_id):
    conn.execute("SELECT set_config('gq.participant_id', %s, true)", (participant_id or "",))


def test_api_role_is_not_privileged(api_conn):
    row = api_conn.execute(
        "SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user"
    ).fetchone()
    assert row == (False, False)


def test_database_refuses_superuser(pg):
    with pytest.raises(RuntimeError, match="superuser"):
        Database(pg["admin_dsn"])


def test_no_actor_sees_nothing(service, api_conn):
    eligible_member(service, "A")
    as_actor(api_conn, None)
    for table in ("participants", "memberships", "consents", "private_intents", "communities"):
        assert api_conn.execute(f"SELECT count(*) FROM privacy.{table}").fetchone()[0] == 0, table


def test_sessions_table_not_readable(service, api_conn):
    _, actor = eligible_member(service, "A")
    as_actor(api_conn, actor.participant_id)
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        api_conn.execute("SELECT * FROM privacy.sessions")


def test_cross_user_intent_read_update_delete_denied(service, api_conn):
    _, a = eligible_member(service, "A")
    _, b = eligible_member(service, "B")
    as_actor(api_conn, a.participant_id)
    rows = api_conn.execute("SELECT participant_id FROM privacy.private_intents").fetchall()
    assert rows == [(a.participant_id,)]
    assert api_conn.execute(
        "UPDATE privacy.private_intents SET max_budget_minor = 0 WHERE participant_id = %s",
        (b.participant_id,),
    ).rowcount == 0
    assert api_conn.execute(
        "DELETE FROM privacy.private_intents WHERE participant_id = %s", (b.participant_id,)
    ).rowcount == 0
    with pytest.raises(psycopg.errors.InsufficientPrivilege):  # RLS WITH CHECK
        api_conn.execute(
            "UPDATE privacy.private_intents SET participant_id = %s WHERE participant_id = %s",
            (b.participant_id, a.participant_id),
        )


def test_cannot_write_rows_for_another_participant(service, api_conn, admin):
    _, a = eligible_member(service, "A")
    _, b = eligible_member(service, "B")
    as_actor(api_conn, a.participant_id)
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        api_conn.execute(
            "INSERT INTO privacy.consents (participant_id, community_id, version, matching,"
            " model_processing, public_interests) VALUES (%s, %s, 99, true, true, true)",
            (b.participant_id, COMMUNITY),
        )
    api_conn.rollback()
    as_actor(api_conn, a.participant_id)
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        api_conn.execute(
            "INSERT INTO privacy.private_intents (participant_id, community_id, intent_version, goal,"
            " interests, area_id, time_zone, availability, max_budget_minor, currency,"
            " max_duration_minutes, consent_version, confirmed_at) VALUES"
            " (%s, %s, 1, 'x', ARRAY['x'], 'demo-campus-central', 'UTC', %s, 0, 'USD', 60, 1, now())",
            (b.participant_id, COMMUNITY, Jsonb([window()])),
        )
    api_conn.rollback()
    budget = admin.execute(
        "SELECT max_budget_minor FROM privacy.private_intents WHERE participant_id = %s",
        (b.participant_id,),
    ).fetchone()[0]
    assert budget == 1200


def test_cannot_create_privileged_rows_directly(service, api_conn):
    _, a = eligible_member(service, "A")
    as_actor(api_conn, a.participant_id)
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        api_conn.execute("INSERT INTO privacy.participants (is_synthetic) VALUES (false)")
    api_conn.rollback()
    as_actor(api_conn, a.participant_id)
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        api_conn.execute("INSERT INTO privacy.communities VALUES ('x', 'x', ARRAY['x'], 'USD', false)")


def test_snapshot_function_requires_eligible_actor(service, api_conn):
    eligible_member(service, "A")
    as_actor(api_conn, None)
    with pytest.raises(psycopg.Error) as exc:
        api_conn.execute("SELECT * FROM privacy.authorized_candidates(%s)", (COMMUNITY,))
    assert exc.value.sqlstate == "GQ401"


def test_internal_eligibility_function_not_callable(api_conn):
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        api_conn.execute("SELECT privacy.is_eligible('demo-campus', 'p_x')")
