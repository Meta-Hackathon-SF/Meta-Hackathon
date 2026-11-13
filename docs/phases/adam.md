# Adam: phased build playbook

Read [your role](../roles/adam.md), [shared instructions](../../AGENTS.md), `contracts/protocol.ts` (v1.0.0, pending D001/D003 ACK), [COORDINATION](../COORDINATION.md) and [phase coordination](README.md) first.
Times are PST on Nov 12-13, 2026 (P0 starts 16:00; feature freeze 04:30; deadline 10:30 AM, team-supplied and not independently verified). Inspect current code and your handoff before choosing a phase. These checklists describe required work, not completion evidence; check an item only with evidence.

## P0: Acknowledge and baseline (16:00-17:00)

- [ ] **Check open PRs/issues for tags (COORDINATION §1):** run the §1 commands, answer every request addressed to you (`ACK`, `CHANGE: ...` or `DELIVERED: ...`) before anything else.

- [ ] **D001/D003 ACK:** Reply to D001 (product and ownership) and D003 (contract `contracts/protocol.ts` v1.0.0), both pending ACK, with your ACK or a concrete objection in docs/DECISIONS.md or the PR discussion. Nothing else is built before it.
- [ ] Build: Read contracts/protocol.ts (v1.0.0) and D001/D003. Make one `muse-spark-1.3` call to reconfirm the model/endpoint; list task names to add (safety_screen ... sky_narration). Claim `constellations/search/`.
- [ ] Exit evidence: ACK recorded; one live call echo and latency recorded (no secrets).
- [ ] Dependency / fallback: If provider fails, report; fixtures continue. If a dependency is missing at the phase boundary: stop, push, open/update a `[BLOCKED]` draft PR tagging the owning teammate if the gap is an interface they own (provider or credential problems go to your human instead) (COORDINATION §2), and continue with a labeled test adapter.
- [ ] Handoff: update `docs/handoffs/adam.md` with exact interface, branch/commit, checks/results and the next consumer action; append `docs/updates/adam.md`.

## P1: Module with synthetic fixtures (17:00-20:00)

- [ ] Build: Read contracts/protocol.ts (v1.0.0) and D001/D003. Make one `muse-spark-1.3` call to reconfirm the model/endpoint; list task names to add (safety_screen ... sky_narration). Claim `constellations/search/`.
- [ ] Exit evidence: Fixture constellations yield identity and 3-level clues passing the no-quote and sensitive checks; fake port published to teammates.
- [ ] Dependency / fallback: Patrik's guard may be a stub; swap for the real one at P2. If a dependency is missing at the phase boundary: stop, push, open/update a `[BLOCKED]` draft PR tagging @patrikliska13 (COORDINATION §2), and continue with a labeled test adapter.
- [ ] Handoff: update `docs/handoffs/adam.md` with exact interface, branch/commit, checks/results and the next consumer action; append `docs/updates/adam.md`.

## P2: Integrated round on 3+ phones (20:00-23:00)

- [ ] Build: Read contracts/protocol.ts (v1.0.0) and D001/D003. Make one `muse-spark-1.3` call to reconfirm the model/endpoint; list task names to add (safety_screen ... sky_narration). Claim `constellations/search/`.
- [ ] Exit evidence: Live clues for a 3+ phone round; per-call latency and model recorded; no clue contains 5+ answer words.
- [ ] Dependency / fallback: Needs Rishi's constellations and Patrik's findable details. If a dependency is missing at the phase boundary: stop, push, open/update a `[BLOCKED]` draft PR tagging @rishibagri and @patrikliska13 (COORDINATION §2), and continue with a labeled test adapter.
- [ ] Handoff: update `docs/handoffs/adam.md` with exact interface, branch/commit, checks/results and the next consumer action; append `docs/updates/adam.md`.

## P3: Sky, safety, blocks, operator complete (23:00-02:00)

- [ ] Build: Read contracts/protocol.ts (v1.0.0) and D001/D003. Make one `muse-spark-1.3` call to reconfirm the model/endpoint; list task names to add (safety_screen ... sky_narration). Claim `constellations/search/`.
- [ ] Exit evidence: Every M8 number matches server counts; red-team results recorded.
- [ ] Dependency / fallback: Needs Kai's Sky counts. If a dependency is missing at the phase boundary: stop, push, open/update a `[BLOCKED]` draft PR tagging @beatopia (COORDINATION §2), and continue with a labeled test adapter.
- [ ] Handoff: update `docs/handoffs/adam.md` with exact interface, branch/commit, checks/results and the next consumer action; append `docs/updates/adam.md`.

## P4: P1 features and hardening (02:00-03:30)

- [ ] Build: Read contracts/protocol.ts (v1.0.0) and D001/D003. Make one `muse-spark-1.3` call to reconfirm the model/endpoint; list task names to add (safety_screen ... sky_narration). Claim `constellations/search/`.
- [ ] Exit evidence: Out-of-allowlist venue rejected; nothing created without 3 approvals (with Kai).
- [ ] Dependency / fallback: Cut first if P3 not fully verified. If a dependency is missing at the phase boundary: stop, push, open/update a `[BLOCKED]` draft PR tagging @patrikliska13 and @beatopia (COORDINATION §2), and continue with a labeled test adapter.
- [ ] Handoff: update `docs/handoffs/adam.md` with exact interface, branch/commit, checks/results and the next consumer action; append `docs/updates/adam.md`.

## P5: Freeze verification (03:30-04:30)

- [ ] Build: Read contracts/protocol.ts (v1.0.0) and D001/D003. Make one `muse-spark-1.3` call to reconfirm the model/endpoint; list task names to add (safety_screen ... sky_narration). Claim `constellations/search/`.
- [ ] Exit evidence: Verified results in handoff; live vs replay labeling confirmed.
- [ ] Dependency / fallback: Preserve failure state; no fake success. If a dependency is missing at the phase boundary: stop, push, open/update a `[BLOCKED]` draft PR tagging @beatopia and @patrikliska13 (COORDINATION §2), and continue with a labeled test adapter.
- [ ] Handoff: update `docs/handoffs/adam.md` with exact interface, branch/commit, checks/results and the next consumer action; append `docs/updates/adam.md`.

## P6: UI, rehearsal, backup, submission (04:30-10:30)

- [ ] Build: Read contracts/protocol.ts (v1.0.0) and D001/D003. Make one `muse-spark-1.3` call to reconfirm the model/endpoint; list task names to add (safety_screen ... sky_narration). Claim `constellations/search/`.
- [ ] Exit evidence: Stable Search segment.
- [ ] Dependency / fallback: Critical fixes only. If a dependency is missing at the phase boundary: stop, push, open/update a `[BLOCKED]` draft PR tagging @willapat and @beatopia (COORDINATION §2), and continue with a labeled test adapter.
- [ ] Handoff: update `docs/handoffs/adam.md` with exact interface, branch/commit, checks/results and the next consumer action; append `docs/updates/adam.md`.

## Resume-worthy evidence
Own the implementation and keep reproducible measurements for your system. Test counts alone are not impact. Report actual correctness, latency, reliability or observed usability results, with scope and limitations. Do not invent achieved improvement or user adoption.
