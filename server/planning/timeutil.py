"""RFC3339 UTC parsing and half-open interval arithmetic [start, end)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Iterable, Sequence

Interval = tuple[datetime, datetime]


def parse_utc(value: object) -> datetime:
    if not isinstance(value, str) or not (value.endswith("Z") or value.endswith("+00:00")):
        raise ValueError("timestamp must be RFC3339 UTC (Z)")
    if "T" not in value:
        raise ValueError("timestamp must include a time")
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None or dt.utcoffset() != timedelta(0):
        raise ValueError("timestamp must be UTC")
    return dt.astimezone(timezone.utc)


def fmt_utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def to_intervals(windows: Iterable[dict]) -> list[Interval]:
    return normalize([(parse_utc(w["start"]), parse_utc(w["end"])) for w in windows])


def normalize(intervals: Iterable[Interval]) -> list[Interval]:
    """Sort and merge overlapping/adjacent intervals; drop empty ones."""
    items = sorted((s, e) for s, e in intervals if s < e)
    merged: list[Interval] = []
    for s, e in items:
        if merged and s <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], e))
        else:
            merged.append((s, e))
    return merged


def intersect(a: Sequence[Interval], b: Sequence[Interval]) -> list[Interval]:
    out: list[Interval] = []
    i = j = 0
    a, b = normalize(a), normalize(b)
    while i < len(a) and j < len(b):
        s = max(a[i][0], b[j][0])
        e = min(a[i][1], b[j][1])
        if s < e:
            out.append((s, e))
        if a[i][1] < b[j][1]:
            i += 1
        else:
            j += 1
    return out


def intersect_all(sets: Iterable[Sequence[Interval]]) -> list[Interval]:
    result: list[Interval] | None = None
    for s in sets:
        result = normalize(s) if result is None else intersect(result, s)
        if not result:
            return []
    return result or []


def covers(intervals: Sequence[Interval], start: datetime, end: datetime) -> bool:
    """True when [start, end) lies entirely inside one interval of the merged set."""
    return any(s <= start and end <= e for s, e in normalize(intervals))


def minutes(start: datetime, end: datetime) -> float:
    return (end - start).total_seconds() / 60.0
