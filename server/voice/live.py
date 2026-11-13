"""Live (streaming) speech-to-text for daily answers.

PROPOSED by Patrik for Will (owner of server/voice); see docs/DECISIONS.md D011.

The browser streams 16 kHz mono PCM16 over a WebSocket to this server; the
server holds the Muse key and relays the audio to Muse Voice Transcribe
realtime (``wss://api.meta.ai/v1/asr/realtime``, PUSH_TO_TALK, cumulative
partials), sending partial and final text back. The key never reaches the
browser. The final text is only a draft: the player edits and submits it
through the normal answer route, where M1 screening runs.

Browser protocol on ``/voice/live``:
  client -> server: binary PCM16 frames; text ``"stop"`` ends the turn.
  server -> client: ``{"type": "ready"}``, ``{"type": "partial", "text"}``,
                    ``{"type": "final", "text"}``, or
                    ``{"type": "error", "code", "message", "retryable"}``.

Privacy: audio and transcripts are never logged or stored. Errors never echo
provider details. Same-host origins only (cookie-authenticated WebSockets are
not covered by CORS). Caps: MAX_LIVE_SECONDS and MAX_LIVE_BYTES per turn; the
final transcript is truncated to MAX_TRANSCRIPT_CHARS like the batch route.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable, Iterable
from typing import Any, Protocol
from urllib.parse import urlsplit

from .muse_stt import MuseSttConfig
from .transcription import MAX_TRANSCRIPT_CHARS

MAX_LIVE_SECONDS = 60  # matches the web recorder's MAX_RECORDING_SECONDS
MAX_LIVE_BYTES = MAX_LIVE_SECONDS * 32_000 + 64_000  # 16 kHz PCM16 plus slack
HANDSHAKE_TIMEOUT_S = 10.0


class Upstream(Protocol):
    async def send(self, message: str | bytes) -> None: ...
    async def recv(self) -> str | bytes: ...
    def __aiter__(self): ...


Connect = Callable[[str], Any]  # returns an async context manager yielding an Upstream


def realtime_url(config: MuseSttConfig) -> str:
    """https://api.meta.ai/v1 -> wss://api.meta.ai/v1/asr/realtime"""
    parts = urlsplit(config.base_url)
    return f"wss://{parts.netloc}{parts.path.rstrip('/')}/asr/realtime"


def handshake(config: MuseSttConfig) -> str:
    payload: dict[str, Any] = {
        "authorization": {"accessToken": f"Bearer {config.api_key}"},
        "audioEncoding": "PCM_16KHZ",
        "model": config.model,
        "mode": "PUSH_TO_TALK",
        "partialMode": "CUMULATIVE",
    }
    if config.language_bias:
        payload["languageBias"] = list(config.language_bias)
    return json.dumps(payload)


def origin_allowed(headers: Any, extra: Iterable[str] = ()) -> bool:
    """Same host as the request, or an explicitly configured origin."""
    origin = headers.get("origin")
    if not origin:
        return False
    if origin in set(extra):
        return True
    host = headers.get("host")
    return bool(host) and urlsplit(origin).netloc == host


def default_connect(url: str):
    import websockets  # lazy: only live mode needs it

    return websockets.connect(url, max_size=2**20, open_timeout=HANDSHAKE_TIMEOUT_S)


def _error(code: str, message: str, retryable: bool) -> dict:
    return {"type": "error", "code": code, "message": message, "retryable": retryable}


async def relay(
    receive: Callable[[], Awaitable[dict]],
    send_json: Callable[[dict], Awaitable[None]],
    config: MuseSttConfig | None,
    *,
    connect: Connect = default_connect,
    max_bytes: int = MAX_LIVE_BYTES,
    max_seconds: float = MAX_LIVE_SECONDS,
) -> None:
    """One push-to-talk turn. ``receive`` yields ASGI websocket.receive messages."""
    if config is None:
        await send_json(_error("PROVIDER_UNAVAILABLE", "Live transcription isn't set up. You can type instead.", False))
        return
    try:
        async with connect(realtime_url(config)) as upstream:
            await upstream.send(handshake(config))
            first = json.loads(await asyncio.wait_for(upstream.recv(), timeout=HANDSHAKE_TIMEOUT_S))
            if not isinstance(first, dict) or "sessionId" not in first:
                raise RuntimeError("handshake rejected")
            await send_json({"type": "ready"})
            await asyncio.wait_for(_pump(receive, send_json, upstream, max_bytes, max_seconds),
                                   timeout=max_seconds + 15)
    except Exception:
        # Never echo provider errors, keys or audio details.
        await send_json(_error("PROVIDER_UNAVAILABLE", "Live transcription is unavailable right now. You can type instead.", True))


async def _pump(receive, send_json, upstream: Upstream, max_bytes: int, max_seconds: float) -> None:
    finished = asyncio.Event()

    async def browser_to_muse() -> None:
        loop = asyncio.get_running_loop()
        started, sent = loop.time(), 0
        try:
            while True:
                msg = await receive()
                if msg.get("type") == "websocket.disconnect":
                    finished.set()  # browser left: nothing to deliver
                    return
                chunk = msg.get("bytes")
                if chunk is not None:
                    sent += len(chunk)
                    if sent > max_bytes or loop.time() - started > max_seconds:
                        break  # cap reached: finish the turn with what we have
                    await upstream.send(chunk)
                elif msg.get("text") == "stop":
                    break
        finally:
            try:
                await upstream.send(json.dumps({"type": "endStream"}))
            except Exception:
                pass

    async def muse_to_browser() -> None:
        try:
            async for raw in upstream:
                if not isinstance(raw, str):
                    continue
                event = json.loads(raw)
                kind = event.get("type")
                if kind == "transcript":
                    text = str(event.get("transcript", ""))[:MAX_TRANSCRIPT_CHARS]
                    final = bool(event.get("final"))
                    await send_json({"type": "final" if final else "partial", "text": text})
                    if final:
                        return
                elif kind == "speechComplete":
                    await send_json({"type": "final", "text": str(event.get("transcript", ""))[:MAX_TRANSCRIPT_CHARS]})
                    return
                elif kind == "error":
                    await send_json(_error("PROVIDER_UNAVAILABLE", "Live transcription stopped. You can type instead.", True))
                    return
            await send_json({"type": "final", "text": ""})  # upstream closed without a final
        finally:
            finished.set()

    sender = asyncio.create_task(browser_to_muse())
    receiver = asyncio.create_task(muse_to_browser())
    await finished.wait()
    for task in (sender, receiver):
        task.cancel()
    await asyncio.gather(sender, receiver, return_exceptions=True)
