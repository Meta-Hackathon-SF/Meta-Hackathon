"""Live speech-to-text relay (/voice/live, PROPOSED D011). Offline: a fake Muse
realtime upstream follows the documented protocol (handshake reply, cumulative
partials, final after endStream). No network, no key, no paid call."""

from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from server.cycle.api import build_router as cycle_router
from server.privacy import PrivacyService, PrivacyStore, actor_dependency, build_router as privacy_router
from server.voice.live import handshake, realtime_url, relay
from server.voice.muse_stt import MuseSttConfig

KEY = "test-key-not-real-0123456789"
CFG = MuseSttConfig(api_key=KEY)
JOIN = {"displayName": "Tester (synthetic)", "matchAnswers": True, "anonymousChat": True, "isAdult": True}
WORDS = ["mostly", "the", "dining", "hall"]


class FakeMuse:
    """Scripted realtime upstream. One partial per audio chunk, final after endStream."""

    def __init__(self, *, reject=False, fail_after=None, final_text=None):
        self.sent: list = []
        self.reject = reject
        self.fail_after = fail_after
        self.final_text = final_text
        self.urls: list[str] = []
        self._events: asyncio.Queue = asyncio.Queue()
        self._chunks = 0

    def connect(self, url):
        self.urls.append(url)

        @asynccontextmanager
        async def cm():
            yield self
        return cm()

    async def send(self, message):
        self.sent.append(message)
        if isinstance(message, bytes):
            self._chunks += 1
            if self.fail_after and self._chunks >= self.fail_after:
                await self._events.put(json.dumps({"type": "error", "message": "internal provider detail XYZ"}))
                return
            text = " ".join(WORDS[: min(self._chunks, len(WORDS))])
            await self._events.put(json.dumps({"type": "transcript", "transcript": text, "final": False}))
        elif json.loads(message).get("type") == "endStream":
            final = self.final_text if self.final_text is not None else " ".join(WORDS[: max(1, self._chunks)]).capitalize() + "."
            await self._events.put(json.dumps({"type": "transcript", "transcript": final, "final": True}))
            await self._events.put(None)

    async def recv(self):
        return json.dumps({"error": "bad key"}) if self.reject else json.dumps({"sessionId": "s-1"})

    def __aiter__(self):
        return self

    async def __anext__(self):
        item = await self._events.get()
        if item is None:
            raise StopAsyncIteration
        return item


@pytest.fixture
def privacy(monkeypatch):
    # Local http in tests, like local dev: the session cookie is Secure by default.
    monkeypatch.setenv("CST_COOKIE_INSECURE_DEV", "1")
    return PrivacyService(PrivacyStore(":memory:"))


def make_app(privacy, fake, *, stt=CFG):
    app = FastAPI()
    app.include_router(privacy_router(privacy), prefix="/api/v1")
    app.include_router(
        cycle_router(object(), actor_dependency(privacy), require_consent=privacy.require_consent,
                     live_stt=stt, live_connect=fake.connect),
        prefix="/api/v1",
    )
    return app


def joined_client(app) -> TestClient:
    c = TestClient(app, base_url="http://testserver")
    assert c.post("/api/v1/communities/community-demo/join", json=JOIN).status_code == 201
    return c


ORIGIN = {"origin": "http://testserver"}


def test_happy_path_streams_partials_then_final(privacy):
    fake = FakeMuse()
    c = joined_client(make_app(privacy, fake))
    seen = []
    with c.websocket_connect("/api/v1/voice/live", headers=ORIGIN) as ws:
        assert ws.receive_json() == {"type": "ready"}
        for _ in WORDS:
            ws.send_bytes(b"\x00\x01" * 1600)
            seen.append(ws.receive_json())
        ws.send_text("stop")
        final = ws.receive_json()
    assert [m["type"] for m in seen] == ["partial"] * 4
    assert seen[-1]["text"] == "mostly the dining hall"
    assert final == {"type": "final", "text": "Mostly the dining hall."}
    # upstream got the documented handshake, the audio, and endStream
    hs = json.loads(fake.sent[0])
    assert hs["authorization"] == {"accessToken": f"Bearer {KEY}"}
    assert (hs["audioEncoding"], hs["mode"], hs["partialMode"], hs["model"]) == (
        "PCM_16KHZ", "PUSH_TO_TALK", "CUMULATIVE", "muse-voice-transcribe-1.0")
    assert sum(isinstance(m, bytes) for m in fake.sent) == 4
    assert json.loads(fake.sent[-1]) == {"type": "endStream"}
    assert fake.urls == ["wss://api.meta.ai/v1/asr/realtime"]
    assert KEY not in json.dumps(seen + [final])  # the key never reaches the browser


@pytest.mark.parametrize("headers", [{}, {"origin": "https://evil.example"}, {"origin": "http://testserver.evil"}])
def test_cross_origin_rejected_before_accept(privacy, headers):
    c = joined_client(make_app(privacy, FakeMuse()))
    with pytest.raises(WebSocketDisconnect) as e:
        with c.websocket_connect("/api/v1/voice/live", headers=headers) as ws:
            ws.receive_json()
    assert e.value.code == 1008


def test_unauthenticated_gets_error_and_no_upstream(privacy):
    fake = FakeMuse()
    c = TestClient(make_app(privacy, fake), base_url="http://testserver")
    with c.websocket_connect("/api/v1/voice/live", headers=ORIGIN) as ws:
        msg = ws.receive_json()
    assert msg["type"] == "error" and msg["code"] == "UNAUTHENTICATED"
    assert fake.urls == []


def test_withdrawn_consent_blocks_live(privacy):
    fake = FakeMuse()
    c = joined_client(make_app(privacy, fake))
    assert c.patch("/api/v1/me/consent", json={"expectedVersion": 1, "matchAnswers": True,
                                                "anonymousChat": False, "isAdult": True}).status_code == 200
    with c.websocket_connect("/api/v1/voice/live", headers=ORIGIN) as ws:
        msg = ws.receive_json()
    assert msg["code"] == "CONSENT_REQUIRED" and fake.urls == []


def test_unconfigured_mounts_no_live_route(privacy):
    """No key -> no route: the browser falls back to POST /voice/transcribe, and
    compositions that only accept HTTP routes keep working."""
    router = cycle_router(object(), actor_dependency(privacy), require_consent=privacy.require_consent)
    assert all(getattr(r, "path", "") != "/voice/live" for r in router.routes)
    assert any(getattr(r, "path", "") == "/voice/transcribe" for r in router.routes)


def test_relay_without_config_is_honest_unavailable():
    out = []

    async def send_json(m):
        out.append(m)

    asyncio.run(relay(lambda: None, send_json, None))
    assert (out[0]["code"], out[0]["retryable"]) == ("PROVIDER_UNAVAILABLE", False)


def test_rejected_handshake_is_generic_error(privacy):
    c = joined_client(make_app(privacy, FakeMuse(reject=True)))
    with c.websocket_connect("/api/v1/voice/live", headers=ORIGIN) as ws:
        msg = ws.receive_json()
    assert msg["code"] == "PROVIDER_UNAVAILABLE" and "bad key" not in json.dumps(msg)


def test_provider_error_mid_stream_never_leaks_detail(privacy):
    c = joined_client(make_app(privacy, FakeMuse(fail_after=2)))
    with c.websocket_connect("/api/v1/voice/live", headers=ORIGIN) as ws:
        assert ws.receive_json()["type"] == "ready"
        ws.send_bytes(b"\x00" * 3200)
        assert ws.receive_json()["type"] == "partial"
        ws.send_bytes(b"\x00" * 3200)
        msg = ws.receive_json()
    assert msg["type"] == "error" and "XYZ" not in json.dumps(msg)


def _drive(fake, chunks, *, max_bytes, final_text=None):
    """Run relay() directly with an in-memory browser."""
    if final_text is not None:
        fake.final_text = final_text
    inbox = [{"type": "websocket.receive", "bytes": c} for c in chunks] + [{"type": "websocket.receive", "text": "stop"}]
    out = []

    async def receive():
        return inbox.pop(0) if inbox else await asyncio.sleep(3600)

    async def send_json(m):
        out.append(m)

    asyncio.run(relay(receive, send_json, CFG, connect=fake.connect, max_bytes=max_bytes))
    return out


def test_byte_cap_ends_turn_early_and_still_returns_final():
    fake = FakeMuse()
    out = _drive(fake, [b"\x00" * 1000] * 10, max_bytes=2500)
    assert sum(isinstance(m, bytes) for m in fake.sent) == 2  # third chunk would exceed the cap
    assert out[-1]["type"] == "final"


def test_final_transcript_is_capped_like_the_batch_route():
    out = _drive(FakeMuse(), [b"\x00" * 10], max_bytes=10**6, final_text="word " * 200)
    assert out[-1]["type"] == "final" and len(out[-1]["text"]) == 400


def test_url_and_handshake_helpers():
    assert realtime_url(MuseSttConfig(api_key="k", base_url="https://api.meta.ai/v1/")) == "wss://api.meta.ai/v1/asr/realtime"
    assert json.loads(handshake(CFG))["languageBias"] == ["English"]
