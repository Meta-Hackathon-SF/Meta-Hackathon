# adam handoff
Current step: 3 (daily loop), tasks 1, 2, 3 and 6 in docs/roles/adam.md done offline; next is task 4 (step 6, event nudges, cuttable)
Status: Muse adapter restored for 2.0.0; question bank, weekly selection and M2 follow-up implemented. Offline-verified only.
Branch + commit: `role/adam-planning` at 78bcedd (code), PR #12 https://github.com/willapat/Meta-Hackathon/pull/12
Updated: 2026-11-13T02:12Z

## Completed tasks
1. `server/providers/` restored from `archive/group-quests-before-pivot`, renamed, extended to the 2.0.0 `MuseTask` list (M1-M8), retested. **Live call NOT re-verified**: no Muse key on this machine (`python3 -m server.providers.smoke` -> `not_configured`).
2. Question bank loader + validation; `QuestionService.select_week`, `released`, `question_for_day`.
3. M2 clarify: `ClarifyService.follow_up`, prompt `clarify.v1`.
6. Muse voice block: `server/providers/voice.py` (`MUSE_VOICE`).

Not started: task 4 (M7 event nudges, nudge card UI), task 5 (M6 question generation), HTTP routes.

## Changed interfaces and files
- No change to `contracts/`. Shared-file edit claimed: one ACK line each under D005 and D006 in docs/DECISIONS.md.
- `server/providers/`: `MusePort.run(MuseRequest) -> MuseResult`, `KeywordMusePort.run(task=, requestId=, promptVersion=, payload=)`, `contract_spec`, `IN_SCHEMAS`/`OUT_SCHEMAS`, `EvidenceLog` (`muse.evidence_log.list()` for GET /operator/calls), `MUSE_VOICE`, `FixtureMuse`.
- `server/planning/`: `QuestionBank`, `load_default_bank`, `QuestionService`, `ClarifyService`, `register_planning_tasks`, ports `OutputGuardPort`, `ChatPostPort`, `WeekStartLookup`, stores `SelectionStore`, `ClarifyStore`.
- `server/planning/data/question-bank.json`: 32 curated questions, superset of the shared fixture (the 12-row fixture cannot fill a third week under the four-week no-repeat rule).
- Tests: `tests/providers/`, `tests/planning/` (`doubles.py` holds the TEST-ONLY adapters).

## Checks run + actual result
- `pytest tests/planning tests/providers`: 69 passed, offline, Python 3.12.9, pytest 9.2.0 (2026-11-12).
- `python3 -m unittest discover -s tests/providers -t .`: 38 OK.
- `python3 -m server.providers.smoke`: exit 2, `not_configured`.
- No web/ changes; web checks not run.

## Fixture versus live evidence
Everything is fixture evidence. Muse outputs come from `FixtureMuse` (labeled `source: "replay"`, model `fixture:scripted-muse`). OutputGuard, cycle lookup and chat are test-only doubles. No route mounted, no durable storage, no live model call on this adapter. Latency figures in server/providers/README.md are from the retired adapter.

## Requests answered
- 2026-11-12: no open PR, issue or comment mentioned `@adamzhang06` at session start.
- ACK D005 and ACK D006 posted in PR #12 and copied to docs/DECISIONS.md.

## Blocked on
Nothing blocks the merged scope. Live wiring needs (requested in PR #12):
- `@patrikliska13`: real `OutputGuard.check`; operator session check for my routes.
- `@beatopia`: router registry for my routes; durable `SelectionStore`/`ClarifyStore`; `ChatPort.postSystem`.
- `@willapat`: `cycleId -> weekStart` lookup; follow-up route passes M1 flag and `followUpUsed`.
- Human (Adam): a Muse key in `server/providers/muse.env` to run the live smoke call.

## Next action
- Me: task 4 (M7 nudges behind the doubles) only if step 6 is not cut; otherwise HTTP routers once Kai's registry exists. Run the live smoke as soon as a key is available and record model echo + latency in server/providers/README.md.
- Consumers: Rishi/Patrik register prompts with `contract_spec` (server/providers/README.md). Will calls `ClarifyService.follow_up` and `QuestionService.released` (server/planning/README.md). Kai calls `register_planning_tasks(registry)` and builds one adapter per process.
