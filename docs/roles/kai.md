# Kai: Round lifecycle and operator console
Branch: `role/kai-orchestration`. Read root AGENTS.md, PROJECT_KNOWLEDGE.md, docs/COORDINATION.md, docs/DECISIONS.md (D001, D003) and `contracts/protocol.ts` (`CONTRACT_VERSION` 1.0.0, pending D001/D003 ACK) first.

Product: Constellations, a campus secret-society game inside Facebook Groups. Muse is the Keeper (game master). Weekly Confession, Induction into societies of 3-5 by meaning, Hunt with 3-level riddles, in-person passphrase/found-code confirm, Sky reveal (guessed vs actual prevalence), then a Ritual quest (P1). Friendship only, 18+. Muse proposes, code enforces.

## Mission
Start with [your phase-by-phase build checklist](../phases/kai.md). It specifies paths, work, dependencies, exit evidence and handoffs for P0-P6 on the re-based timeline (P0 16:00 PST, freeze 04:30, deadline 10:30 AM PST Nov 13, team-supplied and not independently verified).

Own the round lifecycle and live delivery: open, locked, inducting, hunt levels, sky, closed. Fan out Muse calls in parallel so induction finishes in under 60 s, run mutual idempotent passphrase/found-code confirms, stream updates over SSE, compute Sky aggregates, and own the operator console and the Sky projector view.

First action: check for tags (docs/COORDINATION.md §1), then record your ACK of D001 (product and ownership) and D003 (contract `contracts/protocol.ts` v1.0.0), both pending ACK, in docs/DECISIONS.md or the PR discussion.

## Ownership
- `server/orchestration/`
- `server/app/`
- `db/workflow/`
- `web/src/features/constellations/operator/` (operator console)
- `web/src/features/constellations/sky/` (Sky projector view, constellation light-up)
- `web/src/features/constellations/events/` (ritual event + chat, P1)
- `tests/orchestration/`
Also own this role document, docs/handoffs/kai.md and docs/updates/kai.md.
UI lives at `web/src/features/constellations/<area>/` inside the existing mock Facebook shell.

## Starting point
Fresh build; no server exists on main. Build the app registry (`/health`, `/api/v1`), round workflow, jobs, idempotent Find and SSE stream in the owned paths. Server baseline is proposed in D002.

## Producer/consumer contract
Inputs: Patrik's session/authorization hooks; Rishi's validated societies; Adam's M5/M6/M8/M7 job functions; Will's answer, guess and stream client; operator actions.
Outputs: `Round` state machine (`status`, `levelUnlocked` 0-3, `demoTiming`), `Find` (mutual, idempotent, unique pair), `FoundCode`, `POST /rounds/:id/finds` returning confirmed|pending|not_a_match (wrong code reveals nothing; `NOT_IN_SOCIETY`), `SkyStats` (counts computed by server, `count >= threshold` themes only), `RitualQuest` approvals (P1), operator routes (create round, lock, advance-level, sky, reset, synthetic-topup, calls metadata), `GET /rounds/:id/stream`, ModelEvidence list.
Give everyone API registration conventions; give Will the stream client and Sky/operator components; give Patrik table schema for policy review; give Adam server counts for M8.

## Muse jobs owned
None owned; orchestrates M1-M8 (parallel M5 per society, parallel M6 per target/seeker, precompute while the round is open where possible, retries and labeled fallbacks).
Muse model: `muse-spark-1.3` was echoed by the provider during earlier testing on the archived branch; re-verify on this build. Observed single-call latency 17-24 s at low reasoning effort (2 calls, not a benchmark), so fan-out must be parallel. Every Muse response shown in the UI carries a chip: model, call type, latency; cached responses are labeled "Replay of a saved round."

## UI owned
Operator console (pick question, open/lock, advance level, trigger Sky, reset, load synthetic top-up, per-call model metadata and latency); Sky projector view and in-Group Sky (stars are members, lines are confirmed finds, guessed vs actual prevalence); constellation light-up on confirm.

## Implementation sequence
1. Check tags, then ACK D001/D003; agree session/auth and table order with Patrik; build the registry on /api/v1 routes.
2. Round state machine with ROUND_LOCKED errors and persistence; operator create/lock/advance/sky/reset.
3. Lock pipeline: M1 (all answers, parallel) then M3/M4 then M5 per society in parallel then M6 fan-out; each output guarded; record call evidence; target 30 players in under 60 s.
4. Find confirmation: mutual, idempotent, unique pair, found code 4 chars; wrong code returns generic not_a_match; constellation light-up via SSE.
5. Sky aggregates from server counts (guessed vs actual per theme, society and find counts) with threshold; M8 narration validated against counts.
6. Operator console, labeled synthetic top-up loader ("Synthetic player"), reset isolation; then ritual event + chat with 3+ approvals (P1).

## Checkpoints
H0-1 (16:00-17:00 PST, P0): check tags (COORDINATION §1), ACK D001/D003, confirm dependencies, claim shared files.
17:00-20:00 (P1): module runs alone against labeled synthetic fixtures with clear status.
20:00-23:00 (P2): integrated round on 3+ phones: join, confess, induct, riddles, confirm.
23:00-02:00 (P3): Sky, safety triage, blocks and operator console complete; failure cases pass.
02:00-04:30 (P4/P5): P1 features (ritual, riddle veto) only if the critical path is green; hardening; feature freeze at 04:30 with test evidence and no contract ambiguity.
04:30-10:30 (P6): UI/demo/submission only. Polish your component, verify integration, rehearse, support backup video and Devpost.

## Required checks
- Induction for 30 players in under 60 s (record actual); every society validated before release.
- Confirmation mutual and idempotent; duplicate delivery and retries create one Find; wrong code never reveals membership.
- Concurrent finds and double lock; crash after commit; stale provider result; SSE reconnect replay; revoked actor.
- Sky: no theme, stat or line identifies an individual answer; M8 numbers match server counts.
- Demo timing label; reset cannot erase unrelated sessions; synthetic top-up labeled.
Report exact commands/results; do not manufacture performance or quality numbers. Fixture or fake-provider tests prove local behavior, not live Muse integration; label every synthetic element.

## Coordination
Full protocol: [docs/COORDINATION.md](../COORDINATION.md). Your handle is @beatopia.
- Before any work session, check open PRs and issues for tags addressed to you (COORDINATION §1) and answer them first with `ACK`, `CHANGE: <proposal>` or `DELIVERED: <commit/PR>`.
- You depend on: Rishi (@rishibagri): validated societies; Adam (@adamzhang06): Muse jobs M5, M6, M8; Patrik (@patrikliska13): session, guard, flags and threshold.
- Others depend on you: Will (@willapat): rounds, answer routes and stream; Adam (@adamzhang06): Sky counts for M8; Rishi (@rishibagri): lock trigger; every UI owner: operator and Sky data.
- When blocked on any of them: stop at the phase boundary, push your verified work, open or update a `[BLOCKED]` draft PR tagging the owner's handle with the exact block (COORDINATION §2), and continue only with a labeled test-only adapter. Do not edit their paths or silently change `contracts/`.

## Branch workflow
```sh
git fetch origin
git switch --track origin/role/kai-orchestration
# If local branch exists: git switch role/kai-orchestration
git merge origin/main
git status --short
```
Only merge main into a clean branch. Use a separate worktree for another agent, not a shared checkout switched underneath it. Push to role/kai-orchestration; do not force-push. Shared contract modifications go through an explicit producer/consumer agreement in docs/DECISIONS.md and merge before dependent work.

## First prompt for your coding agent
Read AGENTS.md, PROJECT_KNOWLEDGE.md, docs/COORDINATION.md, docs/DECISIONS.md (D001, D003), contracts/protocol.ts (v1.0.0, pending ACK), docs/roles/kai.md and docs/handoffs/kai.md. Confirm the current branch is role/kai-orchestration. First check open PRs/issues for tags addressed to me (COORDINATION §1) and answer them, then record my D001/D003 ACK. Inspect existing code, preserve unrelated edits, and implement the first incomplete checkpoint in my owned paths. If I am blocked on another owner, stop at the phase boundary, push, open or update a `[BLOCKED]` draft PR tagging them with the exact block (COORDINATION §2), and continue only with a labeled test-only adapter. Use the common contracts; report a concrete interface mismatch instead of creating a private incompatible version. Keep my handoff/log updated with verified evidence. Constellations has a feature UI at web/src/features/constellations/ inside the existing mock Facebook shell.
