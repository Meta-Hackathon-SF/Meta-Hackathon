# Launch your coding agent
Each teammate clones this repository locally and checks out their branch. The common AGENTS.md is on every branch. All shared contracts remain visible to everyone.

| Person | Branch | Read next |
| --- | --- | --- |
| rishi | `role/rishi-matching` | [assignment](roles/rishi.md) |
| adam | `role/adam-planning` | [assignment](roles/adam.md) |
| will | `role/will-voice-ui` | [assignment](roles/will.md) |
| patrik | `role/patrik-privacy` | [assignment](roles/patrik.md) |
| kai | `role/kai-orchestration` | [assignment](roles/kai.md) |

Paste this, substituting your name:
> I am NAME. Read AGENTS.md, PROJECT_KNOWLEDGE.md, the shared contracts, and docs/roles/NAME.md. Switch to my assigned role branch only if the checkout is clean; otherwise preserve work and use a separate worktree. Implement my first incomplete checkpoint within my ownership boundaries. Build against the shared interfaces and coordinate any change through docs/DECISIONS.md. Update my handoff with exact verification and dependencies. The web app is a mock Facebook shell; our feature UI lives separately.

## Keeping shared knowledge current
```sh
git fetch origin
git merge origin/main
```
Run from your clean role branch. Do not use reset --hard to sync. If another role's interface is not merged yet, inspect their remote branch and coordinate; don't blindly cherry-pick unrelated work.
Example: `git show origin/role/adam-planning:docs/handoffs/adam.md`.

## Parallel agents on one machine
Use one worktree per role to avoid checkout interference:
```sh
git fetch origin
git worktree add ../group-quests-rishi role/rishi-matching
```
This example assumes the local role branch exists and is not already checked out; otherwise create a tracking branch from origin first. Never reuse a worktree containing another agent's dirty files.

## Shared-file changes
Record proposed contract change, producer, consumers, and compatibility implications in docs/DECISIONS.md. Get their ACK in the PR discussion or decision entry. Merge the contract change to main, sync role branches, then implement consumers. Keep changes small enough to integrate every 2-3 hours.
