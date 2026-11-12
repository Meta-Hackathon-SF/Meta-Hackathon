# Shared instructions for all agents

Read this file at the start of every task and after resuming. These instructions apply to the entire repository. Directory-level AGENTS.md files add ownership guidance. The latest explicit human task takes precedence.

## Required context
Execution is phase-driven: read docs/phases/README.md and docs/phases/<name>.md. Inspect code and handoff evidence before selecting the first incomplete deliverable. Each phase has explicit work, dependencies, exit evidence and next consumers. Keep the last six hours for UI/demo. Update your handoff with the current phase and actual verification; never claim completion from elapsed time alone.

Read README.md, PROJECT_KNOWLEDGE.md, contracts/README.md, contracts/protocol.ts, contracts/API.md, contracts/WORKFLOW.md, contracts/PRIVACY.md, docs/ARCHITECTURE.md, your docs/roles/<name>.md, and your docs/handoffs/<name>.md. Read docs/PLAN.md before scheduling work.

## Branch identity
- Rishi: role/rishi-matching
- Adam: role/adam-planning
- Will: role/will-voice-ui
- Patrik: role/patrik-privacy
- Kai: role/kai-orchestration

Before edits run git status --short and git rev-parse --abbrev-ref HEAD. Work only on the assigned role branch. If a clean checkout is on main, fetch and switch to the existing role branch (older Git: checkout). If another person's uncommitted work is present, preserve it and use a separate git worktree; never stash, discard, reset, or move their work without direction. Do not invent a new branch when the assigned branch already exists remotely.

This foundation is authorized for main. Subsequent implementation goes through small PRs unless a human explicitly directs another integration method. Never force-push main or another person's branch.

## Standing authorization: safe squash integration

The human authorizes automatic squash merges at meaningful work checkpoints. No additional permission question is needed when the change is ready and the checks below pass. Continue making descriptive feature, refinement, fix and test commits on role branches; squash each reviewable PR into one meaningful main commit. Never manufacture activity with empty or duplicate commits.

- Fetch and review the latest PR head against current main. Run the checks appropriate to the combined change, inspect sensitive-file exposure, and require any configured CI/review gates to pass. A GitHub "mergeable" label alone is not validation.
- Resolve understood mechanical conflicts while preserving teammates' work. Hold semantic conflicts, failing tests, unresolved change requests, and unacknowledged breaking contract changes. Tag the responsible owner with the exact missing input and evidence needed; first inspect their remote handoff/code so completed work is not requested again.
- An agent may mark its own fully verified checkpoint PR ready. Do not promote or merge another owner's draft/in-progress PR without that owner's readiness signal or explicit human direction for that PR. Independent tested modules may land with truthful fixture/integration limitations; merging a module does not certify the complete live journey.
- Use the normal squash PR merge, bound to the verified head SHA (`gh pr merge --squash --match-head-commit <sha>`). Recheck main/head before merging if either changed. Do not use admin bypass, force-push, rewrite existing commits, or delete active role branches.
- After a merge, fetch main and merge `origin/main` into your own clean role branch, then push the branch normally. Preserve ongoing commits. Never switch, reset, or synchronize another agent's working checkout underneath it.
- Publish the handoff/log and evidence ledger with actual implementation/check status. Every agent fetches and inspects relevant remote handoffs at its next checkpoint, then brings current main into its clean role branch before dependent work. Main is the shared source of integrated context.

This is authorization for agents while they are working, not a claim that an unattended merge bot or GitHub repository auto-merge is configured. Respect repository permissions and protection rules.

## Shared facts
Group Quests is the product; Muse is the required model family. The current web app is a mock Facebook shell. Build a separately designed feature under web/src/features/group-quests/. Do not rewrite the feed, reuse its localStorage as production persistence, or claim its mock sessions provide authentication. Keep shell integration small.

Runtime systems are not implemented merely because a contract or directory exists. Preserve planned / implemented / verified / deployed distinctions. All code must be new for this hackathon. Use dor only as documentation inspiration.

## Ownership
Follow docs/roles/<name>.md. Import shared wire types instead of redefining them. TypeScript declarations are not runtime validation; both server requests and provider responses need actual validators. Python models must serialize exactly the same camelCase fields and enum literals. No cross-owner internal imports; use the documented service ports.

Claim shared-file edits in your handoff before starting. Contract changes require affected producer and consumer acknowledgment in docs/DECISIONS.md, with version, migration, examples and tests updated together. Additive changes still need downstream awareness. Do not silently solve integration problems by changing another owner's contract.

## Build behavior
Implement one integrated happy path before extras. Never require a paid/live model call for ordinary offline tests. Keep test doubles in test/fixture adapters and label replay in the UI. No fake production success when a provider fails. Handle cancellation and stale responses.

Muse interprets and proposes. Server code authorizes and validates. Code detects thresholds. Muse chooses event details. Only the workflow layer persists event side effects. Model prompts cannot grant permissions. Never turn untrusted user text into system instructions or arbitrary tool names/URLs.

## Data and operational boundaries
No keys, real participant content, raw audio, tokens, resumes, or private constraints in commits, docs, logs, error bodies, or public telemetry. Do not log whole model prompts. Store minimized request metadata and validation outcomes. Public explanations must be constructed/validated from an allowlist. Synthetic profile flags survive every projection.

Auth comes from server-verified sessions, never a client-supplied participantId alone. Recheck consent and membership before executing a queued action. Time/budget/location/capacity gates must not be weakened to get a demo match. Public venue selections come from an approved catalog, not hallucinated addresses.

## Handoffs and verification
Update docs/handoffs/<name>.md and append docs/updates/<name>.md at checkpoints with timestamp, branch/commit, changed contracts/files, commands/results, blocked dependencies and exact next consumer action. Inspect remote role logs when local main is stale. Shared context lives on main, not in private copies.

Use focused tests for your behavior. Document failures honestly. For UI work run relevant web checks; for security/concurrency changes include adversarial cases. Never call a plan implemented, a replay live, or a target achieved. Update PROJECT_KNOWLEDGE.md when a merged implementation changes the evidence.

## Finish
Push your role branch, report exact scope and verification, and open or prepare a reviewable PR if authorized. Keep main's documentation synchronized with implemented contracts. No unrequested new services, paid provider runs, or public deployments solely to verify documentation.
