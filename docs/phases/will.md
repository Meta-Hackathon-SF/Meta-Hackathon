# Will: phased build playbook

Read [your role](../roles/will.md), [shared instructions](../../AGENTS.md), and [phase coordination](README.md) first.
Hours are elapsed from the team's agreed start; check [the shared schedule](../PLAN.md) for clock times. Inspect current code and your handoff before choosing a phase. These checklists describe required work, not completion evidence.

## P0: Map host and feature entry (H0-1)

- [ ] Build: Inspect web/src/App.tsx, layouts, pages and package.json. Read feature AGENTS.md. Agree on five component interfaces with owners and proposed feature route.
- [ ] Exit evidence: Small route/component plan that preserves existing Facebook mock screens.
- [ ] Dependency / parallel fallback: Feature visual design stays independent; no full shell rebuild.
- [ ] Handoff: update `docs/handoffs/will.md` with exact interface, branch/commit, checks/results and the next consumer action; append `docs/updates/will.md`.

## P1: Build voice and typed intent (H1-4)

- [ ] Build: Implement onboarding/ recording controls, typed fallback, transcript review and editable extracted fields. Add server/voice/ transcription adapter as needed. Handle missing fields via Adam's extraction contract.
- [ ] Exit evidence: A user can submit corrected intent using a fake adapter and complete the flow by keyboard.
- [ ] Dependency / parallel fallback: Use labeled development doubles while provider/auth endpoints land.
- [ ] Handoff: update `docs/handoffs/will.md` with exact interface, branch/commit, checks/results and the next consumer action; append `docs/updates/will.md`.

## P2: Wire the real journey (H4-7)

- [ ] Build: Connect Patrik's session/consent and self-intent APIs; Adam's extraction; Rishi's cards; Kai's event room. Register minimal feature entry and route.
- [ ] Exit evidence: Three devices can enter the feature and reach a persisted action. Timer begins at confirmed submission and stops on acknowledged acceptance.
- [ ] Dependency / parallel fallback: Each owner implements their component; report missing props/ports instead of rebuilding their system.
- [ ] Handoff: update `docs/handoffs/will.md` with exact interface, branch/commit, checks/results and the next consumer action; append `docs/updates/will.md`.

## P3: Make interaction resilient (H7-10)

- [ ] Build: Handle mic denial, failed upload, stale responses, cancellation and reconnection. Present revised plans with a clear reconfirm action.
- [ ] Exit evidence: A slow old request cannot overwrite corrected intent; interrupted flows offer recovery.
- [ ] Dependency / parallel fallback: Coordinate command status and revision numbers with Kai.
- [ ] Handoff: update `docs/handoffs/will.md` with exact interface, branch/commit, checks/results and the next consumer action; append `docs/updates/will.md`.

## P4: Compose the continuation (H10-13)

- [ ] Build: Add labeled next-week navigation and host-acceptance entry using Adam/Kai components. Keep simulated state visibly distinguished.
- [ ] Exit evidence: A returning user can see a generated next step and accept hosting.
- [ ] Dependency / parallel fallback: No new business logic in the route component.
- [ ] Handoff: update `docs/handoffs/will.md` with exact interface, branch/commit, checks/results and the next consumer action; append `docs/updates/will.md`.

## P5: Freeze with usability evidence (H13-16)

- [ ] Build: Run phone/desktop, keyboard, error and timer checks. Test with actual consenting teammates and record task completion observations.
- [ ] Exit evidence: Reproducible web checks, truthful measured first-action times and complete route integration.
- [ ] Dependency / parallel fallback: Existing feed tests must still pass where feature routing affects the shell.
- [ ] Handoff: update `docs/handoffs/will.md` with exact interface, branch/commit, checks/results and the next consumer action; append `docs/updates/will.md`.

## P6: Lead feature visual consistency (H16-22)

- [ ] Build: Refine spacing, typography, transitions and accessible states across owner components. Rehearse QR entry and actual demo devices.
- [ ] Exit evidence: Polished separate feature UI, usable mobile journey and no mock/live confusion.
- [ ] Dependency / parallel fallback: Other owners polish their own components; you are not the sole UI implementer.
- [ ] Handoff: update `docs/handoffs/will.md` with exact interface, branch/commit, checks/results and the next consumer action; append `docs/updates/will.md`.


## Resume-worthy evidence
Own the implementation and keep reproducible measurements for your system. Test counts alone are not impact. Report actual correctness, latency, reliability or observed usability results, with scope and limitations. Do not invent achieved improvement or user adoption.
