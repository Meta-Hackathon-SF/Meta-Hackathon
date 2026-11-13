# will handoff
Current step: 2-3 (foundation + daily loop) and the operator part of step 8, see docs/PLAN.md
Status: role tasks 1-7 implemented and fixture-verified. Nothing is composed into a running server, nothing has called Muse, nothing is deployed.
Branch + commit: `role/will-voice-ui` @ 262338a (draft PR #14)
Updated: 2026-11-13T02:25Z

## Completed tasks (docs/roles/will.md)
1. `server/voice/` restored from the archive, renamed to daily-answer terms, transcript cap 400. Default transcriber is unconfigured (503); typing never depends on it.
2. `server/cycle/` state machine `open -> locked -> forming -> revealed -> closed` (forward only, one step), community-time-zone calendar, demo timing flag.
3. Answer submit/edit/delete/catch-up with server weights; future days rejected; writes re-check status at commit (`CYCLE_LOCKED`).
4. Streaks (on-day only; caught-up day neutral; missed day resets).
5. Daily answer UI (`web/src/features/constellations/daily/`): voice or text, follow-up, catch-up, streak chip, guess slider, labels.
6. Operator console (`web/src/features/constellations/operator/`): new cycle, advance, lock, form, reveal, close, synthetic top-up, reset, Muse call list, report queue view.
7. Constellations tab under Groups (`/groups/hackathon-builders/constellations`, `/operator`); feed tests unchanged and passing.

## Interfaces published
- `server.cycle.CycleService`: `current(communityId)`, `advance(cycleId, to)` (= `CyclePort`), `create_cycle`, `reset`, `synthetic_topup`, `current_view`, `released_questions`, `my_answers`, `submit_answer`, `edit_answer`, `delete_answer`, `followup`, `put_guess`, `streak`.
- `server.cycle.api.build_router(service, session_dependency, transcriber=None)` and `install_cycle_error_handler(app)`; paths have no `/api/v1` prefix.
- `server/cycle/wire.py`: Pydantic validators mirroring protocol.ts 2.0.0 for my shapes; `WEIGHTS`.
- `server/cycle/ports.py`: the shapes I consume (`AnswerStore`, `QuestionPort`, `SafetyScreen`, `Clarify`, `TextGuard`, `CycleHooks`, `SyntheticSeeder`, `Session`).
- Web: `CycleClient` in `daily/client.ts` (hand validators for every response), `httpClient.ts` (live, used when `VITE_CONSTELLATIONS_API` is set), `fixtureClient.ts` (TEST-ONLY).

## Shared files touched (claimed)
- `web/src/App.tsx` (two routes), `web/src/pages/SecondaryPages.tsx` (one link on the Hackathon Builders card), `web/src/components/navigation/Header.tsx` (mobile title uses first path segment).
- `docs/DECISIONS.md`: my ACK lines under D005 and D006 only.
- No change to `contracts/`.

## Checks run + actual result
- `python -m pytest tests/cycle tests/voice` -> 68 passed, 13 subtests passed (Python 3.11.9, pydantic 2.14.3, fastapi 0.162.5, local venv; no `pyproject.toml` on main yet).
- `web/`: `npm run lint` exit 0 (4 warnings in my files: fetch-on-mount effects), `npm run build` ok, `npm run test:e2e` -> 30 passed (16 feed + 14 constellations, desktop + mobile).
- Acceptance: answer after lock `CYCLE_LOCKED` (service + HTTP); future-day rejected; client `weight`/`playerId`/`isCatchUp` -> `INVALID_INPUT`; streak fixture -> 2; mic denied -> typing submits (Playwright, fake mic); operator full demo week test completes in about 3 s on the fixture adapter.

## Fixture versus live evidence
All fixture. Server tests use `server/cycle/testing.py` (TEST-ONLY stand-ins for Patrik's store/M1/seeder and Adam's QuestionPort/M2). The web UI ran only on the in-browser fixture adapter, labeled "Fixture mode · no server, no Muse". The HTTP client has never talked to a server. No speech-to-text provider is configured. Cycle state is in-memory and lost on restart. Not tested on a physical phone.

## Proposed additive API (needs ACK; not in contracts/API.md)
`GET /cycles/:id/answers` (own answers), `POST /voice/transcribe` (raw audio body -> `{transcript, mode}`), `PATCH answers/:day` body `{text, answersFollowUp?}`, response shapes `{cycle, question, streak, catchUp}` and `{answer, supportCard}`, optional `evidence: MuseCallEvidence` on the follow-up response (for the Muse chip), a read route for my own guess.

## Requests answered
- D005 ACK and D006 ACK posted in PR #14 (2026-11-13).
- No open PR, issue or comment mentioned `@willapat` at session start.

## Blocked on (PR #14 has the "Needs from" blocks)
- `@patrikliska13`: session dependency, private answer store, M1 `screen`, synthetic player seeding, OutputGuard for M2 text.
- `@adamzhang06`: `QuestionPort.select_week`, M2 clarify callable (ideally with evidence).
- `@beatopia`: registry owner slot `cycle` + mount, `pyproject.toml`/deps on main, `CycleHooks` (SSE, formation job, reveal), `GET /operator/calls` and `/operator/reports`.
- `@rishibagri`: confirm the streak rule (caught-up day neutral vs strict reset).

## Next action
Me: when Patrik's store/session and Kai's registry land, write the thin adapters, remove the fixture adapters from live composition, point the web app at `/api/v1`, and test on phones. Then durable cycle storage (Kai's migration order).
Consumers: Kai mounts `build_router`; Kai's job calls `advance(cycleId, "forming")` then `"revealed"`; Rishi reads `DailyAnswer.weight`/`isCatchUp` via Patrik's snapshot.
