# Adam: Keeper prompts and Muse jobs
Branch: `role/adam-planning` (unchanged). Read root AGENTS.md, PROJECT_KNOWLEDGE.md, docs/DECISIONS.md D009 and `contracts/constellations.ts` (version `2.0.0-proposed`) first. `contracts/protocol.ts` 1.x stays as legacy until you migrate; do not delete it.

Product: Constellations, a campus secret-society game inside Facebook Groups. Muse is the Keeper (game master). Weekly Confession, Induction into societies of 3-5 by meaning, Hunt with 3-level riddles, in-person passphrase/found-code confirm, Sky reveal (guessed vs actual prevalence), then a Ritual quest (P1). Friendship only, 18+. Muse proposes, code enforces.

## Mission
Start with [your phase-by-phase build checklist](../phases/adam.md). It specifies paths, work, dependencies, exit evidence and handoffs for P0-P6 on the re-based timeline (P0 16:00 PST, freeze 04:30, deadline 10:30 AM PST Nov 13, team-supplied and not independently verified).

Own the single Muse adapter and the Keeper voice/prompting rules so no one else invents provider APIs. Build Muse jobs M2 (clarify), M5 (society identity), M6 (riddle chains), M7 (ritual quest, P1) and M8 (Sky narration), and the Hunt view. The Keeper is warm, mysterious, never clinical, never therapeutic.

First action: record your ACK of D009 (proposed ownership and contract 2.0.0) in docs/DECISIONS.md or the PR discussion.

## Ownership
- `server/planning/`
- `server/providers/`
- `web/src/features/constellations/planning/` (shared Keeper presentation if needed)
- `web/src/features/constellations/hunt/` (riddle cards, Hunt view)
- `tests/planning/`
Also own this role document, docs/handoffs/adam.md and docs/updates/adam.md.
UI moves from `web/src/features/group-quests/<area>/` to `web/src/features/constellations/<area>/`; Will migrates the shell. Merged Group Quests code stays until migrated.

## Reuse of merged modules
`server/providers/` Muse adapter (live-verified `muse-spark-1.3`, 2 calls) and `server/planning/` propose/validate loop, prompt modules, public_text and EvidenceBadge. Adapt: add Constellations task names, Keeper system prompt, strict JSON with one retry then labeled fallback. Group Quests planner/catalog modules stay untouched legacy except the venue catalog reused for M7.

## Producer/consumer contract
Inputs: validated societies from Rishi; `Answer` text under random IDs plus approved `FindableDetails` from Patrik; server-computed counts from Kai (M8); approved public venue list and budget cap (M7).
Outputs: `MusePort` adapter plus test fake; `callType` evidence for M1..M8; clarify result (max one follow-up per player per round); society identity (`name`, `motto`, `sigilId`, `colorId`, `phraseA`, `phraseB`); per target per seeker `Riddle` levels 1-3 (cryptic, medium, direct); `RitualQuest`; Sky `headlines[]`.
Give Rishi the adapter and fake early; give Kai job function signatures that can run in parallel; give Will the M2 clarify endpoint contract; give Patrik every Muse text output for the guard.

## Muse jobs owned
M2 clarify, M5 society identity, M6 riddles (strongest model; must be findable in person, never reveal or closely paraphrase the confession), M7 ritual quest (P1), M8 Sky narration (receives server counts only, never raw answers; every number must match server counts exactly). Rishi owns M3/M4; Patrik owns M1.
Muse model verified live: `muse-spark-1.3` (provider echoed the model). Observed single-call latency 17-24 s at low reasoning effort (2 calls, not a benchmark), so fan-out must be parallel. Every Muse response shown in the UI carries a chip: model, call type, latency; cached responses are labeled "Replay of a saved round."

## UI owned
Riddle cards / Hunt view: released levels only, level badge, Demo timing label on accelerated unlocks (20 s or operator tap), Muse metadata chip.

## Implementation sequence
1. Reconfirm model/endpoint with the existing adapter (`muse-spark-1.3` echoed live; Wonder/Ember were not available in docs read and are untested). Record config without secrets.
2. Add the Keeper system prompt and per-job JSON schemas; invalid JSON gets one retry then a labeled fallback; provider outage is a retryable error, cached response only if labeled "Replay of a saved round."
3. Implement M5 and M6 as independently callable parallel jobs (per society, per target/seeker) so Kai can fan out; M6 uses only approved findable details; every output goes through Patrik's no-quote and sensitive-term guard before release; M6 includes a self-check field.
4. Implement M2 clarify (needs_followup, question), M8 narration validated against server counts, then M7 (venue from approved public list, under budget, public places only).
5. Hunt view renders released riddle levels and honest labels; loading, error and retry states.

## Checkpoints
H0-1 (16:00-17:00 PST, P0): ACK D009 first, confirm dependencies, claim shared files.
17:00-20:00 (P1): module runs alone against labeled synthetic fixtures with clear status.
20:00-23:00 (P2): integrated round on 3+ phones: join, confess, induct, riddles, confirm.
23:00-02:00 (P3): Sky, safety triage, blocks and operator console complete; failure cases pass.
02:00-04:30 (P4/P5): P1 features (ritual, riddle veto) only if the critical path is green; hardening; feature freeze at 04:30 with test evidence and no contract ambiguity.
04:30-10:30 (P6): UI/demo/submission only. Polish your component, verify integration, rehearse, support backup video and Devpost.

## Required checks
- Malformed JSON retried once then labeled fallback; provider timeout; prompt injection inside an answer.
- Prompt payload unit test: only random player IDs and answer text; no names, emails, photos or session tokens (Patrik's builder).
- Riddle: no substring of 5+ words from any answer; no sensitive category; red-team list of 30 answers run through the guard; riddle findable in public space only.
- M5 sigil/color from fixed sets, name passes no-quote check; M8 every number matches server counts; M7 venue outside allowlist rejected, nothing created without 3+ approvals.
- Live vs replay metadata correct on every chip. Report actual latencies; fixture tests are not live evidence.
Report exact commands/results; do not manufacture performance or quality numbers. Fixture or fake-provider tests prove local behavior, not live Muse integration; label every synthetic element.

## Branch workflow
```sh
git fetch origin
git switch --track origin/role/adam-planning
# If local branch exists: git switch role/adam-planning
git merge origin/main
git status --short
```
Only merge main into a clean branch. Use a separate worktree for another agent, not a shared checkout switched underneath it. Push to role/adam-planning; do not force-push. Shared contract modifications go through an explicit producer/consumer agreement in docs/DECISIONS.md and merge before dependent work.

## First prompt for your coding agent
Read AGENTS.md, PROJECT_KNOWLEDGE.md, docs/DECISIONS.md (D009), contracts/constellations.ts, docs/roles/adam.md and docs/handoffs/adam.md. Confirm the current branch is role/adam-planning. First record my D009 ACK. Inspect existing code, preserve unrelated edits, and implement the first incomplete checkpoint in my owned paths, adapting the merged modules named above. Use the common contracts; report a concrete interface mismatch instead of creating a private incompatible version. Keep my handoff/log updated with verified evidence. Constellations has a separate feature UI at web/src/features/constellations/ inside the existing mock Facebook shell.
