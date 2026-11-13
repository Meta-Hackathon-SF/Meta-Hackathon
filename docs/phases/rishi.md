# Rishi: phased build playbook

Read [your role](../roles/rishi.md), [shared instructions](../../AGENTS.md), `contracts/protocol.ts` (v1.0.0, pending D001/D003 ACK), [COORDINATION](../COORDINATION.md) and [phase coordination](README.md) first.
Times are PST on Nov 12-13, 2026 (P0 starts 16:00; feature freeze 04:30; deadline 10:30 AM, team-supplied and not independently verified). Inspect current code and your handoff before choosing a phase. These checklists describe required work, not completion evidence; check an item only with evidence.

## P0: Acknowledge and baseline (16:00-17:00)

- [ ] **Check open PRs/issues for tags (COORDINATION §1):** run the §1 commands, answer every request addressed to you (`ACK`, `CHANGE: ...` or `DELIVERED: ...`) before anything else.

- [ ] **D001/D003 ACK:** Reply to D001 (product and ownership) and D003 (contract `contracts/protocol.ts` v1.0.0), both pending ACK, with your ACK or a concrete objection in docs/DECISIONS.md or the PR discussion. Nothing else is built before it.
- [ ] Build: Read contracts/protocol.ts (v1.0.0) and D001/D003. List what the society validator must enforce (3-5, once each, blocks) and the baseline plan. Claim `web/src/features/constellations/matching/` and `induction/`.
- [ ] Exit evidence: ACK recorded; validation plan in handoff; no code claims beyond what exists.
- [ ] Dependency / fallback: Needs Adam's adapter interface; start from fixtures if not ready. If a dependency is missing at the phase boundary: stop, push, open/update a `[BLOCKED]` draft PR tagging @adamzhang06 (COORDINATION §2), and continue with a labeled test adapter.
- [ ] Handoff: update `docs/handoffs/rishi.md` with exact interface, branch/commit, checks/results and the next consumer action; append `docs/updates/rishi.md`.

## P1: Module with synthetic fixtures (17:00-20:00)

- [ ] Build: Read contracts/protocol.ts (v1.0.0) and D001/D003. List what the society validator must enforce (3-5, once each, blocks) and the baseline plan. Claim `web/src/features/constellations/matching/` and `induction/`.
- [ ] Exit evidence: Fixture of 12 synthetic answers (labeled) yields validated societies; baseline vs Muse example recorded (actual output); validator tests pass for size, once-each, blocks, loose-match label.
- [ ] Dependency / fallback: Test-only fake MusePort until Adam's live adapter; fixture results are not live evidence. If a dependency is missing at the phase boundary: stop, push, open/update a `[BLOCKED]` draft PR tagging @adamzhang06 (COORDINATION §2), and continue with a labeled test adapter.
- [ ] Handoff: update `docs/handoffs/rishi.md` with exact interface, branch/commit, checks/results and the next consumer action; append `docs/updates/rishi.md`.

## P2: Integrated round on 3+ phones (20:00-23:00)

- [ ] Build: Read contracts/protocol.ts (v1.0.0) and D001/D003. List what the society validator must enforce (3-5, once each, blocks) and the baseline plan. Claim `web/src/features/constellations/matching/` and `induction/`.
- [ ] Exit evidence: 3+ real phones receive society name, sigil, passphrase half, members-to-find; live M3/M4 latency recorded.
- [ ] Dependency / fallback: Needs Patrik's authorized answers and flags; Kai's lock; fall back to synthetic labeled players. If a dependency is missing at the phase boundary: stop, push, open/update a `[BLOCKED]` draft PR tagging @patrikliska13 and @beatopia (COORDINATION §2), and continue with a labeled test adapter.
- [ ] Handoff: update `docs/handoffs/rishi.md` with exact interface, branch/commit, checks/results and the next consumer action; append `docs/updates/rishi.md`.

## P3: Sky, safety, blocks, operator complete (23:00-02:00)

- [ ] Build: Read contracts/protocol.ts (v1.0.0) and D001/D003. List what the society validator must enforce (3-5, once each, blocks) and the baseline plan. Claim `web/src/features/constellations/matching/` and `induction/`.
- [ ] Exit evidence: All validation and privacy cases pass; any theme under threshold absent from Sky inputs.
- [ ] Dependency / fallback: Needs Patrik's guard and block hooks. If a dependency is missing at the phase boundary: stop, push, open/update a `[BLOCKED]` draft PR tagging @patrikliska13 (COORDINATION §2), and continue with a labeled test adapter.
- [ ] Handoff: update `docs/handoffs/rishi.md` with exact interface, branch/commit, checks/results and the next consumer action; append `docs/updates/rishi.md`.

## P4: P1 features and hardening (02:00-03:30)

- [ ] Build: Read contracts/protocol.ts (v1.0.0) and D001/D003. List what the society validator must enforce (3-5, once each, blocks) and the baseline plan. Claim `web/src/features/constellations/matching/` and `induction/`.
- [ ] Exit evidence: Edge cases (fewer than 3 players, odd counts) place everyone; demo pair tested live; actual results recorded.
- [ ] Dependency / fallback: Cut order: skip anything beyond this. If a dependency is missing at the phase boundary: stop, push, open/update a `[BLOCKED]` draft PR tagging @adamzhang06 (COORDINATION §2), and continue with a labeled test adapter.
- [ ] Handoff: update `docs/handoffs/rishi.md` with exact interface, branch/commit, checks/results and the next consumer action; append `docs/updates/rishi.md`.

## P5: Freeze verification (03:30-04:30)

- [ ] Build: Read contracts/protocol.ts (v1.0.0) and D001/D003. List what the society validator must enforce (3-5, once each, blocks) and the baseline plan. Claim `web/src/features/constellations/matching/` and `induction/`.
- [ ] Exit evidence: Verified results in handoff; induction under 60 s or documented shortfall with cause.
- [ ] Dependency / fallback: Preserve working path; no new ranking features. If a dependency is missing at the phase boundary: stop, push, open/update a `[BLOCKED]` draft PR tagging @patrikliska13 and @beatopia (COORDINATION §2), and continue with a labeled test adapter.
- [ ] Handoff: update `docs/handoffs/rishi.md` with exact interface, branch/commit, checks/results and the next consumer action; append `docs/updates/rishi.md`.

## P6: UI, rehearsal, backup, submission (04:30-10:30)

- [ ] Build: Read contracts/protocol.ts (v1.0.0) and D001/D003. List what the society validator must enforce (3-5, once each, blocks) and the baseline plan. Claim `web/src/features/constellations/matching/` and `induction/`.
- [ ] Exit evidence: Stable induction segment in rehearsal.
- [ ] Dependency / fallback: Critical fixes only after freeze. If a dependency is missing at the phase boundary: stop, push, open/update a `[BLOCKED]` draft PR tagging @willapat and @beatopia (COORDINATION §2), and continue with a labeled test adapter.
- [ ] Handoff: update `docs/handoffs/rishi.md` with exact interface, branch/commit, checks/results and the next consumer action; append `docs/updates/rishi.md`.

## Resume-worthy evidence
Own the implementation and keep reproducible measurements for your system. Test counts alone are not impact. Report actual correctness, latency, reliability or observed usability results, with scope and limitations. Do not invent achieved improvement or user adoption.
