# Shared project knowledge
## Evidence baseline
Original shell baseline: 88e6623eee89d518d006717cbadfde8ce5aec702. Documentation/phase baseline: a9241f1. Integration evidence updated 2026-11-12T21:32Z.
Existing web/ contains a React/Vite/TypeScript mock Facebook shell with local demonstration state, feed components, secondary routes and Playwright tests. Web lint/build were rerun successfully during Kai's P0 checkpoint; this does not verify the future live feature.

Current integration source includes Rishi's matching module from main 56346eb (PR #3), plus Kai's backend composition in PR #5 (implementation commits adb7dc6 and 1a0e045, verification 6359682). The combined source was checked after normal main synchronization bdac27e: `python -m pytest tests -q` passed **144 tests** on Python 3.13.7. Kai's Ruff checks and formatting passed. All matching/business adapters used in these tests are synthetic fixtures. No provider/database/event integration is certified by that count.

Patrik, Adam and Will have independently published role-branch implementations; inspect their latest handoffs before declaring a dependency missing. Their unmerged work is not claimed integrated here. Persistent quest/event effects, live model calls, multi-device acceptance and hosting remain unverified.

## Locked decisions
- Product name: Group Quests. Muse denotes model family only.
- Existing Facebook mock UI is the host shell; feature has separate UI ownership.
- Five engineering owners and branch names are in AGENTS.md.
- Social belonging; teams of 3-5; public venues; explicit acceptance.
- Deterministic guards plus Muse reasoning. Only orchestration executes durable effects.
- Week-two time skip is simulated; adaptation must run live.
- Existing frontend stack stays. FastAPI + PostgreSQL/Supabase is a proposed server baseline.
- Standing human authorization allows safe squash PR integration after current-head validation; see AGENTS.md. Keep active role branches and synchronize them with main at checkpoints. No unattended merge bot is configured.

## Confirm during H0
Actual Muse model IDs, endpoint/auth scheme, audio capability, limits and cost.
Backend hosting, database/auth setup, public venue catalog, demo community, deadline and submission rules.
Deadline used in planning: November 13, 2026 at 10:30 AM PST, supplied by the team, not independently verified here.

## Evidence ledger
| Capability | Status | Required evidence |
| --- | --- | --- |
| Facebook shell | Existing implementation; lint/build passed at Kai P0 | Relevant UI/live integration checks remain separate |
| Shared instructions/contracts | Authored foundation | Link and interface consistency review |
| Backend composition | HTTP baseline verified; 42 offline boundary tests plus local socket probes | Real owner registrations and database readiness |
| Group matching | Implemented independently; 102 offline tests included in combined 144-test run | Actual provider/snapshot integration and evaluation |
| Group Quests feature | Independent modules available; full integration pending | Live multi-device journey |
| Muse reasoning | Provider/planning work on Adam's role branch; not live-verified here | Actual provider response + model metadata |
| Privacy | Implementation on Patrik's role branch; not integrated/verified by Kai | Unauthorized access, revocation and Postgres tests on the integration candidate |
| Reliable events | Planned | Concurrency/retry/stale-job tests |
| Retention/hosting | Planned | Live next-week generation and host acceptance |
| User impact | Unknown | Actual observations, no invented metrics |

Each owner updates their own handoff while working. After merge, update this ledger with exact commit, command and outcome. Do not embed private data.
