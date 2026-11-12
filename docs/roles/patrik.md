# Patrik: Privacy, safety and output guard
Branch: `role/patrik-privacy` (unchanged). Read root AGENTS.md, PROJECT_KNOWLEDGE.md, docs/DECISIONS.md D009 and `contracts/constellations.ts` (version `2.0.0-proposed`) first. `contracts/protocol.ts` 1.x stays as legacy until you migrate; do not delete it.

Product: Constellations, a campus secret-society game inside Facebook Groups. Muse is the Keeper (game master). Weekly Confession, Induction into societies of 3-5 by meaning, Hunt with 3-level riddles, in-person passphrase/found-code confirm, Sky reveal (guessed vs actual prevalence), then a Ritual quest (P1). Friendship only, 18+. Muse proposes, code enforces.

## Mission
Start with [your phase-by-phase build checklist](../phases/patrik.md). It specifies paths, work, dependencies, exit evidence and handoffs for P0-P6 on the re-based timeline (P0 16:00 PST, freeze 04:30, deadline 10:30 AM PST Nov 13, team-supplied and not independently verified).

Own everything that keeps confessions safe: consent, private answers, blocks, M1 safety triage, the output guard, Sky threshold, deletion and TTL, and the prompt builder that strips profile fields. No player ever sees another player's words; this is enforced by server code, not the model.

First action: record your ACK of D009 (proposed ownership and contract 2.0.0) in docs/DECISIONS.md or the PR discussion.

## Ownership
- `server/privacy/`
- `db/privacy/`
- `web/src/features/constellations/privacy/` (consent screen, private support card)
- `tests/privacy/`
Also own this role document, docs/handoffs/patrik.md and docs/updates/patrik.md.
UI moves from `web/src/features/group-quests/<area>/` to `web/src/features/constellations/<area>/`; Will migrates the shell. Merged Group Quests code stays until migrated.

## Reuse of merged modules
`server/privacy/` sessions, consent versioning, authorized snapshots and public projections (Postgres-tested locally); `web/.../group-quests/privacy/` consent controls. Adapt: ConsentV2 has exactly three required toggles (match answers, write clues, 18+); projections become society/riddle/Sky projections; new modules for output guard, safety flags, blocks and prompt builder.

## Producer/consumer contract
Inputs: Will's join and answer payloads; Adam/Rishi Muse text outputs (to guard); Kai's round tables and Sky counts; `contracts/constellations.ts`.
Outputs: server-verified session; `ConsentV2`; private `Answer` store (author + server only; 403 for any other session); `SafetyFlag` via M1; `Block` enforcement hooks; `FindableDetails`; output guard function `guard(text, answers)` (no-quote 5+ consecutive words, sensitive-term filter for health, sexuality, religion, finances, family trauma, home location); prompt builder; Sky threshold filter (3 demo / 25 prod); delete endpoint and 14-day TTL job.
Give Rishi/Adam the authorized snapshot and the guard; give Kai authorization and invalidation hooks plus table schema; give Will consent screen and support card components.

## Muse jobs owned
M1 safety screen (one answer in, `{flag: none|distress|harm, reason}` out; flagged answers excluded everywhere).
Muse model verified live: `muse-spark-1.3` (provider echoed the model). Observed single-call latency 17-24 s at low reasoning effort (2 calls, not a benchmark), so fan-out must be parallel. Every Muse response shown in the UI carries a chip: model, call type, latency; cached responses are labeled "Replay of a saved round."

## UI owned
Consent screen (3 toggles, all required), private support card (campus counseling and the 988 Suicide and Crisis Lifeline, US) shown when an answer is flagged; the player can still play with a different answer. The game never counsels.

## Implementation sequence
1. Reply D009 ACK first; confirm session mechanism with Kai (reject client identity assertions).
2. ConsentV2 and join: no answer stored before all three toggles; revoke honored during model calls.
3. Private answers with row-level checks; deletion before lock and 14-day TTL; deleted answer absent from re-runs.
4. Prompt builder (random IDs plus answer text only) and output guard; expose both to Adam, Rishi and Kai; wire to every Muse text output before release.
5. M1 safety triage through Adam's adapter before matching; flagged answers excluded from societies, riddles and themes; support card.
6. Blocks API and validation hook for M4 output; Sky threshold filter on server aggregates; venue allowlist check for quests; red-team list of 30 answers.

## Checkpoints
H0-1 (16:00-17:00 PST, P0): ACK D009 first, confirm dependencies, claim shared files.
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
Read AGENTS.md, PROJECT_KNOWLEDGE.md, docs/DECISIONS.md (D009), contracts/constellations.ts, docs/roles/patrik.md and docs/handoffs/patrik.md. Confirm the current branch is role/patrik-privacy. First record my D009 ACK. Inspect existing code, preserve unrelated edits, and implement the first incomplete checkpoint in my owned paths, adapting the merged modules named above. Use the common contracts; report a concrete interface mismatch instead of creating a private incompatible version. Keep my handoff/log updated with verified evidence. Constellations has a separate feature UI at web/src/features/constellations/ inside the existing mock Facebook shell.
