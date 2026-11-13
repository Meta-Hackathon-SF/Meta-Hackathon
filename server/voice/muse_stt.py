"""Muse speech-to-text transcriber for daily answers (owner: Will).

Provider facts, read from Meta's Model API docs at dev.meta.ai on 2026-11-13
(/docs/api-reference/voice/transcribe and /voice/schemas):
  - POST {base}/asr/transcribe, ``Authorization: Bearer <key>``
  - multipart/form-data with two parts: ``request`` (JSON settings) and
    ``audio`` (the clip)
  - settings: ``model`` (muse-voice-transcribe-1.0), ``audioEncoding`` ("WAV",
    the only value), ``mode`` (PUSH_TO_TALK default), optional ``languageBias``
  - audio must be RIFF/WAVE, mono integer PCM at 16 kHz or 24 kHz
  - ``Accept: application/json`` returns {sessionId, transcript,
    audioDurationMs, turns}
  - errors: 400 bad audio/body, 406, 413 too large, 429 limits, 500 failure

NOT VERIFIED LIVE: no call has been made with a key. Run
``python -m server.voice.smoke`` once a key is available.

Privacy: audio and transcripts are never logged or put in errors. The only
identifier sent is a random per-call ``sessionId``; nothing about the player.
The key stays on the server.
"""

from __future__ import annotations

import json
import os
import struct
import urllib.error
import urllib.parse
import urllib.request
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Literal

from .transcription import AudioUpload, Transcriber, UnconfiguredTranscriber, VoiceError

DEFAULT_BASE_URL = "https://api.meta.ai/v1"
DEFAULT_STT_MODEL = "muse-voice-transcribe-1.0"
ALLOWED_SAMPLE_RATES = (16000, 24000)
MAX_CLIP_SECONDS = 65  # the browser stops recording at 60 s
MAX_RESPONSE_BYTES = 256 * 1024

# (url, headers, body, timeout_s) -> (status, response bytes). Injected in tests.
Sender = Callable[[str, dict[str, str], bytes, float], tuple[int, bytes]]

_UNAVAILABLE = "Transcription is unavailable right now."


@dataclass(frozen=True)
class WavInfo:
    sample_rate: int
    channels: int
    bits_per_sample: int
    seconds: float


def inspect_wav(data: bytes) -> WavInfo:
    """Parse the RIFF header. Raises ValueError for anything that is not PCM WAV."""
    if len(data) < 12 or data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        raise ValueError("not a WAV container")
    offset = 12
    fmt: tuple[int, int, int, int] | None = None
    data_size: int | None = None
    while offset + 8 <= len(data):
        chunk_id = data[offset : offset + 4]
        (size,) = struct.unpack_from("<I", data, offset + 4)
        body = offset + 8
        if chunk_id == b"fmt ":
            if size < 16 or body + 16 > len(data):
                raise ValueError("bad fmt chunk")
            audio_format, channels, rate, _, _, bits = struct.unpack_from("<HHIIHH", data, body)
            fmt = (audio_format, channels, rate, bits)
        elif chunk_id == b"data":
            data_size = min(size, len(data) - body)
            break
        offset = body + size + (size & 1)
    if fmt is None or data_size is None:
        raise ValueError("missing fmt or data chunk")
    audio_format, channels, rate, bits = fmt
    if audio_format != 1:
        raise ValueError("not integer PCM")
    if channels < 1 or rate < 1 or bits not in (8, 16, 24, 32):
        raise ValueError("bad format values")
    return WavInfo(rate, channels, bits, data_size / (rate * channels * (bits // 8)))


def _urllib_send(url: str, headers: dict[str, str], body: bytes, timeout_s: float) -> tuple[int, bytes]:
    request = urllib.request.Request(url, data=body, method="POST", headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as response:  # noqa: S310 - https enforced
            return response.status, response.read(MAX_RESPONSE_BYTES + 1)
    except urllib.error.HTTPError as exc:
        return exc.code, b""  # the error body is never read or surfaced


@dataclass(frozen=True)
class MuseSttConfig:
    api_key: str = field(repr=False)
    base_url: str = DEFAULT_BASE_URL
    model: str = DEFAULT_STT_MODEL
    timeout_s: float = 30.0
    language_bias: tuple[str, ...] = ("English",)

    def __post_init__(self) -> None:
        if not self.api_key:
            raise ValueError("api_key is required")
        if not self.base_url.startswith("https://"):
            raise ValueError("base_url must use https")
        if not self.model or len(self.model) > 80 or self.model.endswith("-contributor"):
            raise ValueError("unsupported speech-to-text model id")
        if not (1.0 <= self.timeout_s <= 120.0):
            raise ValueError("timeout must be within [1, 120] seconds")

    def describe(self) -> dict[str, object]:
        """Safe for logs and health output (no key)."""
        return {"model": self.model, "baseUrl": self.base_url, "timeoutS": self.timeout_s, "apiKeyConfigured": True}


class MuseTranscriber:
    """``Transcriber`` backed by Muse Voice Transcribe. One request, no retry:
    the player can simply record again or type."""

    mode: Literal["live", "fixture"] = "live"

    def __init__(self, config: MuseSttConfig, *, send: Sender = _urllib_send) -> None:
        self._config = config
        self._send = send

    def _multipart(self, wav: bytes) -> tuple[str, bytes]:
        boundary = f"cst-{uuid.uuid4().hex}"
        settings: dict[str, object] = {
            "model": self._config.model,
            "audioEncoding": "WAV",
            "mode": "PUSH_TO_TALK",
        }
        if self._config.language_bias:
            settings["languageBias"] = list(self._config.language_bias)
        parts = [
            b"--" + boundary.encode() + b"\r\n"
            b'Content-Disposition: form-data; name="request"\r\n'
            b"Content-Type: application/json\r\n\r\n" + json.dumps(settings, separators=(",", ":")).encode() + b"\r\n",
            b"--" + boundary.encode() + b"\r\n"
            b'Content-Disposition: form-data; name="audio"; filename="answer.wav"\r\n'
            b"Content-Type: audio/wav\r\n\r\n" + wav + b"\r\n",
            b"--" + boundary.encode() + b"--\r\n",
        ]
        return boundary, b"".join(parts)

    def transcribe(self, upload: AudioUpload, *, request_id: str) -> str:
        # The provider accepts WAV only; the web client converts recordings first.
        try:
            info = inspect_wav(upload.data)
        except (ValueError, struct.error):
            raise VoiceError("INVALID_INPUT", "Unsupported audio format.", False) from None
        if info.channels != 1 or info.sample_rate not in ALLOWED_SAMPLE_RATES or info.bits_per_sample != 16:
            raise VoiceError("INVALID_INPUT", "Unsupported audio format.", False)
        if info.seconds > MAX_CLIP_SECONDS:
            raise VoiceError("INVALID_INPUT", "The recording is too long.", False)
        if info.seconds < 0.2:
            raise VoiceError("INVALID_INPUT", "No speech was detected. Try again or type instead.", False)

        boundary, body = self._multipart(upload.data)
        # Random per-call id: correlates provider logs without identifying the player.
        session = urllib.parse.quote(f"cst-{uuid.uuid4().hex}")
        url = f"{self._config.base_url.rstrip('/')}/asr/transcribe?sessionId={session}"
        headers = {
            "Authorization": f"Bearer {self._config.api_key}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Accept": "application/json",
            "User-Agent": "constellations-server",
        }
        try:
            status, raw = self._send(url, headers, body, self._config.timeout_s)
        except Exception:  # noqa: BLE001 - network detail (and the key in headers) must not leak
            raise VoiceError("PROVIDER_UNAVAILABLE", _UNAVAILABLE, True) from None
        if status == 429:
            raise VoiceError("RATE_LIMITED", "Voice is busy right now. Try again in a moment or type instead.", True)
        if status in (400, 413):
            raise VoiceError("INVALID_INPUT", "That recording could not be transcribed. Try again or type instead.", False)
        if status in (401, 402, 403, 404, 406):
            raise VoiceError("PROVIDER_UNAVAILABLE", "Voice transcription isn't available. Type your answer instead.", False)
        if status != 200 or len(raw) > MAX_RESPONSE_BYTES:
            raise VoiceError("PROVIDER_UNAVAILABLE", _UNAVAILABLE, True)
        try:
            transcript = json.loads(raw)["transcript"]
        except (ValueError, KeyError, TypeError):
            raise VoiceError("PROVIDER_UNAVAILABLE", _UNAVAILABLE, True) from None
        if not isinstance(transcript, str):
            raise VoiceError("PROVIDER_UNAVAILABLE", _UNAVAILABLE, True)
        return transcript  # transcribe_audio() normalizes, caps and rejects empty text


def load_muse_stt_config(env: Mapping[str, str] | None = None) -> MuseSttConfig | None:
    """None when no key is configured. Reads the same key variables as the Muse
    adapter (MUSE_API_KEY, or MODEL_API_KEY as the provider docs name it)."""
    env = os.environ if env is None else env
    key = env.get("MUSE_API_KEY") or env.get("MODEL_API_KEY") or ""
    if not key:
        return None
    return MuseSttConfig(
        api_key=key,
        base_url=(env.get("MUSE_BASE_URL") or DEFAULT_BASE_URL).rstrip("/"),
        model=env.get("MUSE_STT_MODEL") or DEFAULT_STT_MODEL,
        timeout_s=float(env.get("MUSE_STT_TIMEOUT_S") or 30.0),
    )


def build_transcriber(env: Mapping[str, str] | None = None) -> Transcriber:
    """The transcriber for live composition: Muse when a key is configured,
    otherwise the honest 503 (never a silent fixture)."""
    config = load_muse_stt_config(env)
    return MuseTranscriber(config) if config is not None else UnconfiguredTranscriber()
