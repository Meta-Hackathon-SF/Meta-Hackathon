# Durable workflow
Owner: Kai. Planning owner: Adam. Authorization reviewer: Patrik.

## States
forming -> proposed -> planning -> scheduled -> completed
scheduled -> revision_pending -> scheduled
forming/proposed/planning/revision_pending -> cancelled

forming means assembling an eligible team. proposed means an activity proposal exists for acceptance. planning means the acceptance threshold has been reached and a job is computing final details. If final time/place/cost differs materially from what people accepted, return to proposed for confirmation before scheduled. The UI must distinguish "joining this quest" from "confirming this plan."

revision_pending keeps the prior event for history, marks it awaiting reconfirmation, and never silently presents the new time as accepted. If fewer than three remain, do not keep the event scheduled as if quorum still exists. Declined participants are never re-added without consent.

## Trigger and execution
1. Acceptance transaction checks actor membership, current revision, capacity and consent.
2. Unique key (questId, participantId, revision) prevents duplicate counts.
3. Code detects quorum of at least three, at most five.
4. Transaction creates one durable planning job/outbox item using questId + revision + task.
5. Worker loads a fresh authorized snapshot. Muse proposes event details through PlanningPort.
6. Validate model output against schema, approved venues, budgets and common time.
7. Recheck stored versions and consent in a transaction.
8. Insert or update one event identity per quest; event revisions are separate history records.
9. Commit a public workflow event/outbox message and one assistant opener per revision.
10. Publish after commit. A reconnect reads the persisted snapshot and resumes by sequence.

No exactly-once network delivery claim. Delivery may repeat; unique database constraints and consumer deduplication make effects idempotent. Do not hold a database transaction open during a provider call.

## Revision and revocation races
Availability updates increment intentVersion. Membership/consent changes invalidate queued snapshots. A stale job must not publish; enqueue a fresh revision or return needs_input. Store expected versions with each job. Concurrent accept/leave uses serialized transaction checks or optimistic compare-and-swap. Capacity enforcement occurs in the database transaction, never only in the client.

## Continuation
A labeled simulateTimeSkip command triggers live Muse reasoning on minimal voluntary feedback. It never claims actual attendance occurred. Offer a host role; accepting creates a draft and scoped invitation. No automatic external invites, no event impersonating the user, and no fabricated attendance.

## Recovery
Persist job status pending/running/succeeded/failed, attempt count, retry deadline and sanitized reason. Bound retries and use backoff. A crashed worker's expired lease permits retry without duplicate events. A provider outage leaves a recoverable state. Replay scenarios use separate demo IDs and cannot mutate live participant rooms.

## Acceptance tests
Simultaneous accepts at capacity; retried command; same key different payload; worker crash after DB commit; duplicate publication; leave while planning; revoked consent before commit; stale plan revision; impossible replan; reconnect and missed event replay; assistant opener emitted once per event revision.
