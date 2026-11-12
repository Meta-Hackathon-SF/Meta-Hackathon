# server/providers: Muse adapter (owner: Adam)

Status: **implemented, offline-tested, and live-verified for two tasks** (2026-11-12T22:42Z, `muse-spark-1.3`): one `extract_intent` smoke call and one `rank_group` call through matching's real `rank_with_muse`. Two single calls are not a latency or quality benchmark.

## Live evidence (sanitized, synthetic inputs)
| Date (UTC) | Task | Settings | Outcome | Provider-reported model | Latency |
| --- | --- | --- | --- | --- | --- |
| 2026-11-12T22:41Z | `extract_intent` | default effort ("high"), 30 s x 2 attempts | **timeout** on both attempts | - | 55.8 s total |
| 2026-11-12T22:42Z | `extract_intent` | `reasoning_effort=low`, 90 s x 1 | ok, 6/6 fields kept by validators | `muse-spark-1.3` | 23.8 s |
| 2026-11-12T22:44Z | `rank_group` | `reasoning_effort=low`, 90 s x 1 | ok, matching validator accepted | `muse-spark-1.3` | 17.2 s |

**Model in use: `muse-spark-1.3` (Muse Spark family), confirmed by the provider's echoed `model` field.** Wonder and Ember are not listed in the docs we read and were not tested. Implication: use `MUSE_REASONING_EFFORT=low` and a 60 s+ per-attempt timeout; a chain of sequential calls will not fit a 60 s journey target without parallelism or precomputation.

## Verified provider facts
Source: Meta's official Meta Model API docs at dev.meta.ai, read 2026-11-12 (`/docs/models.md`, `/docs/protocols/chat-completions`, `/docs/structured-output`, `/docs/error-handling`, `/docs/pricing-rate-limits`, `/docs/media-understanding`).

| Item | Documented value | Used here |
| --- | --- | --- |
| Endpoint | `POST https://api.meta.ai/v1/chat/completions` (OpenAI-compatible) | yes |
| Auth | `Authorization: Bearer <key>`; docs name the env var `MODEL_API_KEY` | `MUSE_API_KEY`, `MODEL_API_KEY` accepted |
| Models | `muse-spark-1.3` (recommended), `muse-spark-1.2`, `muse-spark-1.1` | default `muse-spark-1.3` |
| `-contributor` variants | Meta may train on prompts/responses | **rejected** by config (participant data) |
| Structured output | `response_format: {type: "json_schema", json_schema: {name, schema, strict}}`; `strict` defaults false | sent with `strict: false`; local validation is authoritative |
| Response text | `choices[0].message.content`; `model` echoed | evidence uses the echoed model id |
| Roles | `developer` preferred over `system` | `developer` + `user` |
| Errors | 400/401/402/403/404/413/429(`Retry-After`)/500/503(`Retry-After`)/504 | mapped in `transport.classify_status` |
| Reasoning | Muse Spark always reasons; default `reasoning_effort` "high"; `"none"` returns 400 | optional `MUSE_REASONING_EFFORT` pass-through |
| Audio | `input_audio` content parts (1.3 audio "not fully supported"); separate `muse-voice-transcribe-1.0` STT at `POST /v1/asr/transcribe` | not used here (Will owns transcription) |
| Timeouts | not stated | 30 s/attempt code default; example config uses 60 s with low effort (see live evidence) |

Not yet verified: actual latency, structured-output adherence on our schemas, rate limits for our team's key, and whether `strict: true` accepts our schema keywords.

## Configuration
Copy [`muse.env.example`](muse.env.example) outside Git. Server-only; never expose as `VITE_*`. Missing key means `load_muse_config()` returns `None` and every call fails closed with `PROVIDER_UNAVAILABLE` (`kind: not_configured`); there is no silent fixture fallback.

Local setup: put your key in `server/providers/muse.env` (git-ignored, mode 600; copy of the example). Real environment variables take precedence over the file.

Live smoke check (one paid call, synthetic transcript, sanitized output):
```sh
python3 -m server.providers.smoke   # exit 0 ok, 2 not configured/invalid, 1 provider error
```

## Port (Python form of `MusePort` in contracts/protocol.ts)
```python
from server.providers import TaskRegistry, TaskSpec, GenerateRequest, build_muse_adapter, load_muse_config

registry = TaskRegistry()
registry.register(TaskSpec(task="rank_group", prompt_version="rank-group.v1",
                           instructions="...", output_schema={...}, schema_name="rank_group"))
muse = build_muse_adapter(registry, load_muse_config())          # one per process (Kai composes)
result = await muse.generate(GenerateRequest(task="rank_group", request_id=ctx_request_id,
                                             prompt_version="rank-group.v1", payload={...}))
result.output    # dict validated against your output_schema
result.evidence  # ModelEvidence {model, source, generatedAt, latencyMs}
```
- Only registered `(task, promptVersion)` pairs execute; task must be one of the contract literals.
- Schemas use a validated JSON Schema subset (`schema.py`): objects must set `additionalProperties: false`.
- Payload is sent as JSON **data** in the user message after a fixed untrusted-data preamble; instructions come only from the TaskSpec. Keep payloads minimized (opaque IDs, approved fields).
- Retries: timeout / 429 / 5xx / malformed or schema-invalid output, bounded by `MUSE_MAX_ATTEMPTS` (default 2) and an overall deadline (`deadline_s`). Auth/400 are not retried.
- Cancel by cancelling the awaiting asyncio task (the AbortSignal equivalent). Late results are discarded.
- Errors are `ProviderError` with `.kind`, `.retryable`, `.api_code` (`PROVIDER_UNAVAILABLE`/`RATE_LIMITED`/`INVALID_INPUT`). Messages are sanitized and never include bodies.
- Telemetry sink receives only `requestId, task, promptVersion, model, attempts, outcome, latencyMs` (+`status` on errors).
- Semantic validation (IDs in the candidate pool, etc.) stays with the calling owner. Pass a code-generated `correction` string on a re-ask; never include user text in it.

## Matching (`rank_group`) port
`server/providers/rank_port.py` registers `rank_group.v1` (mirrors `server/matching/ranking.py`; `tests/planning/test_rank_port.py` fails on drift) and exposes the keyword-argument form matching calls:
```python
from server.providers.rank_port import build_live_rank_port, build_rank_port
port = build_live_rank_port()   # env vars, then git-ignored muse.env; RuntimeError if no key
out = await port.generate(task="rank_group", requestId=rid, promptVersion="rank_group.v1", payload=payload)
# -> {"output": {...}, "evidence": {model, source, generatedAt, latencyMs}}
```
Matching's own `parse_rank_output` stays authoritative. Matching's default 20 s `timeout_s` is below the observed 17 s live latency margin; pass `timeout_s>=60` for live runs.

## Test double
`server.providers.fixture.FixtureMuse(registry, ScriptedTransport().queue(task, output_or_error, ...))` runs the same pipeline with scripted output, labeled `source: "replay"`, `model: "fixture:scripted-muse"`. Use it in tests and visibly labeled fixture mode only; never in a live path.

## Tests
```sh
python3 -m unittest discover -s tests/planning -t .
```
Standard library only (Python 3.11+); no paid calls. `test_transport_http.py` runs the real HTTP transport against a local stub of the documented envelope.
