# HTTP surface (Constellations 2.0.0, proposed)
Base `/api/v1`. Kai owns API composition: the FastAPI app, router registration, envelope, idempotency and the SSE stream. Each route's named owner implements its handler as a router in their own package; Kai mounts it. Operator routes require the operator role.

## Envelope and errors
Server-verified session (Patrik) on every authenticated route; a client-supplied `playerId` is never identity. JSON camelCase. `X-Request-Id` on every response. Mutations take `Idempotency-Key` bound to actor, route and normalized body; reuse with a different body returns 409 `IDEMPOTENCY_CONFLICT`. Long jobs return 202 `{jobId, status:"pending"}`; `GET /jobs/:jobId` returns status, public result or `ApiError`.

Status codes: 400 `INVALID_INPUT`, 401 `UNAUTHENTICATED`, 403 `FORBIDDEN`/`CONSENT_REQUIRED`, 404 `NOT_FOUND`, 409 `STALE_REVISION`/`IDEMPOTENCY_CONFLICT`/`CYCLE_LOCKED`, 410 `ROOM_EXPIRED`, 422 `MESSAGE_REJECTED`, 429 `RATE_LIMITED`, 503 `PROVIDER_UNAVAILABLE`. Private-resource errors never reveal another player's existence.

## Session, consent, safety (Patrik)
| Route | Input | Output |
| --- | --- | --- |
| POST /communities/:id/join | displayName, matchAnswers, anonymousChat, isAdult | Player (self), Consent, session cookie |
| GET /session | session | Player (self), Consent, isOperator |
| PATCH /me/consent | expectedVersion, toggles | Consent; revocation invalidates jobs and leaves rooms |
| POST /me/blocks | roomId + handle | 204, no existence leak |
| DELETE /me/data | none | 202; deletes answers, guesses, chat authorship links, activity signals |
| PUT /me/activity | useActivity, profileId?, groupIds, eventIds, friendIds, texts (D010) | `{useActivity, topics}`; off deletes stored signals; texts are reduced to allowlisted topics and discarded |

## Weekly cycle and daily answers (Will)
| Route | Input | Output |
| --- | --- | --- |
| GET /cycles/current | session | WeeklyCycle, today's DailyQuestion, my Streak, my CatchUpState |
| GET /cycles/:id/questions | session | DailyQuestion[] released so far (never future days) |
| POST /cycles/:id/answers | day, text 1-400, source | 202; DailyAnswer (self) with server weight; M1 via Patrik at submit |
| WS /voice/live (PROPOSED, D011) | binary PCM16 mono 16 kHz frames, text `stop` | `{type:"ready"}`, `{type:"partial"|"final", text}` (final ≤ 400 chars), or `{type:"error", code, message, retryable}`. Session cookie + consent + same-host origin; mounted only when live STT is configured; a draft only, the player submits via POST answers (M1 there) |
| PATCH / DELETE /cycles/:id/answers/:day | text / none | updated or deleted; `CYCLE_LOCKED` after Saturday lock |
| GET /cycles/:id/answers/:day/followup | session | M2 `{needsFollowup, question}`, max one per answer |
| PUT /cycles/:id/guess | percent 0-100 | stored apart from answers |

## Questions and nudges (Adam)
| Route | Input | Output |
| --- | --- | --- |
| GET /operator/questions | filters | Question[] (bank) |
| POST /operator/questions/generate | count, categoryMix | 202; generated questions pending operator approval |
| POST /operator/cycles/:id/select-week | none | DailyQuestion[] for Mon-Fri |
| POST /operator/rooms/:id/nudge | none | EventNudge posted as `muse_nudge` (also scheduled automatically mid-week) |

## Formation and Sky (Rishi computes, Kai serves)
| Route | Owner | Output |
| --- | --- | --- |
| POST /operator/cycles/:id/form | Kai route, Rishi FormationPort.form | 202; constellations committed, not yet visible |
| GET /operator/cycles/:id/formation-debug | Rishi | baseline vs Muse grouping, ids only, operator only |
| GET /cycles/:id/sky | Kai route, Rishi computeSky | SkyStats (thresholded) |

## Chat, moderation, reveal, realtime (Kai)
| Route | Input | Output |
| --- | --- | --- |
| GET /cycles/:id/room | session | ChatRoom for my constellation (after reveal) |
| GET /rooms/:id/messages | after seq | ChatMessage[] visible to me |
| POST /rooms/:id/messages | text 1-500 | ChatMessage, or 422 `MESSAGE_REJECTED` (Patrik's M1 + OutputGuard) |
| POST /rooms/:id/reports | messageId?, handle, reason | 204; message hidden for reporter now, operator queue |
| POST /rooms/:id/reveal | toHandle | `{result: "pending" | "revealed"}` |
| GET /stream | Last-Event-ID | SSE of StreamEvent, filtered per player |

## Operator (Will owns controls, Kai owns composition)
| Route | Output |
| --- | --- |
| POST /operator/cycles | new WeeklyCycle (open, day 1) |
| POST /operator/cycles/:id/advance | next day, or lock / reveal / close ("Demo timing") |
| POST /operator/cycles/:id/synthetic-topup | adds labeled synthetic players and answers from fixtures |
| POST /operator/cycles/:id/reset | fixture cycles only; never touches real sessions |
| GET /operator/calls | MuseCallEvidence list (model, callType, latency, live/replay) |
| GET /operator/reports | Report queue; remove message, remove member |

## Exposure
Never return another player's DailyAnswer, Guess, SafetyFlag, Theme.memberIds, Constellation.memberIds, sharedMeaning, Report, RevealRequest, raw prompts or provider payloads. Chat uses AnonymousHandle until a MutualReveal exists for that pair.
