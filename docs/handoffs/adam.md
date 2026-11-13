# adam handoff
Current step: integration + deployment. Ownership relaxed 2026-11-13 ~11:40Z: Adam and Rishi own the whole repo (Will, Kai, Patrik offline); contract ACKs no longer gate merges
Status: v3 events (#76), per-task Muse router in the app (#87), Dockerfile (#89) merged; Railway now auto-deploys main from GitHub and runs ff68afc (verified 12:05Z)
Branch + commit: `role/adam-planning` synced with main ff68afc+; merged today: #76, #87, #88, #89
Updated: 2026-11-13T12:10Z

## Deployment (Railway, verified 2026-11-13T12:05Z)
- Project `constellations-demo` (workspace "kai's Projects"), env `production`, service `constellations-api` + `Postgres`; domain constellations-api-production.up.railway.app.
- Source: GitHub `Meta-Hackathon-SF/Meta-Hackathon` branch `main` (connected 12:05Z); every merge to main deploys. Builder: repo `Dockerfile` (reconstructed from the old build log in #89); start command in service settings. Before this, deploys were Kai's local `railway up` snapshot, so #80/#76/#87 were not live.
- Verified: deployment 2d149f2b = ff68afc, `/health/ready` 200 with all 7 services ready, `/api/v1/session` 401, clean startup log.
- Still off: v3 per-viewer routes (`/events`, `/me/nudges`, custom events) are not composed in `server/app/weekly.py` (404). The demo's Sunday nudge uses the v2 room nudge, which is live. Privacy `InterestBucket` uses `6-10`/`11+` while contract + matching use `6-9`/`10+`; align when composing.
- Pending: `railway ssh --service constellations-api -- python -m server.providers.route_check --live` (~$0.01) to confirm each task is served on its measured model.

## Completed tasks
1. `server/providers/` restored from `archive/group-quests-before-pivot`, renamed, extended to the 2.0.0 `MuseTask` list (M1-M8), retested. **Live call re-verified 2026-11-13T02:25Z**: `python3 -m server.providers.smoke` -> ok, `clarify` (M2), provider echoed `muse-spark-1.3`, 16.2 s, attempt 1, `reasoning_effort=low`.
2. Question bank loader + validation; `QuestionService.select_week`, `released`, `question_for_day`.
3. M2 clarify: `ClarifyService.follow_up`, prompt `clarify.v2` (v1 produced a generic yes/no follow-up live; v2 plus a code check for yes/no openings fixed it in one recheck).
4. M7 event nudges: `VenueCatalog`, `NudgeService.propose` / `propose_and_post`, prompt `event_nudge.v1`; `NudgeCard` in `web/src/features/constellations/nudges/`. Mid-week schedule and operator button NOT wired (need Kai).
6. Muse voice block: `server/providers/voice.py` (`MUSE_VOICE`).

Also done: sync adapters for Will's cycle service (`CycleQuestionPort`, `SyncClarify`) and the operator router for Kai's registry (`server/planning/api.py`).
5. M6 question generation: `QuestionGenerator.generate / pending / approve / reject`, prompt `question_generation.v1`; generated questions stay pending and inactive until an operator approves.

Not done: M1 on nudge text called live; the mid-week nudge schedule (Kai, cuttable). Kai's composed app with my nudge wiring is on role/kai-orchestration, not yet on main.

## Changed interfaces and files
- No change to `contracts/`. Shared-file edits claimed: one ACK line each under D005 and D006 in docs/DECISIONS.md; my four rows in the PROJECT_KNOWLEDGE.md evidence ledger.
- PROPOSED additive routes, not in contracts/API.md, need ACK from Kai (composition) and Will (operator console): `GET /operator/questions/pending`, `POST /operator/questions/{id}/approve`, `POST /operator/questions/{id}/reject`. `POST /operator/questions/generate` returns 202 `{status: "pending", questions, rejected, evidence}`.
- `server/providers/`: `MusePort.run(MuseRequest) -> MuseResult`, `KeywordMusePort.run(task=, requestId=, promptVersion=, payload=)`, `contract_spec`, `IN_SCHEMAS`/`OUT_SCHEMAS`, `EvidenceLog` (`muse.evidence_log.list()` for GET /operator/calls), `MUSE_VOICE`, `FixtureMuse`.
- `server/planning/`: `QuestionBank`, `load_default_bank`, `QuestionService`, `ClarifyService`, `register_planning_tasks`, ports `OutputGuardPort`, `ChatPostPort`, `WeekStartLookup`, stores `SelectionStore`, `ClarifyStore`.
- `server/planning/data/question-bank.json`: 32 curated questions, superset of the shared fixture (the 12-row fixture cannot fill a third week under the four-week no-repeat rule).
- `server/planning/` nudges: `NudgeService`, `VenueCatalog`, `ConstellationContext` lookup (new port needed from orchestration), `InMemoryNudgeStore`; `data/venues.json` equals the shared fixture.
- `web/src/features/constellations/nudges/`: `NudgeCard`, `OperatorNudgePanel`, `createNudgeRequester`, `APPROVED_VENUES`, `parseEventNudge`, `parseVenue`, `formatWindow`. Not mounted on a route.
- `server/planning/adapters.py`: `ChatSystemPoster` (bridges to chat `postSystem`).
- Tests: `tests/providers/`, `tests/planning/` (`doubles.py` holds the TEST-ONLY adapters).

## Checks run + actual result
- `pytest tests/planning tests/providers`: 101 passed with FastAPI installed; 93 passed, 8 skipped without it (router tests skip). `pytest tests`: 194 passed on merged main. Before generation: 91 passed (router tests need FastAPI; run with fastapi 0.162.5, pydantic 2.14.3). `pytest tests`: 184 passed on merged main. Earlier count before adapters/router: 81 passed, offline, Python 3.12.9, pytest 9.2.0 (2026-11-12).
- `web/`: `npm run lint` clean; `npm run build` ok; `npm run test:e2e` fails to launch the bundled browser (binary not installed); `PLAYWRIGHT_CHANNEL=chrome npx playwright test` -> 16 passed (existing feed tests). The nudge card has no browser test and has not been looked at in a browser.
- `python3 -m unittest discover -s tests/providers -t .`: 38 OK.
- `python3 -m server.providers.smoke`: exit 0, live M2 call ok (2026-11-13T02:25Z). Earlier the same day: exit 2, `not_configured`, before the key was added.

## Fixture versus live evidence
Live (synthetic input, Adam's key): the M2 smoke (02:25Z); planning live checks M2 x5, M7 x2, M6 x2 (test guard 02:29Z, real guard 03:05Z); Rishi's formation timing runs M3/M4/M5/M8 (02:40Z, 02:51Z); one M7 through Kai's composed app route (05:56Z). Everything else is fixture evidence from `FixtureMuse` (labeled `source: "replay"`, model `fixture:scripted-muse`). Planning routes run inside Kai's composed app with durable selection, clarify and nudge bookkeeping on his branch; they are not deployed.

## Requests answered
- 2026-11-12: no open PR, issue or comment mentioned `@adamzhang06` at session start.
- ACK D005 and ACK D006 posted in PR #12 and copied to docs/DECISIONS.md.
- PR #14 (Will, needs QuestionPort + M2 clarify): ACK + DELIVERED `CycleQuestionPort`, `SyncClarify` at 728d2ab (https://github.com/willapat/Meta-Hackathon/pull/14#issuecomment-6841884230).
- PR #13 (Kai, needs 2.0.0 public factory + readiness export): ACK + DELIVERED `build_muse_adapter`, `register_planning_tasks`, `server.planning.api.build_router`, `PlanningRuntime.ready` (https://github.com/willapat/Meta-Hackathon/pull/13#issuecomment-6841884567).
- Rishi handoff question (instructions inside payload?): answered on PR #11 with ACK on the call shape and CHANGE: register prompts via `contract_spec`/`TaskSpec`, drop `instructions` from payloads (https://github.com/willapat/Meta-Hackathon/pull/11#issuecomment-6841774528).

## Blocked on
Nothing blocks the merged scope. Live wiring needs (requested in PR #12):
- `@patrikliska13`: nothing. Real `OutputGuard` delivered in PR #24 and verified with my services (tests/planning/test_real_guard.py + 4 live calls).
- `@beatopia`: router registry, durable `SelectionStore`/`ClarifyStore` and `postSystem` are DELIVERED on role/kai-orchestration b1192cb (not on main yet). Still needed: pass `nudges=NudgeService(muse, guard, VenueCatalog.load(), <ConstellationContext lookup>, ChatSystemPoster(chat))`, `venues` and `room_constellation` into `PlanningRuntime` (today only `questions` is passed, so the nudge route reports unavailable); the mid-week job; placing `NudgeCard` in chat.
- `@willapat`: nothing further; his cycle service overwrites dates, so the weekStart lookup is only needed for the operator select-week route on a cycle that was not created through his service.

## Real OutputGuard and card check (2026-11-13T03:05Z)
- `python -m pytest tests/planning tests/providers`: 106 passed; `python -m pytest tests`: 560 passed on merged main. All 32 curated questions and hints pass the real guard.
- `python -m tests.planning.live_check` with the real guard: M2 x2, M7, M6 all passed (4 paid calls, 4.6-18.4 s).
- Nudge card viewed in Chrome at 360 px and 900 px via a temporary, uncommitted preview page; no overflow; replay label shown. No committed browser test.

## Kai composed app check (2026-11-13T05:21Z)
- Worktree at origin/role/kai-orchestration 057f5aa (b1192cb app): `python -m pytest tests/planning tests/providers tests/orchestration` 271 passed, 2 skipped (PostgreSQL DSN not set). Kai edits none of my paths; every planning name he imports exists.
- His `ChatService.postSystem(roomId, message)` accepts exactly the `{roomId, handle: "Muse", text, kind}` my nudge sends. Added `ChatSystemPoster` (server/planning/adapters.py) to bridge `post_system` -> `postSystem`; tested against a double copying his input check. Not run against his real chat service. No live calls.

## Operator nudge panel (2026-11-13T05:45Z)
- `OperatorNudgePanel` + `createNudgeRequester` + `APPROVED_VENUES` in web/src/features/constellations/nudges/ give the demo beat "Muse posts an event nudge" an operator button (Will's console has none). Chat itself only gets the nudge text as a `muse_nudge` bubble (Kai's ChatPanel already renders it).
- Checks: web lint (no new warnings), build ok, `PLAYWRIGHT_CHANNEL=chrome npx playwright test` 38 passed; `python -m pytest tests` 563 passed, 1 skipped; temporary preview in Chrome covered posted/failure/bad venue/cancel. Not mounted; not run against the server.

## Nudge route in Kai's composed app (2026-11-13T05:56Z)
- Kai wired `NudgeService` + `ChatSystemPoster` + both lookups in 43f6009 (role/kai-orchestration, now cad28cb; not on main yet).
- Consumer check (scratch, uncommitted) with Kai's `runtime_environment` + scripted Muse: the route's output has exactly the EventNudge keys, UTC times and an allowlisted venue, so it passes `parseEventNudge` rules. The M7 input has only `{sharedMeaning, venues, window, campusEvents}`. One `muse_nudge` message from handle Muse. Non-operator gets 403 FORBIDDEN, unknown room 404 NOT_FOUND.
- One paid live M7 through the same route (all other tasks scripted): 200, `v-cafe`, 8.0 s, evidence live `muse-spark-1.3`. M1 on the nudge text was scripted.
- Full suite on Kai's branch: `python -m pytest tests` 801 passed, 2 skipped (PostgreSQL DSN not set).

## Deploy defaults (2026-11-13T07:00Z)
- `load_muse_config` now defaults to `MUSE_TIMEOUT_S=60` and `MUSE_REASONING_EFFORT=low` (validated: low, medium, high), the settings every live run used. docs/DEPLOYMENT.md lists only key/model/base URL, so before this a key-only deploy would have used 30 s with the provider's "high" effort, which timed out live. `python -m pytest tests` 837 passed, 2 skipped on main + this change.

## Reasoning audit + trace (2026-11-13T07:30Z)
- Shared-file claim: new `docs/audits/2026-11-13-reasoning-audit.md` (findings for all owners; each marked verified or reported).
- Mine, offline-tested: schema-path retry feedback; `KeywordMusePort.run(correction=)`; `ReasoningTrace` on every adapter (`adapter.reasoning_trace`, codes/counts only, replay-labeled for fixtures); M6 `question_generation.v2` + near-duplicate, category quota, reason counts, `basis.matchedSignals`, yes/no generated hints removed; `signals.aggregate_signals` (k>=5, n>=10, 0.05 rounding); trace notes in M2/M6/M7; PROPOSED `GET /operator/reasoning` (mounted only when `PlanningRuntime.trace` is set; needs Kai ACK + API.md).
- Live: 2 M6 calls (v2 draft 15.5 s; final v2 12.5 s; 3/3 kept and grounded each time).
- `python -m pytest tests` 858 passed, 2 skipped.

## Live evals, router, contract 2.2.0 proposal (2026-11-13T09:00Z)
- 4 eval agents, 285 capped calls, about $1.21, synthetic only (`docs/audits/2026-11-13-live-evals.md`; scripts, corpora and counts-only ledger in `tests/providers/live_evals/`).
- Mine, offline-tested on `role/adam-planning`:
  - `MuseRouter` with `MEASURED_ROUTES`;
  - Wonder and Ember models, with per-model efforts;
  - provider token usage and estimated cost per call;
  - D015 event ids (was D013);
  - D014 contract 2.2.0 proposal, with mechanical version and callType bumps in other owners' paths (listed in D014).
- PRs for owners' review, not merged by me:
  - #53 (Rishi): Sky no-quote fix and friend count off.
  - In-progress branches: `adam/rishi-formation-v2`, `adam/patrik-guard-fold`, `adam/patrik-muse-classifiers`.
- `python -m pytest tests`: 898 passed, 2 skipped. Web lint: 0 errors. Build passes.

## D014 ACKed (2026-11-13T08:34Z, recorded 10:00Z)
All four owners ACKed on #60. Patrik's M9 sign-off has conditions (redaction, cap, consent copy), which he implemented on #59. Rishi: v3 (3.0.0, D012) builds on 2.2.0 and removes M5/M8. #58 was merged by Patrik with his review fixes. Will delivered `server/cycle` `question_texts` (#63); my `QuestionService.question_texts` is an equivalent reader from the planning selection, so Kai uses one of them.

## v3 events and custom events + live audit (2026-11-13T10:00Z)
- Live full-loop audit: 4 agents, 947 calls, $2.81. Findings filed as #70 (Kai), #71 (Patrik), #72 (Rishi), #73 (Will) and #74 (mine). The formation break it found (#59 + #62) was fixed by Patrik's #69.
- 3.0.0 review on #68: ACK on my shapes. CHANGE proposals: (1) catalog `end`, done; (2) M7 copy shapes; (3) `custom_event` stays under `event_nudge`; (4) align the v3 fixtures to the catalog. 2-4 await Rishi.
- Built offline: `EventsService`, `EventNudgeService` (copy and cadence), `CustomEventService`, the v3 routes, `sensitivity_allows(required=True)` for v3 paths, and catalog end times. `python -m pytest tests`: 1343 passed, 2 skipped, 12 xfailed. Not composed by Kai yet.

## API budget
Adam's Muse key has a $100 cap for the whole event including the demo. About 47 earlier calls, 285 eval calls ($1.21) and 947 audit calls ($2.81) so far on Adam's key (1 smoke, 9 planning live checks, 28 for Rishi's formation timing, plus retries); Adam reported about 10 cents after the first 12. Live runs stay manual, capped (`MAX_PROVIDER_CALLS = 6` in tests/planning/live_check.py) and targeted with the name filter; ordinary tests never call the model.

## Next action
- DONE (Will, #38 f88311f): `OperatorNudgePanel` mounted in the operator console; verified on main 6d7dc62: Playwright 55 passed incl. the nudge test on desktop+mobile, pytest 565 passed 1 skipped.
- DONE (Kai, #13 fed042e): composed app on main; `POST /api/v1/operator/rooms/{roomId}/nudge` mounted; tests/orchestration/test_nudges.py 13 passed on main.
- M6 generation/approval routes: NOT mounted in the composed app (`PlanningRuntime.generator` is None). Correction: `GET /operator/questions/pending` returns `[{question, evidence}]`, not `Question[]` as I wrote earlier. Kept cut (step 7); no API.md rows unless it is enabled.
- Me: no unblocked build task left. Once Kai wires nudges into `PlanningRuntime`, run the operator nudge route in his app (offline scripted Muse), then one capped live M7.
- Consumers: Rishi/Patrik register prompts with `contract_spec` (server/providers/README.md). Will calls `ClarifyService.follow_up` and `QuestionService.released` (server/planning/README.md). Kai calls `register_planning_tasks(registry)` and builds one adapter per process.
