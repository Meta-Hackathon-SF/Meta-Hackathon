# Will: weekly cycle, daily answers, voice, streaks, operator controls
Branch `role/will-voice-ui` · Handle `@willapat` · Build order steps 2, 3, 8 (shell)

## You own
| Path | What |
| --- | --- |
| `server/cycle/` | WeeklyCycle state machine, day release, Saturday lock, Sunday reveal trigger (calls Kai), catch-up rules, server-side weights, streaks, prevalence guess, CyclePort |
| `server/voice/` | voice boundary: transcription adapter, typed fallback |
| `tests/cycle/`, `tests/voice/` | tests |
| `web/src/features/constellations/daily/` | Facebook Space tab entry, today's question, answer by voice or text, follow-up, catch-up list, streak chip, guess slider, edit/delete until lock, Muse metadata chip |
| `web/src/features/constellations/operator/` | operator console: new cycle, advance day, lock, reveal, synthetic top-up, reset, Muse call list, report queue view |
| shell routing | add the Facebook Space tab inside Groups in `web/src/App.tsx` and navigation; keep feed tests green |

Not yours: answer storage tables (Patrik owns storage; you call his service), chat/reveal/Sky UI (Kai), questions (Adam).

## Interfaces
Produce: `CyclePort`, `WeeklyCycle`, `DailyQuestion`, `DailyAnswer` (via Patrik storage), `WEIGHTS`, `Streak`, `CatchUpState`, `PrevalenceGuess`, routes under "Weekly cycle" in contracts/API.md.
Consume: `QuestionPort.selectWeek` + M2 (Adam), Patrik's answer store + M1 at submit, Kai's reveal trigger and API registration.

## Tasks
1. Restore `server/voice/transcription.py` from the archive; adapt and retest. Typed input always works.
2. Cycle state machine + calendar (community time zone) + demo timing flag (operator-only).
3. Answer submit/edit/delete/catch-up with server weights; reject future days and post-lock writes.
4. Streak computation (Mon-Fri on-day only; catch-up never counts).
5. Daily answer UI (mobile-first, works on phones in the room), catch-up, streak, guess slider; all synthetic items labeled.
6. Operator console with every control in contracts/API.md "Operator".
7. Facebook Space tab in Groups; scoped CSS; existing Playwright feed tests still pass.

## Acceptance checks
- `pytest tests/cycle tests/voice` green; `npm run lint && npm run build && npm run test:e2e` in `web/` green.
- Answer after lock returns `CYCLE_LOCKED`; catch-up for a future day rejected; weight never accepted from client.
- Streak fixture: answered Mon, Tue on day, Wed catch-up -> current 2 after Wed ends.
- Mic denied -> typing still submits.
- Operator can run a full demo week in under 3 minutes with "Demo timing" visible.
