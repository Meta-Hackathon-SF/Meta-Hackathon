# Kai: phased build playbook

Read [your role](../roles/kai.md), [shared instructions](../../AGENTS.md), `contracts/protocol.ts` (v1.0.0, pending D001/D003 ACK), [COORDINATION](../COORDINATION.md) and [phase coordination](README.md) first.
Times are PST on Nov 12-13, 2026 (P0 starts 16:00; feature freeze 04:30; deadline 10:30 AM, team-supplied and not independently verified). Inspect current code and your handoff before choosing a phase. These checklists describe required work, not completion evidence; check an item only with evidence.

## P0: Acknowledge and baseline (16:00-17:00)

- [ ] **Check open PRs/issues for tags (COORDINATION §1):** run the §1 commands, answer every request addressed to you (`ACK`, `CHANGE: ...` or `DELIVERED: ...`) before anything else.

- [ ] **D001/D003 ACK:** Reply to D001 (product and ownership) and D003 (contract `contracts/protocol.ts` v1.0.0), both pending ACK, with your ACK or a concrete objection in docs/DECISIONS.md or the PR discussion. Nothing else is built before it.
- [ ] Build: Read contracts/protocol.ts (v1.0.0), D001/D002/D003. Plan the app registry, `/api/v1` routes and round state machine. Agree session/tables with Patrik. Claim `constellations/operator/`, `sky/`.
- [ ] Exit evidence: ACK recorded; route list and table order published.
- [ ] Dependency / fallback: Parallel with Patrik. If a dependency is missing at the phase boundary: stop, push, open/update a `[BLOCKED]` draft PR tagging @patrikliska13 (COORDINATION §2), and continue with a labeled test adapter.
- [ ] Handoff: update `docs/handoffs/kai.md` with exact interface, branch/commit, checks/results and the next consumer action; append `docs/updates/kai.md`.

## P1: Module with synthetic fixtures (17:00-20:00)

- [ ] Build: Read contracts/protocol.ts (v1.0.0), D001/D002/D003. Plan the app registry, `/api/v1` routes and round state machine. Agree session/tables with Patrik. Claim `constellations/operator/`, `sky/`.
- [ ] Exit evidence: State transitions and duplicate-confirm tests pass; console works against fixture round.
- [ ] Dependency / fallback: Test adapters for ports; provider calls outside DB transactions. If a dependency is missing at the phase boundary: stop, push, open/update a `[BLOCKED]` draft PR tagging @patrikliska13 and @adamzhang06 (COORDINATION §2), and continue with a labeled test adapter.
- [ ] Handoff: update `docs/handoffs/kai.md` with exact interface, branch/commit, checks/results and the next consumer action; append `docs/updates/kai.md`.

## P2: Integrated round on 3+ phones (20:00-23:00)

- [ ] Build: Read contracts/protocol.ts (v1.0.0), D001/D002/D003. Plan the app registry, `/api/v1` routes and round state machine. Agree session/tables with Patrik. Claim `constellations/operator/`, `sky/`.
- [ ] Exit evidence: 3+ phones: join, confess, induct, riddles, confirm; constellation light-up; induction timing recorded against 60 s.
- [ ] Dependency / fallback: Needs Rishi, Adam, Patrik live ports; precompute while round open; top risk if over 60 s. If a dependency is missing at the phase boundary: stop, push, open/update a `[BLOCKED]` draft PR tagging @rishibagri and @adamzhang06 and @patrikliska13 (COORDINATION §2), and continue with a labeled test adapter.
- [ ] Handoff: update `docs/handoffs/kai.md` with exact interface, branch/commit, checks/results and the next consumer action; append `docs/updates/kai.md`.

## P3: Sky, safety, blocks, operator complete (23:00-02:00)

- [ ] Build: Read contracts/protocol.ts (v1.0.0), D001/D002/D003. Plan the app registry, `/api/v1` routes and round state machine. Agree session/tables with Patrik. Claim `constellations/operator/`, `sky/`.
- [ ] Exit evidence: Sky shows guessed vs actual with only above-threshold themes; wrong code reveals nothing; reset leaves unrelated sessions.
- [ ] Dependency / fallback: Needs Patrik's threshold and Adam's M8. If a dependency is missing at the phase boundary: stop, push, open/update a `[BLOCKED]` draft PR tagging @patrikliska13 and @adamzhang06 (COORDINATION §2), and continue with a labeled test adapter.
- [ ] Handoff: update `docs/handoffs/kai.md` with exact interface, branch/commit, checks/results and the next consumer action; append `docs/updates/kai.md`.

## P4: P1 features and hardening (02:00-03:30)

- [ ] Build: Read contracts/protocol.ts (v1.0.0), D001/D002/D003. Plan the app registry, `/api/v1` routes and round state machine. Agree session/tables with Patrik. Claim `constellations/operator/`, `sky/`.
- [ ] Exit evidence: Ritual cannot be created with fewer than 3 approvals; retry creates one Find.
- [ ] Dependency / fallback: Cut ritual first. If a dependency is missing at the phase boundary: stop, push, open/update a `[BLOCKED]` draft PR tagging @adamzhang06 and @patrikliska13 (COORDINATION §2), and continue with a labeled test adapter.
- [ ] Handoff: update `docs/handoffs/kai.md` with exact interface, branch/commit, checks/results and the next consumer action; append `docs/updates/kai.md`.

## P5: Freeze verification (03:30-04:30)

- [ ] Build: Read contracts/protocol.ts (v1.0.0), D001/D002/D003. Plan the app registry, `/api/v1` routes and round state machine. Agree session/tables with Patrik. Claim `constellations/operator/`, `sky/`.
- [ ] Exit evidence: Verified results in handoff; deployed status distinct from local.
- [ ] Dependency / fallback: Preserve failure state; no fake success. If a dependency is missing at the phase boundary: stop, push, open/update a `[BLOCKED]` draft PR tagging @rishibagri and @adamzhang06 and @patrikliska13 (COORDINATION §2), and continue with a labeled test adapter.
- [ ] Handoff: update `docs/handoffs/kai.md` with exact interface, branch/commit, checks/results and the next consumer action; append `docs/updates/kai.md`.

## P6: UI, rehearsal, backup, submission (04:30-10:30)

- [ ] Build: Read contracts/protocol.ts (v1.0.0), D001/D002/D003. Plan the app registry, `/api/v1` routes and round state machine. Agree session/tables with Patrik. Claim `constellations/operator/`, `sky/`.
- [ ] Exit evidence: Stable operator and Sky segments; links verified.
- [ ] Dependency / fallback: Critical fixes only. If a dependency is missing at the phase boundary: stop, push, open/update a `[BLOCKED]` draft PR tagging @willapat (COORDINATION §2), and continue with a labeled test adapter.
- [ ] Handoff: update `docs/handoffs/kai.md` with exact interface, branch/commit, checks/results and the next consumer action; append `docs/updates/kai.md`.

## Resume-worthy evidence
Own the implementation and keep reproducible measurements for your system. Test counts alone are not impact. Report actual correctness, latency, reliability or observed usability results, with scope and limitations. Do not invent achieved improvement or user adoption.
