# Kai: phased build playbook

Read [your role](../roles/kai.md), [shared instructions](../../AGENTS.md), `contracts/constellations.ts` and [phase coordination](README.md) first.
Times are PST on Nov 12-13, 2026 (P0 starts 16:00; feature freeze 04:30; deadline 10:30 AM, team-supplied and not independently verified). Inspect current code and your handoff before choosing a phase. These checklists describe required work, not completion evidence; check an item only with evidence.

## P0: Acknowledge and baseline (16:00-17:00)

- [ ] **D009 ACK (first item):** Reply to D009 (Constellations pivot, contract `2.0.0-proposed`) with your ACK or a concrete objection in docs/DECISIONS.md or the PR discussion. This is the first P0 item; nothing else is built before it.
- [ ] Build: Read contracts/constellations.ts and D009. Inspect merged registry and orchestration workflow; plan `/api/v1` routes and round state machine. Agree session/tables with Patrik. Claim `constellations/operator/`, `sky/`.
- [ ] Exit evidence: ACK recorded; route list and table order published.
- [ ] Dependency / parallel fallback: Parallel with Patrik.
- [ ] Handoff: update `docs/handoffs/kai.md` with exact interface, branch/commit, checks/results and the next consumer action; append `docs/updates/kai.md`.

## P1: Module with synthetic fixtures (17:00-20:00)

- [ ] Build: Round state machine and persistence, operator routes (create, lock, advance-level, sky, reset), SSE stream, idempotent Find with found codes, synthetic top-up loader; operator console and Sky view on fixtures.
- [ ] Exit evidence: State transitions and duplicate-confirm tests pass; console works against fixture round.
- [ ] Dependency / parallel fallback: Test adapters for ports; provider calls outside DB transactions.
- [ ] Handoff: update `docs/handoffs/kai.md` with exact interface, branch/commit, checks/results and the next consumer action; append `docs/updates/kai.md`.

## P2: Integrated round on 3+ phones (20:00-23:00)

- [ ] Build: Lock pipeline: parallel M1, then M3/M4, M5 per society, M6 fan-out with guard on every output; confirm routes; stream to phones; measure 30-player induction time.
- [ ] Exit evidence: 3+ phones: join, confess, induct, riddles, confirm; constellation light-up; induction timing recorded against 60 s.
- [ ] Dependency / parallel fallback: Needs Rishi, Adam, Patrik live ports; precompute while round open; top risk if over 60 s.
- [ ] Handoff: update `docs/handoffs/kai.md` with exact interface, branch/commit, checks/results and the next consumer action; append `docs/updates/kai.md`.

## P3: Sky, safety, blocks, operator complete (23:00-02:00)

- [ ] Build: Sky aggregates (guessed vs actual, societies, finds, threshold), M8 via Adam, projector view, per-call model metadata and latency in console, reset isolation, wrong-code generic response.
- [ ] Exit evidence: Sky shows guessed vs actual with only above-threshold themes; wrong code reveals nothing; reset leaves unrelated sessions.
- [ ] Dependency / parallel fallback: Needs Patrik's threshold and Adam's M8.
- [ ] Handoff: update `docs/handoffs/kai.md` with exact interface, branch/commit, checks/results and the next consumer action; append `docs/updates/kai.md`.

## P4: P1 features and hardening (02:00-03:30)

- [ ] Build: P1: ritual event and chat (3+ approvals), demo timing for level unlocks (20 s or operator tap), crash/retry/reconnect hardening.
- [ ] Exit evidence: Ritual cannot be created with fewer than 3 approvals; retry creates one Find.
- [ ] Dependency / parallel fallback: Cut ritual first.
- [ ] Handoff: update `docs/handoffs/kai.md` with exact interface, branch/commit, checks/results and the next consumer action; append `docs/updates/kai.md`.

## P5: Freeze verification (03:30-04:30)

- [ ] Build: Freeze: crash-after-commit, duplicate delivery, stale results, reconnect; startup, deploy and reset instructions.
- [ ] Exit evidence: Verified results in handoff; deployed status distinct from local.
- [ ] Dependency / parallel fallback: Preserve failure state; no fake success.
- [ ] Handoff: update `docs/handoffs/kai.md` with exact interface, branch/commit, checks/results and the next consumer action; append `docs/updates/kai.md`.

## P6: UI, rehearsal, backup, submission (04:30-10:30)

- [ ] Build: Sky and operator polish, live health and reset checks, rehearsal, backup video, deployment links verified.
- [ ] Exit evidence: Stable operator and Sky segments; links verified.
- [ ] Dependency / parallel fallback: Critical fixes only.
- [ ] Handoff: update `docs/handoffs/kai.md` with exact interface, branch/commit, checks/results and the next consumer action; append `docs/updates/kai.md`.

## Resume-worthy evidence
Own the implementation and keep reproducible measurements for your system. Test counts alone are not impact. Report actual correctness, latency, reliability or observed usability results, with scope and limitations. Do not invent achieved improvement or user adoption.
