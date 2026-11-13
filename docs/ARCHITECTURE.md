# Architecture and integration
Status: design for Constellations (2026-11-12). Nothing here is built. Main contains only the mock Facebook shell (`web/`); the earlier Group Quests server was removed and survives only on branch `archive/group-quests-before-pivot` as reference. Contract: [contracts/protocol.ts](../contracts/protocol.ts) (1.0.0, pending D003 ACK). HTTP surface: [contracts/API.md](../contracts/API.md). State machine: [contracts/WORKFLOW.md](../contracts/WORKFLOW.md). Access matrix: [contracts/PRIVACY.md](../contracts/PRIVACY.md). Cross-owner requests: [COORDINATION.md](COORDINATION.md).

## Existing versus proposed
Existing: `web/` React/Vite mock Facebook shell, and docs and contracts.
Proposed (all unbuilt): Constellations feature UI under `web/src/features/constellations/`; FastAPI plus PostgreSQL/Supabase server (baseline proposed in D002); round lifecycle; formation, clue and Sky pipelines; single Muse adapter. Do not replace the web stack.

## Service boundaries
Owner assignments are proposed under D001 and need acknowledgment.

| Owner | Owns | Muse jobs | Must not |
| --- | --- | --- | --- |
| Will | Join flow, Confession UI, QR deep link, voice/text capture, guess slider, feature composition and routing, Muse chip component | calls M2 via Adam | Hold Muse secrets in the browser |
| Patrik | Consent v2, sessions, answer storage and access, blocks, M1 safety screen, output guard (no-quote, sensitive terms), Sky threshold, delete and TTL, prompt-builder field stripping | M1 | Let a Muse output reach a player without the guard |
| Rishi | Formation engine: M3 themes, M4 constellations, validation (3-5, once each, blocks, loose-match label), keyword/embedding baseline | M3, M4 | Import Patrik's internal tables; read answers outside the authorized snapshot |
| Adam | Single Muse adapter, Muse's voice, M2 clarify, M5 identity, M6 clues, M7 meetup, M8 Sky narration | M2, M5, M6, M7, M8 | Write database effects directly |
| Kai | Round lifecycle, parallel job orchestration, mutual idempotent confirm, SSE, Sky aggregates, Meetup event and chat (P1), operator console, synthetic top-up, reset | none | Bypass privacy guards |

Rules: no browser-to-Muse requests. One Muse adapter. Output guard runs on every Muse text output before release. Only orchestration executes durable effects. Server composition will register services through a registry in `server/app/` (to be built by Kai). When blocked on another owner's interface, stop and tag them per [COORDINATION.md](COORDINATION.md) section 2.

## Data flow per round
1. **Join.** Browser calls `POST /communities/:id/players` with consent. Privacy stores consent v2. No answer endpoint works before consent.
2. **Confession.** Browser posts the answer. Privacy stores it (private) and runs M1. Flagged: excluded, private support card returned. Clean: M2 may return one follow-up. The guess is stored separately from the answer.
3. **Lock.** Operator locks. Orchestration takes an authorized snapshot of unflagged answers with random player IDs.
4. **Formation.** M3 then M4 (Rishi). Code validates size, placement, blocks. Invalid output gets one retry, then a labeled fallback. M5 runs per constellation in parallel. Guard checks names. A constellation is shown only after validation.
5. **Search.** M6 runs per (seeker, target) pair in parallel. Guard checks every level. Orchestration releases levels on operator tap or a 20 second timer ("Demo timing").
6. **Confirm.** `POST /rounds/:id/finds` with a found code. Server confirms only if both are in the same constellation; the find is mutual, idempotent and unique per pair. A wrong code returns "not a match" and reveals nothing.
7. **Sky.** Server computes counts and thresholds (3 demo, 25 production). M8 receives counts only. Code checks every number in the output against the server counts. Pushed to the projector over SSE.
8. **Meetup (P1).** M7 proposes a quest from the venue allowlist under budget. Event and chat are created only after 3 or more approvals.

## Muse call parallelism plan
Observed single-call latency was 17 to 24 s at low reasoning effort (2 calls). Formation for 30 players under 60 s cannot run serially. This is the top technical risk and is unmeasured.

| Stage | Calls | Parallelism |
| --- | --- | --- |
| M1 safety | One per answer | Fire as each answer arrives, while the round is open |
| M2 clarify | One per answer, when needed | At submit, in parallel with M1 where policy allows |
| M3, M4 | One each for the whole round | Serial: M4 depends on M3. About two long calls on the critical path |
| M5 identity | One per constellation | Fully parallel after M4 |
| M6 clues | One per target, or per (seeker, target) | Fully parallel; can continue after the Formation screen shows, since levels unlock later |
| M8 Sky | One | After counts are final |

Plan: precompute M1 and M2 while the round is open so only M3, M4 and M5 are on the lock-to-formation path. Show clues after formation. Put a concurrency cap and per-call timeout in the adapter. Log latency for every call and expose it at `GET /operator/rounds/:id/calls`. Measure end to end before the demo and state the number honestly.

## Privacy boundaries
- Raw answers: readable only by the author and the server.
- Prompts: random player IDs and answer text only. The prompt builder strips profile fields. Unit test every payload.
- Muse output: no-quote check (5+ consecutive words) and sensitive-term filter before release.
- M8 sees counts only. Sky themes render only above the threshold.
- Flagged answers never enter M3, M4, clues or themes.
- Wrong find codes reveal nothing about membership.
- Delete before lock; 14 day TTL after the round.
- Operator console shows metadata and latency, not other players' answers.

## Frontend integration
Keep `web/src/App.tsx` and the existing Facebook routes. Will adds a Constellations tab inside a Group and a QR deep link. Each owner builds their own feature subdirectory under `web/src/features/constellations/` with loading and error states. Feature styles must not override global shell selectors. The feature fetches its own authenticated API. A mock adapter is allowed in development only with visible fixture mode and must not be on the live demo path.

## Build map
Every row is new work except the shell. Old code is not reused on main.

| Area | Directory | Owner | Status |
| --- | --- | --- | --- |
| Mock Facebook shell | `web/` | Will (tab, label) | Existing |
| Constellations feature UI | `web/src/features/constellations/` | One subdirectory per owner; Will composes | Planned |
| API composition, registry, health | `server/app/` | Kai | Planned |
| Single Muse adapter | `server/providers/` | Adam | Planned |
| Privacy, answers, guard | `server/privacy/` | Patrik | Planned |
| Formation engine | `server/matching/` | Rishi | Planned |
| Muse's voice, identity, clues | `server/planning/` | Adam | Planned |
| Round lifecycle, jobs, SSE | `server/orchestration/` | Kai | Planned |
| Confession capture | `server/voice/` | Will | Planned |
| Contract | `contracts/protocol.ts` | All (ACK D003) | Authored, pending ACK |

## Data and storage proposal
Patrik: players, sessions, consent v2, answers, guesses, blocks, findable details. Kai: rounds, constellations, clues, finds, jobs and call log, Sky stats, meetup votes. Coordinate migration order before creating tables. All identifiers are generated server-side. Separate public profile fields from private answers.

## Integration order
1. Kai: round lifecycle and operator console shell. Patrik: sessions, consent v2, answer storage.
2. Will: join and Confession. Adam: adapter with M1 to M8 task names.
3. Patrik: M1 and output guard. Rishi: M3, M4 with validation, against synthetic fixtures.
4. Adam: M5 and M6. Kai: parallel orchestration and confirm.
5. Integrated round on 3 or more phones.
6. Kai: Sky and M8. Rishi: baseline example.
7. P1: Meetup, clue veto. Then freeze.
