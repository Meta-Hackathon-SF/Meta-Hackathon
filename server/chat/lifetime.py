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
