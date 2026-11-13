"""The v3 24-hour access policy, awaiting approved v3 composition."""

from datetime import timedelta

from server.app.errors import ServiceError
from server.chat import policy


def daily_expiry(opened_at):
    policy.stamp(opened_at)
    return opened_at + timedelta(hours=24)


def require_daily_access(room, now):
    """Apply to reads and writes while holding current membership/privacy guards."""
    expected = daily_expiry(policy.moment(room.wire.opensAt))
    if policy.moment(room.wire.expiresAt) != expected:
        raise ServiceError("INVALID_INPUT")
    policy.writable(room, now)


def purge_v3_chat_text(state, cycle_id, locked_at, now):
    """Remove room text and replay copies at the producer-approved deadline.

    Call only inside the guarded workflow transaction. The v3 composition must
    supply the actual lock time from the privacy retention owner.
    """
    policy.stamp(locked_at)
    policy.stamp(now)
    due_rooms = {
        room_id
        for room_id, room in state.rooms.items()
        if room.wire.cycleId == cycle_id
        and now
        >= min(
            locked_at + timedelta(days=14),
            policy.moment(room.wire.expiresAt) + timedelta(days=7),
        )
    }
    for room_id in due_rooms:
        state.rooms[room_id].messages.clear()
        state.rooms[room_id].message_seqs.clear()
    state.deliveries = [
        delivery
        for delivery in state.deliveries
        if delivery.room_id not in due_rooms or delivery.event["type"] != "chat.message"
    ]
    routes = {f"/rooms/{room_id}/messages" for room_id in due_rooms}
    state.idempotency = {
        key: value for key, value in state.idempotency.items() if key[1] not in routes
    }
    return len(due_rooms)
