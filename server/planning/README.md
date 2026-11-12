# server/planning: adaptive planning (owner: Adam)

Status: extraction, `plan`, `revise` and `continue` are **implemented and fixture-tested**; there is no live Muse evidence yet. The planning UI lives in `web/src/features/group-quests/planning/`.

## Intent extraction (for Will and Kai's route registration)
`POST /api/v1/intents/extract` (route registered by Kai; behavior here). Wire shapes are **PROPOSED in docs/DECISIONS.md D005** and declared in `contracts/protocol.ts` under "PROPOSED (D005)".

Request body: `{ "transcript": string (1..2000 chars), "communityId": Id }`.
The route supplies server-side facts: the verified session, current `Consent` (from Patrik), and `CommunityContext` (areas, currency, IANA time zone). The client never supplies these.

```python
from server.planning import IntentExtractor, CommunityContext, Area, PlanningError
extractor = IntentExtractor(muse)                 # muse = the process MusePort
outcome = await extractor.extract(transcript=body["transcript"], community=community_ctx,
                                  consent=consent_dict, request_id=request_id)
return 200, outcome.result                        # ExtractionResult
# PlanningError -> 400 INVALID_INPUT / 403 CONSENT_REQUIRED / 503 PROVIDER_UNAVAILABLE / 429 RATE_LIMITED
#   use err.to_api_error(request_id) for the ApiError envelope
```

Response `ExtractionResult` (example, synthetic):
```json
{
  "status": "draft",
  "draft": {
    "communityId": "c-synthetic", "goal": "meet people into photography and coffee",
    "interests": ["photography", "coffee"], "areaId": "area-north",
    "timeZone": "America/Los_Angeles",
    "availability": [{"start": "2026-11-14T22:00:00Z", "end": "2026-11-15T01:00:00Z"}],
    "maxBudgetMinor": 1000, "currency": "USD", "maxDurationMinutes": null, "groupPreference": "small"
  },
  "missingFields": ["maxDurationMinutes"],
  "questions": [{"field": "maxDurationMinutes", "question": "How much time can you spend on it? For example 30 minutes or an hour."}],
  "evidence": {"model": "muse-spark-1.3", "source": "live", "generatedAt": "2026-11-12T20:00:01.234Z", "latencyMs": 2100}
}
```

Guarantees:
- **Fails closed** without current model-processing consent for that community (checked before any model call).
- **No invented facts:** every value must cite a verbatim transcript quote; unsupported, out-of-bound (budget ≤ 100000 minor, duration 15-480 min, windows 15 min-24 h within 14 days), past, unzoned or off-allowlist (areaId) values are dropped and listed in `missingFields`.
- `questions` are fixed server templates, not model text. `timeZone`/`currency` come from the community.
- The draft has **no** participantId, consent, intentVersion or confirmedAt. Will shows it for editing; Patrik's `PUT /intents/me` persists the confirmed version.
- Prompt-injection text stays data; extra fields (for example `consent`) fail schema validation, are retried once, then return a retryable `PROVIDER_UNAVAILABLE`, never a partial draft.
- The transcript is sent to the provider only inside this call. It is not logged or stored here.

## Validators
`server.planning.wire` validates contract 1.0.0 shapes: Window, Context, ModelEvidence, PrivateIntent, Candidate, GroupProposal, Venue, PlanInput, QuestPlan, PlanResult, ContinuationInput, Continuation, plus the proposed IntentDraft/ExtractionResult. Unknown keys are rejected.

## PlanningPort (for Kai)
```python
from server.planning import QuestPlanner, plan_changes, requires_reconfirmation
planner = QuestPlanner(muse)                       # telemetry= optional sanitized sink
result = await planner.plan(plan_input)            # PlanInput dict -> PlanResult dict
result = await planner.revise(plan_input)          # requires previousPlan (same proposalId)
cont   = await getattr(planner, "continue")(continuation_input)   # or planner.continue_(...)
```
- Inputs are validated (`wire.plan_input`). Participants must be exactly `proposal.memberIds`, and each snapshot's intent/consent versions must equal `proposal.memberVersions`, otherwise you get `STALE_REVISION` before any model call. Kai should reload a fresh snapshot and retry.
- Code-detected outcomes skip the model entirely:
  - no shared slot of at least 15 min → `needs_input` (fields `["availability"]`)
  - no open public venue in the area → `no_feasible_plan`
- Muse's choice must name a catalog `venueId`, fit inside one feasible slot, stay within the group's min duration cap, and keep `costPerPersonMinor` at or below the group's min budget. Public text goes through a leak guard. A failed choice gets one code-written correction; if it fails again, the call raises a retryable `PROVIDER_UNAVAILABLE`. A fake plan is never returned.
- `publicRationale` is rendered by code from allowlisted fact codes. Plans cite only `proposal.sharedInterests`.
- Lineage: `revision = previous.revision + 1` and `basedOnRevision = previous.revision`. `requires_reconfirmation(prev, next)` is true when time, place or cost changed.
- `planId` is generated here as an opaque id. Kai persists it or remaps it.
- `continue`:
  - The model receives only the ids of members who want to return. Attendance is never sent.
  - The host must be one of those willing members, or null.
  - Invitations that claim attendance are rejected.
  - Without `simulateTimeSkip`, a call made before the prior plan ends is rejected.
- Venues: `catalog.demo_venues(time_zone, start)` expands a SYNTHETIC, labeled demo catalog. An approved real catalog source is still unassigned.
- Cancellation: cancel the awaiting task. Nothing is persisted here, so a cancelled or stale result is simply discarded by the caller.

## PROPOSED contract 1.1.0 (D008): preferences, created events, negotiation, challenges
Implemented and offline-tested. **The new tasks have not been called live yet.** Shapes are in `contracts/protocol.ts` (PROPOSED D008), validators in `wire.py`, and examples in `contracts/examples/1.1.0/`. All four classes take one `MusePort`: compose with `build_muse_adapter(register_planning_tasks(TaskRegistry()), config)`, which now registers the 1.1 tasks too.

```python
from server.planning import PreferenceExtractor, EventCreator, Negotiator, ChallengeGenerator

# Will / Kai route POST /preferences/extract (consent dict from Patrik's get_consent(...).wire())
out = await PreferenceExtractor(muse).extract(request=body, community=community_ctx, consent=consent, request_id=rid)
out.result   # PreferenceExtractionResult: needs_follow_up (exactly one question) | ready_to_confirm

# Kai job: nothing in the opportunity store fits
await EventCreator(muse).create(create_event_input)      # -> CreateEventResult (created | no_fit)

# Kai job: venue opportunity + chosen group (simulated venue assistants only)
await Negotiator(muse).negotiate(negotiation_input)      # -> NegotiationResult (deal awaiting_approval | no_deal)

# Kai job after the meetup / labeled time skip
await ChallengeGenerator(muse).challenge(challenge_input)  # -> Challenge (progress 0; Kai updates)
```
- Every method validates its input and its own output, raises `PlanningError` (same codes as above), and has no side effects. Kai persists results and runs approvals.
- To send the follow-up answer, call `extract` again with `followUp: {field, answer, previous}`. The response will never contain a second question.
- Negotiation needs a persona for the venue: `catalog.SYNTHETIC_VENUE_PERSONAS` covers `venue-demo-boulder` and `venue-demo-cafe`. Use `catalog.demo_venues_with_gym(...)` for the climbing demo.
- Live latency is about 17-24 s per call at `reasoning_effort=low`. A negotiation makes 2 calls per round, so a 2-round deal takes about 4 calls. Run it as a background job with streamed turns, not inside a request.
