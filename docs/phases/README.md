# Agent execution map

Every agent follows its own playbook while sharing the contracts and integration gates. Pick your first incomplete phase based on code and verified evidence, not the clock or a checkbox alone.

| Owner | Branch | Playbook | Start in |
| --- | --- | --- | --- |
| Rishi | `role/rishi-matching` | [Matching phases](rishi.md) | `server/matching/`, `tests/matching/` |
| Adam | `role/adam-planning` | [Planning phases](adam.md) | `server/providers/`, `server/planning/` |
| Will | `role/will-voice-ui` | [Voice/UI phases](will.md) | `web/src/features/group-quests/onboarding/`, `shell/` |
| Patrik | `role/patrik-privacy` | [Privacy phases](patrik.md) | `server/privacy/`, `db/privacy/` |
| Kai | `role/kai-orchestration` | [Workflow phases](kai.md) | `server/app/`, `server/orchestration/` |

## Shared phase gates

| Phase | Hours | Team-wide gate |
| --- | --- | --- |
| P0 | 0-1 | Interfaces acknowledged, actual provider configuration investigated, branch and ownership established |
| P1 | 1-4 | Each component can be exercised independently with explicit synthetic fixtures |
| P2 | 4-7 | Three devices complete confirmed intent through a persisted event |
| P3 | 7-10 | Live participant change produces a valid revision or honest no-plan state |
| P4 | 10-13 | Labeled time skip runs live continuation and explicit hosting creates a draft |
| P5 | 13-16 | Integration and critical failure cases pass; feature freeze |
| P6 | 16-22 | UI refinement, demo, recording, early submission and buffer |

P6 is reserved for UI and demo-related work; functional UI must already exist by P2. Every owner implements their own component and participates in polish. Runtime completion is separate from documentation completion.

## What each agent does on every work session

1. Fetch remote state, inspect the working tree and confirm the assigned branch. Preserve all unrelated work.
2. Read root AGENTS.md, shared contracts, your role, your phase playbook and your latest handoff.
3. Inspect existing implementation and tests. Identify the first incomplete deliverable; do not rebuild completed work.
4. Read upstream handoffs on their remote branches when they have not merged. State the exact input needed.
5. Implement the smallest next phase deliverable in owned paths. Use a test-only adapter when an upstream dependency is unavailable.
6. Run meaningful checks for that deliverable. A fake-provider test proves local behavior, not live Muse integration.
7. Update your handoff/log with actual evidence and push the role branch. Coordinate a small integration PR.
8. Continue independent work while a dependency is blocked. Report a precise port/schema mismatch; never silently fork the contract.

## Handoff dependencies

| Producer | Deliverable | Consumer |
| --- | --- | --- |
| Kai + Patrik | Server registration and authenticated session conventions | Everyone |
| Adam | MusePort adapter + extraction result | Rishi + Will |
| Will | Confirmed intent payload | Patrik |
| Patrik | Authorized Candidate snapshot + public projection | Rishi + Adam + Kai |
| Rishi | Validated GroupProposal | Adam + Kai |
| Adam | Validated QuestPlan / revision / continuation | Kai |
| Kai | Event persistence, messages and authorized stream | Feature UI owners |
| Every UI owner | Component props, loading/error/recovery behavior | Will's feature composition |

This is an integration graph, not a requirement to wait serially. P1 uses synthetic adapters to unblock parallel implementation. Replace them with real ports for P2 and distinguish fixture verification from live evidence.

## Shared-file coordination

Will coordinates existing web routing and manifests. Kai coordinates server composition, manifests and migration order. Patrik reviews authorization and database access boundaries. Adam owns the single Muse client. Contract changes require producer/consumer ACK in docs/DECISIONS.md. Coordinate ownership of new common files before creating conflicting versions.

## Handoff state template

```text
Current phase: P0-P6
Status: planned / implementing / blocked / verified
Branch + commit:
Completed deliverables:
Changed interfaces and files:
Checks run + actual result:
Fixture versus live evidence:
Next consumer + exact action:
Blocked on + owner:
Next independent task:
```

Check a task off only with evidence. A team-wide phase gate is not passed merely because one person's local module works. Once H16 arrives, cut optional scope and preserve the working critical path; do not move the deadline to recover an elaborate feature.
