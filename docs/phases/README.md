# Agent execution map

Every agent follows its own playbook while sharing the contracts and integration gates. Pick your first incomplete phase based on code and verified evidence, not the clock or a checkbox alone.

| Owner | Branch | Playbook | Start in |
| --- | --- | --- | --- |
| Rishi | `role/rishi-matching` | [Induction phases](rishi.md) | `server/matching/`, `web/src/features/constellations/matching/`, `induction/` |
| Adam | `role/adam-planning` | [Keeper and Muse job phases](adam.md) | `server/providers/`, `server/planning/`, `web/src/features/constellations/hunt/` |
| Will | `role/will-voice-ui` | [Join, Confession and composition phases](will.md) | `web/src/features/constellations/shell/`, `join/`, `confession/`, `server/voice/` |
| Patrik | `role/patrik-privacy` | [Privacy and safety phases](patrik.md) | `server/privacy/`, `db/privacy/`, `web/src/features/constellations/privacy/` |
| Kai | `role/kai-orchestration` | [Round lifecycle phases](kai.md) | `server/app/`, `server/orchestration/`, `web/src/features/constellations/operator/`, `sky/` |

Product: Constellations (D009, contract `contracts/constellations.ts` at `2.0.0-proposed`; `contracts/protocol.ts` 1.x stays as legacy). Times below are PST, Nov 12-13, 2026. D009 ACK is the first P0 item for every owner. The deadline (10:30 AM Nov 13) is team-supplied and not independently verified.

## Shared phase gates

| Phase | PST | Team-wide gate |
| --- | --- | --- |
| P0 | 16:00-17:00 | D009 and contracts acknowledged by all five owners; Muse call re-verified; ownership and branches confirmed |
| P1 | 17:00-20:00 | Each module runs alone against explicit, labeled synthetic fixtures |
| P2 | 20:00-23:00 | Integrated round on 3+ phones: join, confess, induct, riddles, confirm in person |
| P3 | 23:00-02:00 | Sky, safety triage, blocks and operator console complete; induction timing for 30 players measured against 60 s |
| P4 | 02:00-03:30 | P1 features (ritual, riddle veto) only if P3 is green; hardening |
| P5 | 03:30-04:30 | Integration and failure cases pass; FEATURE FREEZE at 04:30; backup captured |
| P6 | 04:30-10:30 | UI polish, rehearsal, backup video, Devpost, submission; critical fixes only |

P6 is reserved for UI and demo-related work; functional UI must already exist by P2. Never cut: consent, safety triage, no-quote guard, Sky threshold, truth labels. Cut order: P2 vision items, ritual, riddle veto, voice (text always works). Runtime completion is separate from documentation completion.

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
| Kai + Patrik | Server registration, authenticated session and `/api/v1` conventions | Everyone |
| Adam | Single Muse adapter, test fake, Keeper prompt rules | Rishi, Patrik, Will, Kai |
| Will | Component slots/routes, join and answer payloads, Muse chip | Every UI owner, Patrik, Kai |
| Patrik | Authorized unflagged answers, M1 flags, output guard, prompt builder, blocks | Rishi, Adam, Kai |
| Rishi | Validated societies (`Society[]`) and themes | Adam, Kai |
| Adam | Society identity, riddles, Sky headlines, ritual quest (all guarded) | Kai, Will |
| Kai | Round state, finds, SSE stream, Sky counts, operator API | Will, Adam (M8 counts), every UI owner |

This is an integration graph, not a requirement to wait serially. P1 uses synthetic adapters to unblock parallel implementation. Replace them with real ports for P2 and distinguish fixture verification from live evidence.

## Shared-file coordination

Will coordinates web routing and manifests, including the migration of the shell to `web/src/features/constellations/`. Kai coordinates server composition, manifests and migration order. Patrik reviews authorization and database access boundaries. Adam owns the single Muse client; Patrik's output guard runs on every Muse text output before release. Contract changes require producer/consumer ACK in docs/DECISIONS.md. Coordinate ownership of new common files before creating conflicting versions.

## Handoff state template

```text
Current phase: P0-P6 (D009 ACK status first)
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

Check a task off only with evidence. A team-wide phase gate is not passed merely because one person's local module works. Once the 04:30 freeze arrives, cut optional scope and preserve the working critical path; do not move the deadline to recover an elaborate feature.
