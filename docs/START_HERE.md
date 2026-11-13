# Launch your coding agent: Constellations weekly game
Each teammate clones the repo, switches to their branch, and pastes the master prompt below into their coding agent, replacing NAME.

| Person | Branch | Tasks |
| --- | --- | --- |
| rishi | `role/rishi-matching` | [roles/rishi.md](roles/rishi.md) |
| adam | `role/adam-planning` | [roles/adam.md](roles/adam.md) |
| will | `role/will-voice-ui` | [roles/will.md](roles/will.md) |
| patrik | `role/patrik-privacy` | [roles/patrik.md](roles/patrik.md) |
| kai | `role/kai-orchestration` | [roles/kai.md](roles/kai.md) |

```sh
git clone https://github.com/willapat/Meta-Hackathon.git && cd Meta-Hackathon
git fetch origin && git switch --track origin/role/NAME-BRANCH   # or: git switch <branch> && git merge origin/main
```

## Master prompt
```text
I am NAME on the Constellations team (repo: willapat/Meta-Hackathon). The product pivoted to a WEEKLY GAME on 2026-11-12 (decisions D005 and D006). Work only on my role branch and only in my owned paths.

1. Sync: run `git fetch origin`, confirm `git rev-parse --abbrev-ref HEAD` is my role branch (from AGENTS.md), confirm `git status --short` is clean, then `git merge origin/main`. If the checkout has someone else's uncommitted work, use a separate git worktree; never stash, reset or discard it.
2. Tags first: check open PRs, issues and PR comments that mention my GitHub handle (docs/COORDINATION.md §1). Answer each with ACK / CHANGE: / DELIVERED: before my own work. Then post my ACK of D005 and D006 (docs/DECISIONS.md).
3. Read, in order: AGENTS.md, README.md, PROJECT_KNOWLEDGE.md, docs/PLAN.md (eight-step build order), docs/roles/NAME.md (my tasks, owned paths, interfaces, acceptance checks), contracts/README.md, contracts/protocol.ts (2.0.0), contracts/API.md, contracts/WORKFLOW.md, contracts/PRIVACY.md, contracts/fixtures/*.json, docs/handoffs/NAME.md.
4. Build: do the first incomplete task in docs/roles/NAME.md. Task 1 for server owners is restoring my area's archived code from `origin/archive/group-quests-before-pivot` (e.g. `git checkout origin/archive/group-quests-before-pivot -- <my paths>`), renaming it to 2.0.0 terms (constellation, daily answer, weekly cycle; no clues, found codes, hunts, Keeper, Ritual or society), and re-running its tests. Mirror protocol.ts shapes exactly (camelCase) with real runtime validators. Develop against contracts/fixtures/ through a clearly labeled test-only adapter until the owning teammate's port lands. Never edit another owner's paths and never change contracts/ without a DECISIONS.md entry plus producer and consumer ACK.
5. Rules that never bend: Muse proposes, code enforces. No player ever sees another player's answers. Every Muse public text and every chat message passes OutputGuard. Sky themes only at count >= threshold (3 demo). Identity only on mutual reveal. Safety-flagged content never reaches any output. Label everything synthetic ("Simulated Facebook", "Synthetic player", "Synthetic signal", "Demo timing", "Replay of a saved cycle", "Fallback grouping"). No secrets, real participant data or full prompts in commits or logs. Ordinary tests never call the live model.
6. When blocked on another owner's interface, data, endpoint or ACK: stop at the task boundary, push my verified work, open or update a draft PR titled `[BLOCKED] <step>: <what I need>` tagging their real handle with the "Needs from" block (docs/COORDINATION.md §2), record it in my handoff, and continue only with independent work behind a labeled test-only adapter.
7. Verify: run the acceptance checks listed in my role file (pytest for my server paths; `npm run lint && npm run build && npm run test:e2e` in web/ for UI work). Report real results, including failures. Never call fixture results live or a plan implemented.
8. Checkpoint every meaningful task: commit with conventional messages (feat:, fix:, test:, docs:), update docs/handoffs/NAME.md and append docs/updates/NAME.md with timestamp, commit, files, checks, blockers and next consumer action, push my role branch, and open a small PR to main. Never force-push. Never merge another owner's PR without their readiness signal.

Start now with step 1 and keep going task by task. Steps 6 (event nudges) and 7 (question generation, synthetic signals) in docs/PLAN.md are the first scope cuts; feature freeze is 04:30 AM PST Nov 13.
```

## Keeping current
Run `git fetch origin && git merge origin/main` from your clean role branch after every teammate merge. Inspect others' progress with `git show origin/role/<branch>:docs/handoffs/<name>.md`. One worktree per role if several agents share a machine: `git worktree add ../constellations-<name> <branch>`.
