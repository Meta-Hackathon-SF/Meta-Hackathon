# Durable workflow (Constellations)
Owner: Kai. Induction: Rishi. Keeper/riddles: Adam. Authorization/guards: Patrik.

## Round state machine
open -> locked -> inducting -> hunt -> sky -> closed
Hunt carries levelUnlocked 0..3. Only the operator (or the timer) moves forward; no backward transitions except operator reset (fixture rounds only). Answers can be edited or deleted only while open (ROUND_LOCKED after).

## Induction job pipeline
1. Submit time: each answer gets M1 safety screen (M2 clarify at submit too). Flagged answers are excluded everywhere and routed to the private support card.
2. Lock (operator): freeze answers; snapshot unflagged, consenting, non-deleted answers; assign random per-call IDs.
3. M3 theme discovery then M4 society formation (Rishi, InductionPort.induct(roundId)).
4. Validate M4: size 3-5, everyone exactly once, blocks respected, loose-match label for weak fits. A blocked pair or other failure is rejected and re-solved (one retry), then labeled fallback or retryable operator error.
5. In parallel: M5 identity per society, and M6 riddles per target per seeker (three levels each). Run through OutputGuard.check (no-quote, sensitive terms).
6. Validation passes for every society before anyone sees it. Then one transaction commits societies, riddles (unreleased), passphrase halves and found codes.
7. Publish after commit via SSE. Reconnect reads the persisted state and resumes by sequence. Delivery may repeat; unique constraints make effects idempotent. Never hold a DB transaction open during a provider call.
8. Stale jobs (consent revoked, answer deleted) must not publish.

## Level unlock
Real: Level 1 Tuesday, Level 2 Wednesday, Level 3 Friday (community time zone). Demo: every 20 s or operator advance-level; UI shows "Demo timing". Vetoed riddles (P1) are never released.

## Find confirm transaction
POST finds {foundCode}: look up the code inside the caller's own society only. Not found or other society returns not_a_match with no detail. First tap records pending; when both sides have submitted each other's code, one transaction inserts Find with a unique unordered pair constraint and returns confirmed. Duplicate confirm is idempotent. Success reveals only displayName and lights the SSE constellation link.

## Sky aggregation
Server computes per-theme guessed vs actual percent from Guess and Theme membership. Themes with count below threshold (3 demo, 25 production) are dropped before any output. M8 gets counts only; validate every number equals server counts; one retry then fallback to template headlines. Excludes flagged and deleted answers.

## Ritual (P1)
When every member is found, M7 proposes a quest (approved public venue, under budget cap). Each member taps In or Not this week; at 3 or more In, create the Event, group chat and opener. Fewer than 3 means nothing is created.

## Recovery
Persist job status pending/running/succeeded/failed, attempts, retry deadline, sanitized reason. Bounded retries with backoff. Provider outage gives a retryable operator error, or a cached result only if labeled "Replay of a saved round".

## Latency note
muse-spark-1.3 single calls were observed at 17-24 s (reasoning_effort=low, 2 calls, not a benchmark). Under 60 s for 30 players requires parallelism: M1/M2 at submit, M5 per society and M6 riddles in parallel, and precompute while the round is open where possible. Top technical risk.

## Acceptance tests
Parallel jobs finishing out of order; blocked pair re-solve; duplicate confirm; wrong code leaks nothing; worker crash after commit; duplicate publish; reconnect replay; revoked consent before commit; delete then re-run; level advance idempotent; Sky threshold with 2-member theme.
