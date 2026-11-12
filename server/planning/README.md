# server/planning: adaptive planning (owner: Adam)

Status: intent extraction **implemented and fixture-tested**; plan/revise/continue are pending (P2-P4). No live Muse evidence yet.

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
