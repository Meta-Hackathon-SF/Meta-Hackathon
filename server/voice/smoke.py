"""One live speech-to-text call, for verifying the Muse adapter with a real key.

    python -m server.voice.smoke [path/to/clip.wav]

Makes ONE paid provider call. Without a path it sends a generated one-second
tone (synthetic, no speech), which proves auth, the multipart format and the
response envelope; an empty transcript is the expected result for a tone.
With a path, the file must be mono 16-bit PCM WAV at 16 or 24 kHz; use a
synthetic recording, never a participant's.

Prints status and timing only. The transcript text is never printed.
Exit codes: 0 ok, 2 not configured or invalid input, 1 provider error.
"""

from __future__ import annotations

import math
import struct
import sys
import time

from .muse_stt import MuseTranscriber, load_muse_stt_config
from .transcription import AudioUpload, VoiceError


def tone_wav(seconds: float = 1.0, rate: int = 16000, hz: float = 440.0) -> bytes:
    """Synthetic mono 16-bit PCM WAV."""
    count = int(seconds * rate)
    samples = b"".join(
        struct.pack("<h", int(8000 * math.sin(2 * math.pi * hz * i / rate))) for i in range(count)
    )
    header = b"RIFF" + struct.pack("<I", 36 + len(samples)) + b"WAVE"
    fmt = b"fmt " + struct.pack("<IHHIIHH", 16, 1, 1, rate, rate * 2, 2, 16)
    return header + fmt + b"data" + struct.pack("<I", len(samples)) + samples


def main(argv: list[str]) -> int:
    try:
        config = load_muse_stt_config()
    except ValueError as exc:
        print(f"invalid configuration: {exc}")
        return 2
    if config is None:
        print("not configured: set MUSE_API_KEY (or MODEL_API_KEY) in the environment")
        return 2
    if len(argv) > 1:
        with open(argv[1], "rb") as handle:
            data = handle.read()
    else:
        data = tone_wav()
    print(f"config: {config.describe()}")
    started = time.monotonic()
    try:
        text = MuseTranscriber(config).transcribe(AudioUpload("audio/wav", data), request_id="smoke")
    except VoiceError as exc:
        print(f"failed: {exc.code} retryable={exc.retryable} after {time.monotonic() - started:.1f}s")
        return 2 if exc.code == "INVALID_INPUT" else 1
    elapsed = time.monotonic() - started
    print(f"ok: transcript of {len(text)} characters ({len(text.split())} words) in {elapsed:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
