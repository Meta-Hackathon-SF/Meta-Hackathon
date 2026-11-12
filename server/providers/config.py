"""Muse provider configuration (server-only).

Verified against Meta's official Meta Model API docs (dev.meta.ai, read
2026-11-12; see server/providers/README.md):
  - base URL https://api.meta.ai/v1, OpenAI-compatible POST /chat/completions
  - Authorization: Bearer <key>
  - model IDs muse-spark-1.3 (recommended), muse-spark-1.2, muse-spark-1.1
No live call has been verified from this repository yet.

Environment (never commit real values; never expose via VITE_*):
  MUSE_API_KEY        provider key (MODEL_API_KEY accepted as the docs' name)
  MUSE_MODEL          default muse-spark-1.3
  MUSE_BASE_URL       default https://api.meta.ai/v1
  MUSE_TIMEOUT_S      per-attempt timeout, default 30
  MUSE_MAX_ATTEMPTS   default 2 (one bounded retry)
  MUSE_REASONING_EFFORT  optional pass-through; unset = provider default
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Mapping

DEFAULT_BASE_URL = "https://api.meta.ai/v1"
DEFAULT_MODEL = "muse-spark-1.3"
# Standard-mode model IDs from the official model list. "-contributor" variants
# allow Meta to train on prompts, so they are rejected for participant data.
KNOWN_MODELS = frozenset({"muse-spark-1.3", "muse-spark-1.2", "muse-spark-1.1"})


@dataclass(frozen=True)
class MuseConfig:
    api_key: str = field(repr=False)
    model: str = DEFAULT_MODEL
    base_url: str = DEFAULT_BASE_URL
    timeout_s: float = 30.0
    max_attempts: int = 2
    reasoning_effort: str | None = None

    def __post_init__(self) -> None:
        if not self.api_key:
            raise ValueError("api_key is required")
        if self.model not in KNOWN_MODELS:
            raise ValueError(
                "MUSE_MODEL must be a standard-mode Muse Spark model id "
                f"({', '.join(sorted(KNOWN_MODELS))})"
            )
        if not self.base_url.startswith("https://"):
            raise ValueError("MUSE_BASE_URL must use https")
        if not (1.0 <= self.timeout_s <= 120.0):
            raise ValueError("MUSE_TIMEOUT_S must be within [1, 120]")
        if not (1 <= self.max_attempts <= 3):
            raise ValueError("MUSE_MAX_ATTEMPTS must be within [1, 3]")

    def describe(self) -> dict[str, object]:
        """Sanitized description safe for logs/health output (no key)."""
        return {
            "provider": "meta-model-api",
            "model": self.model,
            "baseUrl": self.base_url,
            "timeoutS": self.timeout_s,
            "maxAttempts": self.max_attempts,
            "reasoningEffort": self.reasoning_effort,
            "apiKeyConfigured": True,
        }


def load_muse_config(env: Mapping[str, str] | None = None) -> MuseConfig | None:
    """Return config, or None when no key is configured (adapter then fails closed)."""
    env = os.environ if env is None else env
    key = env.get("MUSE_API_KEY") or env.get("MODEL_API_KEY") or ""
    if not key:
        return None
    return MuseConfig(
        api_key=key,
        model=env.get("MUSE_MODEL") or DEFAULT_MODEL,
        base_url=(env.get("MUSE_BASE_URL") or DEFAULT_BASE_URL).rstrip("/"),
        timeout_s=float(env.get("MUSE_TIMEOUT_S") or 30.0),
        max_attempts=int(env.get("MUSE_MAX_ATTEMPTS") or 2),
        reasoning_effort=env.get("MUSE_REASONING_EFFORT") or None,
    )
