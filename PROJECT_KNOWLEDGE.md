# Shared project knowledge
## Evidence baseline
Main is the mock Facebook shell only (`web/`: React/Vite/TypeScript, local demonstration state, feed components, secondary routes, Playwright tests), plus documentation and `contracts/protocol.ts`. Date of this baseline: 2026-11-12 (Facebook Space pivot and repo reset). Main was reset to the shell; the earlier Group Quests server code, tests, database files and provider adapter were removed. They survive only on branch `archive/group-quests-before-pivot` as reference. Under D005 owners restore reusable pieces (FastAPI app, Muse adapter, privacy/session code, voice boundary) into their own paths and retest them against contract 2.0.0; nothing restored counts as verified until its tests pass on main. Earlier Group Quests test counts are not claimed.

2026-11-12 weekly-game pivot (D005/D006): contract 2.0.0 and `contracts/fixtures/` added; typecheck passes; fixtures parse. Baseline check reported by the audit: `web/` build and lint pass; Playwright browser tests could not launch a browser, so UI regression verification is outstanding.

Muse model note (2026-11-12): `muse-spark-1.3` answered 2 live calls and the provider echoed the model name, through the removed Group Quests adapter. Observed single-call latency was 17 to 24 s at low reasoning effort. Two calls are not a benchmark, and no Facebook Space code has called the model. Wonder and Ember were not available in the docs read and were not tested. Re-verified on the 2.0.0 adapter 2026-11-13T02:25Z: one `clarify` (M2) call on a synthetic answer, provider echoed `muse-spark-1.3`, 16.2 s at low effort, first attempt. Three single calls in total across both adapters; still not a benchmark.

Role-branch work from teammates is not claimed integrated here; inspect their latest handoffs and PRs (see [docs/COORDINATION.md](docs/COORDINATION.md)) before declaring a dependency missing.

## Locked decisions
- Product: Facebook Space weekly game (D005). Daily questions Mon-Fri, catch-up until Saturday 12:00 lock, streaks (on-day only), Sunday 10:00 reveal, anonymous moderated chat expiring at next lock, mutual reveal, event nudges, thresholded Sky with labeled synthetic signals.
- Removed: hunt mechanics, clues, found codes, Keeper, Ritual, society branding. Terms: constellation (not society), daily answer (not confession), weekly cycle (not round).
- Existing Facebook mock UI is the host shell, labeled "Simulated Facebook"; feed tests stay green. Feature UI under `web/src/features/constellations/<area>/`.
- Ownership (D005): Rishi formation/validation/prevalence; Adam Muse adapter/questions/nudges; Will cycle/daily answers/voice/streaks/operator; Patrik verification/sessions/storage/safety/guards; Kai chat/expiry/reveal/realtime/API composition/Sky UI.
- Contract: `contracts/protocol.ts` 2.0.0 (D006, pending ACK). Fixtures in `contracts/fixtures/`.
- Friendship only, 18+, public places only. Facebook Space of 3 to 5.
- Muse proposes, code enforces. OutputGuard on every Muse public text and chat message.
- Answers never shown to other players. Identity only on mutual reveal.
- Sky themes only at 3+ (demo) / 25+ (production).
- Server sets answer weights (on-day 1.0, catch-up 0.6, +0.1 follow-up, max 1.1).
- Never cut: consent, safety screening, OutputGuard, Sky threshold, chat moderation, labels. First cuts: event nudges (step 6), question generation + synthetic signals (step 7).
- Coordination: check tags first; when blocked, push, open a `[BLOCKED]` draft PR and continue behind a labeled test-only adapter (docs/COORDINATION.md, D004).

## Confirm
- **Organizer confirmation of the Muse model** (Spark, Wonder or Ember). `muse-spark-1.3` worked in 2 earlier live calls; Wonder and Ember are untested. Open.
- Latency plan: confirm parallel calls bring formation for 30 players under 60 s given 17 to 24 s per call. Top technical risk.
- Backend hosting, database/auth setup, public venue allowlist, demo Group, submission rules.
- Deadline used in planning: November 13, 2026 at 10:30 AM PST, supplied by the team, not independently verified. Feature freeze 04:30 AM.
- Acknowledgment from all five owners of D005 (weekly game and ownership) and D006 (contract 2.0.0).

## Evidence ledger
| Capability | Owner | Status | Required evidence |
| --- | --- | --- | --- |
| Facebook shell (`web/`) | Will | Existing; mock data; DESIGN.md tokens + polish merged (#55) | Lint 0 errors, build ok, Playwright 71 passed / 1 skipped (2026-11-13, #61) |
| Contract 2.0.0 + fixtures | all | Authored; typechecks; pending D006 ACK | ACK from all five owners |
| API composition (`server/app/`) | Kai | Planned (restore from archive) | Registry, health, every owner's router mounted |
| Muse adapter (`server/providers/`) | Adam | Implemented for 2.0.0 (M1-M8 validators, one malformed retry, evidence log); offline tests pass; **one live M2 call verified** 2026-11-13T02:25Z (`muse-spark-1.3` echoed, 16.2 s, low effort) | Live calls for M1 and M3-M8; timing under parallel load |
| Sessions, consent, private storage (`server/privacy/`) | Patrik | Planned (restore from archive) | 403 test; prompt payload test; TTL test |
| Safety screening + OutputGuard | Patrik | Planned | Seeded distress never appears; no-quote fuzz; red-team 30 |
| Weekly cycle, daily answers, catch-up, streaks | Will | Implemented (`server/cycle`); offline tests pass (lock, catch-up, streak fixture, `answered_today`, `question_texts` #63); not live-verified on phones | A full live week in the composed app |
| Voice boundary (`server/voice/`) | Will | Implemented (upload + D012 live STT relay); offline tests pass; live STT tried on a local harness in desktop Chrome only | Transcription or typed fallback on a phone |
| Question bank + selection, M2 follow-up | Adam | Implemented; offline tests pass, including against the real OutputGuard; live M2 calls pass the real guard (synthetic input, 2026-11-13); operator router not mounted | Run inside the composed app with the real session |
| Semantic formation + validation | Rishi | Planned | week-sample constraints; baseline split example; 30 players timed |
| Prevalence + SkyStats | Rishi | Planned | Threshold test; numbers equal server counts |
| Anonymous chat, moderation, report/block | Kai (+Patrik) | Planned | Contact-info rejection; report hides; block |
| Expiry + mutual reveal | Kai | Planned | ROOM_EXPIRED; one-sided reveal leaks nothing |
| Realtime SSE | Kai | Planned | Reconnect replay by seq; per-player filtering |
| Sky UI | Kai | Planned | Threshold respected; synthetic labels |
| Operator console | Will | Implemented, fixture-verified: full demo week under 3 min (Playwright), close day, custom-event approval queue, reasoning panel (#61); live routes for v3 panels not yet mounted | Same run against the composed server with live Muse |
| Event nudges (step 6, cuttable) | Adam | Implemented server side + card; allowlist and guard tests pass offline with the real OutputGuard; one live M7 nudge passed it; card viewed in a temporary preview only; nothing posted to a real room | Kai's ChatPort and constellation lookup; a nudge seen in a room |
| Question generation + synthetic signals (step 7, cuttable) | Adam, Rishi | Generation with operator approval implemented, offline tests pass; approval routes proposed, not in API.md; synthetic signals not started here | ACK of approval routes; aggregate signals from Rishi; live M6 call |
| v3 daily UI: day colors, daily reveal (S5), your week (S6), `answeredToday` (D012) | Will | Implemented on main (#61) behind a labeled TEST-ONLY adapter; guess UI removed; guess route held until 3.0.0 | Contract 3.0.0 + Rishi's S5/S6 routes, then a live run |
| User impact | all | Unknown | Actual observations only |
