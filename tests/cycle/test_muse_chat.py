"""POST /api/v1/muse-chat (server/cycle/muse_chat.py). Fake Muse transport; no network."""

import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from server.cycle import CycleService
from server.cycle.api import build_router, install_cycle_error_handler
from server.cycle.muse_chat import MuseChat, MuseChatConfig, load_catalog, load_config
from server.cycle.testing import (
    FixtureAnswerStore,
    FixtureQuestionPort,
    FixtureSeeder,
    fixture_clarify,
    fixture_screen,
)
from tests.cycle.test_cycle_api import as_, fake_session_for_tests

CONFIG = MuseChatConfig(key="test-key")
CONTEXT = [{"sender": "You", "text": "what should we do this week @muse"}]


class FakeMuse:
    def __init__(self, reply: dict | None = None, status: int = 200):
        self.reply, self.status, self.calls = reply or {"text": "ok"}, status, []

    def __call__(self, url, headers, body, timeout_s):
        self.calls.append({"url": url, "headers": headers, "body": json.loads(body)})
        content = json.dumps(self.reply)
        return self.status, json.dumps({"choices": [{"message": {"content": content}}]}).encode()


def client_with(chat: MuseChat) -> TestClient:
    service = CycleService(
        answers=FixtureAnswerStore(),
        questions=FixtureQuestionPort(),
        screen=fixture_screen,
        clarify=fixture_clarify,
        seed_synthetic=FixtureSeeder(),
    )
    app = FastAPI()
    install_cycle_error_handler(app)
    app.include_router(
        build_router(service, fake_session_for_tests, muse_chat=chat), prefix="/api/v1"
    )
    return TestClient(app)


def post(client, body, who="maya"):
    return client.post("/api/v1/muse-chat", json=body, headers=as_(who))


def test_requires_a_session_and_a_key():
    fake = FakeMuse()
    client = client_with(MuseChat(CONFIG, send=fake))
    assert (
        client.post("/api/v1/muse-chat", json={"kind": "hangout", "context": CONTEXT}).status_code
        == 401
    )
    unconfigured = client_with(MuseChat(None, send=fake))
    response = post(unconfigured, {"kind": "hangout", "context": CONTEXT})
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "PROVIDER_UNAVAILABLE"
    assert fake.calls == []


def test_only_anonymous_labels_and_catalog_facts_reach_muse():
    fake = FakeMuse({"text": "Board game night fits.", "eventIds": ["ev-board-games"]})
    client = client_with(MuseChat(CONFIG, send=fake))
    context = [
        {"sender": "Maya Chen", "text": "my number is 555"},  # real name: dropped
        {"sender": "Member 1", "text": "i feel like doing something chill"},
        {"sender": "You", "text": "@muse ideas?"},
    ]
    response = post(
        client, {"kind": "hangout", "context": context, "catalog": {"items": ["injected"]}}
    )
    assert response.status_code == 200
    sent = json.loads(fake.calls[0]["body"]["messages"][1]["content"])
    assert [n["sender"] for n in sent["context"]] == ["Member 1", "You"]
    assert "Maya Chen" not in json.dumps(fake.calls[0]["body"])
    assert "injected" not in json.dumps(sent)  # facts come from the catalog, never the request
    assert fake.calls[0]["headers"]["authorization"] == "Bearer test-key"
    assert response.json() == {
        "text": "Board game night fits.",
        "source": "live",
        "itemIds": [],
        "eventIds": ["ev-board-games"],
        "draft": None,
    }


def test_unknown_ids_and_bad_drafts_are_removed():
    chat = MuseChat(
        CONFIG, send=FakeMuse({"text": "x", "itemIds": ["mk-speaker", "mk-fake", "mk-speaker"]})
    )
    assert chat.reply({"kind": "supplies", "context": CONTEXT}, "p1")["itemIds"] == ["mk-speaker"]
    draft = {
        "title": "Picnic",
        "placeId": "v-quad",
        "day": "Saturday",
        "time": "14:00",
        "description": "Bring snacks.",
    }
    chat = MuseChat(CONFIG, send=FakeMuse({"text": "Draft below.", "draft": draft}))
    assert chat.reply({"kind": "create", "context": CONTEXT}, "p1")["draft"] == draft
    for bad in (
        {**draft, "placeId": "v-somewhere-else"},  # not an approved venue
        {**draft, "time": "23:30"},  # outside 08:00-22:00
        {**draft, "day": "Someday"},
        {**draft, "title": "Call 831 555 0142"},  # contact info
    ):
        chat = MuseChat(CONFIG, send=FakeMuse({"text": "Draft.", "draft": bad}))
        assert chat.reply({"kind": "create", "context": CONTEXT}, "p1")["draft"] is None
    # A hangout reply can't smuggle items or a draft.
    chat = MuseChat(CONFIG, send=FakeMuse({"text": "x", "itemIds": ["mk-speaker"], "draft": draft}))
    assert chat.reply({"kind": "hangout", "context": CONTEXT}, "p1")["itemIds"] == []


def test_bad_input_provider_errors_and_rate_limit():
    fake = FakeMuse()
    client = client_with(MuseChat(CONFIG, send=fake, limit=2))
    assert post(client, {"kind": "steal-keys", "context": CONTEXT}).status_code == 400
    assert post(client, {"kind": "hangout", "context": []}).status_code == 400
    assert (
        client.post("/api/v1/muse-chat", content=b"not json", headers=as_("maya")).status_code
        == 400
    )
    assert post(client, {"kind": "hangout", "context": CONTEXT}).status_code == 200
    assert post(client, {"kind": "hangout", "context": CONTEXT}).status_code == 200
    limited = post(client, {"kind": "hangout", "context": CONTEXT})
    assert limited.status_code == 429 and limited.json()["error"]["code"] == "RATE_LIMITED"
    assert (
        post(client, {"kind": "hangout", "context": CONTEXT}, who="dev").status_code == 200
    )  # per player
    down = client_with(MuseChat(CONFIG, send=FakeMuse(status=500)))
    response = post(down, {"kind": "hangout", "context": CONTEXT})
    assert response.status_code == 503 and "500" not in response.text


def test_config_uses_the_api_hosts_existing_key_names():
    assert load_config({}) is None
    assert load_config({"MUSE_API_KEY": "replace-me"}) is None
    assert load_config({"MODEL_API_KEY": "k"}).key == "k"
    config = load_config(
        {"MUSE_API_KEY": "k", "MUSE_MODEL": "m", "MUSE_BASE_URL": "https://example.test/v1/"}
    )
    assert (config.model, config.base_url) == ("m", "https://example.test/v1")
    assert "k" not in repr(config)


def test_catalog_ships_with_the_backend_and_matches_the_approved_venues():
    catalog = load_catalog()
    venues = json.loads(open("server/planning/data/venues.json", encoding="utf-8").read())
    approved = {v["placeId"] for v in venues["venues"]}
    assert {v["placeId"] for v in catalog["venues"]} <= approved
    assert all(e["placeId"] in approved for e in catalog["events"])
    starts = {e["eventId"]: e["start"] for e in venues["campusEvents"]}
    assert all(
        e["start"] == starts[e["eventId"]] for e in catalog["events"] if e["eventId"] in starts
    )


def test_mounted_in_the_composed_backend_behind_session_and_idempotency(monkeypatch):
    """The real app (server/app/weekly.py) serves the route at /api/v1/muse-chat with no wiring change."""
    from tests.orchestration.runtime_helpers import runtime_environment
    from tests.orchestration.test_runtime import call, join

    monkeypatch.delenv("MUSE_API_KEY", raising=False)
    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    body = {"kind": "hangout", "context": CONTEXT}
    with runtime_environment() as env, TestClient(env.app, base_url="https://testserver") as client:
        assert (
            client.post(
                "/api/v1/muse-chat", json=body, headers={"Idempotency-Key": "k"}
            ).status_code
            == 401
        )
        player = join(client, "muse-chat")
        no_key = client.post(
            "/api/v1/muse-chat", json=body, headers={"Authorization": "Bearer " + player.token}
        )
        assert no_key.status_code == 400  # every POST needs an Idempotency-Key
        response = call(client, player, "POST", "/muse-chat", json=body)
        assert response.status_code == 503  # mounted; no Muse key in this test environment
        assert response.json()["error"]["code"] == "PROVIDER_UNAVAILABLE"
