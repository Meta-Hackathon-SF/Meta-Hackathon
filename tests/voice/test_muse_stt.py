"""Offline tests for the Muse speech-to-text adapter. A fake sender stands in
for the provider: no network, no key, no live call."""

import json
import re
import struct

import pytest

from server.voice import UnconfiguredTranscriber, VoiceError, transcribe_audio
from server.voice.muse_stt import (
    MuseSttConfig,
    MuseTranscriber,
    build_transcriber,
    inspect_wav,
    load_muse_stt_config,
)
from server.voice.smoke import tone_wav

KEY = "test-key-not-real"


def wav(seconds=1.0, rate=16000, channels=1, bits=16, audio_format=1) -> bytes:
    frame = channels * bits // 8
    samples = b"\x01" * (int(seconds * rate) * frame)
    fmt = struct.pack("<IHHIIHH", 16, audio_format, channels, rate, rate * frame, frame, bits)
    return b"RIFF" + struct.pack("<I", 36 + len(samples)) + b"WAVE" + b"fmt " + fmt + b"data" + struct.pack("<I", len(samples)) + samples


class FakeSender:
    def __init__(self, status=200, body=None, error=None):
        self.status = status
        self.body = json.dumps({"sessionId": "s", "transcript": "hello there", "audioDurationMs": 1000, "turns": []}).encode() if body is None else body
        self.error = error
        self.calls = []

    def __call__(self, url, headers, body, timeout_s):
        self.calls.append((url, headers, body, timeout_s))
        if self.error:
            raise self.error
        return self.status, self.body


def transcriber(sender, **config):
    return MuseTranscriber(MuseSttConfig(api_key=KEY, **config), send=sender)


def test_request_matches_the_documented_multipart_format():
    sender = FakeSender()
    clip = wav()
    result = transcribe_audio("audio/wav", clip, transcriber(sender), request_id="r1")
    assert result == {"transcript": "hello there"}
    (url, headers, body, timeout_s), = sender.calls
    assert re.fullmatch(r"https://api\.meta\.ai/v1/asr/transcribe\?sessionId=cst-[0-9a-f]{32}", url)
    assert headers["Authorization"] == f"Bearer {KEY}" and headers["Accept"] == "application/json"
    boundary = re.fullmatch(r"multipart/form-data; boundary=(cst-[0-9a-f]{32})", headers["Content-Type"]).group(1)
    parts = body.split(b"--" + boundary.encode())
    assert len(parts) == 4 and parts[0] == b"" and parts[3] == b"--\r\n"
    head, _, settings = parts[1].strip(b"\r\n").partition(b"\r\n\r\n")
    assert b'name="request"' in head and b"application/json" in head
    assert json.loads(settings) == {
        "model": "muse-voice-transcribe-1.0", "audioEncoding": "WAV", "mode": "PUSH_TO_TALK", "languageBias": ["English"],
    }
    head, _, audio = parts[2][2:-2].partition(b"\r\n\r\n")
    assert b'name="audio"' in head and b"audio/wav" in head and audio == clip
    assert timeout_s == 30.0
    assert KEY.encode() not in body and b"r1" not in body  # no key or request id in the payload


def test_two_calls_use_different_random_session_ids():
    sender = FakeSender()
    stt = transcriber(sender)
    stt.transcribe_ids = [transcribe_audio("audio/wav", wav(), stt, request_id="same") for _ in range(2)]
    assert sender.calls[0][0] != sender.calls[1][0]


@pytest.mark.parametrize(
    "clip",
    [
        wav(rate=48000),            # wrong sample rate
        wav(channels=2),            # stereo
        wav(bits=8),                # not 16-bit
        wav(audio_format=3),        # float PCM
        wav(seconds=70),            # too long
        wav(seconds=0.05),          # effectively empty
        b"RIFF\x00\x00\x00\x00WAVE" + b"\x00" * 40,  # WAV signature, no fmt/data
    ],
)
def test_unsupported_wav_never_reaches_the_provider(clip):
    sender = FakeSender()
    with pytest.raises(VoiceError) as exc:
        transcribe_audio("audio/wav", clip, transcriber(sender), request_id="r1")
    assert exc.value.code == "INVALID_INPUT" and sender.calls == []


def test_non_wav_recordings_are_rejected_before_the_provider():
    sender = FakeSender()
    webm = b"\x1a\x45\xdf\xa3" + b"\x00" * 64
    with pytest.raises(VoiceError) as exc:
        transcribe_audio("audio/webm", webm, transcriber(sender), request_id="r1")
    assert exc.value.code == "INVALID_INPUT" and sender.calls == []


def test_24khz_is_accepted_and_long_transcripts_are_capped():
    sender = FakeSender(body=json.dumps({"transcript": "word " * 200}).encode())
    result = transcribe_audio("audio/wav", wav(rate=24000), transcriber(sender), request_id="r1")
    assert len(result["transcript"]) == 400


@pytest.mark.parametrize(
    ("status", "code", "retryable"),
    [
        (400, "INVALID_INPUT", False),
        (413, "INVALID_INPUT", False),
        (401, "PROVIDER_UNAVAILABLE", False),
        (403, "PROVIDER_UNAVAILABLE", False),
        (406, "PROVIDER_UNAVAILABLE", False),
        (429, "RATE_LIMITED", True),
        (500, "PROVIDER_UNAVAILABLE", True),
        (503, "PROVIDER_UNAVAILABLE", True),
    ],
)
def test_provider_statuses_map_to_sanitized_errors(status, code, retryable):
    sender = FakeSender(status=status, body=b'{"message":"secret provider detail"}')
    with pytest.raises(VoiceError) as exc:
        transcribe_audio("audio/wav", wav(), transcriber(sender), request_id="r1")
    assert (exc.value.code, exc.value.retryable) == (code, retryable)
    assert "secret" not in json.dumps(exc.value.to_api_error("r1"))


@pytest.mark.parametrize("body", [b"not json", b"[]", b'{"text":"x"}', b'{"transcript":7}', b"x" * (300 * 1024)])
def test_malformed_provider_responses_fail_closed(body):
    with pytest.raises(VoiceError) as exc:
        transcribe_audio("audio/wav", wav(), transcriber(FakeSender(body=body)), request_id="r1")
    assert exc.value.code == "PROVIDER_UNAVAILABLE"


def test_network_failure_never_leaks_the_key_or_cause():
    sender = FakeSender(error=RuntimeError(f"connect failed with Authorization: Bearer {KEY}"))
    with pytest.raises(VoiceError) as exc:
        transcribe_audio("audio/wav", wav(), transcriber(sender), request_id="r1")
    assert exc.value.code == "PROVIDER_UNAVAILABLE" and exc.value.retryable
    assert KEY not in json.dumps(exc.value.to_api_error("r1")) and exc.value.__cause__ is None


def test_silence_from_the_provider_is_an_input_error():
    with pytest.raises(VoiceError) as exc:
        transcribe_audio("audio/wav", wav(), transcriber(FakeSender(body=b'{"transcript":"  "}')), request_id="r1")
    assert exc.value.code == "INVALID_INPUT"


def test_config_loading_and_fail_closed_default():
    assert load_muse_stt_config({}) is None
    assert isinstance(build_transcriber({}), UnconfiguredTranscriber)
    config = load_muse_stt_config({"MODEL_API_KEY": KEY, "MUSE_BASE_URL": "https://example.test/v1/"})
    assert config.base_url == "https://example.test/v1" and config.model == "muse-voice-transcribe-1.0"
    assert KEY not in repr(config) and KEY not in json.dumps(config.describe())
    live = build_transcriber({"MUSE_API_KEY": KEY})
    assert isinstance(live, MuseTranscriber) and live.mode == "live"
    for bad in ({"base_url": "http://insecure.test"}, {"model": "muse-voice-transcribe-1.0-contributor"}, {"timeout_s": 0.1}):
        with pytest.raises(ValueError):
            MuseSttConfig(api_key=KEY, **bad)
    with pytest.raises(ValueError):
        MuseSttConfig(api_key="")


def test_smoke_tone_is_a_valid_provider_clip():
    info = inspect_wav(tone_wav())
    assert (info.sample_rate, info.channels, info.bits_per_sample) == (16000, 1, 16)
    assert abs(info.seconds - 1.0) < 0.01
