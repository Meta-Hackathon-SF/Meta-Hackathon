# adam handoff
Current step: 7 (question generation) done offline. All six tasks in docs/roles/adam.md are implemented offline; what remains is live verification and integration with other owners
Status: Muse adapter restored for 2.0.0; question bank, weekly selection, M2 follow-up, M7 event nudges, the nudge card and M6 question generation implemented. Offline-verified only.
Branch + commit: `role/adam-planning`; PRs #12 and #17 merged to main; question generation in the follow-up PR. PR #12 merged to main (655903a); nudges in the follow-up PR.
Updated: 2026-11-13T03:05Z

## Completed tasks
1. `server/providers/` restored from `archive/group-quests-before-pivot`, renamed, extended to the 2.0.0 `MuseTask` list (M1-M8), retested. **Live call re-verified 2026-11-13T02:25Z**: `python3 -m server.providers.smoke` -> ok, `clarify` (M2), provider echoed `muse-spark-1.3`, 16.2 s, attempt 1, `reasoning_effort=low`.
2. Question bank loader + validation; `QuestionService.select_week`, `released`, `question_for_day`.
3. M2 clarify: `ClarifyService.follow_up`, prompt `clarify.v2` (v1 produced a generic yes/no follow-up live; v2 plus a code check for yes/no openings fixed it in one recheck).
4. M7 event nudges: `VenueCatalog`, `NudgeService.propose` / `propose_and_post`, prompt `event_nudge.v1`; `NudgeCard` in `web/src/features/constellations/nudges/`. Mid-week schedule and operator button NOT wired (need Kai).
6. Muse voice block: `server/providers/voice.py` (`MUSE_VOICE`).

Also done: sync adapters for Will's cycle service (`CycleQuestionPort`, `SyncClarify`) and the operator router for Kai's registry (`server/planning/api.py`).
5. M6 question generation: `QuestionGenerator.generate / pending / approve / reject`, prompt `question_generation.v1`; generated questions stay pending and inactive until an operator approves.

Not done: `OperatorNudgePanel` mounted in the console (Will); M1 on nudge text called live; the mid-week nudge schedule (Kai, cuttable). Kai's composed app with my nudge wiring is on role/kai-orchestration, not yet on main.

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

## API budget
Adam's Muse key has a $100 cap for the whole event including the demo. About 45 live calls so far on Adam's key (1 smoke, 9 planning live checks, 28 for Rishi's formation timing, plus retries); Adam reported about 10 cents after the first 12. Live runs stay manual, capped (`MAX_PROVIDER_CALLS = 6` in tests/planning/live_check.py) and targeted with the name filter; ordinary tests never call the model.

## Next action
- Will or Kai: mount `OperatorNudgePanel` in the operator console for an open room.
- Me: no unblocked build task left. Once Kai wires nudges into `PlanningRuntime`, run the operator nudge route in his app (offline scripted Muse), then one capped live M7.
- Consumers: Rishi/Patrik register prompts with `contract_spec` (server/providers/README.md). Will calls `ClarifyService.follow_up` and `QuestionService.released` (server/planning/README.md). Kai calls `register_planning_tasks(registry)` and builds one adapter per process.
