# Decisions

Format per entry: ID / UTC timestamp; decision and rationale; owner and affected producers/consumers; status; ACK evidence; contract version / migration; verification.
ACKs are recorded as a reply in the PR that proposed the decision (`ACK`, `CHANGE: ...`) and copied here with the PR link. See docs/COORDINATION.md.

## D001: Product and ownership
ID / UTC timestamp: D001 / 2026-11-13T00:00Z
Decision and rationale: Build **Constellations**, per the team PRD of Nov 12 2026. It is a campus constellation game inside Facebook Groups. Muse  reads private weekly confessions, forms constellations of 3-5 by meaning, writes clue chains, and reveals the community as a Sky of guessed vs actual prevalence. Main was reset to the mock Facebook web UI. Earlier Group Quests code is archived on `archive/group-quests-before-pivot` and is not part of this build.
Owners (branches unchanged):
- Rishi: formation engine (M3 theme discovery, M4 constellation formation, validation, keyword baseline), formation UI.
- Adam: single Muse adapter, Muse prompting, M2 clarify, M5 identity, M6 clues, M7 meetup plan, M8 Sky narration; Search UI.
- Will: join/QR, confession capture (voice/text), follow-up, guess slider, edit/delete, feature composition and routing; Muse metadata chip.
- Patrik: consent (3 toggles incl. 18+), private answers, blocks, M1 safety triage, output guard, Sky threshold, deletion and TTL; consent screen and support card.
- Kai: server scaffold, round lifecycle, parallel Muse job orchestration, find confirm, SSE, Sky aggregates, meetup event (P1), operator console, synthetic top-up, reset.
Status: superseded by D005 (weekly game) on 2026-11-12.
ACK evidence: pending `@adamzhang06`, `@willapat`, `@patrikliska13`, `@beatopia`.
Contract version / migration: see D003.
Verification: documentation only; no runtime exists.

## D002: Server baseline
ID / UTC timestamp: D002 / 2026-11-13T00:00Z
Decision and rationale: Proposed server stack is Python FastAPI with PostgreSQL/Supabase, and the frontend stays the existing React/Vite shell. Kai scaffolds `server/app/` and owns dependency manifests and migration order. Patrik reviews auth and database access boundaries.
Status: accepted for 2.0.0: restore the archived FastAPI app (Kai) and PostgreSQL migrations; Kai owns manifests and migration order.
ACK evidence: pending `@beatopia`, `@patrikliska13`.
Verification: none yet.

## D003: Contract 1.0.0
ID / UTC timestamp: D003 / 2026-11-13T00:00Z
Decision and rationale: `contracts/protocol.ts` 1.0.0 defines the Constellations wire types, Muse job I/O M1-M8 and the ports between owners (MusePort, FormationPort, OutputGuard). JSON keys are camelCase everywhere. Each producer must ACK its shapes; any change goes through a PR plus an entry here.
Status: superseded by D006 (contract 2.0.0) on 2026-11-12.
ACK evidence: pending all owners.
Contract version / migration: 1.0.0, first version.
Verification: `tsc --noEmit --strict contracts/protocol.ts` at the commit that adds it.

## D004: Coordination protocol
ID / UTC timestamp: D004 / 2026-11-13T00:00Z
Decision and rationale: Every agent checks open PRs/issues for tags before work, and answers requests first. When an agent needs another owner's interface, data, ACK or endpoint, it stops at the phase boundary, pushes, opens a `[BLOCKED]` draft PR tagging the owner with the exact need, and continues only behind a labeled test-only adapter. See docs/COORDINATION.md.
Status: accepted (team direction from Rishi).
ACK evidence: n/a (process rule); each owner confirms by following it.

## D005: Weekly game and ownership
ID / UTC timestamp: D005 / 2026-11-12T23:00Z
Decision and rationale: Constellations becomes a weekly game. Mon-Fri daily questions, catch-up until Saturday lock, streaks, Sunday reveal into an anonymous constellation chat with moderation, block/report, weekly expiry and mutual reveal, mid-week event nudges, thresholded Sky statistics with labeled synthetic signals. Removed: hunt mechanics, clues, found codes, Keeper, Ritual, society branding. Renamed: society -> constellation, Confession -> daily answer, round -> weekly cycle. Kept: Facebook shell and feed tests, separate Constellations UI inside Groups, research table, privacy guarantees, safety triage, model/latency labels. Archived FastAPI infra, Muse adapter, privacy/session code and voice boundary are restored per owner, adapted and retested.
Owners (branches unchanged):
- Rishi: semantic formation, validation, prevalence computation, synthetic aggregate signals, formation debug view.
- Adam: Muse adapter, question schema/bank, question generation and selection, M2 follow-up, event nudges.
- Will: weekly cycle, daily-answer experience, voice, streaks, weighted submissions, operator controls, Groups tab.
- Patrik: verification, sessions, consent, private answer storage, safety screening, output guards, retention.
- Kai: anonymous chat, moderation pipeline, expiration, mutual reveal, realtime delivery, API composition, Sky UI.
Status: approved by Rishi (team lead direction). ACK pending `@willapat`, `@beatopia`.
ACK `@adamzhang06` 2026-11-12: ACK (https://github.com/willapat/Meta-Hackathon/pull/12).
ACK `@patrikliska13` 2026-11-13T02:40Z: ACK (recorded here from role/patrik-privacy; no PR thread was reachable from Patrik's agent).
Verification: docs/roles/*.md list tasks and acceptance checks.

## D006: Contract 2.0.0
ID / UTC timestamp: D006 / 2026-11-12T23:00Z
Decision and rationale: `contracts/protocol.ts` 2.0.0 replaces 1.0.0. New types: Question, WeeklyCycle, DailyQuestion, DailyAnswer (server weights), Streak, CatchUpState, PrevalenceGuess, ChatRoom, AnonymousHandle, ChatMessage, Report, RevealRequest, MutualReveal, EventNudge, Venue, SyntheticSignal, StreamEvent. Ports: MusePort, PrivacyPort, OutputGuard, FormationPort, QuestionPort, NudgePort, CyclePort, ChatPort. Shared fixtures in `contracts/fixtures/`.
Status: proposed. Each producer ACKs its shapes; changes go through a PR plus an entry here.
ACK evidence: pending `@willapat`, `@rishibagri`, `@beatopia`.
ACK `@adamzhang06` 2026-11-12: ACK for Question, QuestionPort, MusePort, MuseCallEvidence, M2, M6, M7, EventNudge, Venue, NudgePort; no change requested (https://github.com/willapat/Meta-Hackathon/pull/12).
ACK `@patrikliska13` 2026-11-13T02:40Z: ACK for Player, Consent, Block, SafetyFlag, PrivacyPort, OutputGuard, M1 (producer); no change requested.
Contract version / migration: 2.0.0; 1.0.0 retired, no data to migrate.
Verification: `npx -p typescript@5.6.3 tsc --noEmit --strict --target es2020 --lib es2020,dom contracts/protocol.ts` passes at the commit that adds it; fixtures parse as JSON.

## D007: Privacy storage and session shapes (proposed by Patrik)
ID / UTC timestamp: D007 / 2026-11-13T02:40Z
Decision and rationale: (1) The privacy module stores sessions, consent and (next) private answers in **SQLite from the Python standard library** (`db/privacy/001_privacy.sql`, `server/privacy/store.py`) instead of PostgreSQL, so it runs and tests with no database server or container. Access control moves from Postgres RLS into code: every private query is keyed to the verified session's player, with adversarial tests. (2) Sessions are scoped to one Group: `requireSession` returns `{playerId, communityId, isOperator}`. (3) `POST /communities/:id/join` and `GET /session` return `{player: Player, consent: Consent, isOperator}`; join requires all three toggles (403 `CONSENT_REQUIRED`, nothing stored) and is idempotent for an existing session in that Group. (4) Additive route `DELETE /session` (sign out). (5) Cookie `cst_session` (HttpOnly, Secure, SameSite=Lax, path /api). (6) Operator role granted only by a local setup function, never over HTTP. (7) `ChangeNotice` (ids/versions only) on consent change: `consent_revoked` whenever the player is no longer fully consented.
Owner and affected: producer Patrik; consumers Kai (composition, migration order, D002 database choice), Will (join screen, operator console, answer routes call `require_consent`).
Status: proposed. No wire type in contracts/protocol.ts changes.
ACK evidence: pending `@beatopia` (storage vs D002, composition), `@willapat` (join/session response shape).
Contract version / migration: 2.0.0 unchanged; no data to migrate.
Verification: `server/.venv/bin/python -m pytest tests/privacy -q` 68 passed offline; mutation checks (unscoped consent query, removed synthetic-session filter, removed join consent gate) each fail the suite.
