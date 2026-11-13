"""Offline tests for server/voice. No provider or network is used.

Run from the repository root:
    python -m pytest tests/voice
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from server.voice import (  # noqa: E402
    MAX_AUDIO_BYTES,
    MAX_TRANSCRIPT_CHARS,
    AudioUpload,
    FixtureTranscriber,
    UnconfiguredTranscriber,
    VoiceError,
    transcribe_audio,
    validate_upload,
)

WEBM = b"\x1a\x45\xdf\xa3" + b"\x00" * 64
OGG = b"OggS" + b"\x00" * 64
WAV = b"RIFF" + b"\x00\x00\x00\x00" + b"WAVE" + b"\x00" * 32
MP4 = b"\x00\x00\x00\x18ftypM4A " + b"\x00" * 32
MP3 = b"ID3" + b"\x00" * 32


class StubTranscriber:
    mode = "live"

    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.calls = 0

    def transcribe(self, upload: AudioUpload, *, request_id: str) -> str:
        self.calls += 1
        if self.error:
            raise self.error
        return self.result


class ValidateUploadTests(unittest.TestCase):
    def test_accepts_each_supported_container(self):
        for content_type, data in [
            ("audio/webm;codecs=opus", WEBM),
            ("audio/ogg", OGG),
            ("audio/wav", WAV),
            ("audio/mp4", MP4),
            ("audio/mpeg", MP3),
        ]:
            with self.subTest(content_type=content_type):
                upload = validate_upload(content_type, data)
                self.assertEqual(upload.content_type, content_type.split(";")[0])

    def test_rejects_missing_empty_oversized_unsupported_and_spoofed(self):
        cases = [
            (None, WEBM),
            ("audio/webm", None),
            ("audio/webm", b""),
            ("audio/webm", WEBM[:4] + b"\x00" * MAX_AUDIO_BYTES),
            ("video/webm", WEBM),
            ("text/plain", b"hello"),
            ("audio/webm", b"<script>alert(1)</script>"),
            ("audio/wav", b"RIFF\x00\x00\x00\x00AVI "),
        ]
        for content_type, data in cases:
            with self.subTest(content_type=content_type, size=None if data is None else len(data)):
                with self.assertRaises(VoiceError) as ctx:
                    validate_upload(content_type, data)
                self.assertEqual(ctx.exception.code, "INVALID_INPUT")
                self.assertFalse(ctx.exception.retryable)


class TranscribeAudioTests(unittest.TestCase):
    def test_returns_normalized_transcript(self):
        stub = StubTranscriber("  dining   hall\n with headphones  ")
        self.assertEqual(
            transcribe_audio("audio/webm", WEBM, stub, request_id="r1"),
            {"transcript": "dining hall with headphones"},
        )

    def test_invalid_upload_never_reaches_provider(self):
        stub = StubTranscriber("x")
        with self.assertRaises(VoiceError):
            transcribe_audio("text/plain", b"x", stub, request_id="r1")
        self.assertEqual(stub.calls, 0)

    def test_truncates_long_transcripts(self):
        stub = StubTranscriber("a" * (MAX_TRANSCRIPT_CHARS + 50))
        result = transcribe_audio("audio/ogg", OGG, stub, request_id="r1")
        self.assertEqual(len(result["transcript"]), MAX_TRANSCRIPT_CHARS)

    def test_silence_is_an_input_error(self):
        with self.assertRaises(VoiceError) as ctx:
            transcribe_audio("audio/ogg", OGG, StubTranscriber("   "), request_id="r1")
        self.assertEqual(ctx.exception.code, "INVALID_INPUT")

    def test_provider_exception_is_sanitized(self):
        secret = "provider said: key=sk-123 transcript='my private answer'"
        stub = StubTranscriber(error=RuntimeError(secret))
        with self.assertRaises(VoiceError) as ctx:
            transcribe_audio("audio/webm", WEBM, stub, request_id="r9")
        err = ctx.exception
        self.assertEqual(err.code, "PROVIDER_UNAVAILABLE")
        self.assertTrue(err.retryable)
        body = err.to_api_error("r9")
        self.assertNotIn("sk-123", str(body))
        self.assertNotIn("private answer", str(body))
        self.assertIsNone(err.__cause__)
        self.assertEqual(body["error"]["requestId"], "r9")

    def test_non_string_provider_output_is_rejected(self):
        with self.assertRaises(VoiceError) as ctx:
            transcribe_audio("audio/webm", WEBM, StubTranscriber({"text": "x"}), request_id="r1")
        self.assertEqual(ctx.exception.code, "PROVIDER_UNAVAILABLE")

    def test_unconfigured_transcriber_is_honest_and_not_retryable(self):
        with self.assertRaises(VoiceError) as ctx:
            transcribe_audio("audio/webm", WEBM, UnconfiguredTranscriber(), request_id="r1")
        self.assertEqual(ctx.exception.code, "PROVIDER_UNAVAILABLE")
        self.assertFalse(ctx.exception.retryable)

    def test_fixture_transcriber_is_labeled_and_ignores_audio(self):
        fixture = FixtureTranscriber()
        self.assertEqual(fixture.mode, "fixture")
        a = transcribe_audio("audio/webm", WEBM, fixture, request_id="r1")
        b = transcribe_audio("audio/ogg", OGG, fixture, request_id="r2")
        self.assertEqual(a, b)
        self.assertTrue(a["transcript"].startswith("Synthetic transcript"))
        self.assertLessEqual(len(a["transcript"]), MAX_TRANSCRIPT_CHARS)


if __name__ == "__main__":
    unittest.main()
