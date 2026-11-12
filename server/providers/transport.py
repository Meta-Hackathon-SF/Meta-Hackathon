"""HTTP transport for Meta Model API Chat Completions (stdlib only).

Request/response shape follows dev.meta.ai/docs/protocols/chat-completions and
dev.meta.ai/docs/structured-output (read 2026-11-12):
  POST {base}/chat/completions
  {"model", "messages":[{"role":"developer"|"user", "content"}],
   "response_format":{"type":"json_schema","json_schema":{"name","schema","strict"}},
   "max_completion_tokens", "temperature", "reasoning_effort"?}
  text at choices[0].message.content; model id echoed at "model".

The transport returns the raw text and never logs bodies. urllib runs in a
worker thread; the socket timeout bounds that thread even when the awaiting
task is cancelled (the late result is discarded).
"""
from __future__ import annotations

import asyncio
import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Protocol

from .config import MuseConfig
from .errors import ProviderError

MAX_RESPONSE_BYTES = 1_000_000


@dataclass(frozen=True)
class ChatRequest:
    developer: str
    user: str
    schema_name: str
    schema: dict[str, Any]
    max_output_tokens: int
    temperature: float | None
    timeout_s: float


@dataclass(frozen=True)
class ChatResponse:
    text: str
    model: str | None


class ChatTransport(Protocol):
    async def complete(self, request: ChatRequest) -> ChatResponse: ...


def _retry_after(headers: Any) -> float | None:
    if headers is None:
        return None
    raw = headers.get("Retry-After")
    if not raw:
        return None
    try:
        return max(0.0, float(raw))
    except ValueError:
        return None


def classify_status(status: int, retry_after: float | None) -> ProviderError:
    """Map documented HTTP statuses to sanitized errors (dev.meta.ai/docs/error-handling)."""
    if status == 429:
        return ProviderError("rate_limited", "provider rate limited", status=status, retry_after_s=retry_after)
    if status in (401, 402, 403):
        return ProviderError("auth", "provider rejected credentials or permission", status=status)
    if status in (400, 404, 413, 422):
        return ProviderError("invalid_request", "provider rejected the request", status=status)
    if status == 504:
        return ProviderError("timeout", "provider gateway timeout", status=status, retry_after_s=retry_after)
    return ProviderError("unavailable", "provider unavailable", status=status, retry_after_s=retry_after)


class MetaChatCompletionsTransport:
    def __init__(self, config: MuseConfig) -> None:
        self._config = config

    def _body(self, req: ChatRequest) -> bytes:
        body: dict[str, Any] = {
            "model": self._config.model,
            "messages": [
                {"role": "developer", "content": req.developer},
                {"role": "user", "content": req.user},
            ],
            "response_format": {
                "type": "json_schema",
                # strict is documented as optional, default false; local
                # validation is authoritative either way.
                "json_schema": {"name": req.schema_name, "schema": req.schema, "strict": False},
            },
            "max_completion_tokens": req.max_output_tokens,
        }
        if req.temperature is not None:
            body["temperature"] = req.temperature
        if self._config.reasoning_effort:
            body["reasoning_effort"] = self._config.reasoning_effort
        return json.dumps(body, separators=(",", ":")).encode("utf-8")

    def _send(self, req: ChatRequest) -> ChatResponse:
        http_req = urllib.request.Request(
            f"{self._config.base_url}/chat/completions",
            data=self._body(req),
            method="POST",
            headers={
                "Authorization": f"Bearer {self._config.api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "group-quests-server",
            },
        )
        try:
            with urllib.request.urlopen(http_req, timeout=req.timeout_s) as resp:  # noqa: S310 - https enforced in config
                raw = resp.read(MAX_RESPONSE_BYTES + 1)
        except urllib.error.HTTPError as exc:
            raise classify_status(exc.code, _retry_after(exc.headers)) from None
        except TimeoutError:
            raise ProviderError("timeout", "provider request timed out") from None
        except (urllib.error.URLError, OSError):
            raise ProviderError("unavailable", "provider unreachable") from None
        if len(raw) > MAX_RESPONSE_BYTES:
            raise ProviderError("malformed_output", "provider response too large")
        return parse_chat_completion(raw)

    async def complete(self, request: ChatRequest) -> ChatResponse:
        return await asyncio.wait_for(
            asyncio.to_thread(self._send, request), timeout=request.timeout_s + 1.0
        )


def parse_chat_completion(raw: bytes) -> ChatResponse:
    try:
        doc = json.loads(raw)
        choice = doc["choices"][0]
        content = choice["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError):
        raise ProviderError("malformed_output", "unexpected provider response envelope") from None
    if not isinstance(content, str):
        raise ProviderError("malformed_output", "provider returned no text content")
    if choice.get("finish_reason") == "length":
        raise ProviderError("malformed_output", "provider output truncated")
    model = doc.get("model") if isinstance(doc.get("model"), str) else None
    return ChatResponse(text=content, model=model)
