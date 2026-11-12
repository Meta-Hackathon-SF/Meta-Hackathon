# Will: phased build playbook

Read [your role](../roles/will.md), [shared instructions](../../AGENTS.md), `contracts/constellations.ts` and [phase coordination](README.md) first.
Times are PST on Nov 12-13, 2026 (P0 starts 16:00; feature freeze 04:30; deadline 10:30 AM, team-supplied and not independently verified). Inspect current code and your handoff before choosing a phase. These checklists describe required work, not completion evidence; check an item only with evidence.

## P0: Acknowledge and baseline (16:00-17:00)

- [ ] **D009 ACK (first item):** Reply to D009 (Constellations pivot, contract `2.0.0-proposed`) with your ACK or a concrete objection in docs/DECISIONS.md or the PR discussion. This is the first P0 item; nothing else is built before it.
- [ ] Build: Read contracts/constellations.ts and D009. Inspect merged shell, onboarding and `server/voice/`; plan the migration of `group-quests/shell` into `constellations/shell`. Claim shared web routing files.
- [ ] Exit evidence: ACK recorded; migration plan and component slot contract published to all owners.
- [ ] Dependency / parallel fallback: Publish slots before others build UI.
- [ ] Handoff: update `docs/handoffs/will.md` with exact interface, branch/commit, checks/results and the next consumer action; append `docs/updates/will.md`.

## P1: Module with synthetic fixtures (17:00-20:00)

- [ ] Build: Migrate shell, add Constellations tab with slots; join and explainer screens; Confession (text first, voice via merged recorder); guess slider; Muse chip component; fixture adapter for all screens.
- [ ] Exit evidence: Join to guess flow runs on fixtures in a phone-width browser; chip renders; mock Facebook pages intact.
- [ ] Dependency / parallel fallback: Consent slot may be a stub until Patrik's screen lands.
- [ ] Handoff: update `docs/handoffs/will.md` with exact interface, branch/commit, checks/results and the next consumer action; append `docs/updates/will.md`.

## P2: Integrated round on 3+ phones (20:00-23:00)

- [ ] Build: Wire to real API: session, join, consent, answers, guess, follow-up (M2), stream client; compose Rishi, Adam, Kai, Patrik components; QR deep link.
- [ ] Exit evidence: 3+ real phones join and confess; join under 30 s timed; no answer collected before consent.
- [ ] Dependency / parallel fallback: Needs Kai routes and Patrik session; keep fixture fallback.
- [ ] Handoff: update `docs/handoffs/will.md` with exact interface, branch/commit, checks/results and the next consumer action; append `docs/updates/will.md`.

## P3: Sky, safety, blocks, operator complete (23:00-02:00)

- [ ] Build: Edit/delete before lock, ROUND_LOCKED handling, voice failure fallback, mic denial, stale/cancelled requests, support card display on flag, all truth labels.
- [ ] Exit evidence: Listed cases pass in browser checks; flagged answer shows private card.
- [ ] Dependency / parallel fallback: Needs Patrik's flag signal.
- [ ] Handoff: update `docs/handoffs/will.md` with exact interface, branch/commit, checks/results and the next consumer action; append `docs/updates/will.md`.

## P4: P1 features and hardening (02:00-03:30)

- [ ] Build: P1: riddle veto screen and ritual vote UI if P3 is fully verified; hardening of routing and reconnect.
- [ ] Exit evidence: Veto path works or is explicitly cut.
- [ ] Dependency / parallel fallback: Cut order: veto, ritual, voice.
- [ ] Handoff: update `docs/handoffs/will.md` with exact interface, branch/commit, checks/results and the next consumer action; append `docs/updates/will.md`.

## P5: Freeze verification (03:30-04:30)

- [ ] Build: Freeze: full journey on phones, keyboard and mobile overflow checks, QR URL stable and shared.
- [ ] Exit evidence: Verified results in handoff; deploy status stated separately from local status.
- [ ] Dependency / parallel fallback: Preserve text path.
- [ ] Handoff: update `docs/handoffs/will.md` with exact interface, branch/commit, checks/results and the next consumer action; append `docs/updates/will.md`.

## P6: UI, rehearsal, backup, submission (04:30-10:30)

- [ ] Build: UI polish across the whole app (mobile, error states), five-minute rehearsal, backup recording, Devpost media.
- [ ] Exit evidence: Stable end-to-end demo.
- [ ] Dependency / parallel fallback: Critical fixes only.
- [ ] Handoff: update `docs/handoffs/will.md` with exact interface, branch/commit, checks/results and the next consumer action; append `docs/updates/will.md`.

## Resume-worthy evidence
Own the implementation and keep reproducible measurements for your system. Test counts alone are not impact. Report actual correctness, latency, reliability or observed usability results, with scope and limitations. Do not invent achieved improvement or user adoption.
