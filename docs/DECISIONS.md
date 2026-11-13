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
Status: approved by Rishi (team lead direction). ACKed by all five owners.
ACK `@adamzhang06` 2026-11-12: ACK (https://github.com/willapat/Meta-Hackathon/pull/12).
ACK `@patrikliska13` 2026-11-13T02:40Z: ACK (recorded here from role/patrik-privacy; no PR thread was reachable from Patrik's agent).
ACK `@beatopia` 2026-11-13: ACK for Kai-owned ChatPort, rooms, messages, reveal, SSE and API composition (https://github.com/willapat/Meta-Hackathon/pull/11).
ACK `@willapat` 2026-11-13: https://github.com/willapat/Meta-Hackathon/pull/14
Verification: docs/roles/*.md list tasks and acceptance checks.

## D006: Contract 2.0.0
ID / UTC timestamp: D006 / 2026-11-12T23:00Z
Decision and rationale: `contracts/protocol.ts` 2.0.0 replaces 1.0.0. New types: Question, WeeklyCycle, DailyQuestion, DailyAnswer (server weights), Streak, CatchUpState, PrevalenceGuess, ChatRoom, AnonymousHandle, ChatMessage, Report, RevealRequest, MutualReveal, EventNudge, Venue, SyntheticSignal, StreamEvent. Ports: MusePort, PrivacyPort, OutputGuard, FormationPort, QuestionPort, NudgePort, CyclePort, ChatPort. Shared fixtures in `contracts/fixtures/`.
Status: accepted (all five owners ACKed, below). Changes go through a PR plus an entry here.
ACK evidence: all five owners, below.
ACK `@rishibagri` 2026-11-13: ACK for Theme, Constellation, SkyStats, SyntheticSignal, FormationPort, M3, M4, M5, M8 (producer). `isFallback` is internal only; fallback is public via the guarded `name` suffix "(Fallback grouping)" plus `isLooseMatch` (https://github.com/willapat/Meta-Hackathon/pull/16).
ACK `@beatopia` 2026-11-13: ACK, no contract edits proposed; rejects undeclared wire fields (https://github.com/willapat/Meta-Hackathon/pull/11).
ACK `@adamzhang06` 2026-11-12: ACK for Question, QuestionPort, MusePort, MuseCallEvidence, M2, M6, M7, EventNudge, Venue, NudgePort; no change requested (https://github.com/willapat/Meta-Hackathon/pull/12).
ACK `@patrikliska13` 2026-11-13T02:40Z: ACK for Player, Consent, Block, SafetyFlag, PrivacyPort, OutputGuard, M1 (producer); no change requested.
ACK `@willapat` 2026-11-13 (WeeklyCycle, DailyQuestion, DailyAnswer, WEIGHTS, Streak, CatchUpState, PrevalenceGuess, CyclePort): https://github.com/willapat/Meta-Hackathon/pull/14
Contract version / migration: 2.0.0; 1.0.0 retired, no data to migrate.
Verification: `npx -p typescript@5.6.3 tsc --noEmit --strict --target es2020 --lib es2020,dom contracts/protocol.ts` passes at the commit that adds it; fixtures parse as JSON.

## D007: Privacy storage and session shapes (proposed by Patrik)
ID / UTC timestamp: D007 / 2026-11-13T02:40Z
Decision and rationale: (1) The privacy module stores sessions, consent and (next) private answers in **SQLite from the Python standard library** (`db/privacy/001_privacy.sql`, `server/privacy/store.py`) instead of PostgreSQL, so it runs and tests with no database server or container. Access control moves from Postgres RLS into code: every private query is keyed to the verified session's player, with adversarial tests. (2) Sessions are scoped to one Group: `requireSession` returns `{playerId, communityId, isOperator}`. (3) `POST /communities/:id/join` and `GET /session` return `{player: Player, consent: Consent, isOperator}`; join requires all three toggles (403 `CONSENT_REQUIRED`, nothing stored) and is idempotent for an existing session in that Group. (4) Additive route `DELETE /session` (sign out). (5) Cookie `cst_session` (HttpOnly, Secure, SameSite=Lax, path /api). (6) Operator role granted only by a local setup function, never over HTTP. (7) `ChangeNotice` (ids/versions only) on consent change: `consent_revoked` whenever the player is no longer fully consented.
Owner and affected: producer Patrik; consumers Kai (composition, migration order, D002 database choice), Will (join screen, operator console, answer routes call `require_consent`).
Status: accepted (producer Patrik; consumers Kai and Will ACKed). No wire type in contracts/protocol.ts changes.
ACK `@beatopia` 2026-11-13: "SQLite privacy storage, session scope/response shapes, secure cookie, local-only operator grant and revocation notices are acceptable for this prototype. This supersedes D002 for privacy storage only; cross-store atomic publication is not assumed." (https://github.com/willapat/Meta-Hackathon/pull/15#issuecomment-6841868076).
ACK `@willapat` 2026-11-13: ACK for the session shape `{playerId, communityId, isOperator}` and the join/session response `{player, consent, isOperator}` (https://github.com/willapat/Meta-Hackathon/pull/14).
Contract version / migration: 2.0.0 unchanged; no data to migrate.
Verification: `server/.venv/bin/python -m pytest tests/privacy -q` 68 passed offline; mutation checks (unscoped consent query, removed synthetic-session filter, removed join consent gate) each fail the suite.

## D008: Streak rule with catch-up
ID / UTC timestamp: D008 / 2026-11-13T03:00Z
Decision and rationale: Resolves the conflict Will raised in #14 between contracts/WORKFLOW.md ("missing a day resets to 0") and the role acceptance check ("Mon, Tue on day, Wed catch-up -> current 2"). A question day answered on the day extends the streak. A day caught up before Saturday lock is neutral: it neither extends nor breaks. A day with no answer at all breaks the streak. Between the missed day ending and the catch-up, `current` shows 0; after the catch-up it is restored. Players are rewarded for showing up on the day without being punished for catching up.
Owner and affected: decided by Rishi; producer Will (`server/cycle/streaks.py`); consumers Will UI.
Status: accepted.
ACK evidence: proposal by `@willapat` in https://github.com/willapat/Meta-Hackathon/pull/14; accepted by `@rishibagri`.
Contract version / migration: 2.0.0 unchanged (Streak shape unchanged); contracts/WORKFLOW.md streak paragraph updated.
Verification: Will's streak fixture tests.

## D009: Brightness in the constellation (proposed by Will)
ID / UTC timestamp: D009 / 2026-11-13T04:45Z (proposed)
Decision and rationale: Product direction from Will (human): a constellation shows you and the players whose answers meant the most similar things; the more similar, the closer and brighter their star. Shared Groups may add a small boost. Proposal, kept additive so 2.0.0 consumers keep working:
1. Additive optional field on `AnonymousHandle`: `brightness?: "bright" | "mid" | "faint"` (PUBLIC to room members). Rishi's formation computes a private per-member closeness 0..1 and the server bands it into three levels, so members never see exact scores and a score can't be used to infer anyone's answers. `isSelf` handles omit it.
2. Shared-Group boost is applied inside the private closeness score only. No field says that two players share a Group, because that would leak membership.
3. Scope: stays community-scoped for 2.0.x (sessions D007, `CyclePort.current(communityId)`). The UI is already general (`/constellations`) and plays in one community. Cross-Group play is a post-hackathon change and is not part of this entry.
Owner and affected: producer Rishi (closeness in formation); Kai (room members carry the band, reveal view draws it); consumer Will (UI). Patrik: no shape change; asked to confirm the band leaks nothing under the privacy rules.
Status: implemented on branch `feat/will-force-d009-d010` at the direction of Will (human), ahead of the producer ACKs; merging is Will's call. Still needs ACK from `@rishibagri` (producer) and `@patrikliska13` (privacy). Implementation: `server/matching/closeness.py` (pairwise closeness incl. D010 boosts, rank bands bright/mid/faint, self omitted, raw score never on public output), `Constellation.closeness` private, contract 2.1.0. Kai's room view still has to copy the band onto `AnonymousHandle.brightness` (Kai's code is not on main).
ACK `@beatopia` 2026-11-13T05:30Z (conditional): will carry the optional band and render the approved view once D009 has the producer/consumer ACKs, privacy sign-off and 2.1.0 runtime validators/fixtures; Kai composition stays exact 2.0.0 until then; no raw score or shared-Group flag; `isSelf` omits brightness (https://github.com/Meta-Hackathon-SF/Meta-Hackathon/pull/31). Still needed: `@rishibagri` (producer), `@patrikliska13` (privacy).
Contract version / migration: 2.1.0 (additive, optional); no data to migrate; fixture `chat-room` gains the band on non-self members.
Verification: none yet (proposal).

## D010: More matching signals: Groups, Events, Posts and Comments (proposed by Will)
ID / UTC timestamp: D010 / 2026-11-13T05:10Z (proposed)
Decision and rationale: Product direction from Will (human, product notes): matching and the "why this group" context should also use the Groups a player is in, the Events they are interested in or going to, and their Posts and Comments, not only daily answers. Target audience: people (emphasis college age) who feel they don't relate, want to meet people, and find it hard to take the first step. Proposal:
1. A fourth, optional consent toggle `useActivity` (default off), separate from the three required join toggles. Off means matching uses daily answers only, exactly as today.
2. When on, formation (Rishi) may read: Group memberships, Event interest/going, and topics derived from the player's own Posts and Comments. Raw post or comment text never leaves the formation step, is never quoted, and never reaches any output (same no-quote and sensitive-term guards as answers). Sensitive categories (health, sexuality, religion, finances, family trauma, home location) are excluded at derivation.
3. Shared Groups and shared Events only raise the private closeness score (D009). Before mutual reveal the UI shows counts only ("2 of your 4 stars are in a Group you're in"); which star shares what appears only after both reveal. Already-friends are noted as a count so constellations favour new people.
4. Event heat ("Where people like you are going"): events come from the approved venue catalog (Adam, M7). Code drops any event with fewer than 3 similar people and shows bucketed counts only (3–5, 6–9, 10+). Marking "Interested" is private.
Owner and affected: Patrik (consent toggle, storage, deletion of the new data, privacy sign-off), Rishi (formation inputs and closeness), Adam (event catalog and nudges), Kai (reveal view shows the context). Will: UI only.
Status: implemented on branch `feat/will-force-d009-d010` at the direction of Will (human), ahead of the owners' ACKs; merging is Will's call. Still needs ACK from `@patrikliska13`, `@rishibagri`, `@adamzhang06`, `@beatopia`. Implementation: optional `useActivity` switch (separate from the three required toggles, off by default); `PUT /me/activity` stores opaque Group/Event/friend ids and allowlisted topics derived from the player's own post/comment text, which is discarded (`server/privacy/activity.py`, `db/privacy/004_activity.sql`); deleted on opt-out and by `DELETE /me/data`; formation snapshot gains `activity` keyed by random ref; `member_context` counts and `event_heat` (threshold 3, bucketed) in `server/matching/closeness.py`. Cross-Group play: one pool `facebook-space` (seeded); Groups are signals, not boundaries. Fixture UI computes the same rules against labeled Synthetic players.
Contract version / migration: 2.1.0 together with D009 if accepted (additive: `Consent.useActivity?: boolean`, default false); no data to migrate.
Verification: none yet (proposal). UI: web/tests/constellations.spec.ts "why-this-group" and "event heat" tests prove counts-only and the threshold in the Example.

## D011: Brand rename to Facebook Space
ID / UTC timestamp: D011 / 2026-11-13T06:00Z
Decision and rationale: the product brand is **Facebook Space** everywhere players or readers see it (README, docs, contracts, UI copy, server messages). The 3-5 person group stays a **constellation**, and the Sky keeps its name. Code identifiers, wire fields (`constellationId`, `Constellation`), folder paths (`web/src/features/constellations/`, `tests/matching`) and branch names are unchanged, so no owner's code or contract shapes break. Earlier decision entries and append-only update logs keep the old name as history.
Owner: Rishi (team lead). Affected: all owners (copy only).
Status: accepted.
Contract version / migration: 2.0.0 unchanged (comments only).
Verification: `git grep -w Constellations` matches only history (DECISIONS entries before D011, docs/updates).

## D012: v3 redesign (daily constellations, Saturday sky, Sunday Meta-logo main constellation, 24-hour chat, events)
ID / UTC timestamp: D012 / 2026-11-13T08:00Z
Decision and rationale: make "you are not alone" a daily feeling and keep it anonymous. Each answer shows the constellations you joined that day (several possible, day colors). Saturday shows all of them plus faint second-degree constellations over the whole sky. Sunday reveals one main constellation of your closest people (players who share 2+ constellations or have very similar answers; group of 3-5), drawn as the Meta logo, with a 24-hour anonymous chat that keeps mutual reveal. Removed: percentages and Sky statistics, prevalence guess, constellation and room names, M5 naming, M8 Sky narration. Added: `answeredToday`, event interest and constellation event nudges, custom events every few weeks (operator approved, 3+ RSVPs). Spec: docs/PRD-v3.md. Task board: README "Work board (v3)".
Owner: Rishi (team lead). Affected: all owners.
Status: approved by Rishi; ACK pending `@adamzhang06`, `@willapat`, `@patrikliska13`, `@beatopia` (reply on the D012 issue).
Contract version / migration: 3.0.0, breaking; Rishi drafts `contracts/protocol.ts` 3.0.0. 2.1.0 stays in force until then.
Verification: per-screen acceptance checks in docs/PRD-v3.md and README.

## D013: Live speech-to-text while the player talks (proposed by Patrik, at the human's direction)
ID / UTC timestamp: D013 / 2026-11-13T07:30Z (first filed as D011, then D012; renumbered after the brand-rename D011 and the v3 D012 landed)
Decision and rationale: Today a voice answer is recorded whole, then sent to `POST /voice/transcribe`. Proposal: an additive WebSocket route `WS /api/v1/voice/live` that relays 16 kHz mono PCM16 from the browser to Muse Voice Transcribe realtime (`wss://api.meta.ai/v1/asr/realtime`, `PUSH_TO_TALK`, cumulative partials) and streams partial then final text back, so words appear in the answer box as the player speaks. The server holds the key (never the browser). The transcript is a draft only: the player edits it and submits through `POST /cycles/:id/answers`, where M1 screening runs as before.
Guards: session from the cookie (Patrik's `actor_dependency`, now typed `HTTPConnection` so it works on WebSockets) and `require_consent` before any audio; same-host Origin check (cookie-authenticated WebSockets are not covered by CORS); 60 s and size caps per turn; final text capped at 400 chars; audio and transcripts never logged or stored; provider errors never echoed. The route is mounted only when live STT is configured; otherwise the browser falls back to `POST /voice/transcribe`, and typing always works.
Owner and affected: Will (owner of `server/voice`, `server/cycle/api.py`, the daily UI); Kai (composition: the registry is HTTP-only today, so it must accept WebSocket routes before passing `live_stt`); Patrik (privacy review: no new data stored; audio already goes to Muse for transcription).
Status: merged to main 2026-11-13 at Patrik's human's explicit direction, ahead of owner ACKs (route stays unmounted unless `live_stt` is configured, so HTTP-only compositions are unchanged). ACK or CHANGE still requested from `@willapat` (owner) and `@beatopia` (composition). No wire type in contracts/protocol.ts changes.
Contract version / migration: additive route in contracts/API.md; no data to migrate.
Verification: `tests/voice/test_live.py` 12 offline tests against a fake Muse realtime upstream (handshake shape, partials, final, endStream, caps, origin, unauthenticated, consent withdrawn, provider errors never leaked, key never sent to the browser). Mutation checks: removing the origin check fails 3 tests; removing the consent check fails 1. Full `pytest tests` 848 passed; web lint/build pass; Playwright 59 passed (fixture mode unchanged). Live end to end on a local scratch harness (real privacy, cycle, question bank, real Muse): Chromium fake mic with synthetic speech, words appeared in the answer box every ~0.3 s, ready 1.5 s after the click, exact final text. Hardening after a real-voice failure during a slow Muse moment: wait up to 20 s for Muse's ready (was 10 s) and log one content-free reason code per failure (`connect_failed`, `handshake_timeout`, `handshake_rejected`, `provider_error`, `stream_timeout`, `cap_reached`); 19 relay tests. Tried by Patrik's human with a real voice in desktop Chrome on a local harness: works. Not yet run in Kai's composed app, on a physical phone or in Safari.

## D015: Approved campus events get stable ids (proposed by Adam)
ID / UTC timestamp: D015 / 2026-11-13T08:10Z (first filed as D013, which Patrik's live speech-to-text decision already held; renumbered by Rishi)
Decision and rationale: D010 point 4 says event heat counts only events from the approved catalog, but catalog events had no id to match against (issue #44). Each `campusEvents` entry in `contracts/fixtures/venues.json` (and `server/planning/data/venues.json`, which must equal it) now carries `eventId`, unique, shaped `ev-<name>`. The ids follow Will's UI: `ev-open-mic`, `ev-volleyball`, `ev-board-games`, `ev-film-club`. "Pickup soccer" became "Pickup volleyball", and "Film club screening" at `v-quad` was added to match. `VenueCatalog.event_ids()` is the allowlist to pass to `event_heat(..., approved_event_ids)`. Muse's M7 input is unchanged: `events_between` still returns only `{title, placeId, start}` (M7In in protocol.ts).
Owner and affected: Adam (catalog, producer); Rishi (`event_heat` allowlist, consumer: ACK on #44, implemented at 59ce86a); Will (UI ids, consumer: ACK on #44); Patrik (optional: reject unapproved `eventIds` at `PUT /me/activity`).
Contract version / migration: additive fixture field, no protocol.ts type change. The web copy is `APPROVED_EVENTS` in `web/src/features/constellations/nudges/venues.ts`, and `tests/planning/test_web_venues.py` fails on drift.
ACK `@rishibagri` 2026-11-13T07:12Z (#44). ACK `@willapat` 2026-11-13T07:07Z (#44).
Verification: `python -m pytest tests/planning tests/providers tests/orchestration/test_nudges.py` passed; web build passes.
Addendum 2026-11-13T10:00Z (Adam): every catalog event also carries an explicit `end` (validated: after `start`, at most 3 h), so 3.0.0 `EventView.endsAt` is never guessed. This is additive and the same values are in the web `APPROVED_EVENTS`. M7In events stay `{title, placeId, start}`. Proposed on #68 (item 1).

## D014: Muse sees the questions and the activity; two new Muse tasks (proposed by Adam, at the human's direction)
ID / UTC timestamp: D014 / 2026-11-13T09:00Z (proposed)
Decision and rationale: Live evals on synthetic data (`docs/audits/2026-11-13-live-evals.md`, about $1.21) showed four things. With short answers, attaching each answer's question raised M4 grouping accuracy (pairwise P/R) from about 0.5-0.8 to 1.0 on every model. Server-computed affinity hints broke ties in 11 of 12 runs and never overrode strong meaning. A Muse topic classifier scored F1 0.98 against 0.47 for the keyword list, and the keyword list leaked topics from 18 of 20 sensitive texts. A Muse sensitivity screen caught 114 of 114 sensitive names and headlines that OutputGuard missed (it blocked only 8 of 44). Additive contract 2.2.0:
1. `AnswerText extends PromptText { questionId?: string }` for M3 and M4 answers, plus `M4In.questions?: {questionId, text}[]`. M3In already had `questions`, but it was always sent empty.
2. `M4In.affinity?: {memberIds: [ref, ref]; shared: number}[]`. These are opt-in (D010) pair counts computed by the server. No topics, Group ids or Event ids reach Muse. Meaning comes first, and affinity may only break ties.
3. New MuseTask `activity_classification` (M9): a player's own opted-in posts and comments (and "liked: ..." items) become up to 3 labels from the 14 `ActivityTopic` values, each with a stance, plus a `sensitive` flag. Code drops any text marked sensitive and keeps only positive or neutral labels. Texts are transient: never stored or logged.
4. New MuseTask `sensitivity_screen` (M10): public game text (M5 names, Sky labels and headlines, M7 nudges, M6 questions) is given one `SensitivityCategory`. Code blocks anything except `none`, including a missing or duplicate id or a provider error. It runs after OutputGuard, never instead of it.
5. `MuseCallType` gains `M9` and `M10`.
Owner and affected: Adam (adapter schemas, router: producer). Rishi (M3/M4 payloads and prompts; `MUSE_CALL_TYPES`). Patrik (snapshot `questionId` and `questions`; M9 and M10 prompts and services; **privacy wording**, because post text would now reach Muse transiently). Kai (wiring; orchestration `callType` validator; `CONTRACT_VERSION`). Will (daily client `callType` list).
Contract version / migration: 2.1.0 to 2.2.0, all additive and optional, so old snapshots and payloads stay valid. On `role/adam-planning` at 7843bef, `CONTRACT_VERSION` is bumped in server/app, server/cycle, server/matching and server/privacy, and M9/M10 are added to the callType validators in orchestration, matching, the daily client and the chat runtime.
ACK `@rishibagri` 2026-11-13T08:29Z (#60, comment 6847998531): items 1, 2 and the MUSE_CALL_TYPES edit. Contract 3.0.0 (D012) will build on 2.2.0. D012 removes M5 and M8, so M10's scope shrinks to nudges, generated questions and custom events.
ACK `@willapat` 2026-11-13T08:33Z (#60, comment 6848073135): the daily client parseEvidence and `server/cycle/wire.py` version edits; no UI change.
ACK `@patrikliska13` 2026-11-13T08:34Z (#60, comment 6848083247): snapshot questionId and questions, M9/M10 ownership, version bump. **M9 privacy sign-off with conditions:** emails, phone numbers, links and @mentions redacted in code before sending; texts capped at 2,000 characters; consent copy says Muse reads posts and comments. Patrik implemented these on #59 (5b403b0, `redact_for_model`). M10: ACK.
ACK `@beatopia` 2026-11-13T08:29Z and 08:34Z (#60, comments 6848002008 and 6848085731): will consume `build_muse_router`, the shared trace and the routes once D014 lands, and will update the Kai-owned version and validators. Conditions: migration order confirmed with Rishi (done, 08:29Z), and Patrik's privacy ACK (given with conditions, 08:34Z).
Prompt versions that implement D014: M4 `constellation_formation.v2` (branch `adam/rishi-formation-v2`), M9 `activity_classification.v1` and M10 `sensitivity_screen.v1` (#59).
Verification: `python -m pytest tests` gives 898 passed, 2 skipped with the proposal applied. Web lint has 0 errors and the build passes. Schema drift tests cover the M9 and M10 shapes. The live evidence is in `tests/providers/live_evals/`.

## D017: Stage view for the live demo: two opted-in phones and the Muse pipeline (proposed by Adam, at the human's direction)
ID / UTC timestamp: D017 / 2026-11-13T16:20Z (first filed as D016; renumbered because the matching code already cites D016 for the 5+ constellation size)
Decision and rationale: the demo runs on two phones plus a laptop on the big screen. The laptop shows `/space/stage`: a status panel for each phone and, between them, what Muse and the server do (calls by task with model and latency, themes at 3+, constellations as dots, names). Judges need to see one answer travel through Muse, so the stage may show the answer text of **at most two players who turned it on themselves** (`POST /me/stage` with slot `A` or `B`, from the Privacy screen; default off; the same control turns it off). An operator cannot put anyone else on stage. This is a deliberate, narrow exception to "never render another player's answer text": the player chooses it, only an operator session can read it, and it exists for the presenter screen.
What stays enforced: text comes only from `AnswerStore.eligible_answers`, so a flagged answer (or any answer of a player with one) never appears; `sharedMeaning`, member ids and other players' text are never returned; theme labels need 3 members and pass the output guard again; synthetic players are counted and labeled, not shown.
Owner and affected: Adam (server `server/app/stage.py`, web `web/src/features/constellations/stage/`). Touches Kai's `server/app/weekly.py` (router mounted on the matching registration; `publish_cycle` also notes when a week starts so the stage lists only that week's calls) and Will's `SettingsScreen` / demo panel (one card, one link). Patrik: privacy review welcome; remove the opt-in card to disable.
Contract version / migration: additive routes outside `contracts/protocol.ts`: `GET /me/stage`, `POST /me/stage`, `GET /operator/stage`. No change to existing wire types. Slots live in the workflow store (`stageSlots`, `stageStarted`).
ACK: not waited for (three owners offline; see the 2026-11-13 ownership note in Adam's handoff).
Verification: `tests/orchestration/test_runtime.py` (two stage tests: operator-only, opt-in and opt-out, no other player's text or ids in the response); full `pytest tests` 1362 passed; web `tsc -b` and `oxlint` clean; layout checked at 1600x900 with mocked data.
Amendment (2026-11-13, Will, on human direction): `GET /operator/stage` is open to any signed-in member of the community, not only operators, so every demo account can present (same as the demo buttons). Still session-only (401 without one) and community-scoped; the two-slot opt-in, eligible-answers-only and guard rules are unchanged. Consequence: any member, not only an operator, can read the answer text of the at most two players who put themselves on stage. Adam and Patrik: revert by restoring `privacy.require_operator(actor)` in `server/app/stage.py` if this is not acceptable after the demo.

## D018: 100-person synthetic cast, and formation prompt v3 (proposed by Adam, at the human's direction)
ID / UTC timestamp: D018 / 2026-11-13T19:30Z
Decision and rationale: the demo population is now 100 synthetic young-adult personas (`server/privacy/data/demo_population.json`, loaded by `server/privacy/demo_population.py`) instead of 30 people in five clean themes with two answer variants each. Each persona has their own voice, an answer to all 32 questions of the live bank (the old cast covered only the 12 fixture questions, so on most days it said nothing), 0 to 3 feed posts, comments on other cast members' posts, Groups, approved event RSVPs and a prevalence guess. Participation is uneven on purpose: 35 answer every day, 35 miss a day, 20 answer two or three days, 10 stop after Monday or Tuesday; some answers are catch-ups. Like counts follow shared Groups and interests. There are 20 loose meaning clusters of 5 with one "bridge" person each; nothing tells matching which cluster a player is in.
Formation prompt: running this cast on live Muse showed that `constellation_formation.v2` ("prefer fewer, fuller groups", written when groups were 3 to 5) combined with D016 (5 or more, no maximum) put 79 of 107 players into one constellation. `constellation_formation.v3` asks for specific groups of 5 to 10 and tells Muse to split anything past 12. Same cast, same answers: 13 constellations of 7 to 10, most of them recognisable (intramural players, tabletop with online gamers, film watchers, people far from home with home cooks). One live run each; directional, not a benchmark. Code still enforces only the minimum of 5.
Owner and affected: Adam (cast, seeding). Rishi: the M4 prompt is yours; v3 changes one sentence (`FULLER_GROUPS`) and the version string. Revert or retune if your evals disagree. Will: the top-up now adds 108 players and the feed has 144 population posts (feed storage key bumped to `closer-together-feed-v3` so browsers pick it up). Patrik: text is synthetic and was screened for the sensitive categories; the top-up also stores each synthetic player's Groups, approved events and topic labels as activity signals (no text).
Contract version / migration: none. `topup_rows` rows carry `ownTiming` so a cast member's on-day answer is not marked late when the top-up runs on Friday.
ACK: not waited for.
Verification: `pytest tests` 1381 passed; web `tsc`, oxlint and 57 Playwright tests passed; one local week on live Muse: top-up 397 answers, formation 15 to 18 s, reveal 200.

## D019: The stage drives the demo; phones appear automatically (proposed by Adam, at the human's direction)
ID / UTC timestamp: D019 / 2026-11-13T21:30Z
Decision and rationale: the live site shows no demo controls; the week is driven only from `/space/stage`. One button starts a demo week with the synthetic cast (D018) already answering, "Next day" moves Monday to Friday, then one button locks and starts matching and, once Muse has formed the constellations, one button reveals. The two presenters answer only Friday: Monday to Thursday are filled in for them from `server/app/stage_script.py`, and the stage shows each presenter the line to type for Friday's question. The two scripts mean different things (Phone A watches films alone and wants people to talk them over with; Phone B lives for pickup games and the team chat), so Muse has a real reason to separate them; nothing forces it.
Phones are always on: the two newest real players who joined (not the account viewing the stage) appear as Phone A (older) and Phone B with their display name and answers. This widens D017, which needed an explicit opt-in. A player can pin a side or "Hide me" under Privacy → Demo screen; "Phones" on the stage re-detects. Synthetic players never appear as phones. All other D017 rules stand: only the two phones' unflagged answers are shown as text, no member ids or `sharedMeaning` leave the server, names and themes pass the output guard, themes need 3 members.
Owner and affected: Adam (`server/app/stage.py`, `stage_script.py`, web `stage/`). Will: the Space tab's demo panel now renders only in fixture mode (offline and tests); `CycleService.stage_answers` and `day_question` are new and fixture-cycle-only. Patrik: auto-showing the newest joiners is a privacy trade-off made for the live demo; revert to opt-in after the demo by removing the auto-fill in `resolve`.
Contract version / migration: additive routes outside `contracts/protocol.ts`: `POST /operator/stage/start`, `POST /operator/stage/next`, `POST /operator/stage/phones/reset`; `POST /me/stage` also takes `"off"`; the stage view adds `displayName`, `toType`, `today`, `mapSeed`.
ACK: not waited for.
Verification: `pytest tests` 1408 passed (two new stage tests: auto phones and their privacy, and the full start-to-reveal flow with phones typing only Friday); web `tsc`, 59 Playwright tests passed; every stage phase rendered at 1600x900 against mocked data.
