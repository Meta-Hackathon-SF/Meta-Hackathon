# Patrik: Privacy and group-access system
Branch: `role/patrik-privacy`. Read root AGENTS.md and shared contracts first.

## Mission
Start execution with [your phase-by-phase build checklist](../phases/patrik.md). It specifies paths, work, dependencies, exit evidence and handoffs for P0-P6.

Own identity, consent, authorized snapshots and public projections so private constraints never become shared room state.

## Ownership
- `server/privacy/`
- `db/privacy/`
- `web/src/features/group-quests/privacy/`
- `tests/privacy/`
Also own this role document, docs/handoffs/patrik.md and docs/updates/patrik.md.
These are reserved paths; implementation does not exist until you add it.

## Producer/consumer contract
Inputs: Will's confirmed intent and explicit toggles; Kai's room/job/event tables; shared privacy/wire contracts.
Outputs: Server-verified identity, versioned Consent/PrivateIntent persistence, eligible Candidate service, public DTOs, leave/revoke controls.
Give Rishi authorized snapshot method, Adam minimized planning payload, Will auth/consent hooks, Kai authorization + invalidation hooks.

## Implementation sequence
1. Choose/document the session mechanism with Kai; reject client identity assertions.
2. Implement community membership, consent versions, self-only reads/updates, and authorized candidate snapshot queries.
3. Provide allowlisted public participant/proposal/event projections with persistent synthetic labels.
4. Implement revoke/leave invalidation hooks for Kai; remove subscription authorization promptly.
5. Coordinate migration order with Kai and test actual access policies without service-role bypass.
6. Build consent/membership UI and adversarial boundary tests.

## Checkpoints
H1: acknowledge contracts, confirm dependencies and claim shared files.
H4: independently executable module with synthetic fixtures and clear status.
H7: integrated intent-to-event path with other owners.
H10: handle live changes and failed inputs.
H13: support next-week/hosting continuation and integration scenarios.
H16: feature freeze; provide test evidence and no remaining contract ambiguity.
Final six hours: polish your component, verify integration, and participate in shared demo work.

## Required checks
Forged IDs; unauthenticated writes; cross-user/room reads; consent revoke during model call; private fields in public projection; direct database policy bypass; model-processing opt-out.
Report exact commands/results; do not manufacture performance or quality numbers.

## Branch workflow
```sh
git fetch origin
git switch --track origin/role/patrik-privacy
# If local branch exists: git switch role/patrik-privacy
git merge origin/main
git status --short
```
Only merge main into a clean branch. Use a separate worktree for another agent, not a shared checkout switched underneath it. Push to role/patrik-privacy; do not force-push. Shared contract modifications go through an explicit producer/consumer agreement and merge before dependent work.

## First prompt for your coding agent
Read AGENTS.md, all common contract documents, docs/roles/patrik.md and docs/handoffs/patrik.md. Confirm the current branch is role/patrik-privacy. Inspect existing code, preserve unrelated edits, and implement the first incomplete checkpoint in my owned paths. Use the common contracts; report a concrete interface mismatch instead of creating a private incompatible version. Keep my handoff/log updated with verified evidence. Group Quests has a separate feature UI inside the existing mock Facebook shell.
