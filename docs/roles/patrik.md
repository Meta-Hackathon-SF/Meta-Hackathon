# Patrik: Privacy, safety and output guard
Branch: `role/patrik-privacy`. Read root AGENTS.md, PROJECT_KNOWLEDGE.md, docs/COORDINATION.md, docs/DECISIONS.md (D001, D003) and `contracts/protocol.ts` (`CONTRACT_VERSION` 1.0.0, pending D001/D003 ACK) first.

Product: Constellations, a campus secret-society game inside Facebook Groups. Muse is the Keeper (game master). Weekly Confession, Induction into societies of 3-5 by meaning, Hunt with 3-level riddles, in-person passphrase/found-code confirm, Sky reveal (guessed vs actual prevalence), then a Ritual quest (P1). Friendship only, 18+. Muse proposes, code enforces.

## Mission
Start with [your phase-by-phase build checklist](../phases/patrik.md). It specifies paths, work, dependencies, exit evidence and handoffs for P0-P6 on the re-based timeline (P0 16:00 PST, freeze 04:30, deadline 10:30 AM PST Nov 13, team-supplied and not independently verified).

Own everything that keeps confessions safe: consent, private answers, blocks, M1 safety triage, the output guard, Sky threshold, deletion and TTL, and the prompt builder that strips profile fields. No player ever sees another player's words; this is enforced by server code, not the model.

First action: check for tags (docs/COORDINATION.md §1), then record your ACK of D001 (product and ownership) and D003 (contract `contracts/protocol.ts` v1.0.0), both pending ACK, in docs/DECISIONS.md or the PR discussion.

## Ownership
- `server/privacy/`
- `db/privacy/`
- `web/src/features/constellations/privacy/` (consent screen, private support card)
- `tests/privacy/`
Also own this role document, docs/handoffs/patrik.md and docs/updates/patrik.md.
UI lives at `web/src/features/constellations/<area>/` inside the existing mock Facebook shell.

## Starting point
Fresh build; no privacy code exists on main. Build sessions, ConsentV2 (three required toggles: match answers, write clues, 18+), authorized snapshots, projections, output guard, safety flags, blocks and prompt builder in the owned paths.

## Producer/consumer contract
Inputs: Will's join and answer payloads; Adam/Rishi Muse text outputs (to guard); Kai's round tables and Sky counts; `contracts/protocol.ts`.
Outputs: server-verified session; `ConsentV2`; private `Answer` store (author + server only; 403 for any other session); `SafetyFlag` via M1; `Block` enforcement hooks; `FindableDetails`; output guard function `guard(text, answers)` (no-quote 5+ consecutive words, sensitive-term filter for health, sexuality, religion, finances, family trauma, home location); prompt builder; Sky threshold filter (3 demo / 25 prod); delete endpoint and 14-day TTL job.
Give Rishi/Adam the authorized snapshot and the guard; give Kai authorization and invalidation hooks plus table schema; give Will consent screen and support card components.

## Muse jobs owned
M1 safety screen (one answer in, `{flag: none|distress|harm, reason}` out; flagged answers excluded everywhere).
Muse model: `muse-spark-1.3` was echoed by the provider during earlier testing on the archived branch; re-verify on this build. Observed single-call latency 17-24 s at low reasoning effort (2 calls, not a benchmark), so fan-out must be parallel. Every Muse response shown in the UI carries a chip: model, call type, latency; cached responses are labeled "Replay of a saved round."

## UI owned
Consent screen (3 toggles, all required), private support card (campus counseling and the 988 Suicide and Crisis Lifeline, US) shown when an answer is flagged; the player can still play with a different answer. The game never counsels.

## Implementation sequence
1. Check tags, then ACK D001/D003; confirm session mechanism with Kai (reject client identity assertions).
2. ConsentV2 and join: no answer stored before all three toggles; revoke honored during model calls.
3. Private answers with row-level checks; deletion before lock and 14-day TTL; deleted answer absent from re-runs.
4. Prompt builder (random IDs plus answer text only) and output guard; expose both to Adam, Rishi and Kai; wire to every Muse text output before release.
5. M1 safety triage through Adam's adapter before matching; flagged answers excluded from societies, riddles and themes; support card.
6. Blocks API and validation hook for M4 output; Sky threshold filter on server aggregates; venue allowlist check for quests; red-team list of 30 answers.

## Checkpoints
H0-1 (16:00-17:00 PST, P0): check tags (COORDINATION §1), ACK D001/D003, confirm dependencies, claim shared files.
17:00-20:00 (P1): module runs alone against labeled synthetic fixtures with clear status.
20:00-23:00 (P2): integrated round on 3+ phones: join, confess, induct, riddles, confirm.
23:00-02:00 (P3): Sky, safety triage, blocks and operator console complete; failure cases pass.
02:00-04:30 (P4/P5): P1 features (ritual, riddle veto) only if the critical path is green; hardening; feature freeze at 04:30 with test evidence and no contract ambiguity.
04:30-10:30 (P6): UI/demo/submission only. Polish your component, verify integration, rehearse, support backup video and Devpost.

## Required checks
Privacy tests from the PRD table:
- Another player's session gets 403 on any answer endpoint.
- Unit test on every prompt payload: only random IDs and answer text.
- Fuzz test with known answers: no riddle, name or theme contains 5+ consecutive words from any answer.
- Red-team list of 30 answers: no sensitive categories in riddles.
- Theme with 2 members never renders (threshold 3 demo, 25 prod).
- Seeded distress answer never appears in any society, riddle or theme.
- Deleted answer absent from re-run; expired answers removed after 14 days.
- Blocked pair rejected and re-solved; quest outside venue allowlist rejected; vetoed riddle never sent (P1).
- Forged IDs; unauthenticated writes; consent revoked during a model call; no answer collected before consent.
Report exact commands/results; do not manufacture performance or quality numbers. Fixture or fake-provider tests prove local behavior, not live Muse integration; label every synthetic element.

## Coordination
Full protocol: [docs/COORDINATION.md](../COORDINATION.md). Your handle is @patrikliska13.
- Before any work session, check open PRs and issues for tags addressed to you (COORDINATION §1) and answer them first with `ACK`, `CHANGE: <proposal>` or `DELIVERED: <commit/PR>`.
- You depend on: Will (@willapat): join and answer payloads; Adam (@adamzhang06): Muse adapter for M1 and text outputs to guard; Kai (@beatopia): round tables, session composition and Sky counts.
- Others depend on you: Rishi (@rishibagri): authorized snapshot, blocks, guard; Adam (@adamzhang06): guard, findable details, prompt builder; Kai (@beatopia): session, threshold filter, guard; Will (@willapat): consent API and flag signal.
- When blocked on any of them: stop at the phase boundary, push your verified work, open or update a `[BLOCKED]` draft PR tagging the owner's handle with the exact block (COORDINATION §2), and continue only with a labeled test-only adapter. Do not edit their paths or silently change `contracts/`.

## Branch workflow
```sh
git fetch origin
git switch --track origin/role/patrik-privacy
# If local branch exists: git switch role/patrik-privacy
git merge origin/main
git status --short
```
Only merge main into a clean branch. Use a separate worktree for another agent, not a shared checkout switched underneath it. Push to role/patrik-privacy; do not force-push. Shared contract modifications go through an explicit producer/consumer agreement in docs/DECISIONS.md and merge before dependent work.

## First prompt for your coding agent
Read AGENTS.md, PROJECT_KNOWLEDGE.md, docs/COORDINATION.md, docs/DECISIONS.md (D001, D003), contracts/protocol.ts (v1.0.0, pending ACK), docs/roles/patrik.md and docs/handoffs/patrik.md. Confirm the current branch is role/patrik-privacy. First check open PRs/issues for tags addressed to me (COORDINATION §1) and answer them, then record my D001/D003 ACK. Inspect existing code, preserve unrelated edits, and implement the first incomplete checkpoint in my owned paths. If I am blocked on another owner, stop at the phase boundary, push, open or update a `[BLOCKED]` draft PR tagging them with the exact block (COORDINATION §2), and continue only with a labeled test-only adapter. Use the common contracts; report a concrete interface mismatch instead of creating a private incompatible version. Keep my handoff/log updated with verified evidence. Constellations has a feature UI at web/src/features/constellations/ inside the existing mock Facebook shell.
