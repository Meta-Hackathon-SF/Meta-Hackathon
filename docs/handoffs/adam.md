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

Not done: live calls beyond the one M2 smoke; anything running inside the composed app.

## Changed interfaces and files
- No change to `contracts/`. Shared-file edits claimed: one ACK line each under D005 and D006 in docs/DECISIONS.md; my four rows in the PROJECT_KNOWLEDGE.md evidence ledger.
- PROPOSED additive routes, not in contracts/API.md, need ACK from Kai (composition) and Will (operator console): `GET /operator/questions/pending`, `POST /operator/questions/{id}/approve`, `POST /operator/questions/{id}/reject`. `POST /operator/questions/generate` returns 202 `{status: "pending", questions, rejected, evidence}`.
- `server/providers/`: `MusePort.run(MuseRequest) -> MuseResult`, `KeywordMusePort.run(task=, requestId=, promptVersion=, payload=)`, `contract_spec`, `IN_SCHEMAS`/`OUT_SCHEMAS`, `EvidenceLog` (`muse.evidence_log.list()` for GET /operator/calls), `MUSE_VOICE`, `FixtureMuse`.
- `server/planning/`: `QuestionBank`, `load_default_bank`, `QuestionService`, `ClarifyService`, `register_planning_tasks`, ports `OutputGuardPort`, `ChatPostPort`, `WeekStartLookup`, stores `SelectionStore`, `ClarifyStore`.
- `server/planning/data/question-bank.json`: 32 curated questions, superset of the shared fixture (the 12-row fixture cannot fill a third week under the four-week no-repeat rule).
- `server/planning/` nudges: `NudgeService`, `VenueCatalog`, `ConstellationContext` lookup (new port needed from orchestration), `InMemoryNudgeStore`; `data/venues.json` equals the shared fixture.
- `web/src/features/constellations/nudges/`: `NudgeCard`, `parseEventNudge`, `parseVenue`, `formatWindow`. Not mounted on a route.
- Tests: `tests/providers/`, `tests/planning/` (`doubles.py` holds the TEST-ONLY adapters).

## Checks run + actual result
- `pytest tests/planning tests/providers`: 101 passed with FastAPI installed; 93 passed, 8 skipped without it (router tests skip). `pytest tests`: 194 passed on merged main. Before generation: 91 passed (router tests need FastAPI; run with fastapi 0.162.5, pydantic 2.14.3). `pytest tests`: 184 passed on merged main. Earlier count before adapters/router: 81 passed, offline, Python 3.12.9, pytest 9.2.0 (2026-11-12).
- `web/`: `npm run lint` clean; `npm run build` ok; `npm run test:e2e` fails to launch the bundled browser (binary not installed); `PLAYWRIGHT_CHANNEL=chrome npx playwright test` -> 16 passed (existing feed tests). The nudge card has no browser test and has not been looked at in a browser.
- `python3 -m unittest discover -s tests/providers -t .`: 38 OK.
- `python3 -m server.providers.smoke`: exit 0, live M2 call ok (2026-11-13T02:25Z). Earlier the same day: exit 2, `not_configured`, before the key was added.

## Fixture versus live evidence
One live Muse call exists: the M2 smoke call above, on a synthetic answer. Everything else is fixture evidence. Muse outputs come from `FixtureMuse` (labeled `source: "replay"`, model `fixture:scripted-muse`). OutputGuard, cycle lookup and chat are test-only doubles. No route mounted, no durable storage, no live call for M1 or M3-M8, and plus five live calls through the real services on synthetic fixture input (2026-11-13T02:29-02:31Z, `python3 -m tests.planning.live_check`): M2 x3, M7 x1, M6 x1, all passed validators with the TEST-ONLY guard; table in server/planning/README.md. Observed latency 10-25 s per call.

## Requests answered
- 2026-11-12: no open PR, issue or comment mentioned `@adamzhang06` at session start.
- ACK D005 and ACK D006 posted in PR #12 and copied to docs/DECISIONS.md.
- PR #14 (Will, needs QuestionPort + M2 clarify): ACK + DELIVERED `CycleQuestionPort`, `SyncClarify` at 728d2ab (https://github.com/willapat/Meta-Hackathon/pull/14#issuecomment-6841884230).
- PR #13 (Kai, needs 2.0.0 public factory + readiness export): ACK + DELIVERED `build_muse_adapter`, `register_planning_tasks`, `server.planning.api.build_router`, `PlanningRuntime.ready` (https://github.com/willapat/Meta-Hackathon/pull/13#issuecomment-6841884567).
- Rishi handoff question (instructions inside payload?): answered on PR #11 with ACK on the call shape and CHANGE: register prompts via `contract_spec`/`TaskSpec`, drop `instructions` from payloads (https://github.com/willapat/Meta-Hackathon/pull/11#issuecomment-6841774528).

## Blocked on
Nothing blocks the merged scope. Live wiring needs (requested in PR #12):
- `@patrikliska13`: nothing. Real `OutputGuard` delivered in PR #24 and verified with my services (tests/planning/test_real_guard.py + 4 live calls).
- `@beatopia`: router registry for my routes; durable `SelectionStore`/`ClarifyStore`; `ChatPort.postSystem`; the `ConstellationContext` lookup for nudges; mid-week job + operator button calling `NudgeService.propose_and_post`; placing `NudgeCard` in chat.
- `@willapat`: nothing further; his cycle service overwrites dates, so the weekStart lookup is only needed for the operator select-week route on a cycle that was not created through his service.

## Real OutputGuard and card check (2026-11-13T03:05Z)
- `python -m pytest tests/planning tests/providers`: 106 passed; `python -m pytest tests`: 560 passed on merged main. All 32 curated questions and hints pass the real guard.
- `python -m tests.planning.live_check` with the real guard: M2 x2, M7, M6 all passed (4 paid calls, 4.6-18.4 s).
- Nudge card viewed in Chrome at 360 px and 900 px via a temporary, uncommitted preview page; no overflow; replay label shown. No committed browser test.

## API budget
Adam's Muse key has a $100 cap for the whole event including the demo. About 44 live calls so far on Adam's key (1 smoke, 9 planning live checks, 28 for Rishi's formation timing, plus retries); Adam reported about 10 cents after the first 12. Live runs stay manual, capped (`MAX_PROVIDER_CALLS = 6` in tests/planning/live_check.py) and targeted with the name filter; ordinary tests never call the model.

## Next action
- Me: no unblocked build task left in my role file; then verify the router inside Kai's composed app once #13 lands.
- Consumers: Rishi/Patrik register prompts with `contract_spec` (server/providers/README.md). Will calls `ClarifyService.follow_up` and `QuestionService.released` (server/planning/README.md). Kai calls `register_planning_tasks(registry)` and builds one adapter per process.
