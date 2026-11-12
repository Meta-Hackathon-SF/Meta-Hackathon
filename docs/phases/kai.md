# Kai: phased build playbook

Read [your role](../roles/kai.md), [shared instructions](../../AGENTS.md), and [phase coordination](README.md) first.
Hours are elapsed from the team's agreed start; check [the shared schedule](../PLAN.md) for clock times. Inspect current code and your handoff before choosing a phase. These checklists describe required work, not completion evidence.

## P0: Create integration baseline (H0-1)

- [ ] Build: Inspect contracts and existing web host. Agree server stack, DB migration order and authentication with Patrik. Scaffold server/app/ with reproducible setup and service registration.
- [x] Exit evidence (independent baseline): Backend starts; health endpoint works; shared manifests and routes have one coordinator. Verified by local HTTP probes and 42 offline tests; multi-owner ACK/database integration remains pending, so this does not pass the team-wide P0 gate.
- [ ] Dependency / parallel fallback: Confirm hosting separately; documentation foundation does not imply deployment.
- [ ] Handoff: update `docs/handoffs/kai.md` with exact interface, branch/commit, checks/results and the next consumer action; append `docs/updates/kai.md`.

## P1: Build durable state (H1-4)

Checkpoint: implementation committed on Kai role branch; local offline validation passes. Database exit evidence and privacy-owner approval remain pending CI/review. Stopped at P2 entry for human feedback; P2 exit is not claimed.

- [ ] Build: Implement quests, versioned proposals, acceptance ledger, jobs/outbox and idempotency rules in orchestration/ and db/workflow/. Provide test adapters for ports.
- [ ] Exit evidence: Duplicate acceptance does not increase count; job/state data survive a process restart.
- [ ] Dependency / parallel fallback: Keep provider work outside DB transactions; use Patrik's auth contract.
- [ ] Handoff: update `docs/handoffs/kai.md` with exact interface, branch/commit, checks/results and the next consumer action; append `docs/updates/kai.md`.

## P2: Connect the event loop (H4-7)

- [ ] Build: Register real matching/planning/privacy services. Trigger planning at quorum, validate output, persist event and conversation, expose event-room component and authorized stream.
- [ ] Exit evidence: Three participants create exactly one in-app event; browser refresh restores the snapshot.
- [ ] Dependency / parallel fallback: Real provider output and consent checks required for live evidence.
- [ ] Handoff: update `docs/handoffs/kai.md` with exact interface, branch/commit, checks/results and the next consumer action; append `docs/updates/kai.md`.

## P3: Make revisions and retries reliable (H7-10)

- [ ] Build: Implement stale-job rejection, worker lease recovery, reconnect replay, capacity concurrency and revision reconfirmation.
- [ ] Exit evidence: Simultaneous accepts and retried jobs do not duplicate events; changed availability triggers revision.
- [ ] Dependency / parallel fallback: Adam proposes new details; Patrik invalidates revoked snapshots.
- [ ] Handoff: update `docs/handoffs/kai.md` with exact interface, branch/commit, checks/results and the next consumer action; append `docs/updates/kai.md`.

## P4: Persist hosting progression (H10-13)

- [ ] Build: Implement authorized next-week trigger, live continuation job, host acceptance, draft quest and scoped invitation.
- [ ] Exit evidence: Explicit host acceptance creates one draft, including on retry; simulated time skip remains labeled.
- [ ] Dependency / parallel fallback: No fabricated attendance or unsolicited external messages.
- [ ] Handoff: update `docs/handoffs/kai.md` with exact interface, branch/commit, checks/results and the next consumer action; append `docs/updates/kai.md`.

## P5: Freeze with failure evidence (H13-16)

- [ ] Build: Exercise crash-after-commit, duplicate delivery, stale revisions, leave/revoke races and reconnect. Finalize backend startup/deployment/reset instructions.
- [ ] Exit evidence: Recoverable integrated workflow and verified test results; current handoff and deployed status are distinct.
- [ ] Dependency / parallel fallback: Preserve failure state instead of turning outages into fake success.
- [ ] Handoff: update `docs/handoffs/kai.md` with exact interface, branch/commit, checks/results and the next consumer action; append `docs/updates/kai.md`.

## P6: Polish event experience and release (H16-22)

- [ ] Build: Refine event-room status, loading, revisions and recovery UI. Check live server health and demo reset isolation; support shared rehearsal/submission.
- [ ] Exit evidence: Stable event segment, accessible release links and reset that cannot erase unrelated sessions.
- [ ] Dependency / parallel fallback: Critical fixes only after freeze; avoid architectural rewrites.
- [ ] Handoff: update `docs/handoffs/kai.md` with exact interface, branch/commit, checks/results and the next consumer action; append `docs/updates/kai.md`.


## Resume-worthy evidence
Own the implementation and keep reproducible measurements for your system. Test counts alone are not impact. Report actual correctness, latency, reliability or observed usability results, with scope and limitations. Do not invent achieved improvement or user adoption.
