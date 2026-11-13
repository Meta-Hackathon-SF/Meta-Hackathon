# Weekly cycle workflow (Constellations 2.0.0)
Cycle: Will. Formation and Sky numbers: Rishi. Rooms, reveal, realtime, composition: Kai. Questions and nudges: Adam. Safety, guards, storage: Patrik.

## Calendar (community time zone)
| When | What | Owner |
| --- | --- | --- |
| Sunday before | Adam selects 5 questions for Mon-Fri (QuestionPort.selectWeek) | Adam |
| Mon-Fri | One daily question released each morning. Answer on the day (weight 1.0, extends streak). Optional M2 follow-up. Prevalence guess any time before lock. | Will |
| Mon-Sat noon | Catch-up: answer any missed day of this cycle (weight 0.6, no streak credit) | Will |
| Saturday 12:00 | Lock. Answers frozen. Formation job runs. | Will (lock), Kai (job), Rishi (form) |
| Sunday 10:00 | Reveal. Constellation card, anonymous chat room opens, Sky published. | Kai |
| Sun-next Sat | Chat live; mid-week event nudge; mutual reveal any time | Kai, Adam |
| Next Saturday 12:00 | Room expires (read-only), next cycle locks | Kai |
| +14 days after lock | Answers, guesses, chat text deleted (TTL) | Patrik |

Demo: operator advances day, lock and reveal by button; UI shows "Demo timing". Same code path as real time.

## Cycle state machine
`open -> locked -> forming -> revealed -> closed`. `currentDay` advances 1..5 while open. No backward transitions except operator reset on fixture cycles. Answer writes check status at commit time (`CYCLE_LOCKED`).

## Streaks
`current` counts consecutive question days (Mon-Fri) answered on the day; weekends do not break it. A day caught up before lock is neutral (does not extend, does not break); a day with no answer breaks it. Between a missed day ending and its catch-up, `current` shows 0; after the catch-up it is restored (D008). Streak is private to the player.

## Formation job (Saturday lock)
1. Kai's worker calls `PrivacyPort.formationSnapshot(cycleId)`: consenting, unflagged, non-deleted answers with weights, random per-call ids, blocked pairs.
2. Rishi `FormationPort.form`: keyword/embedding baseline, M3 themes, M4 constellations by meaning (weights inform confidence), M5 names in parallel.
3. Rishi validation: 3-5, everyone exactly once, no blocked pair, loose-match label. Fail: one re-solve, then deterministic fallback (baseline grouping, labeled) or retryable operator error.
4. Patrik OutputGuard on names. Kai commits constellations in one transaction. Never hold a transaction open across a provider call.
5. Rishi `computeSky`: per-theme count, actualPercent, median guess of members, threshold filter, M8 headlines checked number by number.
6. Sunday reveal: Kai opens rooms (`ChatPort.openRooms`), assigns anonymous handles, publishes `constellation.revealed` and `sky.updated`.
7. Stale work (consent revoked, answer deleted after snapshot) is dropped at publish.

## Chat pipeline
Send: session and membership check, room open, rate limit (Kai) -> M1 screen + OutputGuard incl. contact info (Patrik) -> persist -> SSE. Distress: message hidden, sender gets the private support card. Report: hidden for reporter at once, operator queue; 2 distinct reports auto-hide pending review. Block: blocker no longer sees blocked handle; pair never shares a future constellation.

## Mutual reveal
`POST /rooms/:id/reveal {toHandle}` stores a RevealRequest. If the reverse request exists, one transaction creates MutualReveal and emits `reveal.mutual` to those two players only. Duplicate requests idempotent. Requests die with the room.

## Event nudges
Mid-week (Wed demo: operator button) Adam's NudgePort proposes one public event from `venues.json` campus events or allowlist venues. Guarded, posted as a `muse_nudge` message. Never an invite to a private place, never below 3 attendees.

## Recovery and latency
Jobs persist status, attempts, sanitized reason. Bounded retries with backoff. Provider outage: retryable operator error or a saved result labeled "Replay of a saved cycle". muse-spark-1.3 single calls observed at 17-24 s (2 calls, not a benchmark). Formation for 30 players under 60 s needs M1 at submit, M3/M4 once, M5 per constellation in parallel. Measure it.

## Acceptance tests
Out-of-order job completion; blocked pair re-solve; answer after lock; catch-up for future day; streak with catch-up; crash after commit; duplicate SSE delivery; reconnect replay by seq; revoked consent before commit; room expiry; one-sided reveal; duplicate reveal; reported message; Sky with 2-member theme.
