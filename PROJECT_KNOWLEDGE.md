# Shared project knowledge
## Evidence baseline
Original shell baseline: 88e6623eee89d518d006717cbadfde8ce5aec702. Documentation/phase baseline: a9241f1. Integration evidence updated 2026-11-12T21:32Z (Group Quests era; the Constellations pivot began 2026-11-12).
Existing web/ contains a React/Vite/TypeScript mock Facebook shell with local demonstration state, feed components, secondary routes and Playwright tests. Web lint/build were rerun successfully during Kai's P0 checkpoint; this does not verify the future live feature.

Integration source includes Rishi's matching module from main 56346eb (PR #3), plus Kai's backend composition in PR #5 (implementation commits adb7dc6 and 1a0e045, verification 6359682). The combined source was checked after normal main synchronization bdac27e: `python -m pytest tests -q` passed **144 tests** on Python 3.13.7. Kai's Ruff checks and formatting passed. All matching/business adapters used in these tests are synthetic fixtures. No provider/database/event integration is certified by that count. These tests cover Group Quests behavior, not Constellations.

Patrik, Adam and Will have independently published role-branch implementations; inspect their latest handoffs before declaring a dependency missing. Their unmerged work is not claimed integrated here.

Muse live check (2026-11-12): the model `muse-spark-1.3` answered 2 live calls and the provider echoed the model name. Observed single-call latency was 17 to 24 s at low reasoning effort. Two calls are not a benchmark. Wonder and Ember were not available in the docs read and were not tested.

## Locked decisions
- Product name: Constellations (pivot from Group Quests, 2026-11-12). The Keeper is Muse acting as game master. Muse denotes model family only.
- Existing Facebook mock UI is the host shell, labeled "Simulated Facebook". Feature UI lives under `web/src/features/constellations/`; reused `group-quests/` code is migrated by Will.
- Five engineering owners and branch names are in AGENTS.md. Constellations role assignments are PROPOSED under D009 and need acknowledgment.
- Friendship only, 18+, public places only for quests. Groups of 3 to 5.
- Muse proposes, code enforces. Deterministic guards validate every Muse output. Only orchestration executes durable effects.
- Individual answers are never shown to other players. Prompts carry random player IDs only.
- Sky themes show only at 3+ players in the demo (25+ in production).
- Synthetic players, accelerated unlocks and cached responses are always labeled.
- Contracts: `contracts/protocol.ts` stays as legacy 1.x. `contracts/constellations.ts` (2.0.0-proposed) needs producer/consumer acknowledgment (D009).
- Existing frontend stack stays. FastAPI + PostgreSQL/Supabase is a proposed server baseline.
- Never cut: consent, safety triage, no-quote guard, Sky threshold, labels. Cut order if time runs out: P2 vision, Ritual, riddle veto, voice (text always works).
- Standing human authorization allows safe squash PR integration after current-head validation; see AGENTS.md. Keep active role branches and synchronize them with main at checkpoints. No unattended merge bot is configured.

## Confirm
- **Organizer confirmation of the Muse model** (Spark, Wonder or Ember). `muse-spark-1.3` works live; Wonder and Ember are untested. Open.
- Latency plan: confirm parallel calls bring induction for 30 players under 60 s given 17 to 24 s per call. Top technical risk.
- Backend hosting, database/auth setup, public venue allowlist, demo Group, submission rules.
- Deadline used in planning: November 13, 2026 at 10:30 AM PST, supplied by the team, not independently verified. Feature freeze 04:30 AM.
- Decision D009 (contract and ownership) acknowledgment from all five owners.

## Evidence ledger
| Capability | Status | Required evidence |
| --- | --- | --- |
| Facebook shell | Existing implementation; lint/build passed at Kai P0 | Relevant UI/live integration checks remain separate |
| Shared instructions/contracts | Authored for Group Quests; Constellations contract proposed, not acknowledged | Link and interface consistency review; D009 acknowledgments |
| Backend composition (`server/app/`) | HTTP baseline verified; 42 offline boundary tests plus local socket probes | Real owner registrations and database readiness |
| Muse adapter (`server/providers/`) | 2 live calls on `muse-spark-1.3`, 17 to 24 s each; adapter is Group Quests-era | Constellations job schemas; parallel-call timing |
| Privacy (`server/privacy/`) | Postgres-tested locally on Patrik's branch; not integrated | Consent v2, answer access 403 test, prompt-builder test on the integration candidate |
| Matching (`server/matching/`) | Offline; 102 tests in the combined 144-test run; built for constraint-gated groups | Adaptation to meaning-based societies; baseline vs Muse example |
| Orchestration (`server/orchestration/`) | Partial; offline fixtures | Round lifecycle, idempotent confirm, retry tests |
| Voice/onboarding (`server/voice/`) | Fixture only | Real transcription or text fallback on a phone |
| Join and Confession (F1, F2) | Planned | Phone join under 30 s; no answer before consent |
| Safety triage (F9) | Planned | Seeded distress answer never appears |
| Induction (F3) | Planned | 30 players under 60 s; every society validated |
| Hunt riddles (F4) | Planned | No-quote fuzz test; red-team list of 30 answers |
| Passphrase and confirm (F5) | Planned | Mutual idempotent confirm; wrong code reveals nothing |
| Sky (F7) | Planned | Threshold test; numbers match server counts |
| Operator console (F8) | Planned | Model metadata and latency per call |
| Ritual (F6, P1) | Planned | 3+ approvals; venue allowlist test |
| Hosting | Planned | Host acceptance |
| User impact | Unknown | Actual observations, no invented metrics |

Each owner updates their own handoff while working. After merge, update this ledger with exact commit, command and outcome. Do not embed private data.
