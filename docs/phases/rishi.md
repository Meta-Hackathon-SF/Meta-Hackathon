# Rishi: phased build playbook

Read [your role](../roles/rishi.md), [shared instructions](../../AGENTS.md), `contracts/constellations.ts` and [phase coordination](README.md) first.
Times are PST on Nov 12-13, 2026 (P0 starts 16:00; feature freeze 04:30; deadline 10:30 AM, team-supplied and not independently verified). Inspect current code and your handoff before choosing a phase. These checklists describe required work, not completion evidence; check an item only with evidence.

## P0: Acknowledge and baseline (16:00-17:00)

- [ ] **D009 ACK (first item):** Reply to D009 (Constellations pivot, contract `2.0.0-proposed`) with your ACK or a concrete objection in docs/DECISIONS.md or the PR discussion. This is the first P0 item; nothing else is built before it.
- [ ] Build: Read contracts/constellations.ts and D009. Inspect merged `server/matching/` gates and eval harness; list what maps to society validation (3-5, once each, blocks) and what is dropped. Claim `web/src/features/constellations/matching/` and `induction/`.
- [ ] Exit evidence: ACK recorded; written reuse/adapt list in handoff; no code claims beyond what exists.
- [ ] Dependency / parallel fallback: Needs Adam's adapter interface; start from fixtures if not ready.
- [ ] Handoff: update `docs/handoffs/rishi.md` with exact interface, branch/commit, checks/results and the next consumer action; append `docs/updates/rishi.md`.

## P1: Module with synthetic fixtures (17:00-20:00)

- [ ] Build: Society validator and baseline in `server/matching/`; M3 theme discovery and M4 society formation prompts and schemas via Adam's adapter; keyword/embedding-cluster baseline; induction screen against fixture `Society`.
- [ ] Exit evidence: Fixture of 12 synthetic answers (labeled) yields validated societies; baseline vs Muse example recorded (actual output); validator tests pass for size, once-each, blocks, loose-match label.
- [ ] Dependency / parallel fallback: Test-only fake MusePort until Adam's live adapter; fixture results are not live evidence.
- [ ] Handoff: update `docs/handoffs/rishi.md` with exact interface, branch/commit, checks/results and the next consumer action; append `docs/updates/rishi.md`.

## P2: Integrated round on 3+ phones (20:00-23:00)

- [ ] Build: Run real M3/M4 on the live round from Kai's lock; measure 30-synthetic-player induction time with Kai's parallel fan-out; wire induction screen to `GET /rounds/:id/induction`.
- [ ] Exit evidence: 3+ real phones receive society name, sigil, passphrase half, members-to-find; live M3/M4 latency recorded.
- [ ] Dependency / parallel fallback: Needs Patrik's authorized answers and flags; Kai's lock; fall back to synthetic labeled players.
- [ ] Handoff: update `docs/handoffs/rishi.md` with exact interface, branch/commit, checks/results and the next consumer action; append `docs/updates/rishi.md`.

## P3: Sky, safety, blocks, operator complete (23:00-02:00)

- [ ] Build: Blocks respected end to end (rejected and re-solved), flagged answers excluded, deleted answer absent on re-run, loose-match label, theme labels through Patrik's guard.
- [ ] Exit evidence: All validation and privacy cases pass; any theme under threshold absent from Sky inputs.
- [ ] Dependency / parallel fallback: Needs Patrik's guard and block hooks.
- [ ] Handoff: update `docs/handoffs/rishi.md` with exact interface, branch/commit, checks/results and the next consumer action; append `docs/updates/rishi.md`.

## P4: P1 features and hardening (02:00-03:30)

- [ ] Build: Improve M4 quality on red-team and edge sets (few players, one-off answers); curate the live baseline-splits-Muse-joins pair for the demo.
- [ ] Exit evidence: Edge cases (fewer than 3 players, odd counts) place everyone; demo pair tested live; actual results recorded.
- [ ] Dependency / parallel fallback: Cut order: skip anything beyond this.
- [ ] Handoff: update `docs/handoffs/rishi.md` with exact interface, branch/commit, checks/results and the next consumer action; append `docs/updates/rishi.md`.

## P5: Freeze verification (03:30-04:30)

- [ ] Build: Freeze: rerun full suite, 30-player timing, block and flagged cases; no contract ambiguity.
- [ ] Exit evidence: Verified results in handoff; induction under 60 s or documented shortfall with cause.
- [ ] Dependency / parallel fallback: Preserve working path; no new ranking features.
- [ ] Handoff: update `docs/handoffs/rishi.md` with exact interface, branch/commit, checks/results and the next consumer action; append `docs/updates/rishi.md`.

## P6: UI, rehearsal, backup, submission (04:30-10:30)

- [ ] Build: Polish induction screen on mobile, loading/error states; support rehearsal, backup video, Devpost Q&A prep (baseline example, no unmeasured claims).
- [ ] Exit evidence: Stable induction segment in rehearsal.
- [ ] Dependency / parallel fallback: Critical fixes only after freeze.
- [ ] Handoff: update `docs/handoffs/rishi.md` with exact interface, branch/commit, checks/results and the next consumer action; append `docs/updates/rishi.md`.

## Resume-worthy evidence
Own the implementation and keep reproducible measurements for your system. Test counts alone are not impact. Report actual correctness, latency, reliability or observed usability results, with scope and limitations. Do not invent achieved improvement or user adoption.
