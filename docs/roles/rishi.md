# Rishi: Group recommendation engine
Branch: `role/rishi-matching`. Read root AGENTS.md and shared contracts first.

## Mission
Build compatible teams from several people's intents, with hard feasibility gates and a Muse-ranked group-level objective.

## Ownership
- `server/matching/`
- `web/src/features/group-quests/matching/`
- `tests/matching/`
Also own this role document, docs/handoffs/rishi.md and docs/updates/rishi.md.
These are reserved paths; implementation does not exist until you add it.

## Producer/consumer contract
Inputs: Patrik's authorized Candidate snapshots; Adam's MusePort; community size/time/currency limits.
Outputs: MatchingPort.match -> MatchResult. Public team cards and an explicit no-match state. Internal member/consent versions for stale-output rejection.
Give Adam GroupProposal fixtures and Kai validated proposal IDs/revisions. Give Will matching-card component props.

## Implementation sequence
1. Implement deterministic eligibility, unique membership, requester inclusion, time intersections and group size.
2. Rank a bounded shortlist with Muse; validate returned participant IDs against the authorized candidate pool.
3. Evaluate complete groups rather than independent pair scores; build a shared-interest baseline using identical feasibility gates.
4. Render team cards and approved rationale without leaking private constraints.
5. Measure feasibility, response latency and relevance on synthetic cases; record actual results.

## Checkpoints
H1: acknowledge contracts, confirm dependencies and claim shared files.
H4: independently executable module with synthetic fixtures and clear status.
H7: integrated intent-to-event path with other owners.
H10: handle live changes and failed inputs.
H13: support next-week/hosting continuation and integration scenarios.
H16: feature freeze; provide test evidence and no remaining contract ambiguity.
Final six hours: polish your component, verify integration, and participate in shared demo work.

## Required checks
No shared window; fewer than three; revoked consent; duplicate/made-up IDs; requester omitted; incompatible currency; private rationale leakage; baseline comparison.
Report exact commands/results; do not manufacture performance or quality numbers.

## Branch workflow
```sh
git fetch origin
git switch --track origin/role/rishi-matching
# If local branch exists: git switch role/rishi-matching
git merge origin/main
git status --short
```
Only merge main into a clean branch. Use a separate worktree for another agent, not a shared checkout switched underneath it. Push to role/rishi-matching; do not force-push. Shared contract modifications go through an explicit producer/consumer agreement and merge before dependent work.

## First prompt for your coding agent
Read AGENTS.md, all common contract documents, docs/roles/rishi.md and docs/handoffs/rishi.md. Confirm the current branch is role/rishi-matching. Inspect existing code, preserve unrelated edits, and implement the first incomplete checkpoint in my owned paths. Use the common contracts; report a concrete interface mismatch instead of creating a private incompatible version. Keep my handoff/log updated with verified evidence. Group Quests has a separate feature UI inside the existing mock Facebook shell.
