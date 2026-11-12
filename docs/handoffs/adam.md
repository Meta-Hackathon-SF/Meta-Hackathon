# adam handoff
- Owner: adam · Branch: `role/adam-planning` · Shared contract: 1.0.0 (+ D005 proposed additive)
- Updated: 2026-11-12T21:35Z
- Current phase: **P1 done; P2-P4 planning logic + planning UI done against fixtures.** Live Muse evidence and integration with the other owners (the actual P2 gate) are pending.
- PR: draft https://github.com/willapat/Meta-Hackathon/pull/8 (awaiting D005 ACKs)
- Status: verified offline. Live evidence is blocked on credentials; integration is blocked on the server scaffold (Kai) and snapshots (Patrik/Rishi).

## Completed deliverables (fixture/stub evidence only)
- P0: Muse provider facts verified from official dev.meta.ai docs → `server/providers/README.md`, `server/providers/muse.env.example`.
- P1: `server/providers/`: the MusePort adapter (task allowlist, deadline/timeout, cancellation, bounded retry with Retry-After, local schema validation, sanitized telemetry), the stdlib Chat Completions transport, `FixtureMuse`, and the `python3 -m server.providers.smoke` live check.
- P1: `server/planning/extraction.py`: quote-verified intent extraction that fails closed without consent. `wire.py` holds runtime validators for every contract shape.
- P2: `QuestPlanner.plan`. Code computes the feasible options (shared time ∩ venue hours, group caps). Muse chooses among them and code validates the choice. The rationale is built only from allowlisted fact codes.
- P3: `QuestPlanner.revise` carries revision lineage, returns `needs_input` when no slot works, rejects stale snapshots, and flags material changes via `requires_reconfirmation`.
- P4: `QuestPlanner.continue`. The model sees only willing-host ids (no attendance); the host must be willing; invitations claiming attendance are rejected.
- UI: `web/src/features/group-quests/planning/` (`PlanProposalCard`, `RevisionDiff`, `PlanStatusPanel`, `ContinuationCard`, `EvidenceBadge`, plus the `extractIntent`/`createLatestOnly` client helpers). There is also a dev-only fixture preview.

## Changed interfaces and files
- New: `server/providers/*`, `server/planning/*`, `tests/planning/*`, `web/src/features/group-quests/planning/*`.
- Shared (claimed):
  - `contracts/protocol.ts`: appended a "PROPOSED (D005)" section (additive).
  - `docs/DECISIONS.md`: added D005.
  - No shell, route, manifest or global CSS changes.
- Python ports: `MuseAdapter.generate(GenerateRequest)`, `IntentExtractor.extract(...)`, `QuestPlanner.plan/revise/continue(dict) -> dict`. See the two server READMEs.

## Checks run + actual result (2026-11-12, macOS, Python 3.13.0, Node 24.13.0)
- `python3 -m unittest discover -s tests/planning -t .` → **54 tests OK**. Coverage:
  - Adapter and transport: malformed JSON, schema extras, timeout, cancellation, 429/5xx/auth, unknown task, not configured.
  - Extraction: injection, consent, quote and bounds checks.
  - Planning: unknown venue, out of budget, outside the common slot, over the duration cap, leaky public text, unzoned times, no common time, no venue, stale versions, intruder participant, extra private field, provider outage.
  - Revisions and continuation: revision lineage and reconfirmation, old slot rejected after a change, impossible revision, continuation host/attendance guards.
- `cd web && npx tsc -b` → clean. `npm run lint` → 0 warnings. `npm run build` → OK, and the preview fixtures are absent from `dist`.
- `cd web && PLAYWRIGHT_CHANNEL=chrome npx playwright test` → **16/16 existing shell tests pass**, so there's no shell regression.
- Preview screenshots in installed Chrome at 1280 px and 390 px: no horizontal overflow and no page errors. Join and host buttons respond. The only console error is a favicon 404.
- `python3 -m server.providers.smoke` without a key → `not_configured`, exit 2.

## Fixture versus live evidence
Everything above is fixture or local-stub evidence. **No live Muse call has been made.** There are no latency or quality numbers, and no integrated three-device run.

## Next consumer + exact action
- **Kai:**
  - Compose one `MuseAdapter` per process: `build_muse_adapter(register_planning_tasks(TaskRegistry()), load_muse_config())`.
  - Register `POST /intents/extract` → `IntentExtractor`.
  - Call `QuestPlanner.plan` from the quorum job and `revise` on availability change.
  - Use `requires_reconfirmation` to decide between `proposed` and `scheduled`.
  - Call `continue` from the time-skip job.
  - Confirm D005 item 5 (namespace `server` package, stdlib only).
- **Rishi:** register a `rank_group` TaskSpec and test it with `FixtureMuse`. Emit `GroupProposal` exactly as `wire.group_proposal` expects. ACK D005 item 4.
- **Will:**
  - Render `ExtractionResult` (use `extractIntent`/`createLatestOnly`).
  - Compose `PlanProposalCard`/`PlanStatusPanel`/`ContinuationCard` per `web/src/features/group-quests/planning/README.md`.
  - ACK D005 items 2-3.
- **Patrik:**
  - ACK that the extraction draft excludes identity/consent.
  - Supply the `Consent` dict to the extract route.
  - ACK or adjust `PublicPlanCard` as the public plan DTO.
  - Confirm that `Candidate` snapshots for planning may include `maxBudgetMinor`/`maxDurationMinutes`/`availability`. Planning sends only group-level minimums to Muse, never per-person values.

## Blocked on + owner
- Live Muse evidence: needs `MUSE_API_KEY` (team/organizers). Adam then runs the smoke check and records the model id and latency.
- Venue catalog source (owner unassigned): planning ships a labeled synthetic catalog until Kai and Patrik choose a table.
- Server scaffold/routes: Kai.

## Next independent task
- Run the live smoke check as soon as a key exists.
- Add replay recording for a labeled cached fallback (P5).
- Once Kai's scaffold lands, wire an integration test that runs extraction → plan through the real routes.
