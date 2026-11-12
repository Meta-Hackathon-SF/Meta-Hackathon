# Adam: Adaptive planning agent
Branch: `role/adam-planning`. Read root AGENTS.md and shared contracts first.

## Mission
Build the stateful Muse propose/validate/revise loop. Own the single Muse adapter and intent extraction so other owners never invent provider APIs.

## Ownership
- `server/planning/`
- `server/providers/`
- `web/src/features/group-quests/planning/`
- `tests/planning/`
Also own this role document, docs/handoffs/adam.md and docs/updates/adam.md.
These are reserved paths; implementation does not exist until you add it.

## Producer/consumer contract
Inputs: Confirmed/minimized intents from Patrik; Rishi's GroupProposal; approved Venue catalog; workflow revision snapshots from Kai.
Outputs: MusePort, intent draft/missing-field extraction, PlanningPort.plan/revise/continue, validated QuestPlan proposals, public plan/revision components.
Give Rishi MusePort adapter and test fake, Will extraction endpoint/component contract, Kai PlanningPort and validated plan outcomes.

## Implementation sequence
1. Confirm the available Muse model ID, endpoint/auth and audio support with supplied documentation; record verified configuration without secrets.
2. Implement one bounded provider adapter with cancellation, response validation, timeout and sanitized evidence.
3. Extract intent for Will with missing-field questions; never infer consent or fabricate availability.
4. Generate collaborative activities and feasible details from the real group; choose only catalog venue IDs.
5. Revise after changed constraints; return no_feasible_plan when appropriate. Generate live next-week invitation and suggested host.
6. Expose structured public before/after changes in the planning UI; never execute database or external side effects from a prompt.

## Checkpoints
H1: acknowledge contracts, confirm dependencies and claim shared files.
H4: independently executable module with synthetic fixtures and clear status.
H7: integrated intent-to-event path with other owners.
H10: handle live changes and failed inputs.
H13: support next-week/hosting continuation and integration scenarios.
H16: feature freeze; provide test evidence and no remaining contract ambiguity.
Final six hours: polish your component, verify integration, and participate in shared demo work.

## Required checks
Malformed JSON; unknown venue; out-of-budget output; no common interval; provider timeout; prompt injection; stale input; live vs replay metadata; continuation without invented attendance.
Report exact commands/results; do not manufacture performance or quality numbers.

## Branch workflow
```sh
git fetch origin
git switch --track origin/role/adam-planning
# If local branch exists: git switch role/adam-planning
git merge origin/main
git status --short
```
Only merge main into a clean branch. Use a separate worktree for another agent, not a shared checkout switched underneath it. Push to role/adam-planning; do not force-push. Shared contract modifications go through an explicit producer/consumer agreement and merge before dependent work.

## First prompt for your coding agent
Read AGENTS.md, all common contract documents, docs/roles/adam.md and docs/handoffs/adam.md. Confirm the current branch is role/adam-planning. Inspect existing code, preserve unrelated edits, and implement the first incomplete checkpoint in my owned paths. Use the common contracts; report a concrete interface mismatch instead of creating a private incompatible version. Keep my handoff/log updated with verified evidence. Group Quests has a separate feature UI inside the existing mock Facebook shell.
