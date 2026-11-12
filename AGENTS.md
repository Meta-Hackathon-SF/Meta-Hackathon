# Shared instructions for all agents

Read this file at the start of every task and after resuming. These instructions apply to the entire repository. Directory-level AGENTS.md files add ownership guidance. The latest explicit human task takes precedence.

## Required context
Read README.md, PROJECT_KNOWLEDGE.md, contracts/README.md, contracts/protocol.ts, contracts/API.md, contracts/WORKFLOW.md, contracts/PRIVACY.md, docs/ARCHITECTURE.md, your docs/roles/<name>.md, and your docs/handoffs/<name>.md. Read docs/PLAN.md before scheduling work.

## Branch identity
- Rishi: role/rishi-matching
- Adam: role/adam-planning
- Will: role/will-voice-ui
- Patrik: role/patrik-privacy
- Kai: role/kai-orchestration

Before edits run git status --short and git branch --show-current. Work only on the assigned role branch. If a clean checkout is on main, fetch and switch to the existing role branch. If another person's uncommitted work is present, preserve it and use a separate git worktree; never stash, discard, reset, or move their work without direction. Do not invent a new branch when the assigned branch already exists remotely.

This foundation is authorized for main. Subsequent implementation goes through small PRs unless a human explicitly directs another integration method. Never force-push main or another person's branch.

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
