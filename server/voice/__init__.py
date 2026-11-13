"""Voice capture boundary (owner: Will). See transcription.py."""

from .muse_stt import MuseSttConfig, MuseTranscriber, build_transcriber, load_muse_stt_config
from .transcription import (
    ALLOWED_AUDIO_TYPES,
    MAX_AUDIO_BYTES,
    MAX_TRANSCRIPT_CHARS,
    AudioUpload,
    FixtureTranscriber,
    Transcriber,
    UnconfiguredTranscriber,
    VoiceError,
    transcribe_audio,
    validate_upload,
)

__all__ = [
    "ALLOWED_AUDIO_TYPES",
    "MAX_AUDIO_BYTES",
    "MAX_TRANSCRIPT_CHARS",
    "AudioUpload",
    "FixtureTranscriber",
    "MuseSttConfig",
    "MuseTranscriber",
    "Transcriber",
    "UnconfiguredTranscriber",
    "VoiceError",
    "build_transcriber",
    "load_muse_stt_config",
    "transcribe_audio",
    "validate_upload",
]
