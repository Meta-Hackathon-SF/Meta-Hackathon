# Shared project knowledge
## Evidence baseline
Inspected main commit: 88e6623eee89d518d006717cbadfde8ce5aec702.
Existing web/ contains a React/Vite/TypeScript mock Facebook shell with local demonstration state, feed components, secondary routes and Playwright tests. Source and package scripts were inspected; this documentation task did not run the existing application suite.

This foundation adds instructions and planned contracts. Group matching, provider calls, authentication, private database views, event workflow and feature UI are not yet implemented or live-verified.

## Locked decisions
- Product name: Group Quests. Muse denotes model family only.
- Existing Facebook mock UI is the host shell; feature has separate UI ownership.
- Five engineering owners and branch names are in AGENTS.md.
- Social belonging; teams of 3-5; public venues; explicit acceptance.
- Deterministic guards plus Muse reasoning. Only orchestration executes durable effects.
- Week-two time skip is simulated; adaptation must run live.
- Existing frontend stack stays. FastAPI + PostgreSQL/Supabase is a proposed server baseline.

## Confirm during H0
Actual Muse model IDs, endpoint/auth scheme, audio capability, limits and cost.
Backend hosting, database/auth setup, public venue catalog, demo community, deadline and submission rules.
Deadline used in planning: November 13, 2026 at 10:30 AM PST, supplied by the team, not independently verified here.

## Evidence ledger
| Capability | Status | Required evidence |
| --- | --- | --- |
| Facebook shell | Existing implementation, not rerun here | web lint/build and relevant UI checks |
| Shared instructions/contracts | Authored foundation | Link and interface consistency review |
| Group Quests feature | Planned | Live multi-device journey |
| Muse reasoning | Planned | Actual provider response + model metadata |
| Privacy | Planned | Unauthorized access and revocation tests |
| Reliable events | Planned | Concurrency/retry/stale-job tests |
| Retention/hosting | Planned | Live next-week generation and host acceptance |
| User impact | Unknown | Actual observations, no invented metrics |

Each owner updates their own handoff while working. After merge, update this ledger with exact commit, command and outcome. Do not embed private data.
