# Patrik: phased build playbook

Read [your role](../roles/patrik.md), [shared instructions](../../AGENTS.md), `contracts/protocol.ts` (v1.0.0, pending D001/D003 ACK), [COORDINATION](../COORDINATION.md) and [phase coordination](README.md) first.
Times are PST on Nov 12-13, 2026 (P0 starts 16:00; feature freeze 04:30; deadline 10:30 AM, team-supplied and not independently verified). Inspect current code and your handoff before choosing a phase. These checklists describe required work, not completion evidence; check an item only with evidence.

## P0: Acknowledge and baseline (16:00-17:00)

- [ ] **Check open PRs/issues for tags (COORDINATION §1):** run the §1 commands, answer every request addressed to you (`ACK`, `CHANGE: ...` or `DELIVERED: ...`) before anything else.

- [ ] **D001/D003 ACK:** Reply to D001 (product and ownership) and D003 (contract `contracts/protocol.ts` v1.0.0), both pending ACK, with your ACK or a concrete objection in docs/DECISIONS.md or the PR discussion. Nothing else is built before it.
- [ ] Build: Read contracts/protocol.ts (v1.0.0) and D001/D003. Plan ConsentV2 (3 toggles incl. 18+), sessions and projections. Agree session mechanism with Kai.
- [ ] Exit evidence: ACK recorded; session and table order agreed; claim `constellations/privacy/`.
- [ ] Dependency / fallback: Parallel with Kai. If a dependency is missing at the phase boundary: stop, push, open/update a `[BLOCKED]` draft PR tagging @beatopia (COORDINATION §2), and continue with a labeled test adapter.
- [ ] Handoff: update `docs/handoffs/patrik.md` with exact interface, branch/commit, checks/results and the next consumer action; append `docs/updates/patrik.md`.

## P1: Module with synthetic fixtures (17:00-20:00)

- [ ] Build: Read contracts/protocol.ts (v1.0.0) and D001/D003. Plan ConsentV2 (3 toggles incl. 18+), sessions and projections. Agree session mechanism with Kai.
- [ ] Exit evidence: Unit tests: 403 on foreign answer reads, prompt payload only random IDs plus text, guard fuzz with known answers.
- [ ] Dependency / fallback: Guard and prompt builder published to Adam, Rishi and Kai at end of P1. If a dependency is missing at the phase boundary: stop, push, open/update a `[BLOCKED]` draft PR tagging @beatopia (COORDINATION §2), and continue with a labeled test adapter.
- [ ] Handoff: update `docs/handoffs/patrik.md` with exact interface, branch/commit, checks/results and the next consumer action; append `docs/updates/patrik.md`.

## P2: Integrated round on 3+ phones (20:00-23:00)

- [ ] Build: Read contracts/protocol.ts (v1.0.0) and D001/D003. Plan ConsentV2 (3 toggles incl. 18+), sessions and projections. Agree session mechanism with Kai.
- [ ] Exit evidence: Seeded distress answer never appears in societies, riddles or themes; live M1 latency recorded.
- [ ] Dependency / fallback: Fallback: keyword distress screen labeled as fallback. If a dependency is missing at the phase boundary: stop, push, open/update a `[BLOCKED]` draft PR tagging @adamzhang06 and @beatopia (COORDINATION §2), and continue with a labeled test adapter.
- [ ] Handoff: update `docs/handoffs/patrik.md` with exact interface, branch/commit, checks/results and the next consumer action; append `docs/updates/patrik.md`.

## P3: Sky, safety, blocks, operator complete (23:00-02:00)

- [ ] Build: Read contracts/protocol.ts (v1.0.0) and D001/D003. Plan ConsentV2 (3 toggles incl. 18+), sessions and projections. Agree session mechanism with Kai.
- [ ] Exit evidence: Theme with 2 members never renders; deleted answer absent from re-run; red-team results recorded.
- [ ] Dependency / fallback: Needs Kai's aggregates. If a dependency is missing at the phase boundary: stop, push, open/update a `[BLOCKED]` draft PR tagging @beatopia (COORDINATION §2), and continue with a labeled test adapter.
- [ ] Handoff: update `docs/handoffs/patrik.md` with exact interface, branch/commit, checks/results and the next consumer action; append `docs/updates/patrik.md`.

## P4: P1 features and hardening (02:00-03:30)

- [ ] Build: Read contracts/protocol.ts (v1.0.0) and D001/D003. Plan ConsentV2 (3 toggles incl. 18+), sessions and projections. Agree session mechanism with Kai.
- [ ] Exit evidence: Quest outside allowlist rejected; vetoed riddle never sent.
- [ ] Dependency / fallback: Cut order: veto and ritual. If a dependency is missing at the phase boundary: stop, push, open/update a `[BLOCKED]` draft PR tagging @adamzhang06 and @beatopia (COORDINATION §2), and continue with a labeled test adapter.
- [ ] Handoff: update `docs/handoffs/patrik.md` with exact interface, branch/commit, checks/results and the next consumer action; append `docs/updates/patrik.md`.

## P5: Freeze verification (03:30-04:30)

- [ ] Build: Read contracts/protocol.ts (v1.0.0) and D001/D003. Plan ConsentV2 (3 toggles incl. 18+), sessions and projections. Agree session mechanism with Kai.
- [ ] Exit evidence: Verified results in handoff; any unmet row stated honestly.
- [ ] Dependency / fallback: Never cut: consent, triage, guard, threshold, labels. If a dependency is missing at the phase boundary: stop, push, open/update a `[BLOCKED]` draft PR tagging @beatopia (COORDINATION §2), and continue with a labeled test adapter.
- [ ] Handoff: update `docs/handoffs/patrik.md` with exact interface, branch/commit, checks/results and the next consumer action; append `docs/updates/patrik.md`.

## P6: UI, rehearsal, backup, submission (04:30-10:30)

- [ ] Build: Read contracts/protocol.ts (v1.0.0) and D001/D003. Plan ConsentV2 (3 toggles incl. 18+), sessions and projections. Agree session mechanism with Kai.
- [ ] Exit evidence: Stable privacy segment.
- [ ] Dependency / fallback: Critical fixes only. If a dependency is missing at the phase boundary: stop, push, open/update a `[BLOCKED]` draft PR tagging @willapat (COORDINATION §2), and continue with a labeled test adapter.
- [ ] Handoff: update `docs/handoffs/patrik.md` with exact interface, branch/commit, checks/results and the next consumer action; append `docs/updates/patrik.md`.

## Resume-worthy evidence
Own the implementation and keep reproducible measurements for your system. Test counts alone are not impact. Report actual correctness, latency, reliability or observed usability results, with scope and limitations. Do not invent achieved improvement or user adoption.
