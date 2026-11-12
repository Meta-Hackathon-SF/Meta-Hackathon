# Rishi: phased build playbook

Read [your role](../roles/rishi.md), [shared instructions](../../AGENTS.md), and [phase coordination](README.md) first.
Hours are elapsed from the team's agreed start; check [the shared schedule](../PLAN.md) for clock times. Inspect current code and your handoff before choosing a phase. These checklists describe required work, not completion evidence.

## P0: Agree on matching inputs (H0-1)

- [ ] Build: Inspect contracts/protocol.ts and contracts/PRIVACY.md. Confirm Patrik's candidate snapshot fields and Adam's MusePort. Create synthetic feasible and impossible team cases in tests/matching/.
- [ ] Exit evidence: A fixture containing three feasible participants and one no-common-time case; ACK the port in your handoff.
- [ ] Dependency / parallel fallback: No live dependencies: use a test-only authorized snapshot adapter.
- [ ] Handoff: update `docs/handoffs/rishi.md` with exact interface, branch/commit, checks/results and the next consumer action; append `docs/updates/rishi.md`.

## P1: Build feasibility first (H1-4)

- [ ] Build: Implement server/matching/ interval intersection, eligibility, requester inclusion, deduplication, area/currency agreement, and group-size checks. Add a bounded candidate shortlist and a shared-interest baseline.
- [ ] Exit evidence: Tests reject invalid groups and return a typed no_match. Export the MatchingPort-compatible entry point for Kai.
- [ ] Dependency / parallel fallback: Do not wait for Muse: a fake ranking adapter can exercise feasibility offline.
- [ ] Handoff: update `docs/handoffs/rishi.md` with exact interface, branch/commit, checks/results and the next consumer action; append `docs/updates/rishi.md`.

## P2: Connect Muse and the feature (H4-7)

- [ ] Build: Consume Adam's provider adapter and Patrik's actual snapshots. Validate every selected ID. Build matching/ team cards, rationale and no-match UI; document props for Will.
- [ ] Exit evidence: One actual API call produces a validated group for Kai and renders in Will's feature route.
- [ ] Dependency / parallel fallback: Real consent snapshot and provider adapter needed for live evidence; retain clearly labeled fixture harness until available.
- [ ] Handoff: update `docs/handoffs/rishi.md` with exact interface, branch/commit, checks/results and the next consumer action; append `docs/updates/rishi.md`.

## P3: Handle changing candidates (H7-10)

- [ ] Build: Recompute after updated availability or membership. Reject stale intent/consent versions. Publish only privacy-approved rationale fields.
- [ ] Exit evidence: A removed participant never appears in the new proposal; impossible combinations explain why no match exists.
- [ ] Dependency / parallel fallback: Coordinate snapshot refresh with Patrik and stale-result handling with Kai.
- [ ] Handoff: update `docs/handoffs/rishi.md` with exact interface, branch/commit, checks/results and the next consumer action; append `docs/updates/rishi.md`.

## P4: Support next-week groups (H10-13)

- [ ] Build: Let continuation prefer willing returning members while rerunning hard eligibility. Preserve opt-in for proposed newcomers; avoid re-adding people who declined.
- [ ] Exit evidence: A follow-up can keep an eligible team or return no_match without fabricating participation.
- [ ] Dependency / parallel fallback: Adam supplies continuation intent; Kai supplies current membership.
- [ ] Handoff: update `docs/handoffs/rishi.md` with exact interface, branch/commit, checks/results and the next consumer action; append `docs/updates/rishi.md`.

## P5: Freeze with evidence (H13-16)

- [ ] Build: Run the same synthetic cases against baseline and Muse ranking. Record feasibility, latency and relevance assessment method. Verify matching-card integration.
- [ ] Exit evidence: Runnable evaluation command, actual results, current handoff and no unresolved contract mismatch.
- [ ] Dependency / parallel fallback: Separate offline fake tests from live provider results.
- [ ] Handoff: update `docs/handoffs/rishi.md` with exact interface, branch/commit, checks/results and the next consumer action; append `docs/updates/rishi.md`.

## P6: Polish and demonstrate (H16-22)

- [ ] Build: Polish your cards, explanations, loading/no-match states. Verify the group chosen on the demo devices and provide a concise technical explanation.
- [ ] Exit evidence: No new ranking features; matching segment stable for rehearsal and submission.
- [ ] Dependency / parallel fallback: Help shared UI/demo work after your component is verified.
- [ ] Handoff: update `docs/handoffs/rishi.md` with exact interface, branch/commit, checks/results and the next consumer action; append `docs/updates/rishi.md`.


## Resume-worthy evidence
Own the implementation and keep reproducible measurements for your system. Test counts alone are not impact. Report actual correctness, latency, reliability or observed usability results, with scope and limitations. Do not invent achieved improvement or user adoption.
