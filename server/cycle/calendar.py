"""Weekly calendar in the community time zone (owner: Will).

Mon-Fri question days; Saturday 12:00 local lock; Sunday 10:00 local reveal;
chat expires at the next cycle's lock (Saturday 12:00 one week later).
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

LOCK_TIME = time(12, 0)
REVEAL_TIME = time(10, 0)


def iso(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def week_start_for(now: datetime, tz: ZoneInfo) -> date:
    """Monday of the local week containing ``now``."""
    local = now.astimezone(tz).date()
    return local - timedelta(days=local.weekday())


def _local_to_utc(day: date, at: time, tz: ZoneInfo) -> datetime:
    return datetime.combine(day, at, tzinfo=tz).astimezone(UTC)


def cycle_times(week_start: date, tz: ZoneInfo) -> tuple[datetime, datetime, datetime]:
    """(locksAt, revealsAt, chatExpiresAt) as UTC datetimes."""
    if week_start.weekday() != 0:
        raise ValueError("weekStart must be a Monday")
    locks = _local_to_utc(week_start + timedelta(days=5), LOCK_TIME, tz)
    reveals = _local_to_utc(week_start + timedelta(days=6), REVEAL_TIME, tz)
    expires = _local_to_utc(week_start + timedelta(days=12), LOCK_TIME, tz)
    return locks, reveals, expires


def day_date(week_start: date, day: int) -> date:
    return week_start + timedelta(days=day - 1)


def clock_day(week_start: date, now: datetime, tz: ZoneInfo) -> int:
    """Question day (1-5) the wall clock is on; weekends stay on Friday's 5."""
    offset = (now.astimezone(tz).date() - week_start).days
    return max(1, min(5, offset + 1))
