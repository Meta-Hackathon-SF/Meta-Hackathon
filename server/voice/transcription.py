"""Voice transcription boundary for daily answers (owner: Will).

Facebook Space 2.0.0: a player may speak a daily answer. The browser uploads
the recording, this module validates it, calls a configured ``Transcriber``
and returns ``{"transcript": str}`` (or raises ``VoiceError`` carrying a
contract ErrorCode). The player reviews the transcript and submits it as a
DailyAnswer with ``source: "voice"``. Typing always works without this module.

Framework-independent: the route layer passes the upload's content type and
bytes to ``transcribe_audio``.

No speech-to-text provider is assumed. Muse audio support is unconfirmed (see
PROJECT_KNOWLEDGE.md); until a provider is verified, the server should use
``UnconfiguredTranscriber`` (honest 503) and clients fall back to typing.
``FixtureTranscriber`` exists for offline tests and labeled fixture mode only.

Privacy (contracts/PRIVACY.md): audio and transcripts are never logged,
stored or included in error messages by this module.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

MAX_AUDIO_BYTES = 5 * 1024 * 1024  # ~60 s of opus/webm is far below this.
MAX_TRANSCRIPT_CHARS = 400  # DailyAnswer.text is 1-400 chars (contracts/protocol.ts).

ALLOWED_AUDIO_TYPES = frozenset(
    {"audio/webm", "audio/ogg", "audio/mp4", "audio/mpeg", "audio/wav", "audio/x-wav"}
)

ErrorCode = Literal["INVALID_INPUT", "PROVIDER_UNAVAILABLE", "RATE_LIMITED"]


class VoiceError(Exception):
    """Sanitized failure. ``message`` is safe to return to the requester."""

    def __init__(self, code: ErrorCode, message: str, retryable: bool) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable

    def to_api_error(self, request_id: str) -> dict:
        """Shape matching ApiError in contracts/protocol.ts."""
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                "requestId": request_id,
                "retryable": self.retryable,
            }
        }


@dataclass(frozen=True)
class AudioUpload:
    content_type: str
    data: bytes


class Transcriber(Protocol):
    """Speech-to-text adapter. Must honor its own timeout and raise VoiceError
    (or any exception, which is mapped to PROVIDER_UNAVAILABLE)."""

    mode: Literal["live", "fixture"]

    def transcribe(self, upload: AudioUpload, *, request_id: str) -> str: ...


def _base_type(content_type: str) -> str:
    return content_type.split(";", 1)[0].strip().lower()


def _looks_like(base: str, data: bytes) -> bool:
    """Cheap container signature check so arbitrary files are rejected."""
    if base == "audio/webm":
        return data[:4] == b"\x1a\x45\xdf\xa3"
    if base == "audio/ogg":
        return data[:4] == b"OggS"
    if base in ("audio/wav", "audio/x-wav"):
        return data[:4] == b"RIFF" and data[8:12] == b"WAVE"
    if base == "audio/mp4":
        return data[4:8] == b"ftyp"
    if base == "audio/mpeg":
        return data[:3] == b"ID3" or (len(data) > 1 and data[0] == 0xFF and data[1] & 0xE0 == 0xE0)
    return False


def validate_upload(content_type: str | None, data: bytes | None) -> AudioUpload:
    if not content_type or data is None:
        raise VoiceError("INVALID_INPUT", "An audio file is required.", False)
    base = _base_type(content_type)
    if base not in ALLOWED_AUDIO_TYPES:
        raise VoiceError("INVALID_INPUT", "Unsupported audio format.", False)
    if not data:
        raise VoiceError("INVALID_INPUT", "The recording is empty.", False)
    if len(data) > MAX_AUDIO_BYTES:
        raise VoiceError("INVALID_INPUT", "The recording is too long.", False)
    if not _looks_like(base, data):
        raise VoiceError("INVALID_INPUT", "The file is not valid audio.", False)
    return AudioUpload(content_type=base, data=data)


def transcribe_audio(
    content_type: str | None,
    data: bytes | None,
    transcriber: Transcriber,
    *,
    request_id: str,
) -> dict:
    """Validate, transcribe and return the public response body."""
    upload = validate_upload(content_type, data)
    try:
        text = transcriber.transcribe(upload, request_id=request_id)
    except VoiceError:
        raise
    except Exception:  # noqa: BLE001 - provider details must not leak
        raise VoiceError("PROVIDER_UNAVAILABLE", "Transcription is unavailable right now.", True) from None
    if not isinstance(text, str):
        raise VoiceError("PROVIDER_UNAVAILABLE", "Transcription is unavailable right now.", True)
    transcript = " ".join(text.split())[:MAX_TRANSCRIPT_CHARS]
    if not transcript:
        raise VoiceError("INVALID_INPUT", "No speech was detected. Try again or type instead.", False)
    return {"transcript": transcript}


class UnconfiguredTranscriber:
    """Default until a speech-to-text provider is verified. Honest 503."""

    mode: Literal["live", "fixture"] = "live"

    def transcribe(self, upload: AudioUpload, *, request_id: str) -> str:
        raise VoiceError(
            "PROVIDER_UNAVAILABLE",
            "Voice transcription isn't configured. Type your answer instead.",
            False,
        )


FIXTURE_TRANSCRIPT = "Synthetic transcript: mostly the dining hall, usually with headphones in."


class FixtureTranscriber:
    """TEST/FIXTURE ONLY. Ignores the audio and returns a canned sentence."""

    mode: Literal["live", "fixture"] = "fixture"

    def transcribe(self, upload: AudioUpload, *, request_id: str) -> str:
        return FIXTURE_TRANSCRIPT
