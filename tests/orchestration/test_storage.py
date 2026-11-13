"""Private storage tests. All records and chat content are synthetic.

The actual PostgreSQL tests require an explicitly supplied disposable admin DSN.
They never contact a model or reuse participant databases.
"""

import asyncio
import json
import os
import re
from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql
from psycopg.conninfo import make_conninfo

from server.app.errors import ServiceError
from server.orchestration.storage import (
    PostgresWorkflowRepository,
    StorageFormatError,
    WorkflowState,
    dump_state,
    load_state,
)
from tests.chat.adapters import Driver
from tests.orchestration.storage_adapter import TestWorkflowRepository


@pytest.fixture
def rich_state():
    async def scenario():
        driver = Driver()
        a, b, c = driver.players
        message = await driver.post(a, "Synthetic hello for storage")
        await driver.report(b, message)
        await driver.report(c, message)
        await driver.reveal(a, b)
        await driver.reveal(b, a)
        await driver.reveal(c, a)
        driver.block(c, b)
        return WorkflowState(
            chat=driver.state,
            records={
                "cycle-demo-w1": {
                    "status": "forming",
                    "answerId": "synthetic-answer-id",
                    "promptVersion": "constellation_formation.v1",
                    "revision": "opaque-synthetic-revision",
                    "question": {"text": "What small thing improved your day?"},
                    "sharedMeaning": "Synthetic guarded meaning",
                    "evidence": [{"source": "replay", "latencyMs": 12}],
                    "themes": [{"label": "Synthetic guarded theme"}],
                }
            },
        )

    return asyncio.run(scenario())


def test_full_chat_roundtrip_preserves_policy_state_and_metadata(rich_state):
    encoded = dump_state(rich_state)
    restored = load_state(json.loads(json.dumps(encoded)))
    assert dump_state(restored) == encoded
    room = next(iter(restored.chat.rooms.values()))
    assert room.requests and room.reveals and room.blocked and room.attempts
    assert room.messages and room.message_seqs and len(room.reports) == 2
    assert restored.chat.idempotency and restored.chat.deliveries
    assert all(player.isSynthetic for reveal in room.reveals.values() for player in reveal.players)
    assert restored.records["cycle-demo-w1"]["answerId"] == "synthetic-answer-id"
    assert repr(restored) == "<WorkflowState private>"


def test_jsonb_key_reordering_does_not_reorder_chat_messages(rich_state):
    encoded = dump_state(rich_state)
    restored = load_state(json.loads(json.dumps(encoded, sort_keys=True)))
    room = next(iter(restored.chat.rooms.values()))
    assert list(room.messages) == sorted(room.messages, key=room.message_seqs.__getitem__)


@pytest.mark.parametrize(
    "key",
    ["answers", "againstAnswers", "raw_prompt", "prompts", "payload", "sessionToken", "apiKey"],
)
def test_raw_privacy_provider_and_session_material_is_not_durable_metadata(key):
    state = WorkflowState(records={"synthetic-job": {"nested": [{key: "SYNTHETIC PRIVATE VALUE"}]}})
    with pytest.raises(StorageFormatError) as failure:
        dump_state(state)
    assert str(failure.value) == "PROVIDER_UNAVAILABLE"
    assert "SYNTHETIC PRIVATE VALUE" not in str(failure.value)


@pytest.mark.parametrize("value", [float("inf"), float("nan"), object()])
def test_non_json_metadata_fails_closed(value):
    with pytest.raises(StorageFormatError):
        dump_state(WorkflowState(records={"synthetic-job": {"value": value}}))


@pytest.mark.parametrize("change", [True, 2, "1"])
def test_unknown_or_coerced_document_versions_are_rejected(change):
    document = dump_state(WorkflowState())
    document["schemaVersion"] = change
    with pytest.raises(StorageFormatError):
        load_state(document)


@pytest.mark.parametrize(
    "mutation",
    [
        "private_message_field",
        "message_room",
        "duplicate_member_handle",
        "missing_message_seq",
        "reveal_audience",
        "duplicate_event_seq",
        "duplicate_command",
        "foreign_pending_player",
    ],
)
def test_corrupt_persisted_references_are_rejected(rich_state, mutation):
    document = deepcopy(dump_state(rich_state))
    room_id = next(iter(document["rooms"]))
    room = document["rooms"][room_id]
    if mutation == "private_message_field":
        room["messages"][0]["playerId"] = "SYNTHETIC PRIVATE ACTOR"
    elif mutation == "message_room":
        room["messages"][0]["roomId"] = "foreign-room"
    elif mutation == "duplicate_member_handle":
        players = list(room["members"])
        room["members"][players[1]] = room["members"][players[0]]
    elif mutation == "missing_message_seq":
        room["messageSeqs"] = {}
    elif mutation == "reveal_audience":
        event = next(d for d in document["deliveries"] if d["event"]["type"] == "reveal.mutual")
        event["recipients"] = list(room["members"])
    elif mutation == "duplicate_event_seq":
        document["deliveries"][-1]["event"]["seq"] = document["deliveries"][0]["event"]["seq"]
    elif mutation == "duplicate_command":
        document["idempotency"].append(deepcopy(document["idempotency"][0]))
    else:
        room["requests"].append([next(iter(room["members"])), "foreign-player"])
    with pytest.raises(StorageFormatError) as failure:
        load_state(document)
    assert str(failure.value) == "PROVIDER_UNAVAILABLE"


def test_fixture_repository_commits_only_on_success_and_detaches_escaped_references(rich_state):
    repository = TestWorkflowRepository(rich_state)
    with pytest.raises(RuntimeError), repository.transaction() as state:
        state.records.clear()
        state.chat.rooms.clear()
        raise RuntimeError("Synthetic rollback")
    with repository.transaction() as state:
        assert state.records and state.chat.rooms
        state.records["new-synthetic-job"] = {"status": "pending"}
        escaped = state
    escaped.records.clear()
    with repository.transaction() as state:
        assert state.records["new-synthetic-job"] == {"status": "pending"}
    repository.close()
    assert repository.ready() is False
    with pytest.raises(ServiceError), repository.transaction():
        pass


def test_fixture_repository_serializes_simultaneous_commits():
    repository = TestWorkflowRepository(WorkflowState(records={"counter": {"value": 0}}))

    def increment(_):
        with repository.transaction() as state:
            state.records["counter"]["value"] += 1

    with ThreadPoolExecutor(max_workers=4) as executor:
        list(executor.map(increment, range(20)))
    with repository.transaction() as state:
        assert state.records["counter"]["value"] == 20


def test_fixture_repository_rejects_nested_transactions_without_losing_outer_commit():
    repository = TestWorkflowRepository()
    with repository.transaction() as state:
        state.records["outer"] = {"status": "pending"}
        with pytest.raises(ServiceError), repository.transaction():
            pass
    with repository.transaction() as state:
        assert state.records["outer"] == {"status": "pending"}


def test_postgres_adapter_rejects_nesting_before_opening_another_connection(monkeypatch):
    # TEST ONLY SQL transport; actual PostgreSQL durability is tested separately.
    opened = []
    connection = SimpleNamespace(
        transaction=lambda: nullcontext(),
        execute=lambda *args: SimpleNamespace(fetchone=lambda: (dump_state(WorkflowState()),)),
    )

    def connect(*args, **kwargs):
        opened.append(True)
        return nullcontext(connection)

    monkeypatch.setattr(psycopg, "connect", connect)
    repository = PostgresWorkflowRepository("synthetic-configured-dsn")
    with repository.transaction():
        with pytest.raises(ServiceError), repository.transaction():
            pass
    assert len(opened) == 1
    with repository.transaction():
        pass
    assert len(opened) == 2


def test_database_failure_is_sanitized_without_fallback(monkeypatch):
    def unavailable(*args, **kwargs):
        raise psycopg.OperationalError("SYNTHETIC PRIVATE CONNECTION DETAILS")

    monkeypatch.setattr(psycopg, "connect", unavailable)
    repository = PostgresWorkflowRepository("synthetic-configured-dsn")
    assert repository.ready() is False
    with pytest.raises(ServiceError) as failure, repository.transaction():
        pass
    assert str(failure.value) == "PROVIDER_UNAVAILABLE"
    repository.close()
    assert repository.ready() is False


@pytest.fixture
def postgres_dsn():
    admin_dsn = os.environ.get("CONSTELLATIONS_TEST_ADMIN_DSN")
    if not admin_dsn:
        pytest.skip("Actual PostgreSQL requires explicit disposable CONSTELLATIONS_TEST_ADMIN_DSN")
    database_name = "cst_storage_test_" + uuid4().hex
    assert re.fullmatch(r"cst_storage_test_[a-f0-9]{32}", database_name)
    created = False
    admin = None
    try:
        admin = psycopg.connect(admin_dsn, autocommit=True, connect_timeout=5)
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database_name)))
        created = True
        dsn = make_conninfo(admin_dsn, dbname=database_name)
        with psycopg.connect(dsn, autocommit=True, connect_timeout=5) as connection:
            folder = Path(__file__).parents[2] / "db/workflow"
            for name in ("001_workflow.sql", "002_runtime_state.sql"):
                connection.execute((folder / name).read_text())
        yield dsn
    except psycopg.Error:
        pytest.fail("Disposable PostgreSQL storage test setup failed", pytrace=False)
    finally:
        if created and admin is not None:
            assert re.fullmatch(r"cst_storage_test_[a-f0-9]{32}", database_name)
            admin.execute(
                sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(database_name))
            )
        if admin is not None:
            admin.close()


def test_postgres_commit_reload_rollback_and_race(postgres_dsn, rich_state):
    first = PostgresWorkflowRepository(postgres_dsn)
    assert first.ready()
    with first.transaction() as state:
        state.chat = rich_state.chat
        state.records = {"counter": {"value": 0}}
    first.close()
    second = PostgresWorkflowRepository(postgres_dsn)
    with second.transaction() as state:
        assert dump_state(state)["rooms"] == dump_state(rich_state)["rooms"]
    with pytest.raises(RuntimeError), second.transaction() as state:
        state.chat.rooms.clear()
        state.records["counter"]["value"] = -1
        raise RuntimeError("Synthetic rollback")

    def increment(_):
        with second.transaction() as state:
            state.records["counter"]["value"] += 1

    with ThreadPoolExecutor(max_workers=4) as executor:
        list(executor.map(increment, range(12)))
    with second.transaction() as state:
        assert state.records["counter"]["value"] == 12
        assert state.chat.rooms
    second.close()


def test_postgres_private_rls_and_server_role(postgres_dsn):
    with psycopg.connect(postgres_dsn) as connection:
        security = connection.execute(
            "SELECT relrowsecurity, relforcerowsecurity FROM pg_class "
            "WHERE oid = 'workflow.runtime_state'::regclass"
        ).fetchone()
        assert security == (True, True)
        assert connection.execute(
            "SELECT rolcanlogin FROM pg_roles WHERE rolname = 'workflow_runtime'"
        ).fetchone() == (False,)
        assert connection.execute(
            "SELECT count(*) FROM pg_class c, "
            "LATERAL aclexplode(coalesce(c.relacl, acldefault('r', c.relowner))) a "
            "WHERE c.oid = 'workflow.runtime_state'::regclass AND a.grantee = 0"
        ).fetchone() == (0,)
        connection.execute("SET LOCAL ROLE workflow_runtime")
        assert connection.execute(
            "SELECT state_key FROM workflow.runtime_state WHERE state_key = 'weekly'"
        ).fetchone() == ("weekly",)
        connection.execute(
            "UPDATE workflow.runtime_state SET revision = revision + 1 WHERE state_key = 'weekly'"
        )
