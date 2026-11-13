# Shared contracts: Facebook Space 2.1.0 (weekly game; 2.1.0 adds D009 brightness + D010 activity, additive)
Common interface agreement for all five workstreams. Normative design plus TypeScript wire declarations and JSON fixtures. Not a running backend.

## Files
- [protocol.ts](protocol.ts): `CONTRACT_VERSION = "2.1.0"`. Typechecks with `npx -p typescript@5.6.3 tsc --noEmit --strict --target es2020 --lib es2020,dom contracts/protocol.ts`.
- [API.md](API.md) routes, [WORKFLOW.md](WORKFLOW.md) weekly state machine and jobs, [PRIVACY.md](PRIVACY.md) access matrix and required tests.
- [fixtures/](fixtures): shared synthetic test data every owner builds against: `question-bank.json`, `week-sample.json` (8 synthetic players, answers, blocks, distress and injection cases, expected formation constraints), `sky-stats.json`, `chat-room.json`, `venues.json`. Fixtures are synthetic and must stay labeled as such.

1.0.0 (hunt rounds, clues, found codes) is retired. Archived Group Quests code on `archive/group-quests-before-pivot` is reference only; restore pieces into your own paths and retest them against 2.0.0.

## Ownership
| Contract | Producer | Consumers |
| --- | --- | --- |
| Consent, sessions, Block, SafetyFlag, PrivacyPort, OutputGuard, M1 | Patrik | everyone |
| Question bank, QuestionPort, MusePort, M2, M6 question generation, M7 EventNudge/NudgePort | Adam | Will, Kai, Rishi |
| WeeklyCycle, DailyQuestion, DailyAnswer, WEIGHTS, Streak, CatchUpState, PrevalenceGuess, CyclePort | Will | Rishi, Kai, Patrik |
| Theme, Constellation, SkyStats, SyntheticSignal, FormationPort, M3, M4, M5, M8 | Rishi | Kai (renders Sky, opens rooms), Adam |
| ChatRoom, AnonymousHandle, ChatMessage, Report, RevealRequest, MutualReveal, StreamEvent, ChatPort, API composition | Kai | Will (shell), Patrik (moderation), Adam (nudges) |

## Validation rules (code enforces, Muse proposes)
- Facebook Space: size 3-5; every eligible player placed exactly once; no blocked pair; weak fits get `isLooseMatch`, never dropped silently. Eligible = consented, not flagged, at least one non-deleted answer this cycle.
- Weights: server sets `DailyAnswer.weight` (on-day 1.0, catch-up 0.6, +0.1 if follow-up used, max 1.1). Clients never send weight. Catch-up allowed only for missed days of the current cycle and only before Saturday lock. Catch-up never extends a streak.
- No-quote: no constellation name, theme label, Sky headline, nudge or generated question contains 5+ consecutive words from any answer.
- Sensitive categories (never in Muse-written public text): health, sexuality, religion, finances, family trauma, home location.
- Sky: a theme renders only if `count >= threshold` (3 demo, 25 production). Suppressed themes return a count only. Synthetic signals are never mixed into real counts and always render with "Synthetic signal".
- Chat: every message passes M1 screening and OutputGuard (adds `contact_info` while no reveal exists). Rejected message returns `MESSAGE_REJECTED`. Rooms expire at `expiresAt` (next Saturday lock); expired rooms are read-only, then deleted with the cycle's TTL.
- Mutual reveal: identity is revealed only when both players have requested each other. The requester never learns a refusal; `RevealResult` is `pending` until mutual.
- Prompts contain random per-call ids and text only. M8 and M6 receive aggregates only.
- Every Muse call: strict JSON, schema-validated, one retry, then labeled fallback or retryable operator error.
- Auth from the server session only; never accept `playerId` from the client as identity. Demo timing is operator-set.
- IDs opaque and server-created; times RFC3339 UTC; days in the community time zone.

## Required boundary cases
Voice fails and typing works; one follow-up max per answer; distress answer never appears anywhere after M1; prompt injection stays data; deleted answer absent from re-run; answer after lock returns `CYCLE_LOCKED`; catch-up for a future day rejected; blocked pair rejected and re-solved; theme with 2 members never renders; message to expired room returns `ROOM_EXPIRED`; one-sided reveal leaks nothing; reported message hidden for reporter immediately; consent revoked mid-job publishes nothing for that player.

## Changing a contract
Proposal in a PR, entry in docs/DECISIONS.md, ACK from producer and every consumer, version bump, fixtures and tests updated together. See docs/COORDINATION.md.
