# Proposed HTTP surface (Constellations)
Base: /api/v1. Contracts to implement, not existing endpoints; no server exists on main yet. Kai registers routes; the named owner implements behavior. Operator routes require the operator role.

## Common envelope and errors
Authenticated requests use a server-verified session (Patrik's auth flow); never accept a playerId as proof of identity. JSON is camelCase. Return X-Request-Id on every response. Mutations require Idempotency-Key, bound to actor, route and normalized body; reuse with a different body returns 409 IDEMPOTENCY_CONFLICT. Async commands return 202 with {jobId, status:"pending"}; GET /jobs/:jobId returns authorized status, public result or ApiError.

Errors use ApiError in protocol.ts: 400 INVALID_INPUT, 401 UNAUTHENTICATED, 403 FORBIDDEN/CONSENT_REQUIRED, 404 NOT_FOUND, 409 STALE_REVISION/CAPACITY_REACHED/IDEMPOTENCY_CONFLICT/ROUND_LOCKED, 429 RATE_LIMITED, 503 PROVIDER_UNAVAILABLE. Do not disclose another player's existence through private-resource errors. A wrong found code returns the generic not_a_match result, never NOT_IN_CONSTELLATION.

## Player routes
| Route | Owner | Input | Output |
| --- | --- | --- | --- |
| GET /session | Patrik | session | Player + ConsentV2 |
| POST /communities/:id/players | Patrik + Will | displayName, consent toggles (matchAnswers, writeClues, isAdult) | Player, ConsentV2 |
| PATCH /players/me/consent | Patrik | expectedVersion, toggles | ConsentV2 (revocation invalidates jobs) |
| PUT /players/me/findable | Patrik | items: string[] | FindableDetails (self only) |
| POST /players/me/blocks | Patrik | blockedId | 204; no existence leak |
| GET /rounds/current | Kai | session | Round |
| POST /rounds/:id/answers | Will + Patrik | text 1-400, source voice or text | 202 job; Answer id; M1 runs at submit |
| PATCH / DELETE /rounds/:id/answers/me | Patrik | text / none | updated or deleted; ROUND_LOCKED after lock |
| GET /rounds/:id/followup | Adam | session | {needsFollowup, question} (max 1 per round) |
| POST /rounds/:id/guess | Will | percent 0-100 | stored separately from the answer |
| GET /rounds/:id/formation | Rishi + Kai | session | my constellation card: name, shape, color, my found code, members to find, isLooseMatch |
| GET /rounds/:id/clues | Adam + Kai | session | my clues, released levels only |
| POST /rounds/:id/clues/:rid/veto | Adam (P1) | none | target vetoes a clue about self before release |
| POST /rounds/:id/finds | Kai | foundCode | confirmed / pending / not_a_match |
| GET /rounds/:id/sky | Kai | session | SkyStats (thresholded) |
| GET /rounds/:id/stream | Kai | Last-Event-ID | SSE of round events, authorized per player |
| POST /constellations/:id/meetup/vote | Kai (P1) | choice in / not_this_week | MeetupPlan approvals |

## Operator routes
| Route | Owner | Input | Output |
| --- | --- | --- | --- |
| POST /operator/rounds | Kai | questionId | Round (open) |
| POST /operator/rounds/:id/lock | Kai | none | 202 formation job |
| POST /operator/rounds/:id/advance-level | Kai | none | Round with levelUnlocked+1 ("Demo timing") |
| POST /operator/rounds/:id/sky | Kai | none | 202 job; SkyStats |
| POST /operator/rounds/:id/reset | Kai | none | fixture reset only; cannot touch other sessions |
| POST /operator/rounds/:id/synthetic-topup | Kai | count | adds labeled synthetic players |
| GET /operator/rounds/:id/calls | Kai | none | MuseCallEvidence list (model, callType, latency, source) |

## Exposure
Never return another player's Answer, SafetyFlag, Guess, Theme.memberIds, Constellation.sharedMeaning, raw prompts or private model payloads. Constellation members see names only after a confirmed Find. Public DTO validators are Patrik's integration deliverable.

## Async and stale responses
Client retains requestId and ignores superseded results. Job writes check consent and answer versions at publish time. GET and SSE recheck membership on every call.
