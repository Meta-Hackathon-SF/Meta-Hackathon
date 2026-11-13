# Shared instructions for all agents

Read this file at the start of every task and after resuming. These instructions apply to the entire repository. Directory-level AGENTS.md files add ownership guidance. The latest explicit human task takes precedence.

## Required context
Execution is phase-driven and tag-driven. **Before any work, check open PRs and issues for tags addressed to you and answer them first (docs/COORDINATION.md §1).** Then read docs/PLAN.md (eight-step build order) and docs/roles/<name>.md (your tasks, owned paths, interfaces, acceptance checks), inspect code and handoff evidence, and select the first incomplete task. Keep the last six hours for UI/demo. Update your handoff with the current step and actual verification; never claim completion from elapsed time alone.

Read README.md, PROJECT_KNOWLEDGE.md, docs/COORDINATION.md, contracts/README.md, contracts/protocol.ts, contracts/API.md, contracts/WORKFLOW.md, contracts/PRIVACY.md, docs/ARCHITECTURE.md, docs/DECISIONS.md, docs/roles/<name>.md and docs/handoffs/<name>.md. Read docs/PLAN.md and docs/DEMO.md for shared priorities.

## Branch identity
- Rishi: role/rishi-matching
- Adam: role/adam-planning
- Will: role/will-voice-ui
- Patrik: role/patrik-privacy
- Kai: role/kai-orchestration

Before edits run git status --short and git rev-parse --abbrev-ref HEAD. Work only on the assigned role branch. If a clean checkout is on main, fetch and switch to the existing role branch (older Git: checkout). If another person's uncommitted work is present, preserve it and use a separate git worktree; never stash, discard, reset, or move their work without direction. Do not invent a new branch when the assigned branch already exists remotely.

This foundation is authorized for main. Subsequent implementation goes through small PRs unless a human explicitly directs another integration method. Never force-push main or another person's branch.

## Standing authorization: safe squash integration

The human authorizes automatic integration at meaningful work checkpoints. No additional permission question is needed when the change is ready and the checks below pass. Continue making descriptive feature, refinement, fix and test commits on role branches. Use squash for small single-purpose PRs; retain meaningful feature/test commit history with a normal PR merge when useful. Never blindly squash every PR or manufacture activity with empty or duplicate commits.

- Fetch and review the latest PR head against current main. Run the checks appropriate to the combined change, inspect sensitive-file exposure, and require any configured CI/review gates to pass. A GitHub "mergeable" label alone is not validation.
- Resolve understood mechanical conflicts while preserving teammates' work. Hold semantic conflicts, failing tests, unresolved change requests, and unacknowledged breaking contract changes. Tag the responsible owner with the exact missing input and evidence needed; first inspect their remote handoff/code so completed work is not requested again.
- An agent may mark its own fully verified checkpoint PR ready. Do not promote or merge another owner's draft/in-progress PR without that owner's readiness signal or explicit human direction for that PR. Independent tested modules may land with truthful fixture/integration limitations; merging a module does not certify the complete live journey.
- Use the chosen normal PR merge method, bound to the verified head SHA (`gh pr merge --squash|--merge --match-head-commit <sha>`). Recheck main/head before merging if either changed. Do not use admin bypass, force-push, rewrite existing commits, or delete active role branches.
- After a merge, fetch main and merge `origin/main` into your own clean role branch, then push the branch normally. Preserve ongoing commits. Never switch, reset, or synchronize another agent's working checkout underneath it.
- Publish the handoff/log and evidence ledger with actual implementation/check status. Every agent fetches and inspects relevant remote handoffs at its next checkpoint, then brings current main into its clean role branch before dependent work. Main is the shared source of integrated context.

This is authorization for agents while they are working, not a claim that an unattended merge bot or GitHub repository auto-merge is configured. Respect repository permissions and protection rules.

## Shared facts
**Constellations** is a weekly game inside Facebook Groups (D005). Mon-Fri one daily question; catch-up until Saturday 12:00 lock; streaks for on-day answers; Sunday 10:00 reveal of each player's constellation (3-5 people matched by meaning) into an anonymous, moderated chat that expires at the next lock; mutual reveal of identity only when both ask; a mid-week event nudge to a public venue; and a thresholded Sky of guessed vs actual prevalence. Muse (`muse-spark-1.3`, re-verify) is the model. Contract: contracts/protocol.ts 2.0.0 (D006, pending ACK) with fixtures in contracts/fixtures/. Hunt mechanics, clues, found codes, Keeper, Ritual and society branding are removed; do not reintroduce them.

Main holds the mock Facebook web UI (`web/`), docs, contracts and fixtures. Archived Group Quests server code on `archive/group-quests-before-pivot` is restored per owner into their own paths during step 2, renamed to 2.0.0 terms and retested; until retested it is not evidence. Build feature UI under web/src/features/constellations/<area>/. Do not rewrite the feed, reuse its localStorage as production persistence, or claim its mock sessions provide authentication. Keep the existing feed tests green.

Runtime systems are not implemented merely because a contract or directory exists. Preserve planned / implemented / verified / deployed distinctions.

## Coordination: check tags, stop and tag when blocked
Follow docs/COORDINATION.md exactly:
- **Every session starts** with `gh pr list` / `gh issue list` searches for your handle and PR comments. Answer requests addressed to you (`ACK`, `CHANGE:`, `DELIVERED:`) before your own next deliverable.
- **When your next task needs another owner's interface, data, ACK or endpoint that does not exist yet, stop at the task boundary.** Push your verified work, then open or update a `[BLOCKED]` draft PR that tags that owner's real handle with the exact "Needs from" block. Record it in your handoff, and continue only with independent work behind a labeled test-only adapter.
- Never invent the missing interface, edit another owner's paths, or silently change contracts to get unblocked.

## Ownership
Follow docs/roles/<name>.md. Import shared wire types instead of redefining them. TypeScript declarations are not runtime validation; both server requests and provider responses need actual validators. Python models must serialize exactly the same camelCase fields and enum literals. No cross-owner internal imports; use the documented service ports.

Claim shared-file edits in your handoff before starting. Contract changes require affected producer and consumer acknowledgment in docs/DECISIONS.md, with version, migration, examples and tests updated together. Additive changes still need downstream awareness. Do not silently solve integration problems by changing another owner's contract.

## Build behavior
Implement one integrated happy path before extras. Never require a paid/live model call for ordinary offline tests. Keep test doubles in test/fixture adapters and label replay in the UI. No fake production success when a provider fails. Handle cancellation and stale responses.

Muse interprets and proposes (themes, constellations, names, follow-ups, questions, event nudges, Sky headlines). Server code authorizes, validates and enforces every guarantee. Code detects thresholds and computes every Sky number. Only the orchestration layer persists side effects. Model prompts cannot grant permissions. Never turn untrusted user text into system instructions or arbitrary tool names/URLs.

## Data and operational boundaries
No keys, real participant content, raw audio, tokens, resumes, or private constraints in commits, docs, logs, error bodies, or public telemetry. Do not log whole model prompts. Store minimized request metadata and validation outcomes. Public explanations must be constructed/validated from an allowlist. Synthetic profile flags survive every projection.

Auth comes from server-verified sessions, never a client-supplied participantId alone. Recheck consent and membership before executing a queued action. Time/budget/location/capacity gates must not be weakened to get a demo match. Public venue selections come from an approved catalog, not hallucinated addresses.

## Handoffs and verification
Update docs/handoffs/<name>.md and append docs/updates/<name>.md at checkpoints with timestamp, branch/commit, changed contracts/files, commands/results, blocked dependencies and exact next consumer action. Inspect remote role logs when local main is stale. Shared context lives on main, not in private copies.

Use focused tests for your behavior. Document failures honestly. For UI work run relevant web checks; for security/concurrency changes include adversarial cases. Never call a plan implemented, a replay live, or a target achieved. Never let a player see another player's answers: constellation names, Sky themes, nudges and generated questions pass the no-quote and sensitive-term guards; every chat message passes M1 and OutputGuard; safety-flagged content never reaches any game output. Update PROJECT_KNOWLEDGE.md when a merged implementation changes the evidence.

## Finish
Push your role branch, report exact scope and verification, and open or prepare a reviewable PR if authorized. Keep main's documentation synchronized with implemented contracts. No unrequested new services, paid provider runs, or public deployments solely to verify documentation.
