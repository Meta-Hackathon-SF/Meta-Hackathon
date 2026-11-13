"""D010 activity signals: opt-in only, topics not text, deleted on opt-out and
with /me/data, and visible to formation only by random ref. Offline, synthetic."""

from __future__ import annotations

import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from privacy_helpers import COMMUNITY, consent_body, join_body
from server.privacy import build_router, install_error_handlers
from server.privacy.activity import SAFE_TOPICS, ActivityStore, derive_topics
from server.privacy.answers import AnswerStore
from server.privacy.formation import PrivacyFormation
from server.privacy.moderation import ModerationStore

JOIN = f"/api/v1/communities/{COMMUNITY}/join"
CYCLE = "cycle-demo-w1"
SECRET = "my private post about the dining hall and board games"


@pytest.fixture
def parts(store, service):
    answers = AnswerStore(store, service)
    moderation = ModerationStore(store, service)
    activity = ActivityStore(store)
    return answers, moderation, activity


@pytest.fixture
def app(service, parts):
    answers, moderation, activity = parts
    app = FastAPI()
    install_error_handlers(app)
    app.include_router(build_router(service, answers, activity=activity), prefix="/api/v1")
    return app


def joined(app, name="Tester (synthetic)") -> TestClient:
    c = TestClient(app, base_url="https://testserver")
    assert c.post(JOIN, json=join_body(name)).status_code == 201
    return c


def body(**over):
    b = {"useActivity": True, "groupIds": ["g-hackathon", "g-xr"], "eventIds": ["e-boardgames"],
         "friendIds": ["f-maya"], "texts": [SECRET]}
    b.update(over)
    return b


def test_off_by_default_and_on_after_opt_in(app):
    c = joined(app)
    assert c.get("/api/v1/session").json()["consent"]["useActivity"] is False
    r = c.put("/api/v1/me/activity", json=body())
    assert r.status_code == 200
    assert r.json() == {"useActivity": True, "topics": ["food", "gaming"]}
    assert c.get("/api/v1/session").json()["consent"]["useActivity"] is True


def test_text_is_never_stored_or_echoed(app, store):
    c = joined(app)
    r = c.put("/api/v1/me/activity", json=body())
    assert SECRET not in r.text
    with store.tx() as conn:
        dump = json.dumps([dict(row) for row in conn.execute("SELECT * FROM activity_signals")])
    assert "dining hall" not in dump and "board games" not in dump and "private post" not in dump


def test_opt_out_deletes_the_row(app, store):
    c = joined(app)
    c.put("/api/v1/me/activity", json=body())
    r = c.put("/api/v1/me/activity", json={"useActivity": False})
    assert r.json() == {"useActivity": False, "topics": []}
    with store.tx() as conn:
        assert conn.execute("SELECT count(*) FROM activity_signals").fetchone()[0] == 0
    assert c.get("/api/v1/session").json()["consent"]["useActivity"] is False


def test_delete_my_data_removes_activity(app, store):
    c = joined(app)
    c.put("/api/v1/me/activity", json=body())
    assert c.delete("/api/v1/me/data").status_code == 202
    with store.tx() as conn:
        assert conn.execute("SELECT count(*) FROM activity_signals").fetchone()[0] == 0


def test_requires_session_and_full_consent(app):
    anon = TestClient(app, base_url="https://testserver")
    assert anon.put("/api/v1/me/activity", json=body()).status_code == 401
    c = joined(app)
    v = c.get("/api/v1/session").json()["consent"]["version"]
    c.patch("/api/v1/me/consent", json=consent_body(v, match=False))
    assert c.put("/api/v1/me/activity", json=body()).status_code == 403


@pytest.mark.parametrize("mutate", [
    lambda b: b.update(playerId="p-other"),            # identity never from the body
    lambda b: b.update(groupIds=["has space"]),        # ids are opaque tokens only
    lambda b: b.update(groupIds=["g"] * 51),           # bounded
    lambda b: b.update(texts=["x" * 2001]),            # bounded
    lambda b: b.update(useActivity="true"),            # no coercion
    lambda b: b.update(use_activity=True),             # camelCase only
])
def test_rejects_hostile_input(app, mutate):
    c = joined(app)
    b = body()
    mutate(b)
    assert c.put("/api/v1/me/activity", json=b).status_code == 400


def test_sensitive_words_never_become_topics():
    sensitive = ["my therapist and my diagnosis", "church on sunday", "my debt and rent",
                 "my sexuality", "my address is 12 Main St", "my parents divorce"]
    assert derive_topics(sensitive) == []
    assert not {"health", "religion", "finances", "sexuality", "family", "location"} & set(SAFE_TOPICS)


def test_snapshot_carries_activity_by_ref_only(store, service, parts, app):
    answers, moderation, activity = parts
    c = joined(app, "Ana (synthetic)")
    c.put("/api/v1/me/activity", json=body())
    player = c.get("/api/v1/session").json()["player"]["playerId"]
    answers.save({"answerId": "a1", "cycleId": CYCLE, "day": 1, "questionId": "q", "playerId": player,
                  "text": "Mostly the dining hall", "source": "text", "isCatchUp": False, "weight": 1.0,
                  "followUpUsed": False, "createdAt": "2026-11-11T17:00:00Z", "editedAt": None,
                  "deletedAt": None}, "none")
    lease = PrivacyFormation(store, answers, moderation, activity).prepare_formation(CYCLE, COMMUNITY)
    snap = lease.snapshot
    ref = next(iter(snap["idMap"]))
    assert set(snap["activity"]) == {ref}  # keyed by the random ref, never the player id
    assert snap["activity"][ref] == {"profileId": None, "groupIds": ["g-hackathon", "g-xr"], "eventIds": ["e-boardgames"],
                                     "friendIds": ["f-maya"], "topics": ["food", "gaming"]}
    assert player not in json.dumps(snap["activity"])


def test_snapshot_has_no_activity_key_without_opt_in(store, service, parts):
    answers, moderation, activity = parts
    lease = PrivacyFormation(store, answers, moderation, activity).prepare_formation(CYCLE, COMMUNITY)
    assert "activity" not in lease.snapshot


def test_global_pool_is_seeded_and_joinable(service):
    from privacy_helpers import join_req
    result = service.join("facebook-space", join_req("Global (synthetic)"))
    assert result.created and result.view.consent.community_id == "facebook-space"
