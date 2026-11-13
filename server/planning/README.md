# server/planning: question bank, weekly selection, M2 follow-up, M7 event nudges, M6 question generation (owner: Adam)

Contract: `contracts/protocol.ts` 2.0.0 (`Question`, `DailyQuestion`, `QuestionPort`, `M2In`/`M2Out`, `Venue`, `EventNudge`, `NudgePort`, `M7In`/`M7Out`).
Status (2026-11-12): **implemented and offline-tested against fixtures and labeled test-only adapters.** The operator router exists but is not mounted in a running app, nothing is persisted durably, and no live Muse call has run through this code.

## What is here
| File | What |
| --- | --- |
| `questions.py` | `QuestionBank.load / from_doc`, `question_problems`, `load_default_bank()`. A bad row stops the load. |
| `data/question-bank.json` | Curated bank, 32 questions. Superset of `contracts/fixtures/question-bank.json`, row for row. |
| `selection.py` | `QuestionService.select_week` (QuestionPort), `released`, `question_for_day`, `pick_week`, `InMemorySelectionStore`. |
| `clarify.py` | `ClarifyService.follow_up` (M2), prompt `clarify.v2`, `InMemoryClarifyStore`. |
| `venues.py`, `data/venues.json` | `VenueCatalog`: the approved public venue allowlist (same rows as the shared fixture). |
| `nudges.py` | `NudgeService.propose` (NudgePort), `propose_and_post`, prompt `event_nudge.v1`. |
| `generation.py` | `QuestionGenerator.generate / pending / approve / reject` (M6), prompt `question_generation.v1`. |
| `adapters.py` | `CycleQuestionPort`, `SyncClarify`: the synchronous shapes Will's cycle service consumes. `run_sync`. |
| `api.py` | FastAPI router factory `build_router(runtime, session_dependency)`, `PlanningRuntime.ready`, `install_planning_error_handler`. The only module that needs FastAPI. |
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
- A proposal must be a single open question (not yes/no) of at most 140 characters and pass `OutputGuard.check(text, [])`. The reader is the answer's own author, so the no-quote list is empty; sensitive-term, PII and contact checks still apply.
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

## M6 question generation (step 7, cuttable)
```python
from server.planning import QuestionGenerator
gen = QuestionGenerator(muse, output_guard, questions)
res = await gen.generate(count=5, request_id=..., category_mix={"belonging": 2, "routine": 1},
                         aggregate_signals=[{"tag": "solitude", "share": 0.43}])
res.pending     # Question rows with source "generated", active False
gen.approve(question_id)    # operator only: joins the bank as active
gen.reject(question_id)
```
- The prompt holds aggregates only: `{tag, share}` pairs, the category mix, a count and recent question ids. A signal that is not a lowercase tag, or carries any extra field, is refused before the call, so answer text cannot ride in.
- Each proposal must validate as a `Question` and pass `OutputGuard` (text and hint); repeats of the bank or of another proposal are dropped. `"high"` sensitivity fails the adapter schema.
- Survivors wait in a pending queue outside the bank, so `select_week` cannot pick them. Only `approve` makes one active. Approved questions live in process memory until orchestration persists the bank.
- `aggregate_signals` must come from Rishi's thresholded aggregates. Nothing in this package computes them.

## Wiring for the cycle service (Will)
```python
from server.planning import (ClarifyService, CycleQuestionPort, InMemorySelectionStore,
                             QuestionService, SyncClarify, load_default_bank)
bank = load_default_bank()
questions = QuestionService(bank, InMemorySelectionStore(), week_start_lookup)
question_port = CycleQuestionPort(questions)                      # .select_week(cycle_id, community_id) -> 5 DailyQuestion dicts
clarify = SyncClarify(ClarifyService(muse, output_guard), bank)   # clarify(question_text, answer_text) -> M2Out dict
```
Both are synchronous. `SyncClarify` is stateless (the cycle service keeps the once-per-answer rule and the M1 skip) and never raises on provider failure: it returns the curated hint or no follow-up. Call it from a sync handler; a Muse call can take 20 s.

## Operator router (Kai mounts it)
```python
from server.planning.api import PlanningRuntime, build_router, install_planning_error_handler
runtime = PlanningRuntime(questions, nudges, room_constellation, venues, muse_configured=muse.configured)
ServiceRegistration(owner="planning", router=build_router(runtime, session_dependency),
                    authorize=session_dependency, ready=runtime.ready)
install_planning_error_handler(app)
```
Routes (paths without `/api/v1`): `GET /operator/questions` (`active`, `category`, `source` filters), `POST /operator/cycles/{cycleId}/select-week`, `POST /operator/rooms/{roomId}/nudge` (registered only when `nudges` and `room_constellation` are given), and with `runtime.generator` set: `POST /operator/questions/generate` (202) plus three routes that are **not in contracts/API.md yet** (proposed, need ACK): `GET /operator/questions/pending`, `POST /operator/questions/{id}/approve`, `POST /operator/questions/{id}/reject`. Each handler rechecks the operator role from the session (`is_operator` / `isOperator`) and takes the community from the session, never from the client. `ready()` checks local state only (bank, venues, Muse key present) and never calls the model.

## Not done / needs other owners
- The router is tested on a bare FastAPI app with a test-only session stand-in. It has not run inside Kai's composed app or behind Patrik's real session.
- `OutputGuardPort`, `WeekStartLookup`, `ConstellationContext`, `ChatPostPort` and the selection/clarify/nudge stores and the pending-question queue are satisfied in tests by `tests/planning/doubles.py` (TEST ONLY) and the in-memory stores. Durable stores belong to orchestration.

## Live check (manual, paid)
`python3 -m tests.planning.live_check [m2-vague m2-specific m7 m6]` runs the real prompts once each on synthetic fixture input through the live adapter, with a hard cap of 6 provider calls. It uses the TEST-ONLY guard double. Results from 2026-11-13 (5 calls, all `muse-spark-1.3`, `reasoning_effort=low`):

| Call | Prompt | Result | Latency |
| --- | --- | --- | --- |
| M2, vague answer | `clarify.v1` | passed validators, but a generic yes/no follow-up; led to `clarify.v2` and the yes/no check | 25.0 s |
| M2, vague answer | `clarify.v2` | one specific open follow-up, passed | 18.3 s |
| M2, specific answer | `clarify.v1` | correctly no follow-up | 10.6 s |
| M7 | `event_nudge.v1` | picked the fixture board-game event at an allowlisted venue inside the window; title, why and chat line passed | 23.9 s |
| M6, count 3 | `question_generation.v1` | 3 of 3 proposals valid and pending, 0 rejected | 19.8 s |

Five single calls: enough to show the prompts and validators work with live output, not a benchmark of quality or latency. A follow-up takes 10-25 s, so the answer flow must not wait on it.

## Tests
```sh
pytest tests/planning tests/providers
```
Offline only. Results against the doubles are fixture evidence, not integration evidence.
