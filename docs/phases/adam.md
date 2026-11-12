# Adam: phased build playbook

Read [your role](../roles/adam.md), [shared instructions](../../AGENTS.md), `contracts/constellations.ts` and [phase coordination](README.md) first.
Times are PST on Nov 12-13, 2026 (P0 starts 16:00; feature freeze 04:30; deadline 10:30 AM, team-supplied and not independently verified). Inspect current code and your handoff before choosing a phase. These checklists describe required work, not completion evidence; check an item only with evidence.

## P0: Acknowledge and baseline (16:00-17:00)

- [ ] **D009 ACK (first item):** Reply to D009 (Constellations pivot, contract `2.0.0-proposed`) with your ACK or a concrete objection in docs/DECISIONS.md or the PR discussion. This is the first P0 item; nothing else is built before it.
- [ ] Build: Read contracts/constellations.ts and D009. Reconfirm the live `muse-spark-1.3` adapter still works with one call; list task names to add (safety_screen ... sky_narration). Claim `constellations/hunt/`.
- [ ] Exit evidence: ACK recorded; one live call echo and latency recorded (no secrets).
- [ ] Dependency / parallel fallback: If provider fails, report; fixtures continue.
- [ ] Handoff: update `docs/handoffs/adam.md` with exact interface, branch/commit, checks/results and the next consumer action; append `docs/updates/adam.md`.

## P1: Module with synthetic fixtures (17:00-20:00)

- [ ] Build: Keeper system prompt, strict JSON schemas, one retry then labeled fallback; M5 identity, M6 riddles, M2 clarify as callable jobs; test fake MusePort; Hunt view against fixture riddles.
- [ ] Exit evidence: Fixture societies yield identity and 3-level riddles passing the no-quote and sensitive checks; fake port published to teammates.
- [ ] Dependency / parallel fallback: Patrik's guard may be a stub; swap for the real one at P2.
- [ ] Handoff: update `docs/handoffs/adam.md` with exact interface, branch/commit, checks/results and the next consumer action; append `docs/updates/adam.md`.

## P2: Integrated round on 3+ phones (20:00-23:00)

- [ ] Build: Live M5 per society and M6 per target/seeker in parallel from Kai's fan-out; M2 clarify endpoint for Will; Hunt view wired to `GET /rounds/:id/riddles` with released levels only.
- [ ] Exit evidence: Live riddles for a 3+ phone round; per-call latency and model recorded; no riddle contains 5+ answer words.
- [ ] Dependency / parallel fallback: Needs Rishi's societies and Patrik's findable details.
- [ ] Handoff: update `docs/handoffs/adam.md` with exact interface, branch/commit, checks/results and the next consumer action; append `docs/updates/adam.md`.

## P3: Sky, safety, blocks, operator complete (23:00-02:00)

- [ ] Build: M8 Sky narration validated against server counts; M6 self-check field; red-team list of 30 answers through the guard; injection test.
- [ ] Exit evidence: Every M8 number matches server counts; red-team results recorded.
- [ ] Dependency / parallel fallback: Needs Kai's Sky counts.
- [ ] Handoff: update `docs/handoffs/adam.md` with exact interface, branch/commit, checks/results and the next consumer action; append `docs/updates/adam.md`.

## P4: P1 features and hardening (02:00-03:30)

- [ ] Build: M7 ritual quest (P1): venue from approved public list, under budget; riddle veto support (P1) if green.
- [ ] Exit evidence: Out-of-allowlist venue rejected; nothing created without 3 approvals (with Kai).
- [ ] Dependency / parallel fallback: Cut first if P3 not fully verified.
- [ ] Handoff: update `docs/handoffs/adam.md` with exact interface, branch/commit, checks/results and the next consumer action; append `docs/updates/adam.md`.

## P5: Freeze verification (03:30-04:30)

- [ ] Build: Freeze: failure cases (timeout, malformed JSON, replay labels) pass; latency numbers recorded.
- [ ] Exit evidence: Verified results in handoff; live vs replay labeling confirmed.
- [ ] Dependency / parallel fallback: Preserve failure state; no fake success.
- [ ] Handoff: update `docs/handoffs/adam.md` with exact interface, branch/commit, checks/results and the next consumer action; append `docs/updates/adam.md`.

## P6: UI, rehearsal, backup, submission (04:30-10:30)

- [ ] Build: Hunt view polish, rehearsal of riddle reveals (Demo timing label), backup recording support, Devpost AI-integration section from evidence.
- [ ] Exit evidence: Stable Hunt segment.
- [ ] Dependency / parallel fallback: Critical fixes only.
- [ ] Handoff: update `docs/handoffs/adam.md` with exact interface, branch/commit, checks/results and the next consumer action; append `docs/updates/adam.md`.

## Resume-worthy evidence
Own the implementation and keep reproducible measurements for your system. Test counts alone are not impact. Report actual correctness, latency, reliability or observed usability results, with scope and limitations. Do not invent achieved improvement or user adoption.
