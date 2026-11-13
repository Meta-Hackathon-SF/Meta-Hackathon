"""TEST ONLY complete weekly runtime with synthetic inputs and scripted Muse.

Uses real privacy/cycle/guard/matching services. The model transport and workflow
repository are the labeled test adapters; this helper is never imported by server.
"""

from contextlib import contextmanager
from datetime import UTC, datetime
from itertools import combinations
from types import SimpleNamespace

from server.app.config import Settings
from server.privacy import PrivacyStore
from server.privacy.fixtures import seed_community
from server.providers.fixture import FixtureMuse, ScriptedTransport
from tests.orchestration.storage_adapter import TestWorkflowRepository

COMMUNITY = "synthetic-community"


class SyntheticRuntimeEnvironment(SimpleNamespace):
    def __repr__(self):
        return "<SyntheticRuntimeEnvironment>"


class SyntheticClock:
    def __init__(self):
        self.now = datetime(2026, 11, 9, 18, tzinfo=UTC)

    def __call__(self):
        return self.now


def _refs(payload):
    return list(dict.fromkeys(answer["id"] for answer in payload["answers"]))


def _groups(ids, blocks):
    if not ids:
        return []
    if len(ids) < 3:
        return None
    for size in (3, 4, 5):
        if size > len(ids):
            continue
        for rest in combinations(ids[1:], size - 1):
            group = [ids[0], *rest]
            if any(a in group and b in group for a, b in blocks):
                continue
            remaining = [value for value in ids if value not in group]
            result = _groups(remaining, blocks)
            if result is not None:
                return [group, *result]
    return None


def scripted_transport():
    """Schema-valid fixture decisions, not evidence of live semantic quality."""
    transport = ScriptedTransport()
    transport.on("safety_screen", lambda _payload: {"flag": "none", "reason": "synthetic fixture"})
    transport.on("clarify", lambda _payload: {"needsFollowup": False, "question": ""})
    transport.on(
        "theme_discovery",
        lambda payload: {
            "themes": [
                {
                    "id": "synthetic-theme",
                    "label": "Shared campus routines",
                    "description": "A familiar weekly rhythm",
                    "memberIds": _refs(payload),
                }
            ]
        },
    )
    transport.on(
        "constellation_formation",
        lambda payload: {
            "constellations": [
                {
                    "memberIds": group,
                    "sharedMeaning": "A shared weekly rhythm",
                    "confidence": 0.8,
                }
                for group in (_groups(_refs(payload), payload["blockedPairs"]) or [])
            ]
        },
    )
    transport.on(
        "constellation_naming",
        lambda payload: {
            "name": "Quiet Orbit",
            "shapeId": {3: "triangle", 4: "kite", 5: "w-cass"}[payload["size"]],
            "colorId": "tide",
        },
    )
    transport.on("sky_narration", lambda _payload: {"headlines": ["Some routines are shared."]})
    return transport


@contextmanager
def runtime_environment():
    from server.app.weekly import build_weekly_app

    repository = TestWorkflowRepository()
    privacy_store = PrivacyStore(":memory:")
    seed_community(privacy_store, COMMUNITY, "Synthetic test Group")
    clock, transport = SyntheticClock(), scripted_transport()
    try:
        app = build_weekly_app(
            repository=repository,
            privacy_store=privacy_store,
            muse_factory=lambda registry: FixtureMuse(registry, transport),
            clock=clock,
            settings=Settings(environment="test"),
            start_worker=False,
        )
        yield SyntheticRuntimeEnvironment(
            app=app,
            repository=repository,
            privacy_store=privacy_store,
            clock=clock,
            transport=transport,
        )
    finally:
        repository.close()
        privacy_store.close()
