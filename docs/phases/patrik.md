# Patrik: phased build playbook

Read [your role](../roles/patrik.md), [shared instructions](../../AGENTS.md), and [phase coordination](README.md) first.
Hours are elapsed from the team's agreed start; check [the shared schedule](../PLAN.md) for clock times. Inspect current code and your handoff before choosing a phase. These checklists describe required work, not completion evidence.

## P0: Agree identity and storage boundaries (H0-1)

- [ ] Build: Read PRIVACY.md and Kai's schema proposal. Decide session/auth mechanism, private field ownership, public projections and migration order.
- [ ] Exit evidence: Documented auth approach and authorized candidate service signature.
- [ ] Dependency / parallel fallback: Use local synthetic identities for offline tests, never as production authorization.
- [ ] Handoff: update `docs/handoffs/patrik.md` with exact interface, branch/commit, checks/results and the next consumer action; append `docs/updates/patrik.md`.

## P1: Implement private participant foundation (H1-4)

- [ ] Build: Build server/privacy/ session checks, community membership, consent versions and self-only intent CRUD. Add db/privacy/ policies and fixture setup.
- [ ] Exit evidence: Cross-user reads/writes denied; Rishi can obtain a minimized authorized snapshot through a service port.
- [ ] Dependency / parallel fallback: Coordinate tables with Kai; do not create conflicting migrations independently.
- [ ] Handoff: update `docs/handoffs/patrik.md` with exact interface, branch/commit, checks/results and the next consumer action; append `docs/updates/patrik.md`.

## P2: Integrate consent and public views (H4-7)

- [ ] Build: Wire Will's consent and confirmation. Deliver public profile/proposal projections, identity guards and membership checks for routes/subscriptions. Build privacy/ controls.
- [ ] Exit evidence: Live matching sees only opted-in candidates; room members cannot inspect another member's budget or raw transcript.
- [ ] Dependency / parallel fallback: Rishi/Adam consume snapshots; Kai applies your guards at effects and reads.
- [ ] Handoff: update `docs/handoffs/patrik.md` with exact interface, branch/commit, checks/results and the next consumer action; append `docs/updates/patrik.md`.

## P3: Close revocation races (H7-10)

- [ ] Build: Implement leave/revoke callbacks, version increments and subscription invalidation. Recheck queued model jobs before publication.
- [ ] Exit evidence: A participant leaving during planning prevents stale publication and further private access.
- [ ] Dependency / parallel fallback: Kai handles job invalidation/transactions; coordinate exact expected versions.
- [ ] Handoff: update `docs/handoffs/patrik.md` with exact interface, branch/commit, checks/results and the next consumer action; append `docs/updates/patrik.md`.

## P4: Secure continuation and invitations (H10-13)

- [ ] Build: Ensure hosting requires explicit identity/acceptance; invitations are scoped and revocable. Only authorized, opted-in feedback reaches continuation.
- [ ] Exit evidence: An old invite or revoked consent cannot regain access or authorize a new plan.
- [ ] Dependency / parallel fallback: Review Kai's draft creation and Adam's feedback projection.
- [ ] Handoff: update `docs/handoffs/patrik.md` with exact interface, branch/commit, checks/results and the next consumer action; append `docs/updates/patrik.md`.

## P5: Freeze with access evidence (H13-16)

- [ ] Build: Exercise forged IDs, cross-room reads, revoked reconnects, public-field leakage and real database policies without service-role bypass.
- [ ] Exit evidence: Documented adversarial tests and verified privacy boundaries, with remaining limits explicit.
- [ ] Dependency / parallel fallback: If direct DB access exists, test it separately from API authorization.
- [ ] Handoff: update `docs/handoffs/patrik.md` with exact interface, branch/commit, checks/results and the next consumer action; append `docs/updates/patrik.md`.

## P6: Polish privacy interaction (H16-22)

- [ ] Build: Refine consent/leave controls and demo-safe public explanations. Verify the final deployed configuration and help rehearse safety answers.
- [ ] Exit evidence: Visible controls work and measured tests support claims.
- [ ] Dependency / parallel fallback: Do not claim encryption/provider retention guarantees that were not implemented.
- [ ] Handoff: update `docs/handoffs/patrik.md` with exact interface, branch/commit, checks/results and the next consumer action; append `docs/updates/patrik.md`.


## Resume-worthy evidence
Own the implementation and keep reproducible measurements for your system. Test counts alone are not impact. Report actual correctness, latency, reliability or observed usability results, with scope and limitations. Do not invent achieved improvement or user adoption.
