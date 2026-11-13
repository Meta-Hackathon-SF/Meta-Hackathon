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
import socket
import ssl
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any, Protocol

from .config import MuseConfig
from .errors import ProviderError

MAX_RESPONSE_BYTES = 1_000_000
_POOL = ThreadPoolExecutor(max_workers=64, thread_name_prefix="muse-http")


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
    # Token counts reported by the provider (counts only): inputTokens,
    # outputTokens, reasoningTokens. None when the envelope has no usage.
    usage: dict[str, int] | None = None


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


def network_cause(exc: BaseException) -> str:
    """Fixed, non-sensitive cause label for a failed connection (no hostnames, bodies or keys)."""
    reason = getattr(exc, "reason", exc)
    if isinstance(reason, ssl.SSLCertVerificationError):
        return "tls_certificate_verify_failed"
    if isinstance(reason, ssl.SSLError):
        return "tls_error"
    if isinstance(reason, socket.gaierror):
        return "dns_lookup_failed"
    if isinstance(reason, ConnectionRefusedError):
        return "connection_refused"
    if isinstance(reason, ConnectionResetError):
        return "connection_reset"
    if isinstance(reason, (TimeoutError, socket.timeout)):
        return "connect_timeout"
    if isinstance(reason, OSError) and reason.errno is not None:
        return f"os_error_{reason.errno}"
    return "network_error"


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
                "User-Agent": "constellations-server",
            },
        )
        try:
            with urllib.request.urlopen(http_req, timeout=req.timeout_s) as resp:  # noqa: S310 - https enforced in config
                raw = resp.read(MAX_RESPONSE_BYTES + 1)
        except urllib.error.HTTPError as exc:
            raise classify_status(exc.code, _retry_after(exc.headers)) from None
        except TimeoutError:
            raise ProviderError("timeout", "provider request timed out") from None
        except (urllib.error.URLError, OSError) as exc:
            cause = network_cause(exc)
            if cause == "connect_timeout":  # urllib wraps socket timeouts in URLError
                raise ProviderError("timeout", "provider connect timed out") from None
            raise ProviderError("unavailable", f"provider unreachable ({cause})") from None
        if len(raw) > MAX_RESPONSE_BYTES:
            raise ProviderError("malformed_output", "provider response too large")
        return parse_chat_completion(raw)

    async def complete(self, request: ChatRequest) -> ChatResponse:
        # Dedicated pool: the default to_thread pool (min(32, cpu+4)) queued bursts on
        # small hosts, and queue time ate into the model timeout (audit 2: a false
        # Ember timeout at 9 s on a 2-vCPU emulation).
        loop = asyncio.get_running_loop()
        return await asyncio.wait_for(
            loop.run_in_executor(_POOL, self._send, request), timeout=request.timeout_s + 1.0
        )


def parse_chat_completion(raw: bytes) -> ChatResponse:
    try:
        doc = json.loads(raw)
        choice = doc["choices"][0]
        content = choice["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError):
        raise ProviderError("malformed_output", "unexpected provider response envelope") from None
    if choice.get("finish_reason") == "length":
        # Reasoning tokens count toward max_completion_tokens; raise the TaskSpec budget.
        raise ProviderError("malformed_output", "provider output truncated (completion token budget exhausted)")
    if not isinstance(content, str):
        raise ProviderError("malformed_output", "provider returned no text content")
    model = doc.get("model") if isinstance(doc.get("model"), str) else None
    return ChatResponse(text=content, model=model, usage=_usage(doc.get("usage")))


def _count(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def _usage(raw: Any) -> dict[str, int] | None:
    """OpenAI-style usage reduced to three non-negative integer counts."""
    if not isinstance(raw, dict):
        return None
    details = raw.get("completion_tokens_details")
    out = {
        "inputTokens": _count(raw.get("prompt_tokens")),
        "outputTokens": _count(raw.get("completion_tokens")),
        "reasoningTokens": _count(details.get("reasoning_tokens")) if isinstance(details, dict) else None,
    }
    kept = {k: v for k, v in out.items() if v is not None}
    return kept or None
