# Kai handoff - Constellations 2.0.0

Branch: `role/kai-orchestration`; handle: `@beatopia`; repository: `Meta-Hackathon-SF/Meta-Hackathon`.
Updated 2026-11-13T05:44Z. Source checkpoints: b1192cb composed app, 057f5aa delivery docs, de0f646 private support-card UI, 0c51048 clean merge of current main (3f62413); 43f6009 guarded operator nudge composition. All source pushed; checkout clean before this docs checkpoint. PR #13 remains draft at the baseline-debug/public reveal projection and owner UI-mount boundaries. Source checkpoint CI is green.

## Current implementation and consumer action

Adam can import `build_weekly_app` from `server.app.weekly`. Configured entrypoint:
`python -m uvicorn server.app.bootstrap:create_configured_app --factory --host 127.0.0.1 --port 8000 --no-access-log`.
Configure server-only `CONSTELLATIONS_WORKFLOW_DSN` (LOGIN inherits workflow_runtime; apply db/workflow/001 then 002) and `CST_PRIVACY_DB` (durable SQLite outside checkout). No secrets or environment files are committed. Missing storage/config fails readiness; voice is unavailable without an explicit transcriber. No production memory/fixture fallback.

The factory wires actual public privacy/session/answer/M1/OutputGuard/publish ports, serialized cycle/question/M2, matching/Sky, moderated chat/report/block/mutual reveal, operator readers and authenticated per-player SSE. Cycle -> privacy -> workflow lock order is enforced; slow providers run outside storage transactions and late results recheck current state. No cross-database atomicity claim.

Will can import `LiveConstellation` from `web/src/features/constellations/chat/index.ts`, mount behind PrivacyGate with verified `cycleId` and own-session `viewerPlayerId`, and pass `demoTiming` from verified WeeklyCycle. viewerPlayerId stays local and is never authentication. Optional messageEvidence/nudgeSlot/projector retain their documented meanings. No Will-owned routing was edited. Live Muse text stays hidden without supplied evidence. The sender-only support card requires the exact allowlisted rejection; held text never becomes a message bubble.

## Tasks and verified scope

1. Archived foundation restored/adapted/retested; registry, middleware, strict camelCase validators, migrations and CI supplied.
2. Formation worker, guarded commit, Sunday publishing, durable recovery/retries and separate Sky jobs implemented. Actual first-lock retention purges canonical answer/guess and cycle-private workflow data. Demo rooms open at actual operator time.
3-5. Durable chat, handles, M1 then OutputGuard, reports, canonical blocks, rate limits, expiry, mutual-only identity, SSE seq/replay/member filtering implemented and offline tested against real owner ports.
6. Chat/Sky shared-fixture components plus authenticated HTTP/fetch-SSE container implemented. Runtime rejects private fields, stale responses and unrelated reveal identities; Sky does not recompute numbers and suppresses subthreshold themes/headlines. Synthetic/Fallback grouping/Demo timing labels preserved.
No deployment, physical-phone run, live provider run or complete live journey is claimed.

## Requests answered

- D005/D006 ACK posted #11 and copied to decisions by #18; D007 ACK posted #15 and accepted. Contracts remain unchanged.
- #13 Patrik privacy lease/publish guard, M1/OutputGuard/answer snapshots/report-block storage and #30 full registration delivery ACKed. These are delivered and used, not blockers.
- #14 registry, cycle slot/hooks, operator readers and UI exports delivered to Will. Root SerializedCycle uses only public owner methods; late session/consent/cycle gates tested.
- #26 Rishi timeout request delivered in 0c35cde (120s configurable execution ceiling, not under-60s performance evidence). Actual debug-baseline artifact requested separately; no fabricated data.
- #13 Adam composed app delivered in b1192cb/057f5aa (comment6844866340). Adam independently ran 271 passing planning/provider/orchestration tests with 2 PostgreSQL skips. His ChatSystemPoster/nudge wiring request ACKed in comment6845039376; adapter delivered on main and merged cleanly. Operator route now wired with both private lookups, durable dedupe and fresh publication checks; 13 new offline tests pass. DELIVERED comment6845201965 links pushed43f6009 and exact next scripted integration action.
- #31 D009 optional brightness proposal ACKed conditionally (comment6845059137): await producer/privacy ACKs and matching version/fixtures/validators before carrying bands; current app stays exact 2.0.0.
- #13 Patrik stale-handoff correction ACKed in comment6845039376; this handoff replaces the obsolete missing-privacy list.

## Checks and actual results

- Full local `pytest tests -q` at43f6009: 800 passed, 2 skipped, 13 subtests passed (23.04s), one Starlette TestClient httpx deprecation warning. The 2 skips require actual PostgreSQL admin DSN, absent locally. No model call.
- Focused composed app/recovery/provider-auth/bootstrap/serialization: 34 passed. Separate support/service/runtime/app agent check: 75 passed. Storage/planning: 51 passed + 2 PostgreSQL skips; chat real-port integration: 15 passed. Nudge/recovery/chat combined43passed; Ruff check/format clean on53owned Python files.
- Web lint exit0 with 2 existing warnings in Will-owned DailyPage/OperatorConsole; build passed. Initial full E2E: 36 passed/2 mobile page-load timeouts; both passed isolated with one worker (8.2s). Full single-worker repeat passed all 38 tests (1.8m). No browser suites overlapped.
- Full custom chat/Sky suite: 42 passed desktop/mobile (44.6s), including sender support cue vs contact rejection, pair-only identity, auth loss, replay, stale expiry and runtime privacy validation. Browser HTTP is intercepted by labeled TEST-ONLY adapter; not a backend/live integration claim.
- Earlier foundation CI at 62e6487 passed backend/PostgreSQL and frontend/browser. CI run43372465531 verified exact head de0f646: Backend/PostgreSQL passed46s and frontend/browser passed2m8s, including the configured real disposable PostgreSQL tests. Current source CI run43373392258 verified exact43f60093cd5cbf505079ff99997123a813f808d0: backend/PostgreSQL passed47s and frontend/browser passed1m50s. The disposable PostgreSQL jobs execute the actual storage/migration/RLS checks, not local skips. Subsequent docs-only checkpoint is not a new source validation claim.

## Remaining boundaries and next actions

- Rishi: actual IDs-only baseline debug artifact/public method needed for operator comparison (#26 comment6843775909). Current route returns retryable PROVIDER_UNAVAILABLE rather than deriving nonexistent groups from agreement flags.
- Named reveal-card metadata is absent from ChatRoom. Need producer/consumer-approved public projection for name/shape/isLooseMatch/evidence; do not expose full private Constellation or add fields silently. Formal Needs from Will recorded in #13 body alongside his verified Groups mount. Generic room/chat UI works; no fixture is claimed live.
- Will's cycle state/once-per-answer M2 cache is process-local; cycle owner routes validate idempotency headers but lack full actor/route/body replay. Public cache TTL hook not supplied. Workflow/chat/formation state and planning selection/decision stores are durable; this does not imply durable owner cycle/M2 state.
- Step6 operator M7 is now mounted using Adam's NudgeService/VenueCatalog/ChatSystemPoster. Both async private lookups scope to verified operator community; fresh consent/session/cycle/formation gates run before persistence, after M7 and inside chat commit after M1. Every public field/text passes real OutputGuard; member answers stay guard-only. First proposal wins durably, rows bind cycle + formation version, and chat command replay recovers a crash after posting. Private nudge data is removed on invalidation/14-day retention. Mid-week scheduling and step7 generation remain first cuts; no live M7 run.
- Required local acceptance and exact source-head CI now pass. Ownership/diff whitespace review clean across85changed paths relative to main; no contracts changed. Before ready/integration: resolve or explicitly cut the public card/debug/UI-mount boundaries through the named owners; do not merge a teammate draft. No independent required Kai task remains outside these interface boundaries. Source is available to Adam now.

## Parallelism and ownership

Storage/planning, chat service and live client agents worked on disjoint Kai-owned files; root reviewed, integrated, committed and pushed. Root implemented serialized cycle gates, runtime recovery, app/bootstrap and synthetic labels. Latest read-only peer agent checked delivery comments/planning prerequisites and nudge adversarial cases while root ran acceptance/implemented composition. It found stale cycle/formation row reuse; root fixed and tested both; no overlapping edits or browser suites. No measured speedup claim.
Only Kai-owned paths plus explicitly task1-authorized pyproject.toml/.github/workflows/validation.yml/db/workflow edited. Root alone performs Git integration/commits/pushes/PR changes; never force-push/reset/stash or merge teammate drafts. Sites skill was used for local repository UI only; no hosting/deployment.


## Adam operator panel delivery - 2026-11-13T05:52Z

Adam's new #13 comment6845295464 delivers OperatorNudgePanel/createNudgeRequester in main #34; he already asked Will to mount it on #31. Kai ACKed in comment6845333879 and merged current main d1c259d cleanly as32cc47b, preserving owner paths. Requester path/cookie/Idempotency-Key and validated EventNudge response match the backend already delivered43f6009. Targeted nudge + venue parity checks14passed; web lint exit0 with2existing Will warnings and build passed. Browser/full backend suites were not repeated for this delivery sync; prior source evidence remains above, new merged-head CI unverified. No paid call.
Next consumer: Will mounts OperatorNudgePanel in his console with apiBase=/api/v1 and an open roomId; Adam can exercise the actual scripted operator route now. Mid-week scheduling remains cut. Player chat Muse bubbles still require separately supplied messageEvidence in Kai's current live component; do not claim the full player nudge card/evidence mount is complete from this operator-panel delivery. Contracts remain unchanged.


## Composed-app main release - 2026-11-13T06:34:29Z

Latest human direction: answer Adam's06:02Z CHANGE on #13, merge verified app to main, and exclude optional baseline-debug/public-card work from the release gate. Current main6d7dc62 (including Will's console nudge mount#38) merged normally as95ecfa0. No teammate source was edited. This release supersedes the earlier draft/blocked status above; main merge SHA and exact final check results are recorded in the next checkpoint.

ACK item1 posted comment6845848957. CHANGE item2 clarified in comment6845873187: M6 routes are conditional on PlanningRuntime.generator, currently None in this factory. Actual pending output is [{question: Question, evidence: MuseCallEvidence}], not Question[]. Generate returns202{status:'pending',questions,rejected,evidence}; approve active Question; reject204. API rows/decision await Adam's producer ACK and Will's console-consumer ACK of the exact envelope. No contract file/type changed and no unmounted route claimed mounted. This separate contract work does not delay the composed app.

Rishi's MatchingPort.debug delivery#35 ACKed; not yet on main, optional guarded persistence/serving remains a separate follow-up. The existing debug endpoint still fails closed; no synthetic baseline invented. Named reveal metadata, D009/D010, mid-week nudge scheduling, chat NudgeCard and M6 enablement are excluded from this release, preserving current2.0.0 contracts and safety.

Verification observations: first normal full backend run802pass/1failure/2PGskips; serial repeat had the same Rishi schedule-test failure (61.5s then61.2s scaled). Exact unchanged assertion passed59.5s with process-only1ms Windows timer resolution, restored afterward; full suite with that setting follows. No owner file/threshold changed. Full app browser55pass/1intentional mobile skip. Chat/Sky initially40pass/2fail because sent-message text locator also matched pending draft textarea; fixed own test to scope to Messages list, retaining the visible-message assertion. Full custom rerun follows. Web lint/build exit0; warnings remain confined to Will-owned files. No live call.

Parallelism: one read-only agent checked M6 surface and then Windows scheduling sensitivity while root handled current-main sync, actual test runs, selector fix and release. No overlapping writes or browser suites. Root alone commits/pushes/merges.

2026-11-13T06:36:41Z local release check complete against6d7dc62: backend803passed/2PGskips with temporary1ms Windows timer setting; full app55passed/1intentional skip; full custom42passed after Messages-list selector fix. Before push, latest-main recheck found#40 newly merged asb9ada53 with contract2.1.0/owner source changes; merge and compatibility verification follow. No prior results are claimed for that new combined head.

2026-11-13T06:39:04Z current-main compatibility checkpoint: #40 merged during release checks (mainb9ada53; contract2.1.0 ahead of owner ACKs). Its new PRIVATE closeness/memberContext fields caused8formation/runtime/contract test failures. Kai-owned strict validators and matching-result roundtrip now accept/validate those private fields, preserve them privately and omit empty fields for legacy data. No public brightness/context projection or activity service is enabled. Targeted composition/formation/store/nudge74pass; separate legacy/private invalid-lineage regressions9pass; Ruff clean. Read-only agent wrote only separate owned regression file; root implemented/reviewed/ran checks. Full combined-head checks/CI follow; no source change in contracts or teammate paths.

2026-11-13T06:41:45Z latest-main full run834passed/2PGskips with one remaining version-advertisement failure: app config still said2.0.0 while main now declares2.1.0. Updated own health/app version and exact health test expectation; app-focused checks pass. This advertises existing main schema, not approval/activation of optional D009/D010 projections. All new private metadata regression checks pass. Main-release CI reruns on the new pushed head.
