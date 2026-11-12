# Architecture and integration
Status: design for the Constellations pivot (2026-11-12). Nothing here is built unless the reuse map says so. Contracts: [contracts/constellations.ts](../contracts/constellations.ts) (proposed, D009), [contracts/protocol.ts](../contracts/protocol.ts) (legacy 1.x). HTTP surface: [contracts/API.md](../contracts/API.md). State machine: [contracts/WORKFLOW.md](../contracts/WORKFLOW.md). Access matrix: [contracts/PRIVACY.md](../contracts/PRIVACY.md).

## Existing versus proposed
Existing: `web/` React/Vite mock Facebook shell; FastAPI baseline; Muse adapter; privacy, matching, orchestration and voice modules built for Group Quests.
Proposed: Constellations feature UI under `web/src/features/constellations/`; round lifecycle; induction, riddle and Sky pipelines; FastAPI plus PostgreSQL/Supabase persistence. Do not replace the web stack.

## Service boundaries
Owner assignments are proposed under D009 and need acknowledgment.

| Owner | Owns | Muse jobs | Must not |
| --- | --- | --- | --- |
| Will | Join flow, Confession UI, QR deep link, voice/text capture, guess slider, feature composition and routing, Muse chip component | calls M2 via Adam | Hold Muse secrets in the browser |
| Patrik | Consent v2, sessions, answer storage and access, blocks, M1 safety screen, output guard (no-quote, sensitive terms), Sky threshold, delete and TTL, prompt-builder field stripping | M1 | Let a Muse output reach a player without the guard |
| Rishi | Induction engine: M3 themes, M4 societies, validation (3-5, once each, blocks, loose-match label), keyword/embedding baseline | M3, M4 | Import Patrik's internal tables; read answers outside the authorized snapshot |
| Adam | Single Muse adapter, Keeper voice, M2 clarify, M5 identity, M6 riddles, M7 ritual, M8 Sky narration | M2, M5, M6, M7, M8 | Write database effects directly |
| Kai | Round lifecycle, parallel job orchestration, mutual idempotent confirm, SSE, Sky aggregates, Ritual event and chat (P1), operator console, synthetic top-up, reset | none | Bypass privacy guards |

Rules: no browser-to-Muse requests. One Muse adapter. Output guard runs on every Muse text output before release. Only orchestration executes durable effects. Server composition registers services through `server.app.registry`.

## Data flow per round
1. **Join.** Browser calls `POST /communities/:id/players` with consent. Privacy stores consent v2. No answer endpoint works before consent.
2. **Confession.** Browser posts the answer. Privacy stores it (private) and runs M1. Flagged: excluded, private support card returned. Clean: M2 may return one follow-up. The guess is stored separately from the answer.
3. **Lock.** Operator locks. Orchestration takes an authorized snapshot of unflagged answers with random player IDs.
4. **Induction.** M3 then M4 (Rishi). Code validates size, placement, blocks. Invalid output gets one retry, then a labeled fallback. M5 runs per society in parallel. Guard checks names and mottos. A society is shown only after validation.
5. **Hunt.** M6 runs per (seeker, target) pair in parallel. Guard checks every level. Orchestration releases levels on operator tap or a 20 second timer ("Demo timing").
6. **Confirm.** `POST /rounds/:id/finds` with a found code. Server confirms only if both are in the same society; the find is mutual, idempotent and unique per pair. A wrong code returns "not a match" and reveals nothing.
7. **Sky.** Server computes counts and thresholds (3 demo, 25 production). M8 receives counts only. Code checks every number in the output against the server counts. Pushed to the projector over SSE.
8. **Ritual (P1).** M7 proposes a quest from the venue allowlist under budget. Event and chat are created only after 3 or more approvals.

## Muse call parallelism plan
Observed single-call latency was 17 to 24 s at low reasoning effort (2 calls). Induction for 30 players under 60 s cannot run serially. This is the top technical risk and is unmeasured.

| Stage | Calls | Parallelism |
| --- | --- | --- |
| M1 safety | One per answer | Fire as each answer arrives, while the round is open |
| M2 clarify | One per answer, when needed | At submit, in parallel with M1 where policy allows |
| M3, M4 | One each for the whole round | Serial: M4 depends on M3. About two long calls on the critical path |
| M5 identity | One per society | Fully parallel after M4 |
| M6 riddles | One per target, or per (seeker, target) | Fully parallel; can continue after the Induction screen shows, since levels unlock later |
| M8 Sky | One | After counts are final |

Plan: precompute M1 and M2 while the round is open so only M3, M4 and M5 are on the lock-to-induction path. Show riddles after induction. Put a concurrency cap and per-call timeout in the adapter. Log latency for every call and expose it at `GET /operator/rounds/:id/calls`. Measure end to end before the demo and state the number honestly.

## Privacy boundaries
- Raw answers: readable only by the author and the server.
- Prompts: random player IDs and answer text only. The prompt builder strips profile fields. Unit test every payload.
- Muse output: no-quote check (5+ consecutive words) and sensitive-term filter before release.
- M8 sees counts only. Sky themes render only above the threshold.
- Flagged answers never enter M3, M4, riddles or themes.
- Wrong find codes reveal nothing about membership.
- Delete before lock; 14 day TTL after the round.
- Operator console shows metadata and latency, not other players' answers.

## Frontend integration
Keep `web/src/App.tsx` and the existing Facebook routes. Will adds a Constellations tab inside a Group and a QR deep link. Each owner builds their own feature subdirectory under `web/src/features/constellations/` with loading and error states. Feature styles must not override global shell selectors. The feature fetches its own authenticated API. A mock adapter is allowed in development only with visible fixture mode and must not be on the live demo path.

## Reuse map
| Existing module | Current purpose | Constellations use | Needed change |
| --- | --- | --- | --- |
| `web/` shell | Mock Facebook | Host shell, "Simulated Facebook" | Add tab and label |
| `web/src/features/group-quests/` | Group Quests UI | Source for migrated components | Will migrates to `features/constellations/` |
| `server/app/` | FastAPI composition, registry, health | Same | Register new routers |
| `server/providers/` | Muse adapter, live-verified 2 calls | The single Muse adapter | Add M1 to M8 task names; parallel execution; metadata with call type |
| `server/privacy/` | Sessions, consent, projections | Consent v2, answer access, blocks | Answer storage, guard, TTL, prompt builder |
| `server/matching/` | Constraint-gated groups, eval harness | Induction validation and baseline | Replace ranking by meaning-based societies |
| `server/planning/` | Preferences, events, negotiation, challenges | Prompt patterns and public-text checks | Most Group Quests logic retired; reuse guard and prompt scaffolding |
| `server/orchestration/` | Workflow, jobs | Round lifecycle, confirm, SSE | New state machine and job types |
| `server/voice/` | Transcription, onboarding | Confession voice input | Text fallback always works |
| `contracts/protocol.ts` | Legacy 1.x types | Still parsed by merged code and tests | Keep; do not delete |

## Data and storage proposal
Patrik: players, sessions, consent v2, answers, guesses, blocks, findable details. Kai: rounds, societies, riddles, finds, jobs and call log, Sky stats, ritual votes. Coordinate migration order before creating tables. All identifiers are generated server-side. Separate public profile fields from private answers.

## Integration order
1. Kai: round lifecycle and operator console shell. Patrik: sessions, consent v2, answer storage.
2. Will: join and Confession. Adam: adapter with M1 to M8 task names.
3. Patrik: M1 and output guard. Rishi: M3, M4 with validation, against synthetic fixtures.
4. Adam: M5 and M6. Kai: parallel orchestration and confirm.
5. Integrated round on 3 or more phones.
6. Kai: Sky and M8. Rishi: baseline example.
7. P1: Ritual, riddle veto. Then freeze.
