# Shared project knowledge
## Evidence baseline
Main is the mock Facebook shell only (`web/`: React/Vite/TypeScript, local demonstration state, feed components, secondary routes, Playwright tests), plus documentation and `contracts/protocol.ts`. Date of this baseline: 2026-11-12 (Constellations pivot and repo reset). Main was reset to the shell; the earlier Group Quests server code, tests, database files and provider adapter were removed. They survive only on branch `archive/group-quests-before-pivot` as reference. Nothing is reused, merged, live-verified or fixture-verified on main. Earlier test counts and lint/build results from the Group Quests era no longer describe main and are not claimed. Constellations is a fresh build.

Muse model note (2026-11-12): `muse-spark-1.3` answered 2 live calls and the provider echoed the model name, through the removed Group Quests adapter. Observed single-call latency was 17 to 24 s at low reasoning effort. Two calls are not a benchmark, and no Constellations code has called the model. Wonder and Ember were not available in the docs read and were not tested. Re-verify on the new adapter.

Role-branch work from teammates is not claimed integrated here; inspect their latest handoffs and PRs (see [docs/COORDINATION.md](docs/COORDINATION.md)) before declaring a dependency missing.

## Locked decisions
- Product name: Constellations (pivot from Group Quests, 2026-11-12). Muse is Muse acting as game master. Muse denotes model family only.
- Existing Facebook mock UI is the host shell, labeled "Simulated Facebook". Feature UI will live under `web/src/features/constellations/`.
- Five engineering owners and branch names are in AGENTS.md. Constellations role assignments are PROPOSED under D001 and need acknowledgment.
- Friendship only, 18+, public places only for quests. Groups of 3 to 5.
- Muse proposes, code enforces. Deterministic guards validate every Muse output. Only orchestration executes durable effects.
- Individual answers are never shown to other players. Prompts carry random player IDs only.
- Sky themes show only at 3+ players in the demo (25+ in production).
- Synthetic players, accelerated unlocks and cached responses are always labeled.
- Contract: `contracts/protocol.ts`, `CONTRACT_VERSION = "1.0.0"`, the first Constellations contract, pending producer/consumer ACK (D003).
- Coordination: check PRs/issues for tags first; when blocked, stop, push, open a `[BLOCKED]` draft PR with a `Needs from @<handle>` block and continue only with a labeled test-only adapter (docs/COORDINATION.md, D004).
- Existing frontend stack stays. FastAPI + PostgreSQL/Supabase is a proposed server baseline (D002).
- Never cut: consent, safety triage, no-quote guard, Sky threshold, labels. Cut order if time runs out: P2 vision, Meetup, clue veto, voice (text always works).
- Standing human authorization allows safe squash PR integration after current-head validation; see AGENTS.md. Keep active role branches and synchronize them with main at checkpoints. No unattended merge bot is configured.

## Confirm
- **Organizer confirmation of the Muse model** (Spark, Wonder or Ember). `muse-spark-1.3` worked in 2 earlier live calls; Wonder and Ember are untested. Open.
- Latency plan: confirm parallel calls bring formation for 30 players under 60 s given 17 to 24 s per call. Top technical risk.
- Backend hosting, database/auth setup, public venue allowlist, demo Group, submission rules.
- Deadline used in planning: November 13, 2026 at 10:30 AM PST, supplied by the team, not independently verified. Feature freeze 04:30 AM.
- Acknowledgment from all five owners of D001 (product and ownership), D002 (server baseline), D003 (contract 1.0.0) and D004 (coordination protocol).

## Evidence ledger
| Capability | Status | Required evidence |
| --- | --- | --- |
| Facebook shell (`web/`) | Existing implementation; mock data only | Relevant UI checks rerun on main before any claim |
| Shared instructions and contract (`contracts/protocol.ts` 1.0.0) | Authored, pending ACK | Link and interface consistency review; D001 to D004 acknowledgments |
| Backend composition (`server/app/`) | Planned | Registry, health, owner registrations, database readiness |
| Muse adapter (`server/providers/`) | Planned | Constellations job schemas; re-verified live call; parallel-call timing |
| Privacy (`server/privacy/`) | Planned | Consent, answer access 403 test, prompt-builder test |
| Formation (`server/matching/`) | Planned | Meaning-based constellations; baseline vs Muse example |
| Orchestration (`server/orchestration/`) | Planned | Round lifecycle, idempotent confirm, retry tests |
| Voice capture (`server/voice/`) | Planned | Real transcription or text fallback on a phone |
| Join and Confession (F1, F2) | Planned | Phone join under 30 s; no answer before consent |
| Safety triage (F9) | Planned | Seeded distress answer never appears |
| Formation (F3) | Planned | 30 players under 60 s; every constellation validated |
| Search clues (F4) | Planned | No-quote fuzz test; red-team list of 30 answers |
| Found code and confirm (F5) | Planned | Mutual idempotent confirm; wrong code reveals nothing |
| Sky (F7) | Planned | Threshold test; numbers match server counts |
| Operator console (F8) | Planned | Model metadata and latency per call |
| Meetup (F6, P1) | Planned | 3+ approvals; venue allowlist test |
| Hosting | Planned | Host acceptance |
| User impact | Unknown | Actual observations, no invented metrics |

Each owner updates their own handoff while working. After merge, update this ledger with exact commit, command and outcome. Do not embed private data.
