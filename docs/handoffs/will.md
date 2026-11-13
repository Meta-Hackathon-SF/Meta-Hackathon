# will handoff
Current step: 2-3 (foundation + daily loop) and the operator part of step 8, see docs/PLAN.md
Status: role tasks 1-7 implemented and fixture-verified. Nothing is composed into a running server, nothing has called Muse, nothing is deployed.
Branch + commit: `role/will-voice-ui` @ 8e03bd1; PR #14 merged to main as 4437e21 (2026-11-13)
Updated: 2026-11-13T04:10Z

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

## Added after teammates replied (2026-11-13T03:05Z)
- `CycleService.gate(cycleId) -> CycleGate(cycle, revision)` and `check_gate(cycleId, revision, status=None)` (`STALE_REVISION` when the cycle changed). For Kai's formation commit, reveal and room expiry.
- On lock the service calls `answers.mark_locked(cycleId, lockedAt)` when the store has it (Patrik's store does).
- `build_router(service, session_dependency, transcriber=None, require_consent=None)`: `session_dependency` may return Patrik's `Actor`; `require_consent(actor)` runs before answer, follow-up and guess writes. Reads and delete stay available after revocation.
- `tests/cycle/test_cycle_integration.py`: my service with Adam's real `CycleQuestionPort` from `server.planning` (offline bank), and an Actor-shaped session with a consent check.
- Operator console mounts Rishi's `FormationDebug` from `GET /operator/cycles/:id/formation-debug` (accepts his object alone or `{data, evidence, totalMs, usedFallback}`); fixture mode shows an honest empty state.

## Muse speech-to-text (2026-11-13T04:10Z, NOT verified live)
- `server/voice/muse_stt.py`: `MuseTranscriber`, `MuseSttConfig`, `load_muse_stt_config`, `build_transcriber(env=None)`. Provider format read from dev.meta.ai docs on 2026-11-13: `POST {base}/asr/transcribe`, multipart `request` (JSON: model `muse-voice-transcribe-1.0`, `audioEncoding: "WAV"`, `mode: "PUSH_TO_TALK"`, `languageBias`) + `audio`; response `{transcript, ...}`. Audio must be mono 16-bit PCM WAV at 16 or 24 kHz.
- Composition: pass `transcriber=server.voice.build_transcriber()` to `build_router`. It uses `MUSE_API_KEY` / `MODEL_API_KEY`, `MUSE_BASE_URL`, optional `MUSE_STT_MODEL`, `MUSE_STT_TIMEOUT_S`; with no key it is the 503 transcriber. It reads the process environment only (it does not load `server/providers/muse.env`).
- `web/.../daily/wav.ts`: the live client converts each recording to 16 kHz mono WAV in memory before upload.
- To verify with a key: `python -m server.voice.smoke` (one paid call, synthetic tone, prints status and timing only). Not run.
- Unknowns until a live call: whether the team key is enabled for the voice model, real latency, transcript quality on phone recordings, and Safari's decode of its own mp4 recordings.

## Shared files touched (claimed)
- `web/src/App.tsx` (two routes), `web/src/pages/SecondaryPages.tsx` (one link on the Hackathon Builders card), `web/src/components/navigation/Header.tsx` (mobile title uses first path segment).
- `docs/DECISIONS.md`: my ACK lines under D005 and D006 only.
- No change to `contracts/`.

## Checks run + actual result
- `python -m pytest tests/cycle tests/voice` -> 100 passed, 13 subtests passed (Python 3.11.9, pydantic 2.14.3, fastapi 0.162.5, local venv; no `pyproject.toml` on main yet).
- `web/`: `npm run lint` exit 0 (4 warnings in my files: fetch-on-mount effects), `npm run build` ok, `npm run test:e2e` -> 32 passed (16 feed + 16 constellations, desktop + mobile).
- Acceptance: answer after lock `CYCLE_LOCKED` (service + HTTP); future-day rejected; client `weight`/`playerId`/`isCatchUp` -> `INVALID_INPUT`; streak fixture -> 2; mic denied -> typing submits (Playwright, fake mic); operator full demo week test completes in about 3 s on the fixture adapter.

## Fixture versus live evidence
All fixture. Server tests use `server/cycle/testing.py` (TEST-ONLY stand-ins for Patrik's store/M1/seeder and Adam's QuestionPort/M2). The web UI ran only on the in-browser fixture adapter, labeled "Fixture mode · no server, no Muse". The HTTP client has never talked to a server. The Muse speech-to-text adapter exists but has never made a live call. Cycle state is in-memory and lost on restart. Not tested on a physical phone.

## Proposed additive API (needs ACK; not in contracts/API.md)
`GET /cycles/:id/answers` (own answers), `POST /voice/transcribe` (raw audio body -> `{transcript, mode}`), `PATCH answers/:day` body `{text, answersFollowUp?}`, response shapes `{cycle, question, streak, catchUp}` and `{answer, supportCard}`, optional `evidence: MuseCallEvidence` on the follow-up response (for the Muse chip), a read route for my own guess.

## Requests answered
- D005 ACK and D006 ACK posted in PR #14 (2026-11-13).
- Kai (PR #13 "Needs from Will"): ACK registry; DELIVERED CyclePort, router factory and the revision gate.
- Rishi (PR #14 comment): ACK D008 streak rule; DELIVERED FormationDebug mount in the operator console.
- Adam (PR #14 comment): ACK `CycleQuestionPort` / `SyncClarify`; integration-tested the question port.
- Patrik (handoff + D007): ACK join/session response shape in DECISIONS.md; router accepts `Actor` and `require_consent`; `mark_locked` is called on lock.
- No open PR, issue or comment mentioned `@willapat` at session start.

## Blocked on (PR #14)
- `@beatopia`: `server/app` registry on main (PR #13 is still a draft) so the router can be mounted; `CycleHooks` implementation; `GET /operator/calls` and `/operator/reports` sources.
- `@patrikliska13`: `server/privacy/answers.py` (AnswerStore) and M1 `screen` on main; they are on his branch or planned. Open question: does `purge_cycle` clear `mark_locked` so an operator reset of a demo cycle can accept answers again?
- `@adamzhang06`: nothing blocking. `SyncClarify` needs a live Muse and Patrik's real OutputGuard before the follow-up is live.
- `@rishibagri`: nothing blocking. Confirm the formation-debug response envelope.

## Next action
Me: when Patrik's store/session and Kai's registry land, write the thin adapters, remove the fixture adapters from live composition, point the web app at `/api/v1`, and test on phones. Then durable cycle storage (Kai's migration order).
Consumers: Kai mounts `build_router`; Kai's job calls `advance(cycleId, "forming")` then `"revealed"`; Rishi reads `DailyAnswer.weight`/`isCatchUp` via Patrik's snapshot.
