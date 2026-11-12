# adam handoff
- Owner: adam · Branch: `role/adam-planning` · Shared contract: 1.0.0 (+ D005 proposed additive)
- Updated: 2026-11-12T21:15Z
- Current phase: **P1 complete (fixture-verified)**; P0 provider docs verified, live call pending credentials. Next: P2 planning.
- Status: verified offline / blocked on credentials for live evidence

## Completed deliverables
- P0: Muse provider facts verified from official dev.meta.ai docs (endpoint, auth, model ids, structured output, errors, audio/STT). Sanitized notes: `server/providers/README.md`; example config `server/providers/muse.env.example`.
- P1: `server/providers/` bounded MusePort adapter (task allowlist, timeout + deadline, cancellation, bounded retry incl. Retry-After, local JSON-schema validation, sanitized telemetry/evidence), stdlib HTTP transport for `/chat/completions`, `FixtureMuse` test double, live smoke command.
- P1: `server/planning/` intent extraction (quote-verified values, community allowlists, deterministic bounds, missing-field questions, consent fail-closed) and runtime validators for every contract shape at the planning boundary (`wire.py`).

## Changed interfaces and files
- New: `server/providers/*`, `server/planning/*`, `tests/planning/*`.
- Shared (claimed): `contracts/protocol.ts` appended "PROPOSED (D005)" `IntentField`/`IntentDraft`/`ExtractionResult`; `docs/DECISIONS.md` D005. No existing type changed; CONTRACT_VERSION unchanged.
- Python port: `await muse.generate(GenerateRequest(...)) -> GenerateResult(output, evidence, attempts)`; owners register a `TaskSpec` per task.

## Checks run + actual result
- `python3 -m unittest discover -s tests/planning -t .` → 33 tests OK (Python 3.13.0, macOS).
  Covers: malformed JSON retry, schema extra field, auth no-retry, 429 Retry-After, deadline, timeout, cancellation, telemetry has no payload/key, oversize payload, unknown task, not-configured fail-closed, fixture never labeled live, documented HTTP envelope/status mapping via local stub, quote verification, area allowlist, past/far/short/unzoned windows, budget/duration bounds, prompt injection (extra `consent` field; absurd budget; unknown area), consent missing/revoked/other community, invalid transcripts, provider outage.
- `python3 -m server.providers.smoke` without key → `{"status":"not_configured"}` exit 2 (fails closed).

## Fixture versus live evidence
All results above are fixture/stub evidence. **No live Muse call has been made.** No latency or quality numbers exist yet.

## Next consumer + exact action
- **Rishi:** register a `TaskSpec(task="rank_group", prompt_version=..., output_schema=...)` in `server/matching/` and test with `FixtureMuse`; see `server/providers/README.md`. ACK D005 item 4.
- **Will:** render `ExtractionResult` (`server/planning/README.md` example) in onboarding; edit fields; ask `questions`; submit confirmed fields to Patrik. ACK D005 items 2-3.
- **Patrik:** ACK the draft excludes identity/consent; `PUT /intents/me` owns versioning. Provide `Consent` dict to the extract route.
- **Kai:** register `POST /api/v1/intents/extract` using `IntentExtractor`, build one `MuseAdapter` per process via `build_muse_adapter(registry, load_muse_config())`; confirm D005 item 5 (namespace `server` package, stdlib-only).

## Blocked on + owner
- Live Muse evidence: needs `MUSE_API_KEY` from the team/organizers (Adam to run smoke once provided).
- Approved venue catalog source (needed for P2): owner unassigned. Proposal: planning ships a labeled synthetic catalog fixture until Kai/Patrik pick a table.

## Next independent task
P2: `PlanningPort.plan` with deterministic feasibility pre-check (time ∩ venue hours ∩ budget ∩ duration), Muse choice of venue/time/activity, validation + allowlisted public rationale; planning proposal UI under `web/src/features/group-quests/planning/`.
