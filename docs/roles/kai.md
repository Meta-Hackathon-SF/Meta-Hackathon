# Kai: Reliable event orchestration system
Branch: `role/kai-orchestration`. Read root AGENTS.md and shared contracts first.

## Mission
Start execution with [your phase-by-phase build checklist](../phases/kai.md). It specifies paths, work, dependencies, exit evidence and handoffs for P0-P6.

Own durable state transitions and real-time delivery so model-generated proposals produce one correct event even under retries and simultaneous users.

## Ownership
- `server/orchestration/`
- `server/app/`
- `db/workflow/`
- `web/src/features/group-quests/events/`
- `tests/orchestration/`
Also own this role document, docs/handoffs/kai.md and docs/updates/kai.md.
These are reserved paths; implementation does not exist until you add it.

## Producer/consumer contract
Inputs: Patrik's authorization/consent guards; Rishi's versioned proposals; Adam's PlanningPort; participant commands from feature UI.
Outputs: Persistent quests/events/messages/jobs, API composition, authorized SSE snapshots, event-room UI, draft hosting and recoverable failure states.
Give each owner API registration conventions, Will event-room components and stream client contract, Patrik table schema for policy review.

## Implementation sequence
1. Scaffold backend and reproducible run instructions; coordinate server manifests and migration ordering.
2. Implement acceptance transactions, capacity checks, idempotency ledger, outbox/worker leases and unique event identities.
3. Dispatch planning after code detects quorum; revalidate versions before effects and require reconfirmation for material changes.
4. Persist room conversation with explicit assistant identity; implement reconnect snapshot and sequence deduplication.
5. Implement live change trigger, next-week time-skip command and explicit host acceptance creating draft/invite.
6. Build event room components and demonstrate concurrency/crash/retry behavior.

## Checkpoints
H1: acknowledge contracts, confirm dependencies and claim shared files.
H4: independently executable module with synthetic fixtures and clear status.
H7: integrated intent-to-event path with other owners.
H10: handle live changes and failed inputs.
H13: support next-week/hosting continuation and integration scenarios.
H16: feature freeze; provide test evidence and no remaining contract ambiguity.
Final six hours: polish your component, verify integration, and participate in shared demo work.

## Required checks
Concurrent accepts at capacity; duplicate key/same body; same key/new body; crash after commit; stale provider result; revoked actor; stream reconnect; duplicated opener; host acceptance replay.
Report exact commands/results; do not manufacture performance or quality numbers.

## Branch workflow
```sh
git fetch origin
git switch --track origin/role/kai-orchestration
# If local branch exists: git switch role/kai-orchestration
git merge origin/main
git status --short
```
Only merge main into a clean branch. Use a separate worktree for another agent, not a shared checkout switched underneath it. Push to role/kai-orchestration; do not force-push. Shared contract modifications go through an explicit producer/consumer agreement and merge before dependent work.

## First prompt for your coding agent
Read AGENTS.md, all common contract documents, docs/roles/kai.md and docs/handoffs/kai.md. Confirm the current branch is role/kai-orchestration. Inspect existing code, preserve unrelated edits, and implement the first incomplete checkpoint in my owned paths. Use the common contracts; report a concrete interface mismatch instead of creating a private incompatible version. Keep my handoff/log updated with verified evidence. Group Quests has a separate feature UI inside the existing mock Facebook shell.
