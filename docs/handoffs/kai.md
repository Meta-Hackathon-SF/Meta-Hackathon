# Kai handoff - Constellations 2.0.0

Branch: `role/kai-orchestration`; handle: `@beatopia`; repository: `Meta-Hackathon-SF/Meta-Hackathon`.
Updated 2026-11-13T05:39Z. Source checkpoints: b1192cb composed app, 057f5aa delivery docs, de0f646 private support-card UI, 0c51048 clean merge of current main (3f62413); operator nudge checkpoint follows. PR #13 remains draft pending final CI/integration review.

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
- #13 Adam composed app delivered in b1192cb/057f5aa (comment6844866340). Adam independently ran 271 passing planning/provider/orchestration tests with 2 PostgreSQL skips. His ChatSystemPoster/nudge wiring request ACKed in comment6845039376; adapter delivered on main and merged cleanly. Operator route now wired with both private lookups, durable dedupe and fresh publication checks; 13 new offline tests pass.
- #31 D009 optional brightness proposal ACKed conditionally (comment6845059137): await producer/privacy ACKs and matching version/fixtures/validators before carrying bands; current app stays exact 2.0.0.
- #13 Patrik stale-handoff correction ACKed in comment6845039376; this handoff replaces the obsolete missing-privacy list.

## Checks and actual results

- Full local `pytest tests -q`: 782 passed, 2 skipped, 13 subtests passed, one Starlette TestClient httpx deprecation warning. The 2 skips require actual PostgreSQL admin DSN, absent locally. No model call.
- Focused composed app/recovery/provider-auth/bootstrap/serialization: 34 passed. Separate support/service/runtime/app agent check: 75 passed. Storage/planning: 51 passed + 2 PostgreSQL skips; chat real-port integration: 15 passed. Ruff check/format clean on 51 owned Python files.
- Web lint exit0 with 2 existing warnings in Will-owned DailyPage/OperatorConsole; build passed. Initial full E2E: 36 passed/2 mobile page-load timeouts; both passed isolated with one worker (8.2s). Full single-worker repeat passed all 38 tests (1.8m). No browser suites overlapped.
- Full custom chat/Sky suite: 42 passed desktop/mobile (44.6s), including sender support cue vs contact rejection, pair-only identity, auth loss, replay, stale expiry and runtime privacy validation. Browser HTTP is intercepted by labeled TEST-ONLY adapter; not a backend/live integration claim.
- Earlier foundation CI at 62e6487 passed backend/PostgreSQL and frontend/browser. CI run43372465531 verified exact head de0f646: Backend/PostgreSQL passed46s and frontend/browser passed2m8s, including the configured real disposable PostgreSQL tests. Nudge/main-merge head needs its own run; do not reuse de0f646 as evidence for later code.

## Remaining boundaries and next actions

- Rishi: actual IDs-only baseline debug artifact/public method needed for operator comparison (#26 comment6843775909). Current route returns retryable PROVIDER_UNAVAILABLE rather than deriving nonexistent groups from agreement flags.
- Named reveal-card metadata is absent from ChatRoom. Need producer/consumer-approved public projection for name/shape/isLooseMatch; do not expose full private Constellation or add fields silently. Generic room/chat UI works.
- Will's cycle state/once-per-answer M2 cache is process-local; cycle owner routes validate idempotency headers but lack full actor/route/body replay. Public cache TTL hook not supplied. Workflow/chat/formation state and planning selection/decision stores are durable; this does not imply durable owner cycle/M2 state.
- Step6 operator M7 is now mounted using Adam's NudgeService/VenueCatalog/ChatSystemPoster. Both async private lookups scope to verified operator community; fresh consent/session/cycle/formation gates run before persistence, after M7 and inside chat commit after M1. Every public field/text passes real OutputGuard; member answers stay guard-only. First proposal wins durably, rows bind cycle + formation version, and chat command replay recovers a crash after posting. Private nudge data is removed on invalidation/14-day retention. Mid-week scheduling and step7 generation remain first cuts; no live M7 run.
- Before ready: finish required web acceptance and verify current CI including actual disposable PostgreSQL tests, then review exact head against current main. Source remains available to Adam now.

## Parallelism and ownership

Storage/planning, chat service and live client agents worked on disjoint Kai-owned files; root reviewed, integrated, committed and pushed. Root implemented serialized cycle gates, runtime recovery, app/bootstrap and synthetic labels. Latest read-only peer agent checked delivery comments/planning prerequisites and nudge adversarial cases while root ran acceptance/implemented composition. It found stale cycle/formation row reuse; root fixed and tested both; no overlapping edits or browser suites. No measured speedup claim.
Only Kai-owned paths plus explicitly task1-authorized pyproject.toml/.github/workflows/validation.yml/db/workflow edited. Root alone performs Git integration/commits/pushes/PR changes; never force-push/reset/stash or merge teammate drafts. Sites skill was used for local repository UI only; no hosting/deployment.
