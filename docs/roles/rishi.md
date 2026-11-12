# Rishi: Induction engine
Branch: `role/rishi-matching` (unchanged). Read root AGENTS.md, PROJECT_KNOWLEDGE.md, docs/DECISIONS.md D009 and `contracts/constellations.ts` (version `2.0.0-proposed`) first. `contracts/protocol.ts` 1.x stays as legacy until you migrate; do not delete it.

Product: Constellations, a campus secret-society game inside Facebook Groups. Muse is the Keeper (game master). Weekly Confession, Induction into societies of 3-5 by meaning, Hunt with 3-level riddles, in-person passphrase/found-code confirm, Sky reveal (guessed vs actual prevalence), then a Ritual quest (P1). Friendship only, 18+. Muse proposes, code enforces.

## Mission
Start with [your phase-by-phase build checklist](../phases/rishi.md). It specifies paths, work, dependencies, exit evidence and handoffs for P0-P6 on the re-based timeline (P0 16:00 PST, freeze 04:30, deadline 10:30 AM PST Nov 13, team-supplied and not independently verified).

Build the induction engine: read all unflagged answers, discover themes by meaning (M3), form secret societies of 3-5 by meaning (M4), and validate every output in code. Maintain a keyword/embedding-cluster baseline so the demo can show one live example where the baseline splits two people who meant the same thing and Muse puts them together. Do not claim a measured improvement unless it is measured.

First action: record your ACK of D009 (proposed ownership and contract 2.0.0) in docs/DECISIONS.md or the PR discussion.

## Ownership
- `server/matching/`
- `web/src/features/constellations/matching/`
- `web/src/features/constellations/induction/` (induction screen: society name, sigil, passphrase half, members-to-find)
- `tests/matching/`
Also own this role document, docs/handoffs/rishi.md and docs/updates/rishi.md.
UI moves from `web/src/features/group-quests/<area>/` to `web/src/features/constellations/<area>/`; Will migrates the shell. Merged Group Quests code stays until migrated.

## Reuse of merged modules
`server/matching/` constraint gates, bounded shortlist, complete-group evaluation and eval harness (feasibility, models, ranking, evaluation). Adapt: the pair/team feasibility gates become society validation; the shared-interest baseline becomes the keyword/embedding-cluster baseline. Group Quests intent fields are dropped.

## Producer/consumer contract
Inputs: Patrik's authorized snapshot of unflagged `Answer` text under random IDs plus `Block` pairs and `ConsentV2` (matchAnswers true only); Adam's Muse adapter and Keeper prompt rules; Kai's lock trigger.
Outputs: `Theme[]` (member IDs private), validated `Society[]` (`memberIds`, `sharedMeaning` private, `confidence`, `isLooseMatch`), baseline-vs-Muse comparison record, `ModelEvidence` with callType `theme_discovery` / `society_formation`. Induction screen props from `GET /rounds/:id/induction`.
Give Adam validated societies (input to M5 identity and M6 riddles) and fixtures; give Kai validated societies plus revision IDs; give Will induction-screen component props; give Patrik theme labels to run through the output guard.

## Muse jobs owned
M3 theme discovery and M4 society formation (strongest available model; prompt example: "I call my sister every night" and "I miss my family more than I expected" belong together; group by underlying meaning, not shared keywords). Muse proposes, code enforces.
Muse model verified live: `muse-spark-1.3` (provider echoed the model). Observed single-call latency 17-24 s at low reasoning effort (2 calls, not a benchmark), so fan-out must be parallel. Every Muse response shown in the UI carries a chip: model, call type, latency; cached responses are labeled "Replay of a saved round."

## UI owned
Induction screen: society name, sigil, own passphrase half, number of members to find, honest loose-match label ("Your connection here is looser this week"), Muse metadata chip.

## Implementation sequence
1. Adapt the merged validation: every consenting unflagged player in exactly one society, size 3-5, no blocked pair together, loose-match players placed in the best society with an honest label, never left out. Invalid M4 output is rejected and re-solved (blocked pair), with one JSON retry then labeled fallback.
2. Implement M3 and M4 through Adam's adapter with strict JSON schema validation; answers appear only under random IDs.
3. Implement the keyword/embedding-cluster baseline and a labeled pair example ("cooking for one is depressing" vs "I eat in my room so no one sees me alone") showing baseline split vs Muse join. Record actual outcomes only.
4. Make induction fast: parallel-friendly interface so Kai can run M5 per society concurrently. Measure 30 synthetic players end to end against the 60 s target (single call observed 17-24 s; this is the top technical risk).
5. Render the induction screen from authorized data only; theme labels and names pass Patrik's output guard before release.

## Checkpoints
H0-1 (16:00-17:00 PST, P0): ACK D009 first, confirm dependencies, claim shared files.
17:00-20:00 (P1): module runs alone against labeled synthetic fixtures with clear status.
20:00-23:00 (P2): integrated round on 3+ phones: join, confess, induct, riddles, confirm.
23:00-02:00 (P3): Sky, safety triage, blocks and operator console complete; failure cases pass.
02:00-04:30 (P4/P5): P1 features (ritual, riddle veto) only if the critical path is green; hardening; feature freeze at 04:30 with test evidence and no contract ambiguity.
04:30-10:30 (P6): UI/demo/submission only. Polish your component, verify integration, rehearse, support backup video and Devpost.

## Required checks
- Induction for 30 players completes in under 60 s (record actual); every society passes validation before anyone sees it.
- Everyone placed once; size 3-5; blocked pair society rejected and re-solved; fewer players than 3; duplicate or made-up member IDs rejected.
- Flagged answer never in any society or theme; deleted answer absent from re-run.
- No theme or sharedMeaning exposed to non-operators; theme labels pass no-quote check (no 5+ consecutive words from any answer).
- Loose-match label shown; no player left out. Baseline comparison recorded with actual results only.
Report exact commands/results; do not manufacture performance or quality numbers. Fixture or fake-provider tests prove local behavior, not live Muse integration; label every synthetic element.

## Branch workflow
```sh
git fetch origin
git switch --track origin/role/rishi-matching
# If local branch exists: git switch role/rishi-matching
git merge origin/main
git status --short
```
Only merge main into a clean branch. Use a separate worktree for another agent, not a shared checkout switched underneath it. Push to role/rishi-matching; do not force-push. Shared contract modifications go through an explicit producer/consumer agreement in docs/DECISIONS.md and merge before dependent work.

## First prompt for your coding agent
Read AGENTS.md, PROJECT_KNOWLEDGE.md, docs/DECISIONS.md (D009), contracts/constellations.ts, docs/roles/rishi.md and docs/handoffs/rishi.md. Confirm the current branch is role/rishi-matching. First record my D009 ACK. Inspect existing code, preserve unrelated edits, and implement the first incomplete checkpoint in my owned paths, adapting the merged modules named above. Use the common contracts; report a concrete interface mismatch instead of creating a private incompatible version. Keep my handoff/log updated with verified evidence. Constellations has a separate feature UI at web/src/features/constellations/ inside the existing mock Facebook shell.
