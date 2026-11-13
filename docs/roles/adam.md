# Adam: Muse adapter, questions, event nudges
Branch `role/adam-planning` · Handle `@adamzhang06` · Build order steps 2, 3, 6, 7

## You own
| Path | What |
| --- | --- |
| `server/providers/` | the single Muse adapter (MusePort): transport, config, strict JSON, one retry, fallback, evidence (model, callType, latency, live/replay), fixture/replay transport |
| `server/planning/` | question bank, M2 clarify, M6 question generation and weekly selection (QuestionPort), M7 event nudges (NudgePort), venue allowlist loader |
| `tests/planning/`, `tests/providers/` | tests |
| `web/src/features/constellations/nudges/` | event nudge card rendered inside chat (Kai places it) |

Not yours: chat rooms (Kai), safety screening (Patrik), formation prompts (Rishi writes them; your adapter runs them).

## Interfaces
Produce: `MusePort.run`, `QuestionPort.selectWeek`, `NudgePort.propose`, `Question`, `EventNudge`, `Venue`, M2/M6/M7 I/O.
Consume: `OutputGuard.check` (Patrik) on every generated question and nudge; `ChatPort.postSystem` (Kai) to post nudges; `contracts/fixtures/question-bank.json`, `venues.json`.

## Tasks
1. Restore `server/providers/*` from `archive/group-quests-before-pivot` (port, transport, schema, fixture, smoke, config, `muse.env.example`). Rename Group Quests terms, extend `MuseTask` to the 2.0.0 list, retest. Re-verify one live `muse-spark-1.3` call and record model echo + latency.
2. Question bank loader + schema validation of `question-bank.json`; `selectWeek` picks 5 for Mon-Fri with category mix, no repeats within 4 weeks, low sensitivity on Monday.
3. M2 clarify: one follow-up max per answer; Will calls it.
4. (Step 6, cuttable) M7 event nudges: input sharedMeaning + venues + campus events; output must use an allowlisted placeId, guarded `why`, `minAttendees` 3; schedule mid-week, operator button in demo.
5. (Step 7, cuttable) M6 question generation from aggregate signal tags only; generated questions need operator approval before `active`.
6. Muse voice system prompt: warm, curious, never clinical or therapeutic.

## Acceptance checks
- `pytest tests/planning tests/providers` green offline; no live call in ordinary tests.
- Invalid JSON gets exactly one retry, then labeled fallback or `PROVIDER_UNAVAILABLE`.
- Every evidence record has model, callType, latencyMs, source.
- Nudge with a non-allowlisted placeId rejected; nudge text passes OutputGuard.
- `selectWeek` deterministic with a seed; no future-day question leaked by any route.
