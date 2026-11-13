"""Privacy test harness. Fully offline: in-memory SQLite store, no database
server, no container, no model calls. Clock is injectable for expiry tests."""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from server.privacy.service import PrivacyService  # noqa: E402
from server.privacy.store import PrivacyStore  # noqa: E402


class FakeClock:
    def __init__(self, start: datetime = datetime(2026, 11, 11, 17, 0, tzinfo=timezone.utc)):
        self.now = start

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **kwargs) -> None:
        self.now += timedelta(**kwargs)


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def store():
    s = PrivacyStore(":memory:")
    yield s
    s.close()


@pytest.fixture
def service(store, clock) -> PrivacyService:
    return PrivacyService(store, clock=clock)
