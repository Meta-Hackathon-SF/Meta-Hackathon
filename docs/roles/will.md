# Will: Voice-to-action interaction system
Branch: `role/will-voice-ui`. Read root AGENTS.md and shared contracts first.

## Mission
Start execution with [your phase-by-phase build checklist](../phases/will.md). It specifies paths, work, dependencies, exit evidence and handoffs for P0-P6.

Own the user's voice-to-confirmed-intent journey and compose independently owned feature components within the existing mock Facebook shell.

## Ownership
- `web/src/features/group-quests/onboarding/`
- `web/src/features/group-quests/shell/`
- `server/voice/`
- `tests/onboarding/`
Also own this role document, docs/handoffs/will.md and docs/updates/will.md.
These are reserved paths; implementation does not exist until you add it.

## Producer/consumer contract
Inputs: Adam's extraction results and missing fields; Patrik's self/session/consent API; Rishi/Adam/Kai/Patrik feature components.
Outputs: Confirmed intent submission, accessible voice/text flow, request cancellation/recovery, live first-action timer, minimal feature route.
Give Patrik confirmed payload, Adam extraction UX requirements, and every owner the feature component integration contract. Provide multi-device entry URL once deployed.

## Implementation sequence
1. Implement recording/upload via a documented STT adapter or verified browser capability; always offer typed entry.
2. Show transcript and extracted fields for confirmation; missing time/area/budget questions are explicit.
3. Handle denied microphone, unsupported browser, cancellation and stale asynchronous results.
4. Add minimal route/navigation entry while keeping mock Facebook pages and styling intact.
5. Compose owner components; feature CSS is scoped and the feature gets its own design. Do not implement everyone else's business logic.
6. Instrument intent submission to persisted quest acceptance; record completed and abandoned attempts separately.

## Checkpoints
H1: acknowledge contracts, confirm dependencies and claim shared files.
H4: independently executable module with synthetic fixtures and clear status.
H7: integrated intent-to-event path with other owners.
H10: handle live changes and failed inputs.
H13: support next-week/hosting continuation and integration scenarios.
H16: feature freeze; provide test evidence and no remaining contract ambiguity.
Final six hours: polish your component, verify integration, and participate in shared demo work.

## Required checks
Mic denial; text alternative; keyboard interaction; mobile overflow; cancelled request returns late; correction changes submitted intent; timer ends only on real acceptance.
Report exact commands/results; do not manufacture performance or quality numbers.

## Branch workflow
```sh
git fetch origin
git switch --track origin/role/will-voice-ui
# If local branch exists: git switch role/will-voice-ui
git merge origin/main
git status --short
```
Only merge main into a clean branch. Use a separate worktree for another agent, not a shared checkout switched underneath it. Push to role/will-voice-ui; do not force-push. Shared contract modifications go through an explicit producer/consumer agreement and merge before dependent work.

## First prompt for your coding agent
Read AGENTS.md, all common contract documents, docs/roles/will.md and docs/handoffs/will.md. Confirm the current branch is role/will-voice-ui. Inspect existing code, preserve unrelated edits, and implement the first incomplete checkpoint in my owned paths. Use the common contracts; report a concrete interface mismatch instead of creating a private incompatible version. Keep my handoff/log updated with verified evidence. Group Quests has a separate feature UI inside the existing mock Facebook shell.
