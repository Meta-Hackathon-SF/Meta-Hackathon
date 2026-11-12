# Proposed HTTP surface
Base: /api/v1. These routes are contracts to implement, not existing endpoints.
Kai registers the server routes. The named owner implements the behavior.

## Common envelope and errors
Authenticated requests use a server-verified session. Session creation is Patrik's documented auth flow; never accept a participantId as proof of identity. JSON responses use camelCase. Return X-Request-Id on every response. Mutations require Idempotency-Key; bind it to actor, route and normalized body. Reuse with a different body returns 409 IDEMPOTENCY_CONFLICT. Async commands return 202 with {jobId, status:"pending"}; GET /jobs/:jobId returns authorized status, public result or ApiError.

Errors use ApiError in protocol.ts: 400 INVALID_INPUT, 401 UNAUTHENTICATED, 403 FORBIDDEN/CONSENT_REQUIRED, 404 NOT_FOUND, 409 STALE_REVISION/CAPACITY_REACHED/IDEMPOTENCY_CONFLICT, 429 RATE_LIMITED, 503 PROVIDER_UNAVAILABLE. Do not disclose another user's existence through private resource errors. Retryable is explicit.

## Routes
| Method / path | Owner | Request | Response / behavior |
| --- | --- | --- | --- |
| GET /session | Patrik | session cookie/token | current public self profile and consent |
| POST /communities/:id/join | Patrik | displayName, explicit consent toggles | authorized membership and current consent |
| PATCH /communities/:id/consent | Patrik | expectedVersion, toggles | incremented Consent; revocation invalidates jobs |
| POST /voice/transcribe | Will | bounded audio multipart | {transcript}; no public storage |
| POST /intents/extract | Adam | transcript, communityId | private draft plus missingFields; no automatic consent |
| PUT /intents/me | Patrik | confirmed intent fields, expectedVersion | PrivateIntent visible only to self |
| POST /communities/:id/matches | Rishi | confirmedIntentVersion | job producing MatchResult, public projection only |
| POST /quests | Kai | proposalId, proposalRevision | forming quest; proposal revalidated |
| POST /quests/:id/plan | Adam + Kai | expectedRevision | job producing public quest proposal |
| POST /quests/:id/accept | Kai | revision, choice | acceptance and QuestSnapshot |
| PATCH /intents/me/availability | Patrik + Kai | expectedVersion, availability | updated private intent; internal change event triggers replan |
| POST /quests/:id/leave | Patrik + Kai | expectedRevision | removes actor and triggers invalidation/replan |
| GET /quests/:id | Kai | session | authorized QuestSnapshot |
| GET /quests/:id/stream | Kai | last sequence via Last-Event-ID | authorized SSE WorkflowEvent stream |
| GET /quests/:id/messages | Kai | cursor | member-only ConversationMessage page |
| POST /quests/:id/messages | Kai | text | participant message, server assigns sender |
| GET /jobs/:id | Kai | session | requester/member-authorized job status |
| POST /quests/:id/continuation | Adam + Kai | expectedRevision, simulateTimeSkip | live continuation job; simulation marked |
| POST /quests/:id/host | Kai | continuationId, explicit accept | draft quest + revocable scoped invite token |
| POST /demo/scenarios/:id/reset | Kai | demo capability | fixture reset only; cannot reset other sessions |

## Exposure
Never return full MatchInput, PlanInput, candidate constraints, raw transcripts or private model payloads to peers. MatchResult's public projection contains IDs, approved profiles and public rationale; memberVersions and internal feasibility information remain server-side. QuestPlan likewise becomes an allowlisted event/proposal card, not a raw model blob. Public endpoint DTO validators are Patrik's integration deliverable.

## Async/stale responses
The client retains requestId and ignores results from superseded/cancelled UI requests. Job writes use actor/consent/intent/quest revisions checked at publication. GET endpoints and subscriptions recheck membership; a previously valid join link is not permanent access.
