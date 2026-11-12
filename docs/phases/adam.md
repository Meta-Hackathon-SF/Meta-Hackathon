# Adam: phased build playbook

Read [your role](../roles/adam.md), [shared instructions](../../AGENTS.md), and [phase coordination](README.md) first.
Hours are elapsed from the team's agreed start; check [the shared schedule](../PLAN.md) for clock times. Inspect current code and your handoff before choosing a phase. These checklists describe required work, not completion evidence.

## P0: Verify provider and ports (H0-1)

- [ ] Build: Read protocol and workflow contracts. Confirm model ID, auth, endpoint, structured-output support and audio support from organizer materials. Define adapter construction for Rishi and extraction result for Will.
- [ ] Exit evidence: Sanitized provider configuration notes and one verified call when credentials are available.
- [ ] Dependency / parallel fallback: If access is missing, document it and build the fake adapter without claiming live integration.
- [ ] Handoff: update `docs/handoffs/adam.md` with exact interface, branch/commit, checks/results and the next consumer action; append `docs/updates/adam.md`.

## P1: Build provider, extraction and validators (H1-4)

- [ ] Build: Implement server/providers/ MusePort with bounded timeout, cancellation and sanitized error handling. Implement server/planning/ intent extraction and missing-field output. Add runtime validators for model responses.
- [ ] Exit evidence: Rishi can call your adapter; Will can render a private draft and required follow-up fields.
- [ ] Dependency / parallel fallback: Do not couple provider client to Kai's database implementation.
- [ ] Handoff: update `docs/handoffs/adam.md` with exact interface, branch/commit, checks/results and the next consumer action; append `docs/updates/adam.md`.

## P2: Plan an actual group activity (H4-7)

- [ ] Build: Consume GroupProposal and authorized participant constraints. Select approved venue/time/cost and an interaction-producing task. Build planning/ proposal UI and publish component props.
- [ ] Exit evidence: A real group produces a feasible structured plan that Kai can persist after validation and acceptance.
- [ ] Dependency / parallel fallback: Rishi provides proposals; Patrik minimizes inputs; Kai owns persistence.
- [ ] Handoff: update `docs/handoffs/adam.md` with exact interface, branch/commit, checks/results and the next consumer action; append `docs/updates/adam.md`.

## P3: Implement revisions (H7-10)

- [ ] Build: On changed availability, produce a new proposal or needs_input/no_feasible_plan. Include revision lineage; prevent public explanations from revealing private constraints.
- [ ] Exit evidence: Demo a changed constraint altering the plan; the event is not silently rescheduled without reconfirmation.
- [ ] Dependency / parallel fallback: Kai discards stale jobs and executes effects; you only return proposals.
- [ ] Handoff: update `docs/handoffs/adam.md` with exact interface, branch/commit, checks/results and the next consumer action; append `docs/updates/adam.md`.

## P4: Generate continuation and host invitation (H10-13)

- [ ] Build: Implement PlanningPort.continue using voluntary feedback and current participants. Generate a small next activity and a suggested willing host.
- [ ] Exit evidence: Live reasoning follows the labeled time skip; host suggestion does not claim that attendance happened.
- [ ] Dependency / parallel fallback: Kai supplies feedback/state and implements explicit host acceptance.
- [ ] Handoff: update `docs/handoffs/adam.md` with exact interface, branch/commit, checks/results and the next consumer action; append `docs/updates/adam.md`.

## P5: Freeze with adversarial evidence (H13-16)

- [ ] Build: Exercise malformed JSON, invalid venues, impossible plans, timeouts, injection and stale inputs. Document actual latency and schema validity.
- [ ] Exit evidence: Provider and planning tests, verified integration, clear replay behavior and up-to-date handoff.
- [ ] Dependency / parallel fallback: Do not add more model families just for the pitch.
- [ ] Handoff: update `docs/handoffs/adam.md` with exact interface, branch/commit, checks/results and the next consumer action; append `docs/updates/adam.md`.

## P6: Polish the reasoning demonstration (H16-22)

- [ ] Build: Improve public plan and change explanations, verify live model labels, rehearse adaptation and support the backup recording.
- [ ] Exit evidence: Planning/replanning works in the five-minute flow; fallback is honest and recoverable.
- [ ] Dependency / parallel fallback: No unvalidated feature additions after freeze.
- [ ] Handoff: update `docs/handoffs/adam.md` with exact interface, branch/commit, checks/results and the next consumer action; append `docs/updates/adam.md`.


## Resume-worthy evidence
Own the implementation and keep reproducible measurements for your system. Test counts alone are not impact. Report actual correctness, latency, reliability or observed usability results, with scope and limitations. Do not invent achieved improvement or user adoption.
