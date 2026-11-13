"""Private, durable weekly workflow storage; never a public wire projection.

Apply Kai's workflow migrations before constructing this repository. The configured
server-only PostgreSQL LOGIN must inherit ``workflow_runtime``; browser roles get
no access. Provider calls must run outside ``transaction()``. Privacy/cycle guards
are the caller's responsibility and precede this transaction in the lock order.

The single row deliberately serializes this prototype's short commits. It provides
durable rollback/reload, not a distributed transaction with privacy's SQLite store.
"""

import json
import math
import threading
from collections.abc import Iterator
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from typing import Annotated, Protocol

import psycopg
from psycopg.types.json import Jsonb
from pydantic import Field, JsonValue, ValidationError, model_validator

from server.app.errors import ServiceError
from server.chat.policy import ChatState, Room
from server.chat.wire import ChatMessage, ChatRoom, MutualReveal, Report
from server.orchestration.stream import EVENT, Delivery, StreamEvent
from server.orchestration.wire import IsoTime, NonNegative, Text, Wire

Pair = Annotated[list[Text], Field(min_length=2, max_length=2)]
Positive = Annotated[int, Field(ge=1)]


@dataclass(repr=False)
class WorkflowState:
    """PRIVATE mutable state, only usable while the repository transaction is held."""

    chat: ChatState = field(default_factory=ChatState)
    records: dict[str, dict] = field(default_factory=dict)

    def __repr__(self) -> str:
        return "<WorkflowState private>"


class WorkflowRepository(Protocol):
    def transaction(self) -> AbstractContextManager[WorkflowState]: ...

    def ready(self) -> bool: ...

    def close(self) -> None: ...


class StorageFormatError(ServiceError):
    """A fixed error with no record contents, DSN or schema-validation echo."""

    def __init__(self) -> None:
        super().__init__("PROVIDER_UNAVAILABLE")


class _StoredRoom(Wire):
    wire: ChatRoom
    members: dict[Text, Text]
    messages: list[ChatMessage]
    messageSeqs: dict[Text, Positive]
    reports: list[Report]
    requests: list[Pair]
    reveals: list[MutualReveal]
    blocked: list[Pair]
    attempts: dict[Text, list[IsoTime]]

    @model_validator(mode="after")
    def references(self):
        handles = {member.handle for member in self.wire.members}
        if len(set(self.members.values())) != len(self.members):
            raise ValueError("invalid member mapping")
        if not set(self.members.values()) <= handles:
            raise ValueError("invalid member mapping")
        messages = {message.messageId: message for message in self.messages}
        if len(messages) != len(self.messages) or set(messages) != set(self.messageSeqs):
            raise ValueError("invalid message references")
        if len(set(self.messageSeqs.values())) != len(self.messageSeqs):
            raise ValueError("invalid message sequence")
        for message in self.messages:
            if message.roomId != self.wire.roomId:
                raise ValueError("invalid message room")
            if message.kind == "player" and message.handle not in handles:
                raise ValueError("invalid message handle")
        for report in self.reports:
            if report.roomId != self.wire.roomId:
                raise ValueError("invalid report room")
        pairs: set[frozenset[str]] = set()
        for reveal in self.reveals:
            ids = frozenset(player.playerId for player in reveal.players)
            if reveal.roomId != self.wire.roomId or not ids <= self.members.keys() or ids in pairs:
                raise ValueError("invalid reveal references")
            pairs.add(ids)
        for group in (self.requests, self.blocked):
            if len({tuple(pair) for pair in group}) != len(group):
                raise ValueError("invalid duplicate pair")
            if any(a == b or a not in self.members or b not in self.members for a, b in group):
                raise ValueError("invalid pair references")
        return self


class _StoredDelivery(Wire):
    event: StreamEvent
    recipients: list[Text]
    roomId: str

    @model_validator(mode="after")
    def audience(self):
        if not self.recipients or len(set(self.recipients)) != len(self.recipients):
            raise ValueError("invalid event recipients")
        if self.event.type == "reveal.mutual":
            ids = {player.playerId for player in self.event.reveal.players}
            if set(self.recipients) != ids or self.roomId != self.event.reveal.roomId:
                raise ValueError("invalid identity audience")
        elif self.event.type == "chat.message":
            if self.roomId != self.event.message.roomId:
                raise ValueError("invalid message event room")
        elif self.event.type in {"constellation.revealed", "room.expired"}:
            if self.roomId != self.event.roomId:
                raise ValueError("invalid event room")
        return self


class _StoredCommand(Wire):
    actorId: Text
    route: Text
    key: Annotated[str, Field(min_length=1, max_length=128, pattern=r"^[!-~]+$")]
    bodyHash: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
    result: dict[str, JsonValue]


class _Document(Wire):
    schemaVersion: Annotated[int, Field(ge=1, le=1)]
    seq: NonNegative
    rooms: dict[Text, _StoredRoom]
    deliveries: list[_StoredDelivery]
    idempotency: list[_StoredCommand]
    records: dict[Text, dict[str, JsonValue]]

    @model_validator(mode="after")
    def references(self):
        for room_id, room in self.rooms.items():
            if room_id != room.wire.roomId or any(
                seq > self.seq for seq in room.messageSeqs.values()
            ):
                raise ValueError("invalid room reference")
        sequences = [delivery.event.seq for delivery in self.deliveries]
        if any(seq < 1 or seq > self.seq for seq in sequences):
            raise ValueError("invalid outbox sequence")
        if sequences != sorted(set(sequences)):
            raise ValueError("invalid outbox ordering")
        identities = [(item.actorId, item.route, item.key) for item in self.idempotency]
        if len(set(identities)) != len(identities):
            raise ValueError("invalid duplicate idempotency entry")
        return self


_FORBIDDEN_RECORD_KEYS = frozenset(
    {
        "answers",
        "againstanswers",
        "prompt",
        "prompts",
        "rawprompt",
        "rawprompts",
        "payload",
        "sessiontoken",
        "apikey",
        "authorization",
        "credentials",
    }
)


def _safe_records(value) -> None:
    """Metadata is durable; private answer/provider/session material is not."""
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str) or key.replace("_", "").lower() in _FORBIDDEN_RECORD_KEYS:
                raise StorageFormatError()
            _safe_records(item)
    elif isinstance(value, list):
        for item in value:
            _safe_records(item)
    elif value is not None and type(value) not in {str, int, float, bool}:
        raise StorageFormatError()
    elif type(value) is float and not math.isfinite(value):
        raise StorageFormatError()


def _validated(body: object) -> _Document:
    try:
        document = _Document.model_validate(body)
        _safe_records(document.records)
        # JsonValue permits non-finite floats on some Pydantic releases. JSON
        # persistence must not silently accept them in any nested result.
        json.dumps(document.model_dump(mode="json"), allow_nan=False)
        return document
    except (ValidationError, ValueError, TypeError, OverflowError):
        raise StorageFormatError() from None


def dump_state(state: WorkflowState) -> dict:
    """Validate and serialize every private chat transition and metadata record."""
    try:
        if not isinstance(state, WorkflowState):
            raise StorageFormatError()
        rooms = {}
        for room_id, room in state.chat.rooms.items():
            rooms[room_id] = {
                "wire": room.wire.model_dump(mode="json"),
                "members": dict(room.members),
                "messages": [message.model_dump(mode="json") for message in room.messages.values()],
                "messageSeqs": dict(room.message_seqs),
                "reports": [report.model_dump(mode="json") for report in room.reports],
                "requests": [list(pair) for pair in sorted(room.requests)],
                "reveals": [reveal.model_dump(mode="json") for reveal in room.reveals.values()],
                "blocked": [list(pair) for pair in sorted(room.blocked)],
                "attempts": {
                    player_id: [stamp.isoformat().replace("+00:00", "Z") for stamp in stamps]
                    for player_id, stamps in room.attempts.items()
                },
            }
        body = {
            "schemaVersion": 1,
            "seq": state.chat.seq,
            "rooms": rooms,
            "deliveries": [
                {
                    "event": EVENT.validate_python(delivery.event).model_dump(mode="json"),
                    "recipients": sorted(delivery.recipients),
                    "roomId": delivery.room_id,
                }
                for delivery in state.chat.deliveries
            ],
            "idempotency": [
                {
                    "actorId": actor,
                    "route": route,
                    "key": key,
                    "bodyHash": fingerprint,
                    "result": result,
                }
                for (actor, route, key), (fingerprint, result) in state.chat.idempotency.items()
            ],
            "records": state.records,
        }
        return _validated(body).model_dump(mode="json")
    except (AttributeError, KeyError, TypeError, ValueError, ValidationError):
        raise StorageFormatError() from None


def load_state(body: object) -> WorkflowState:
    """Rehydrate only a complete, validated storage document; reject corruption."""
    document = _validated(body)
    state = WorkflowState()
    state.chat.seq = document.seq
    for room_id, stored in document.rooms.items():
        messages = {message.messageId: message for message in stored.messages}
        room = Room(
            wire=stored.wire,
            members=dict(stored.members),
            messages=dict(sorted(messages.items(), key=lambda entry: stored.messageSeqs[entry[0]])),
            message_seqs=dict(stored.messageSeqs),
            reports=list(stored.reports),
            requests={tuple(pair) for pair in stored.requests},
            reveals={
                frozenset(p.playerId for p in reveal.players): reveal for reveal in stored.reveals
            },
            blocked={tuple(pair) for pair in stored.blocked},
            attempts={
                player_id: [
                    datetime.fromisoformat(stamp.replace("Z", "+00:00")) for stamp in stamps
                ]
                for player_id, stamps in stored.attempts.items()
            },
        )
        state.chat.rooms[room_id] = room
    state.chat.deliveries = [
        Delivery(item.event.model_dump(mode="json"), frozenset(item.recipients), item.roomId)
        for item in document.deliveries
    ]
    state.chat.idempotency = {
        (item.actorId, item.route, item.key): (item.bodyHash, dict(item.result))
        for item in document.idempotency
    }
    state.records = document.model_dump(mode="json")["records"]
    return state


class PostgresWorkflowRepository:
    """One PostgreSQL row lock per short, durable workflow transaction.

    Connections live for one operation and always close. No credentials or state
    are logged, and no fixture/memory fallback is installed on connection failure.
    ``close`` prevents new transactions; it has no pending connection to drain.
    """

    def __init__(self, dsn: str, *, state_key: str = "weekly") -> None:
        if not isinstance(dsn, str) or not dsn.strip():
            raise ValueError("A configured workflow database is required")
        if not isinstance(state_key, str) or not state_key.strip() or len(state_key) > 128:
            raise ValueError("Invalid workflow state key")
        self._dsn = dsn
        self._key = state_key
        self._closed = False
        self._active = threading.local()

    def _connect(self):
        if self._closed:
            raise ServiceError("PROVIDER_UNAVAILABLE")
        return psycopg.connect(self._dsn, connect_timeout=5)

    @contextmanager
    def transaction(self) -> Iterator[WorkflowState]:
        if getattr(self._active, "value", False):
            # A fresh connection cannot reenter its own row lock. Detect this
            # before opening a second connection instead of waiting indefinitely.
            raise ServiceError("PROVIDER_UNAVAILABLE")
        self._active.value = True
        try:
            with self._connect() as connection:
                with connection.transaction():
                    connection.execute(
                        "INSERT INTO workflow.runtime_state (state_key, body) VALUES (%s, %s) "
                        "ON CONFLICT (state_key) DO NOTHING",
                        (self._key, Jsonb(dump_state(WorkflowState()))),
                    )
                    row = connection.execute(
                        "SELECT body FROM workflow.runtime_state WHERE state_key = %s FOR UPDATE",
                        (self._key,),
                    ).fetchone()
                    if row is None:
                        raise ServiceError("PROVIDER_UNAVAILABLE")
                    state = load_state(row[0])
                    yield state
                    connection.execute(
                        "UPDATE workflow.runtime_state SET body = %s, revision = revision + 1, "
                        "updated_at = clock_timestamp() WHERE state_key = %s",
                        (Jsonb(dump_state(state)), self._key),
                    )
        except psycopg.Error:
            raise ServiceError("PROVIDER_UNAVAILABLE") from None
        finally:
            self._active.value = False

    def ready(self) -> bool:
        try:
            with self._connect() as connection:
                allowed = connection.execute(
                    "SELECT has_table_privilege('workflow.runtime_state', 'SELECT') "
                    "AND has_table_privilege('workflow.runtime_state', 'INSERT') "
                    "AND has_table_privilege('workflow.runtime_state', 'UPDATE')"
                ).fetchone()
                if allowed != (True,):
                    return False
                row = connection.execute(
                    "SELECT body FROM workflow.runtime_state WHERE state_key = %s", (self._key,)
                ).fetchone()
                if row is None:
                    return False
                load_state(row[0])
                return True
        except (psycopg.Error, ServiceError):
            return False

    def close(self) -> None:
        self._closed = True
