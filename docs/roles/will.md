# Will: Join, Confession and feature composition
Branch: `role/will-voice-ui`. Read root AGENTS.md, PROJECT_KNOWLEDGE.md, docs/COORDINATION.md, docs/DECISIONS.md (D001, D003) and `contracts/protocol.ts` (`CONTRACT_VERSION` 1.0.0, pending D001/D003 ACK) first.

Product: Constellations, a campus secret-society game inside Facebook Groups. Muse is the Keeper (game master). Weekly Confession, Induction into societies of 3-5 by meaning, Hunt with 3-level riddles, in-person passphrase/found-code confirm, Sky reveal (guessed vs actual prevalence), then a Ritual quest (P1). Friendship only, 18+. Muse proposes, code enforces.

## Mission
Start with [your phase-by-phase build checklist](../phases/will.md). It specifies paths, work, dependencies, exit evidence and handoffs for P0-P6 on the re-based timeline (P0 16:00 PST, freeze 04:30, deadline 10:30 AM PST Nov 13, team-supplied and not independently verified).

Own the player's front door and the shell: the Constellations tab inside the mock Facebook shell, QR deep link, one-screen explainer, join, the Confession (voice or text, 1-400 chars), one follow-up, the guess slider, edit/delete before lock. Compose every owner's component and own routing. A player can join from a phone in under 30 seconds. Build the Constellations shell in `web/src/features/constellations/`.

First action: check for tags (docs/COORDINATION.md §1), then record your ACK of D001 (product and ownership) and D003 (contract `contracts/protocol.ts` v1.0.0), both pending ACK, in docs/DECISIONS.md or the PR discussion.

## Ownership
- `server/voice/`
- `web/src/features/constellations/shell/` (composition and routing)
- `web/src/features/constellations/join/`
- `web/src/features/constellations/confession/` (answer, follow-up, guess slider, edit/delete)
- `web/src/features/constellations/components/` (Muse metadata chip)
- `tests/onboarding/`
Also own this role document, docs/handoffs/will.md and docs/updates/will.md.
UI lives at `web/src/features/constellations/<area>/` inside the existing mock Facebook shell.

## Starting point
Fresh build; main contains only the mock Facebook web UI. Keep the mock Facebook pages and styling intact; label "Simulated Facebook". Build join, Confession and the Constellations shell in the owned paths.

## Producer/consumer contract
Inputs: Adam's M2 clarify contract (via endpoint); Patrik's session/consent API (`GET /session`, `POST /communities/:id/players`, `PATCH /players/me/consent`); Kai's `GET /rounds/current`, stream client and answer routes; every owner's component props.
Outputs: `POST /rounds/:id/answers` (source voice|text, text 1-400, `followUpUsed`), `PATCH|DELETE /rounds/:id/answers/me`, `POST /rounds/:id/guess` (stored separately from the answer), join payload (display name, avatar color), Muse metadata chip component, feature route and composition contract.
Give Patrik consent-screen slot and join payload; give every owner the composition/route contract and chip props; give the team the multi-device entry URL and QR once deployed.

## Muse jobs owned
None owned. Calls M2 clarify through Adam's endpoint; shows model name, call type and latency on every Muse-derived element via the chip.
Muse model: `muse-spark-1.3` was echoed by the provider during earlier testing on the archived branch; re-verify on this build. Observed single-call latency 17-24 s at low reasoning effort (2 calls, not a benchmark), so fan-out must be parallel. Every Muse response shown in the UI carries a chip: model, call type, latency; cached responses are labeled "Replay of a saved round."

## UI owned
Join, explainer, Confession, follow-up, guess slider (0-100), answer review with edit/delete, Muse metadata chip component, tab/route in the shell.

## Implementation sequence
1. Build the shell in `features/constellations/shell` with a Constellations tab; keep existing mock pages working; define component slots for induction, hunt, sky, operator.
2. Join flow: explainer (what the Keeper does, what is private, what is shared), consent screen slot from Patrik (no answer collected before consent), display name and avatar color, QR deep link.
3. Confession: voice via a recorder and `server/voice/` transcription with text always available; voice failure falls back to text without losing the session; mic denial and unsupported browser handled.
4. One follow-up at most (skippable); guess slider saved separately; show own answer; edit/delete until lock; handle stale async results and cancelled requests.
5. Compose Rishi, Adam, Patrik and Kai components with scoped CSS, mobile-first; real-time via SSE client; Muse chip and truth labels everywhere.

## Checkpoints
H0-1 (16:00-17:00 PST, P0): check tags (COORDINATION §1), ACK D001/D003, confirm dependencies, claim shared files.
17:00-20:00 (P1): module runs alone against labeled synthetic fixtures with clear status.
20:00-23:00 (P2): integrated round on 3+ phones: join, confess, induct, riddles, confirm.
23:00-02:00 (P3): Sky, safety triage, blocks and operator console complete; failure cases pass.
02:00-04:30 (P4/P5): P1 features (ritual, riddle veto) only if the critical path is green; hardening; feature freeze at 04:30 with test evidence and no contract ambiguity.
04:30-10:30 (P6): UI/demo/submission only. Polish your component, verify integration, rehearse, support backup video and Devpost.

## Required checks
- Join from a phone in under 30 s (record actual); no answer collected before consent.
- Mic denial; text alternative; voice failure keeps session; keyboard interaction; mobile overflow; request cancelled and returns late.
- Guess stored separately from answer; edit changes stored answer; delete removes it; no edit after lock (ROUND_LOCKED).
- One follow-up per player per round, skippable.
- Every Muse-derived element shows model/callType/latency chip; "Simulated Facebook", "Synthetic player" and "Demo timing" labels present.
Report exact commands/results; do not manufacture performance or quality numbers. Fixture or fake-provider tests prove local behavior, not live Muse integration; label every synthetic element.

## Coordination
Full protocol: [docs/COORDINATION.md](../COORDINATION.md). Your handle is @willapat.
- Before any work session, check open PRs and issues for tags addressed to you (COORDINATION §1) and answer them first with `ACK`, `CHANGE: <proposal>` or `DELIVERED: <commit/PR>`.
- You depend on: Adam (@adamzhang06): M2 clarify endpoint; Patrik (@patrikliska13): session, consent API and flag signal; Kai (@beatopia): rounds, answer routes and stream; Rishi (@rishibagri) and Adam: component props.
- Others depend on you: Every owner: component slots, routes and the Muse chip; Patrik (@patrikliska13): consent slot and join payload; Kai (@beatopia): answer and guess payloads.
- When blocked on any of them: stop at the phase boundary, push your verified work, open or update a `[BLOCKED]` draft PR tagging the owner's handle with the exact block (COORDINATION §2), and continue only with a labeled test-only adapter. Do not edit their paths or silently change `contracts/`.

## Branch workflow
```sh
git fetch origin
git switch --track origin/role/will-voice-ui
# If local branch exists: git switch role/will-voice-ui
git merge origin/main
git status --short
```
Only merge main into a clean branch. Use a separate worktree for another agent, not a shared checkout switched underneath it. Push to role/will-voice-ui; do not force-push. Shared contract modifications go through an explicit producer/consumer agreement in docs/DECISIONS.md and merge before dependent work.

## First prompt for your coding agent
Read AGENTS.md, PROJECT_KNOWLEDGE.md, docs/COORDINATION.md, docs/DECISIONS.md (D001, D003), contracts/protocol.ts (v1.0.0, pending ACK), docs/roles/will.md and docs/handoffs/will.md. Confirm the current branch is role/will-voice-ui. First check open PRs/issues for tags addressed to me (COORDINATION §1) and answer them, then record my D001/D003 ACK. Inspect existing code, preserve unrelated edits, and implement the first incomplete checkpoint in my owned paths. If I am blocked on another owner, stop at the phase boundary, push, open or update a `[BLOCKED]` draft PR tagging them with the exact block (COORDINATION §2), and continue only with a labeled test-only adapter. Use the common contracts; report a concrete interface mismatch instead of creating a private incompatible version. Keep my handoff/log updated with verified evidence. Constellations has a feature UI at web/src/features/constellations/ inside the existing mock Facebook shell.
