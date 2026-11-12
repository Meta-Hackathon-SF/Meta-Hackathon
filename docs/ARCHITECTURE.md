# Architecture and integration
## Existing versus proposed
Existing: web/ React/Vite Facebook mock, local demonstration data, feed routes and Playwright tests.
Foundation: common documents, wire types and directory ownership.
Proposed implementation: separate Group Quests feature UI, FastAPI server and PostgreSQL/Supabase persistence. Confirm server choice at H0; do not replace the existing web stack to adopt this proposal.

## Service boundaries
Will owns capture/transcription integration and feature composition. Adam owns Muse extraction, provider adapter and planning. Patrik verifies identity, stores private intents, returns authorized minimized snapshots. Rishi forms teams from those snapshots. Kai owns durable commands, job dispatch, events/messages and subscriptions.

No browser-to-Muse secret-bearing requests. No Rishi-to-Patrik internal-table imports. No Adam direct database effects. No Kai bypass of privacy guards. Server composition registers services through shared ports.

## Frontend integration
Keep web/src/App.tsx and existing Facebook routes. Will adds a feature route and small entry button/navigation item. Each owner implements their feature subdirectory with documented props and async/loading/error states. New feature styles must not override global shell selectors. Feature design is intentionally open.

Do not assume the current /groups or /events mock has real data. The mock shell may link into Group Quests; the feature fetches its own authenticated API. A local mock adapter is allowed during development only with visible fixture mode. Remove it from live paths before demo.

## Data/storage proposal
Patrik: participants, sessions/auth mapping, memberships, consent revisions, private intents, authorized views/policies.
Kai: quests, proposals, plan revisions, acceptances, event records, messages, jobs, idempotency ledger, outbox and invitations.
Coordinate migrations before table creation. All database identifiers are generated server-side. Separate public profile fields from private constraints.

## First integration order
1. Kai starts backend shell; Patrik provides session and self-intent persistence.
2. Will submits confirmed intent; Adam implements extraction behind the common adapter.
3. Rishi uses authorized snapshots to return GroupProposal.
4. Adam returns a plan from that proposal and catalog venues.
5. Kai stores proposal, accepts members, dispatches final planning and persists event.
6. Owners wire component outputs into Will's shell.
7. Availability update invalidates snapshot and triggers revision.
8. Continuation/hosting completes the loop.

## Provider and fallback
Verify Muse model IDs/auth/audio against organizer-provided documentation. Do not add guessed vendor URLs or pretend all models support audio. Adam owns request limits and schemas. Will's STT adapter returns text; typed input always reaches the same extraction/confirmation path.

Offline tests use fake adapters. A labeled cached replay uses its recorded inputs and cannot claim newly personalized output. A no-fit match offers another slot or optional soft preference changes; never relax authorization, availability, budget or capacity behind the scenes.

## Observability
Record requestId, task, model identifier, prompt/schema version, latency, retry count, validation outcome and sanitized error code. Do not store raw audio, transcript, complete prompts or private constraints in logs. UI timers are measurements, not decorative countdowns.
