# server/providers: the single Muse adapter (owner: Adam)

Contract: `contracts/protocol.ts` 2.0.0 (`MusePort`, `MuseTask`, `MuseCallEvidence`, M1-M8 I/O).

Status (2026-11-13): **live-verified across all three Muse text models and every task (M1-M8), plus prototype M9/M10.** 285 capped calls on synthetic inputs through this adapter (about $1.21) are summarized in [docs/audits/2026-11-13-live-evals.md](../../docs/audits/2026-11-13-live-evals.md), with scripts and the counts-only cost ledger in [tests/providers/live_evals/](../../tests/providers/live_evals/). These are small samples (1-10 runs per cell): directional evidence, not benchmarks. Contract 2.2.0 (D014: M9 `activity_classification`, M10 `sensitivity_screen`, questionId and affinity for M3/M4) is **PROPOSED** and awaits ACKs.

## Live evidence (2.0.0 adapter, synthetic input)
| Date (UTC) | Task | Settings | Outcome | Provider-reported model | Latency |
| --- | --- | --- | --- | --- | --- |
| 2026-11-13T02:25Z | `clarify` (M2), prompt `clarify.smoke.v1` | `reasoning_effort=low`, 60 s x 2 attempts | ok on attempt 1; output passed the M2Out schema | `muse-spark-1.3` | 16.2 s |
| 2026-11-13T05:56Z | `event_nudge` (M7), prompt `event_nudge.v1`, inside Kai's composed app (role/kai-orchestration cad28cb) via `POST /api/v1/operator/rooms/{id}/nudge`; all other tasks scripted | `reasoning_effort=low`, live calls capped at 1 | 200; allowlisted `v-cafe`, `minAttendees` 3, posted once as `muse_nudge`; M1 on the nudge text was scripted, not live | `muse-spark-1.3` | 8.0 s |

Run with `python3 -m server.providers.smoke`. Evidence record: `{model: "muse-spark-1.3", source: "live", callType: "M2", latencyMs: 16237}`.

## Earlier live evidence (retired adapter, synthetic inputs, not evidence for 2.0.0)
| Date (UTC) | Task (retired) | Settings | Outcome | Provider-reported model | Latency |
| --- | --- | --- | --- | --- | --- |
| 2026-11-12T22:41Z | `extract_intent` | default effort ("high"), 30 s x 2 attempts | **timeout** on both attempts | - | 55.8 s total |
| 2026-11-12T22:42Z | `extract_intent` | `reasoning_effort=low`, 90 s x 1 | ok | `muse-spark-1.3` | 23.8 s |
| 2026-11-12T22:44Z | `rank_group` | `reasoning_effort=low`, 90 s x 1 | ok | `muse-spark-1.3` | 17.2 s |

Implication that still applies: use `MUSE_REASONING_EFFORT=low` and a 60 s per-attempt timeout. Wonder and Ember were not listed in the docs read and were not tested.

## Verified provider facts
Source: Meta's official Meta Model API docs at dev.meta.ai, read 2026-11-12 (`/docs/models.md`, `/docs/protocols/chat-completions`, `/docs/structured-output`, `/docs/error-handling`, `/docs/pricing-rate-limits`, `/docs/media-understanding`).

| Item | Documented value | Used here |
| --- | --- | --- |
| Endpoint | `POST https://api.meta.ai/v1/chat/completions` (OpenAI-compatible) | yes |
| Auth | `Authorization: Bearer <key>`; docs name the env var `MODEL_API_KEY` | `MUSE_API_KEY`, `MODEL_API_KEY` accepted |
| Models | GET /v1/models for the team key (2026-11-13): `muse-wonder-1.0` (preview, most capable), `muse-spark-1.3/1.2/1.1`, `muse-ember-1.0` (low cost), plus non-text models (`muse-image-1.0`, `muse-voice-transcribe-1.0`, `sam-3.1`) | default `muse-spark-1.3`; Wonder, Spark and Ember accepted; per-task choice in `router.py` |
| `-contributor` variants | Meta may train on prompts/responses | **rejected** by config (participant data) |
| Pricing | per 1M tokens in/out: Wonder $4/$20, Spark 1.3 $1.25/$4.25, Ember $0.10/$0.50 (dev.meta.ai/docs/pricing-rate-limits, read 2026-11-13); 3,000 RPM / 4M TPM per model | `pricing.py` estimates cost per call from reported usage |
| Structured output | `response_format: {type: "json_schema", json_schema: {name, schema, strict}}`; `strict` defaults false | sent with `strict: false`; local validation is authoritative |
| Response text | `choices[0].message.content`; `model` echoed | evidence uses the echoed model id |
| Roles | `developer` preferred over `system` | `developer` + `user` |
| Errors | 400/401/402/403/404/413/429(`Retry-After`)/500/503(`Retry-After`)/504 | mapped in `transport.classify_status` |
| Reasoning | Muse models always reason; Wonder/Ember document `minimal` to `max` (default `max`); Spark 1.3 accepted `minimal` and `max` live; `"none"` returns 400 | per-model allowlist `MODEL_EFFORTS`; reasoning tokens are about 95% of output |
| Audio | `input_audio` content parts (1.3 audio "not fully supported"); separate `muse-voice-transcribe-1.0` STT at `POST /v1/asr/transcribe` | not used here (Will owns transcription) |
| Timeouts | not stated | from the environment: 60 s/attempt and `reasoning_effort=low` by default (the settings every live check and formation timing run used); override with `MUSE_TIMEOUT_S` / `MUSE_REASONING_EFFORT`; routes set per-task timeouts |

Not verified: latency under real load (Ember stalled ~68 s on 3 of 10 burst calls; Wonder ranged 3-74 s), rate limits in practice, and whether `strict: true` accepts our schema keywords. Structured output held on 285 of 285 eval calls with `strict: false` plus local validation.

## Configuration
Copy [`muse.env.example`](muse.env.example) to `server/providers/muse.env` (git-ignored, mode 600) or set real environment variables, which take precedence. Server-only; never expose as `VITE_*`. With no key, `load_muse_config()` returns `None` and every call fails closed with `PROVIDER_UNAVAILABLE` (`kind: not_configured`). There is no silent fixture fallback.

Live smoke check (one paid `clarify` call on a synthetic answer; prints evidence only, never model text):
```sh
python3 -m server.providers.smoke   # exit 0 ok, 2 not configured/invalid, 1 provider error
```

## Port (Python form of `MusePort.run`)
```python
from server.providers import (MuseRequest, TaskRegistry, build_muse_adapter,
                              contract_spec, load_muse_config, MUSE_VOICE)

registry = TaskRegistry()
registry.register(contract_spec("constellation_naming", "naming.v1", MY_INSTRUCTIONS + MUSE_VOICE))
muse = build_muse_adapter(registry, load_muse_config())      # one per process (Kai composes)
result = await muse.run(MuseRequest(task="constellation_naming", request_id=request_id,
                                    prompt_version="naming.v1", payload={"sharedMeaning": "...", "size": 4}))
result.output    # dict validated against M5Out
result.evidence  # MuseCallEvidence {model, source, generatedAt, latencyMs, callType: "M5"}
```
`KeywordMusePort(muse).run(task=, requestId=, promptVersion=, payload=)` returns `{"output", "evidence"}` in the wire spelling.

| Task | Call | Prompt owner | Registered by |
| --- | --- | --- | --- |
| `safety_screen` | M1 | Patrik | `server/privacy` |
| `clarify` | M2 | Adam | `server.planning.register_planning_tasks` |
| `theme_discovery`, `constellation_formation`, `constellation_naming` | M3, M4, M5 | Rishi | `server/matching` |
| `question_generation`, `event_nudge` | M6, M7 | Adam | `server.planning` (steps 7 and 6) |
| `sky_narration` | M8 | Rishi | `server/matching` |

- `contract_spec(task, promptVersion, instructions)` attaches the contract's own input and output validators from [`contract.py`](contract.py). `tests/providers/test_contract_schemas.py` fails if they drift from `protocol.ts`.
- Only registered `(task, promptVersion)` pairs execute. The payload is validated against the input schema **before** any call; a field outside the contract (a name, a `playerId`) is rejected with `invalid_request`.
- The payload travels as JSON **data** in the user message after a fixed untrusted-data preamble. Instructions come only from the TaskSpec.
- Invalid JSON or schema-invalid output: exactly one retry, then `ProviderError(kind="malformed_output")`, `api_code` `PROVIDER_UNAVAILABLE`, `retryable` true. The adapter never invents an answer; the caller decides on a labeled fallback (for example "Fallback grouping").
- Timeout / 429 / 5xx: bounded by `MUSE_MAX_ATTEMPTS` (default 2) and the overall `deadline_s`, honoring `Retry-After`. Auth and 400 are not retried.
- Cancel by cancelling the awaiting asyncio task (the AbortSignal equivalent). Late results are discarded.
- Evidence: every successful call returns `MuseCallEvidence` and appends it (plus `requestId`) to `muse.evidence_log`, the source for `GET /operator/calls`. Failed calls add none.
- Telemetry sink receives only `requestId, task, callType, promptVersion, model, source, attempts, outcome, latencyMs`, plus `inputTokens, outputTokens, reasoningTokens` (summed across attempts) and `estCostUsd` when the provider reports usage, and `status` on errors. No payloads, prompts or outputs.
- `adapter.reasoning_trace` ([`trace.py`](trace.py)): one entry per call plus code verdicts `(stage, code, count)` noted by services; fixed vocabulary, no text; fixture runs say `replay`. Served by the PROPOSED `GET /operator/reasoning` once Kai passes it to `PlanningRuntime(trace=...)`.
- Malformed-output retries tell Muse which schema location failed (sanitized; never model or player text).

## Router ([`router.py`](router.py))
`build_muse_router(registry, config)` returns one MusePort that serves each task with its measured model (`MEASURED_ROUTES`): M1 Ember low (8 s, 1 attempt, then Spark), M2 Ember minimal (6 s, 1 attempt, then Spark), M5 and M8 Wonder low (12 s / 30 s, 1 attempt, then Ember; never Spark for M8), M6 and M7 Spark low (45 s, then Ember). M4 is routed to Ember (live checks in docs/audits/2026-11-13-live-evals.md, A2); M3 has no route yet and runs on the base model (audit #74). Fallback only on rate limit, outage, timeout or malformed output, never past the caller's `deadline_s`, and every fallback is noted in the trace. Shares one evidence log and trace across models. Override with `MUSE_ROUTES` via `parse_routes`. **Kai's composed app still builds a single-model adapter**; switching is one line in `server/app/weekly.py` (requested on #49).
- Semantic checks (ids in the pool, numbers equal to server counts, OutputGuard) stay with the calling owner. Pass a code-generated `correction` string on a re-ask; never put player text in it.
- [`voice.py`](voice.py) holds `MUSE_VOICE`, the shared style block for player-facing text. Style only; guards decide.

## Test double
`server.providers.fixture.FixtureMuse(registry, ScriptedTransport().queue(task, output_or_error, ...))` runs the same pipeline with scripted output, labeled `source: "replay"`, `model: "fixture:scripted-muse"`. Tests and visibly labeled replay mode only ("Replay of a saved cycle"); never in a live path.

## Tests
```sh
pytest tests/providers        # or: python3 -m unittest discover -s tests/providers -t .
```
Standard library only (Python 3.11+); no paid calls. `test_transport_http.py` runs the real HTTP transport against a local stub of the documented envelope, which proves wire handling, not live Muse access.
