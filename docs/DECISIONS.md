# Shared decisions
## D001: Feature boundary
Accepted by explicit user direction: existing web/ is a mock Facebook shell. Group Quests gets a separate UI/framework under web/src/features/group-quests/. Preserve existing routes and host layout; Will owns minimal entry integration.

## D002: Workstream ownership
Accepted from the latest team split: Rishi matching, Adam planning, Will voice interaction, Patrik privacy, Kai orchestration. All five own technical systems and their UI components.

## D003: Initial protocol
Foundation proposal: contract version 1.0.0 in contracts/. Each producer/consumer should ACK at H0. Runtime validators and implementations remain pending.

## D004: Server baseline
Proposed: FastAPI + PostgreSQL/Supabase; no server selected or installed by this foundation. Kai + Patrik confirm auth/database configuration, Adam confirms provider integration. Record any changed implementation choice here before parallel backend work.

## D005: Muse provider configuration, extraction wire shape, fixture evidence label
ID / UTC timestamp: D005 / 2026-11-12 (Adam, role/adam-planning)
Decision and rationale:
1. Provider (informational, no contract change): Muse is reached through Meta's Meta Model API, OpenAI-compatible `POST https://api.meta.ai/v1/chat/completions`, `Authorization: Bearer`, default model `muse-spark-1.3`, structured output via `response_format.json_schema`. Verified from official dev.meta.ai docs on 2026-11-12; no live call verified yet. `-contributor` model variants are rejected because Meta may train on their prompts. See server/providers/README.md.
2. Additive wire shapes `IntentField`, `IntentDraft`, `ExtractionResult` for `POST /intents/extract` (protocol.ts "PROPOSED (D005)" section). The draft carries no identity/consent/version fields; `timeZone` and `currency` come from the community. Missing facts are listed with fixed server questions, never invented.
3. Additive proposal: allow `ModelEvidence.source = "fixture"` so scripted test doubles are not labeled replay. Interim (until ACK): fixtures use `source: "replay"` with a `model` prefixed `fixture:`; UIs should treat that prefix as fixture.
4. Python MusePort form: `await muse.generate(GenerateRequest(task, request_id, prompt_version, payload, deadline_s?, correction?)) -> GenerateResult(output, evidence, attempts)`; asyncio cancellation replaces AbortSignal. Each owner registers its own `TaskSpec` (instructions + output schema) for its task; the adapter executes only registered (task, promptVersion) pairs.
5. Packaging (Kai to confirm): planning/provider code is standard-library-only Python 3.11+, importable as `server.providers` / `server.planning` with `server/` as a PEP 420 namespace (no shared `server/__init__.py` added). Offline tests: `python3 -m unittest discover -s tests/planning -t .`.
Owner / affected producers and consumers: Adam (producer). Will (renders ExtractionResult), Patrik (persists confirmed intent; consent check input), Rishi (MusePort consumer; registers rank_group spec), Kai (route registration, server composition, manifests).
Status (proposed or accepted): proposed. Items 2-3 need Will + Patrik ACK; item 3 needs all UI owners; items 4-5 need Rishi + Kai ACK.
ACK evidence: pending.
Contract version / migration: additive; CONTRACT_VERSION stays 1.0.0 until ACK, then 1.1.0. No migration.
Verification: tests/planning (33 offline tests, fixture transport + local HTTP stub). Live: pending credentials (`python3 -m server.providers.smoke`).

## Change template
ID / UTC timestamp:
Decision and rationale:
Owner / affected producers and consumers:
Status (proposed or accepted):
ACK evidence:
Contract version / migration:
Verification:
