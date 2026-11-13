"""Muse provider configuration (server-only).

Verified against Meta's official Meta Model API docs (dev.meta.ai, read
2026-11-12; see server/providers/README.md):
  - base URL https://api.meta.ai/v1, OpenAI-compatible POST /chat/completions
  - Authorization: Bearer <key>
  - model IDs muse-spark-1.3 (recommended), muse-spark-1.2, muse-spark-1.1
Live evidence for the 2.0.0 adapter is recorded in server/providers/README.md.

Environment (never commit real values; never expose via VITE_*):
  MUSE_API_KEY        provider key (MODEL_API_KEY accepted as the docs' name)
  MUSE_MODEL          default muse-spark-1.3
  MUSE_BASE_URL       default https://api.meta.ai/v1
  MUSE_TIMEOUT_S      per-attempt timeout, default 60 (the live-tested setting)
  MUSE_MAX_ATTEMPTS   default 2 (one bounded retry)
  MUSE_REASONING_EFFORT  low | medium | high, default low (the live-tested setting;
                      the provider's own default "high" timed out at 30 s live)
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
# Defaults applied when loading from the environment, so a deployed server that
# sets only MUSE_API_KEY runs with the settings every live check used.
ENV_DEFAULT_TIMEOUT_S = 60.0
ENV_DEFAULT_REASONING_EFFORT = "low"
REASONING_EFFORTS = frozenset({"low", "medium", "high"})  # "none" is rejected by the provider


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
        if self.reasoning_effort is not None and self.reasoning_effort not in REASONING_EFFORTS:
            raise ValueError("MUSE_REASONING_EFFORT must be one of low, medium, high")

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
        timeout_s=float(env.get("MUSE_TIMEOUT_S") or ENV_DEFAULT_TIMEOUT_S),
        max_attempts=int(env.get("MUSE_MAX_ATTEMPTS") or 2),
        reasoning_effort=env.get("MUSE_REASONING_EFFORT") or ENV_DEFAULT_REASONING_EFFORT,
    )


DEFAULT_ENV_FILE = os.path.join(os.path.dirname(__file__), "muse.env")


def load_env_file(path: str = DEFAULT_ENV_FILE, env: dict[str, str] | None = None) -> bool:
    """Load simple KEY=VALUE lines into the environment without overriding existing values.

    Local-development convenience only: ``muse.env`` is git-ignored. Deployed
    servers should set real environment variables instead. Returns False when
    the file does not exist.
    """
    target = os.environ if env is None else env
    try:
        with open(path, encoding="utf-8") as fh:
            lines = fh.readlines()
    except FileNotFoundError:
        return False
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip().removeprefix("export ").strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
            value = value[1:-1]
        if key and value and key not in target:
            target[key] = value
    return True
