# Launch your coding agent: Constellations
Start with the [execution map](phases/README.md) and your [per-person phased build checklist](phases/README.md). These define P0-P6 tasks on the re-based timeline (P0 16:00 PST, freeze 04:30, deadline 10:30 AM PST) with dependencies and completion evidence. The product is Constellations (D001). Your first P0 item is checking tags (see [COORDINATION.md](COORDINATION.md) §1), then your D001/D003 ACK. Read the playbook alongside your role assignment before writing code.

Each teammate clones this repository locally and checks out their branch. The common AGENTS.md is on every branch. All shared contracts remain visible to everyone. Cross-owner requests follow [COORDINATION.md](COORDINATION.md).

| Person | Branch | Read next |
| --- | --- | --- |
| rishi | `role/rishi-matching` | [assignment](roles/rishi.md) |
| adam | `role/adam-planning` | [assignment](roles/adam.md) |
| will | `role/will-voice-ui` | [assignment](roles/will.md) |
| patrik | `role/patrik-privacy` | [assignment](roles/patrik.md) |
| kai | `role/kai-orchestration` | [assignment](roles/kai.md) |

Paste this, substituting your name:
> I am NAME. Read AGENTS.md, PROJECT_KNOWLEDGE.md, docs/COORDINATION.md, docs/DECISIONS.md (D001, D003), contracts/protocol.ts (v1.0.0, pending ACK), and docs/roles/NAME.md and docs/phases/NAME.md. FIRST check open PRs/issues for tags addressed to me (COORDINATION §1) and answer them before anything else; then record my D001/D003 ACK. Switch to my assigned role branch only if the checkout is clean; otherwise preserve work and use a separate worktree. Implement my first incomplete checkpoint within my ownership boundaries. Build against the shared interfaces and coordinate any change through docs/DECISIONS.md. If I am blocked on another owner's interface, contract change, data shape, ACK or endpoint: stop at the phase boundary, push, open or update a `[BLOCKED]` draft PR tagging that owner's handle with the exact request block (COORDINATION §2), and continue only with a labeled test-only adapter; never invent their interface. Update my handoff with exact verification and dependencies. The web app is a mock Facebook shell; Constellations feature UI lives at web/src/features/constellations/. Muse proposes, code enforces; label every synthetic element.

Product in one line: a campus constellation game inside Facebook Groups where Muse  turns private weekly confessions into constellations of 3-5 matched by meaning, who find each other in person.

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
git worktree add ../constellations-rishi role/rishi-matching
```
This example assumes the local role branch exists and is not already checked out; otherwise create a tracking branch from origin first. Never reuse a worktree containing another agent's dirty files.

## Shared-file changes
Record proposed contract change, producer, consumers, and compatibility implications in docs/DECISIONS.md. Get their ACK in the PR discussion or decision entry. Merge the contract change to main, sync role branches, then implement consumers. Keep changes small enough to integrate every 2-3 hours.
