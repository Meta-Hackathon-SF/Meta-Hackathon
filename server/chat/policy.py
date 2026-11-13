"""Pure chat state transitions for an authorized transaction.

These functions do not authenticate, store private answers, make moderation
judgments or provide production persistence. Call them ONLY inside a transaction
that rechecks server-verified session, current consent/membership/blocks and cycle
revision. The fixture transaction driver is exclusively in tests/chat/adapters.py.
Production composition is blocked on the owning privacy/cycle interfaces.
"""

import hashlib
import json
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import uuid4

from server.app.errors import ServiceError
from server.chat.wire import ChatMessage, ChatRoom, MutualReveal, Player, Report
from server.orchestration.domain import validate_partition
from server.orchestration.stream import EVENT, Delivery
from server.orchestration.wire import Constellation, WeeklyCycle


def stamp(now: datetime) -> str:
    if now.tzinfo is None or now.utcoffset().total_seconds() != 0:
        raise ValueError("trusted clock must be UTC")
    return now.astimezone(UTC).isoformat().replace("+00:00", "Z")


def moment(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


@dataclass
class Room:
    wire: ChatRoom
    members: dict[str, str]  # PRIVATE playerId -> anonymous handle
    messages: dict[str, ChatMessage] = field(default_factory=dict)
    message_seqs: dict[str, int] = field(default_factory=dict)
    reports: list[Report] = field(default_factory=list)
    requests: set[tuple[str, str]] = field(default_factory=set)
    reveals: dict[frozenset[str], MutualReveal] = field(default_factory=dict)
    blocked: set[tuple[str, str]] = field(default_factory=set)
    attempts: dict[str, list[datetime]] = field(default_factory=dict)


@dataclass
class ChatState:
    """PRIVATE transaction state; repository owns atomic commit and durable reload."""

    rooms: dict[str, Room] = field(default_factory=dict)
    deliveries: list[Delivery] = field(default_factory=list)
    idempotency: dict[tuple[str, str, str], tuple[str, dict]] = field(default_factory=dict)
    seq: int = 0

    def emit(self, body: dict, recipients: set[str], room_id: str):
        self.seq += 1
        event = EVENT.validate_python({**body, "seq": self.seq}).model_dump()
        if not recipients:
            raise ServiceError("INVALID_INPUT")
        self.deliveries.append(Delivery(event, frozenset(recipients), room_id))
        return self.seq


def member(state: ChatState, room_id: str, actor_id: str, eligible: set[str]) -> Room:
    room = state.rooms.get(room_id)
    if room is None or actor_id not in room.members or actor_id not in eligible:
        # Identical error for absent/other player's room; no membership enumeration.
        raise ServiceError("NOT_FOUND")
    return room


def writable(room: Room, now: datetime):
    if room.wire.status != "open" or now >= moment(room.wire.expiresAt):
        raise ServiceError("ROOM_EXPIRED")
    if now < moment(room.wire.opensAt):
        raise ServiceError("NOT_FOUND")


def open_rooms(
    state: ChatState,
    cycle: WeeklyCycle,
    constellations: list[Constellation],
    eligible: set[str],
    blocked_pairs: list[tuple[str, str]],
    now: datetime,
):
    if cycle.status != "revealed" or now < moment(cycle.revealsAt):
        raise ServiceError("STALE_REVISION")
    if now >= moment(cycle.chatExpiresAt):
        raise ServiceError("ROOM_EXPIRED")
    if len({c.constellationId for c in constellations}) != len(constellations):
        raise ServiceError("INVALID_INPUT")
    if any(c.cycleId != cycle.cycleId for c in constellations):
        raise ServiceError("INVALID_INPUT")
    validate_partition(constellations, eligible, blocked_pairs)
    result = []
    for constellation in constellations:
        existing = [
            r
            for r in state.rooms.values()
            if r.wire.constellationId == constellation.constellationId
            and r.wire.cycleId == cycle.cycleId
        ]
        if existing:
            room = existing[0]
            if set(room.members) != set(constellation.memberIds):
                raise ServiceError("STALE_REVISION")
        else:
            room_id = str(uuid4())
            members = {p: f"Star {i + 1}" for i, p in enumerate(constellation.memberIds)}
            colors = ["#7c9cff", "#ffb86b", "#6be3c1", "#c9a7ff", "#ff7ab6"]
            wire = ChatRoom.model_validate(
                {
                    "roomId": room_id,
                    "constellationId": constellation.constellationId,
                    "cycleId": cycle.cycleId,
                    "status": "open",
                    "opensAt": cycle.revealsAt,
                    "expiresAt": cycle.chatExpiresAt,
                    "members": [
                        {
                            "roomId": room_id,
                            "handle": handle,
                            "starColor": colors[i],
                            "isSelf": False,
                        }
                        for i, handle in enumerate(members.values())
                    ],
                }
            )
            room = Room(wire, members)
            state.rooms[room_id] = room
            state.emit({"type": "constellation.revealed", "roomId": room_id}, set(members), room_id)
        result.append(room.wire.model_dump())
    return result


def room_for(state, room_id, actor_id, eligible, now):
    room = member(state, room_id, actor_id, eligible)
    if now < moment(room.wire.opensAt):
        raise ServiceError("NOT_FOUND")
    result = room.wire.model_dump()
    if now >= moment(room.wire.expiresAt) and result["status"] == "open":
        result["status"] = "expired"
    active_handles = {h for p, h in room.members.items() if p in eligible}
    result["members"] = [h for h in result["members"] if h["handle"] in active_handles]
    for handle in result["members"]:
        handle["isSelf"] = handle["handle"] == room.members[actor_id]
    return result


def visible(room: Room, message: ChatMessage, actor_id: str):
    author = next((p for p, handle in room.members.items() if handle == message.handle), None)
    return (
        message.moderation == "visible"
        and (actor_id, author) not in room.blocked
        and not any(
            r.reporterId == actor_id and r.messageId == message.messageId for r in room.reports
        )
    )


def messages_for(state, room_id, actor_id, eligible, now, after=0):
    room_for(state, room_id, actor_id, eligible, now)
    room = state.rooms[room_id]
    return [
        m.model_dump()
        for m in room.messages.values()
        if room.message_seqs[m.messageId] > after and visible(room, m, actor_id)
    ]


def replay_command(state, actor_id, route, key, body):
    if (
        not isinstance(key, str)
        or not 1 <= len(key) <= 128
        or any(not 33 <= ord(ch) <= 126 for ch in key)
    ):
        raise ServiceError("INVALID_INPUT")
    fingerprint = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    previous = state.idempotency.get((actor_id, route, key))
    if previous is not None and previous[0] != fingerprint:
        raise ServiceError("IDEMPOTENCY_CONFLICT")
    return fingerprint, deepcopy(previous[1]) if previous else None


def reserve_attempt(room, actor_id, now):
    recent = [t for t in room.attempts.get(actor_id, []) if (now - t).total_seconds() < 60]
    if len(recent) >= 6:
        raise ServiceError("RATE_LIMITED")
    room.attempts[actor_id] = [*recent, now]


async def moderate(privacy, guard, text: str, against_answers: list[str]):
    """Call exactly the shared PrivacyPort.screen and OutputGuard.check methods."""
    if not isinstance(text, str) or not text.strip() or not 1 <= len(text) <= 500:
        raise ServiceError("INVALID_INPUT")
    try:
        if await privacy.screen(text, "chat_message") != "none":
            raise ServiceError("MESSAGE_REJECTED")
        result = guard.check(text, against_answers)
        if (
            not isinstance(result, dict)
            or set(result) != {"ok", "reasons"}
            or result["ok"] is not True
            or result["reasons"] != []
        ):
            raise ServiceError("MESSAGE_REJECTED")
    except ServiceError:
        raise
    except Exception:
        raise ServiceError("PROVIDER_UNAVAILABLE") from None


def commit_message(state, room, actor_id, text, now, key, fingerprint, *, kind="player"):
    """Caller must run moderate + current OutputGuard inside its commit gate.

    This transition accepts only trusted server calls, never an HTTP moderation
    flag. No provider operation is performed while the transaction is held.
    """
    writable(room, now)
    if kind not in {"player", "system", "muse_nudge"}:
        raise ServiceError("INVALID_INPUT")
    handle = room.members[actor_id] if kind == "player" else "Muse"
    message = ChatMessage(
        messageId=str(uuid4()),
        roomId=room.wire.roomId,
        handle=handle,
        text=text,
        createdAt=stamp(now),
        moderation="visible",
        kind=kind,
    )
    room.messages[message.messageId] = message
    seq = state.emit(
        {"type": "chat.message", "message": message.model_dump()},
        set(room.members),
        room.wire.roomId,
    )
    room.message_seqs[message.messageId] = seq
    result = message.model_dump()
    route = f"/rooms/{room.wire.roomId}/messages"
    state.idempotency[(actor_id, route, key)] = (fingerprint, result)
    return result


def report(state, room, actor_id, handle, message_id, reason, now):
    writable(room, now)
    if handle not in room.members.values():
        raise ServiceError("NOT_FOUND")
    if message_id is not None:
        message = room.messages.get(message_id)
        if message is None or message.handle != handle:
            raise ServiceError("NOT_FOUND")
    item = Report(
        reportId=str(uuid4()),
        roomId=room.wire.roomId,
        messageId=message_id,
        reporterId=actor_id,
        reportedHandle=handle,
        reason=reason,
        createdAt=stamp(now),
    )
    # Duplicate reports do not increase the number of distinct reporters.
    if any(
        r.reporterId == actor_id and r.messageId == message_id and r.reportedHandle == handle
        for r in room.reports
    ):
        return
    room.reports.append(item)
    if message_id is not None:
        distinct = {r.reporterId for r in room.reports if r.messageId == message_id}
        if len(distinct) >= 2:
            room.messages[message_id] = room.messages[message_id].model_copy(
                update={"moderation": "hidden_pending"}
            )
            recipients = set(room.members)
        else:
            recipients = {actor_id}
        state.emit(
            {"type": "chat.moderated", "messageId": message_id, "moderation": "hidden_pending"},
            recipients,
            room.wire.roomId,
        )


def request_reveal(state, room, actor_id, to_handle, profiles: dict[str, Player], now):
    writable(room, now)
    target = next((p for p, h in room.members.items() if h == to_handle), None)
    if (
        target is None
        or target == actor_id
        or (actor_id, target) in room.blocked
        or (target, actor_id) in room.blocked
    ):
        raise ServiceError("NOT_FOUND")
    room.requests.add((actor_id, target))
    if (target, actor_id) not in room.requests:
        return {"result": "pending"}
    pair = frozenset({actor_id, target})
    if pair not in room.reveals:
        if any(p not in profiles or profiles[p].playerId != p for p in pair):
            raise ServiceError("PROVIDER_UNAVAILABLE")
        # Profiles are private until this exact mutual pair transaction succeeds.
        reveal = MutualReveal(
            roomId=room.wire.roomId,
            players=[profiles[p] for p in sorted(pair)],
            revealedAt=stamp(now),
        )
        room.reveals[pair] = reveal
        state.emit(
            {"type": "reveal.mutual", "reveal": reveal.model_dump()}, set(pair), room.wire.roomId
        )
    return {"result": "revealed"}


def block_room(room, actor_id, target_id):
    """Room-local effect only; canonical future-cycle block write belongs to privacy."""
    if actor_id not in room.members or target_id not in room.members or actor_id == target_id:
        raise ServiceError("NOT_FOUND")
    room.blocked.add((actor_id, target_id))
    room.requests.discard((actor_id, target_id))
    room.requests.discard((target_id, actor_id))
    room.reveals.pop(frozenset({actor_id, target_id}), None)


def expire(state, cycle_id, now):
    count = 0
    for room in state.rooms.values():
        if (
            room.wire.cycleId != cycle_id
            or room.wire.status != "open"
            or now < moment(room.wire.expiresAt)
        ):
            continue
        room.wire = room.wire.model_copy(update={"status": "expired"})
        room.requests.clear()
        room.reveals.clear()
        state.emit(
            {"type": "room.expired", "roomId": room.wire.roomId},
            set(room.members),
            room.wire.roomId,
        )
        count += 1
    return count


def delete_at_ttl(state, cycle: WeeklyCycle, now):
    from datetime import timedelta

    if now < moment(cycle.locksAt) + timedelta(days=14):
        return 0
    removed = {rid for rid, r in state.rooms.items() if r.wire.cycleId == cycle.cycleId}
    for rid in removed:
        del state.rooms[rid]
    state.deliveries = [d for d in state.deliveries if d.room_id not in removed]
    state.idempotency = {
        key: val
        for key, val in state.idempotency.items()
        if not any(rid in key[1] for rid in removed)
    }
    return len(removed)


def events_for(state, actor_id, eligible, now, after):
    result = []
    for delivery in state.deliveries:
        event = delivery.event
        if actor_id not in delivery.recipients or event["seq"] <= after:
            continue
        try:
            room = member(state, delivery.room_id, actor_id, eligible)
        except ServiceError:
            continue
        if now < moment(room.wire.opensAt):
            continue
        if event["type"] == "chat.message":
            message = room.messages.get(event["message"]["messageId"])
            if message is None or not visible(room, message, actor_id):
                continue
        if event["type"] == "reveal.mutual":
            ids = {p["playerId"] for p in event["reveal"]["players"]}
            if (
                frozenset(ids) not in room.reveals
                or room.wire.status != "open"
                or not ids <= eligible
                or now >= moment(room.wire.expiresAt)
                or any((a, b) in room.blocked for a in ids for b in ids)
            ):
                continue
        result.append(deepcopy(event))
    return result
