# Patrik: phased build playbook

Read [your role](../roles/patrik.md), [shared instructions](../../AGENTS.md), `contracts/constellations.ts` and [phase coordination](README.md) first.
Times are PST on Nov 12-13, 2026 (P0 starts 16:00; feature freeze 04:30; deadline 10:30 AM, team-supplied and not independently verified). Inspect current code and your handoff before choosing a phase. These checklists describe required work, not completion evidence; check an item only with evidence.

## P0: Acknowledge and baseline (16:00-17:00)

- [ ] **D009 ACK (first item):** Reply to D009 (Constellations pivot, contract `2.0.0-proposed`) with your ACK or a concrete objection in docs/DECISIONS.md or the PR discussion. This is the first P0 item; nothing else is built before it.
- [ ] Build: Read contracts/constellations.ts and D009. Inspect merged sessions, consent and projections; list ConsentV2 changes (3 toggles incl. 18+). Agree session mechanism with Kai.
- [ ] Exit evidence: ACK recorded; session and table order agreed; claim `constellations/privacy/`.
- [ ] Dependency / parallel fallback: Parallel with Kai.
- [ ] Handoff: update `docs/handoffs/patrik.md` with exact interface, branch/commit, checks/results and the next consumer action; append `docs/updates/patrik.md`.

## P1: Module with synthetic fixtures (17:00-20:00)

- [ ] Build: ConsentV2, private answer store with row-level checks, prompt builder, output guard (no-quote, sensitive terms), block store, delete and TTL logic; consent screen and support card on fixtures.
- [ ] Exit evidence: Unit tests: 403 on foreign answer reads, prompt payload only random IDs plus text, guard fuzz with known answers.
- [ ] Dependency / parallel fallback: Guard and prompt builder published to Adam, Rishi and Kai at end of P1.
- [ ] Handoff: update `docs/handoffs/patrik.md` with exact interface, branch/commit, checks/results and the next consumer action; append `docs/updates/patrik.md`.

## P2: Integrated round on 3+ phones (20:00-23:00)

- [ ] Build: M1 safety screen through Adam's adapter before matching; flagged answers excluded; authorized snapshot for Rishi; guard wired on all Muse outputs; real session with Kai.
- [ ] Exit evidence: Seeded distress answer never appears in societies, riddles or themes; live M1 latency recorded.
- [ ] Dependency / parallel fallback: Fallback: keyword distress screen labeled as fallback.
- [ ] Handoff: update `docs/handoffs/patrik.md` with exact interface, branch/commit, checks/results and the next consumer action; append `docs/updates/patrik.md`.

## P3: Sky, safety, blocks, operator complete (23:00-02:00)

- [ ] Build: Sky threshold (3 demo / 25 prod) on server aggregates; deletion endpoint, 14-day TTL job; block validation hook; red-team list of 30 answers; consent revoke during model call.
- [ ] Exit evidence: Theme with 2 members never renders; deleted answer absent from re-run; red-team results recorded.
- [ ] Dependency / parallel fallback: Needs Kai's aggregates.
- [ ] Handoff: update `docs/handoffs/patrik.md` with exact interface, branch/commit, checks/results and the next consumer action; append `docs/updates/patrik.md`.

## P4: P1 features and hardening (02:00-03:30)

- [ ] Build: P1: venue allowlist and 3-approval check for quests; veto never-sent guarantee; hardening.
- [ ] Exit evidence: Quest outside allowlist rejected; vetoed riddle never sent.
- [ ] Dependency / parallel fallback: Cut order: veto and ritual.
- [ ] Handoff: update `docs/handoffs/patrik.md` with exact interface, branch/commit, checks/results and the next consumer action; append `docs/updates/patrik.md`.

## P5: Freeze verification (03:30-04:30)

- [ ] Build: Freeze: rerun the entire privacy table; review Kai's schema and routes for authorization gaps.
- [ ] Exit evidence: Verified results in handoff; any unmet row stated honestly.
- [ ] Dependency / parallel fallback: Never cut: consent, triage, guard, threshold, labels.
- [ ] Handoff: update `docs/handoffs/patrik.md` with exact interface, branch/commit, checks/results and the next consumer action; append `docs/updates/patrik.md`.

## P6: UI, rehearsal, backup, submission (04:30-10:30)

- [ ] Build: Polish consent and support card; verify labels; rehearsal; Devpost privacy section from tested rules only.
- [ ] Exit evidence: Stable privacy segment.
- [ ] Dependency / parallel fallback: Critical fixes only.
- [ ] Handoff: update `docs/handoffs/patrik.md` with exact interface, branch/commit, checks/results and the next consumer action; append `docs/updates/patrik.md`.

## Resume-worthy evidence
Own the implementation and keep reproducible measurements for your system. Test counts alone are not impact. Report actual correctness, latency, reliability or observed usability results, with scope and limitations. Do not invent achieved improvement or user adoption.
