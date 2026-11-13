# will handoff
Current step: 2-3 (foundation + daily loop) and the operator part of step 8, see docs/PLAN.md
Status: role tasks 1-7 implemented and fixture-verified. Nothing is composed into a running server, nothing has called Muse, nothing is deployed.
Branch + commit: `feat/will-constellations-feed-ui` @ d52b3ea (human-requested UI branch, open PR); `role/will-voice-ui` = main ea3672f (PR #29 merged).
Updated: 2026-11-13T04:29Z

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

## Added after teammates replied (2026-11-13T02:26Z)
- `CycleService.gate(cycleId) -> CycleGate(cycle, revision)` and `check_gate(cycleId, revision, status=None)` (`STALE_REVISION` when the cycle changed). For Kai's formation commit, reveal and room expiry.
- On lock the service calls `answers.mark_locked(cycleId, lockedAt)` when the store has it (Patrik's store does).
- `build_router(service, session_dependency, transcriber=None, require_consent=None)`: `session_dependency` may return Patrik's `Actor`; `require_consent(actor)` runs before answer, follow-up and guess writes. Reads and delete stay available after revocation.
- `tests/cycle/test_cycle_integration.py`: my service with Adam's real `CycleQuestionPort` from `server.planning` (offline bank), and an Actor-shaped session with a consent check.
- Operator console mounts Rishi's `FormationDebug` from `GET /operator/cycles/:id/formation-debug` (accepts his object alone or `{data, evidence, totalMs, usedFallback}`); fixture mode shows an honest empty state.

## Muse speech-to-text (2026-11-13T02:43Z, NOT verified live)
- `server/voice/muse_stt.py`: `MuseTranscriber`, `MuseSttConfig`, `load_muse_stt_config`, `build_transcriber(env=None)`. Provider format read from dev.meta.ai docs on 2026-11-13: `POST {base}/asr/transcribe`, multipart `request` (JSON: model `muse-voice-transcribe-1.0`, `audioEncoding: "WAV"`, `mode: "PUSH_TO_TALK"`, `languageBias`) + `audio`; response `{transcript, ...}`. Audio must be mono 16-bit PCM WAV at 16 or 24 kHz.
- Composition: pass `transcriber=server.voice.build_transcriber()` to `build_router`. It uses `MUSE_API_KEY` / `MODEL_API_KEY`, `MUSE_BASE_URL`, optional `MUSE_STT_MODEL`, `MUSE_STT_TIMEOUT_S`; with no key it is the 503 transcriber. It reads the process environment only (it does not load `server/providers/muse.env`).
- `web/.../daily/wav.ts`: the live client converts each recording to 16 kHz mono WAV in memory before upload.
- To verify with a key: `python -m server.voice.smoke` (one paid call, synthetic tone, prints status and timing only). Not run.
- Unknowns until a live call: whether the team key is enabled for the voice model, real latency, transcript quality on phone recordings, and Safari's decode of its own mp4 recordings.

## UI redesign + privacy gate (2026-11-13T03:47Z, branch `feat/will-daily-ui-polish`)
- Daily page redesigned: night-sky week view (answered days light stars; consecutive on-day answers draw the streak line), composer with "Only you can read this" bar and recording timer, Catch up section, collapsible Earlier this week, large-number guess slider, post-lock status card, skeleton and empty states, delete confirmation.
- Patrik's `PrivacyGate` mounted inside `DailyPage` (under the page header, so the title stays while joining); the week loads only after join with all three consents. His `SupportCard` replaces my inline card. `onDataDeleted` remounts the page; fixture mode also clears this tab's answers via the new optional `CycleClient.clearLocalData()`.
- Operator console redesigned: Mon..Close stepper, state pill, next-step button with its effect, confirmations for Reset and for New cycle over a running week, Muse call summary.
- Operator console is not gated (operators act through server roles); live-mode 401/403 show plain messages.
- Checks: web lint 0 errors (2 warnings in my files), build ok, Playwright 38 passed; full `pytest tests` 560 passed. Fixture mode only; not tried on a real phone.

## Facebook-native redesign (2026-11-13T04:29Z, branch `feat/will-constellations-feed-ui`)
- Home feed card (`daily/FeedCard.tsx`) directly under the composer: Join opens Patrik's `JoinScreen` in the shell `Modal`; joined players answer today's question in place.
- Left sidebar shortcut "Constellations"; `LeftSidebar` NavLinks now use `end` so only the exact page highlights.
- Page rebuilt as a Facebook Group page (cover, tabs, About column). Modules split: `useDaily.ts`, `QuestionPost.tsx`, `GuessCard.tsx`, `WeekGraph.tsx` (Obsidian-style force graph, draggable, keyboard-focusable day nodes).
- Styling uses the shell's tokens (`--blue`, `.card`, `.button-*`, `.post-meta`). My CSS restyles Patrik's `.cstp-card` only where it sits inside my page or my join dialog (spacing, border); his files are unchanged.
- Checks: web lint 0 errors (warnings only), build ok, Playwright 42 passed; `pytest tests` 560 passed. Fixture mode only; not on a real phone.

## Product direction from Will (human), 2026-11-13T04:38Z: needs a team decision, not yet proposed
- Constellations is a Facebook-wide feature, not one Group's. The UI now lives at `/constellations`; until the contract changes it plays in `PLAY_COMMUNITY` ("hackathon-builders") because cycles and sessions are community-scoped in 2.0.0 / D007.
- A constellation is you plus the people whose answers are most similar; the closer the match, the brighter their star. People who share your Groups may get a brighter signal.
- "Sky" and "Constellation" are one view; the UI has no separate Sky tab.
- Implications for owners (unacked): Rishi would publish per-member closeness (0-1) for each constellation and a shared-Group boost; Kai's reveal view would draw it; Patrik's sessions and Will's cycles would become global or multi-community. The Constellation tab shows only a labeled Example until that data exists.

## Shared files touched (claimed)
- `web/src/App.tsx` (`/constellations` routes plus redirects from the old Group paths), `web/src/pages/SecondaryPages.tsx` (per-Group link added earlier, now removed), `web/src/components/navigation/Header.tsx` (mobile title uses first path segment), `web/src/pages/HomePage.tsx` (one feed card line), `web/src/components/navigation/navigation.ts` (one sidebar item), `web/src/components/layout/LeftSidebar.tsx` (`end` on NavLink).
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
- Patrik (handoff "Blocked on", 2026-11-13): mount `PrivacyGate` + use `SupportCard` + Playwright join flow: DELIVERED on `feat/will-daily-ui-polish`. `AnswerStore` swap and `mark_locked`: my side done (lock calls it); the swap itself is in Kai's composition root.
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

- D009 constellation brightness (PR #31 comment https://github.com/Meta-Hackathon-SF/Meta-Hackathon/pull/31#issuecomment-6844535941): needs ACK from `@rishibagri` (per-member closeness banded bright/mid/faint), `@beatopia` (carry it on room members, reveal view), `@patrikliska13` (privacy sign-off). Until then the Constellation tab shows a labeled Example only.
- D010 more matching signals (Groups, Events, Posts/Comments behind an optional `useActivity` consent toggle): needs ACK from `@patrikliska13`, `@rishibagri`, `@adamzhang06`, `@beatopia`. Branch `feat/will-signals-rewards` shows them only as labeled Examples ("Needs your OK"); no such data is read.

## Branch feat/will-signals-rewards (2026-11-13)
From Will's product notes: streak rewards (`rewards.ts`, `StreakRewards.tsx`; cosmetic, computed in code from the server Streak + `isCatchUp`), "Why this group" (`MatchReasons.tsx`, Example, counts only before reveal), event heat (`EventHeat.tsx`, Example, code threshold 3 + bucketed counts), audience copy on the feed card and About. Verified: lint 0 errors, build ok, Playwright constellations suite passes (fixture mode only).

## Next action
Me: when Patrik's store/session and Kai's registry land, write the thin adapters, remove the fixture adapters from live composition, point the web app at `/api/v1`, and test on phones. Then durable cycle storage (Kai's migration order).
Consumers: Kai mounts `build_router`; Kai's job calls `advance(cycleId, "forming")` then `"revealed"`; Rishi reads `DailyAnswer.weight`/`isCatchUp` via Patrik's snapshot.
