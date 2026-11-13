# server/planning: question bank, weekly selection, M2 follow-up, M7 event nudges (owner: Adam)

Contract: `contracts/protocol.ts` 2.0.0 (`Question`, `DailyQuestion`, `QuestionPort`, `M2In`/`M2Out`, `Venue`, `EventNudge`, `NudgePort`, `M7In`/`M7Out`).
Status (2026-11-12): **implemented and offline-tested against fixtures and labeled test-only adapters.** No HTTP route is mounted, nothing is persisted durably, and no live Muse call has run through this code. Question generation (M6) is not implemented.

## What is here
| File | What |
| --- | --- |
| `questions.py` | `QuestionBank.load / from_doc`, `question_problems`, `load_default_bank()`. A bad row stops the load. |
| `data/question-bank.json` | Curated bank, 32 questions. Superset of `contracts/fixtures/question-bank.json`, row for row. |
| `selection.py` | `QuestionService.select_week` (QuestionPort), `released`, `question_for_day`, `pick_week`, `InMemorySelectionStore`. |
| `clarify.py` | `ClarifyService.follow_up` (M2), prompt `clarify.v1`, `InMemoryClarifyStore`. |
| `venues.py`, `data/venues.json` | `VenueCatalog`: the approved public venue allowlist (same rows as the shared fixture). |
| `nudges.py` | `NudgeService.propose` (NudgePort), `propose_and_post`, prompt `event_nudge.v1`. |
| `ports.py` | The ports planning consumes: `OutputGuardPort` (Patrik), `ChatPostPort` (Kai), `WeekStartLookup` (Will). |

## Weekly selection
```python
from server.planning import QuestionService, InMemorySelectionStore, load_default_bank
svc = QuestionService(load_default_bank(), store, week_start_lookup)   # lookup: async cycleId -> "YYYY-MM-DD" (a Monday)
week = await svc.select_week(cycle_id, community_id)        # DailyQuestion[5]; operator only (holds future days)
today = svc.released(cycle_id, cycle["currentDay"])          # player-safe: days 1..currentDay
one = svc.question_for_day(cycle_id, day, cycle["currentDay"])   # future day -> NOT_FOUND
```
Rules, enforced by code with no model call: no question from the community's previous four cycles; Monday low sensitivity; at most two medium questions and never on adjacent days; five different categories when the bank allows. The seed defaults to a hash of `(communityId, cycleId)`, so the result is reproducible; a cycle that already has a selection always gets that selection back. If the bank cannot satisfy the rules the call raises `PlanningError("INVALID_INPUT")` instead of relaxing them.

**Future days.** `select_week` returns all five days and belongs behind the operator role only. Every player route must go through `released` or `question_for_day`, passing `currentDay` from server cycle state, never from the client.

## M2 follow-up
```python
from server.planning import ClarifyService, register_planning_tasks
register_planning_tasks(registry)                 # once, at startup
svc = ClarifyService(muse, output_guard)
res = await svc.follow_up(answer_id=..., question=daily["question"], answer_text=...,
                          request_id=..., safety_flag=m1_flag, follow_up_used=answer["followUpUsed"])
res.output    # M2Out exactly: {"needsFollowup": bool, "question": str}
res.source    # "muse" | "fallback" | "none"
res.evidence  # MuseCallEvidence when Muse answered, else None
```
- One follow-up max: the first decision for an `answer_id` is stored and returned on every later call without another Muse call; `follow_up_used=True` returns none.
- `safety_flag` other than `"none"` returns no follow-up and makes no Muse call. Call M1 first.
- The prompt holds the question text, a random per-call id and the answer text. Nothing else.
- A proposal must be a single question of at most 140 characters and pass `OutputGuard.check(text, [])`. The reader is the answer's own author, so the no-quote list is empty; sensitive-term, PII and contact checks still apply.
- Provider failure, invalid JSON after the one retry, or a rejected proposal falls back to the curated `followUpHint` (itself guarded) or to no follow-up, with `source: "fallback"` and no evidence. The answer flow never blocks on Muse. A malformed guard verdict or a guard that raises counts as a rejection.

## M7 event nudges (step 6, cuttable)
```python
from server.planning import NudgeService, VenueCatalog
svc = NudgeService(muse, output_guard, VenueCatalog.load(), constellation_context, chat, time_zone="America/Los_Angeles")
nudge = await svc.propose(constellation_id)             # EventNudge | None  (NudgePort)
posted = await svc.propose_and_post(constellation_id)   # {"nudge": EventNudge, "message": ChatMessage}
```
`constellation_context` is an async lookup supplied by orchestration: `constellationId -> {constellationId, roomId, sharedMeaning, memberCount, roomOpen, againstAnswers} | None`. `againstAnswers` feeds the no-quote guard only; it is never sent to Muse.

Code enforces: at least 3 members and an open room before any call; `placeId` must be in the catalog; the time window must parse, lie inside the requested window, start in the future and last at most 3 hours; title, why and the final chat line each pass `OutputGuard` against the members' answers plus `sharedMeaning`; `minAttendees` is always 3. The chat line is assembled by code from validated fields. One nudge per constellation, posted at most once; the room is rechecked at post time.

There is **no invented fallback nudge**: `EventNudge.evidence` must be a real Muse call, so a provider failure or a rejected proposal returns `None` (`propose`) or raises retryable `PROVIDER_UNAVAILABLE` (`propose_and_post`). `propose_detailed` returns the code-generated reason for operators.

The mid-week schedule and the operator button are not wired: both call `propose_and_post` once the route and Kai's job runner exist.

## Not done / needs other owners
- Routes in contracts/API.md ("Questions and nudges (Adam)") need Kai's router registry and Patrik's operator session check.
- `OutputGuardPort`, `WeekStartLookup`, `ConstellationContext`, `ChatPostPort` and the selection/clarify/nudge stores are satisfied in tests by `tests/planning/doubles.py` (TEST ONLY) and the in-memory stores. Durable stores belong to orchestration.

## Tests
```sh
pytest tests/planning tests/providers
```
Offline only. Results against the doubles are fixture evidence, not integration evidence.
