# Adam: Keeper prompts and Muse jobs
Branch: `role/adam-planning`. Read root AGENTS.md, PROJECT_KNOWLEDGE.md, docs/COORDINATION.md, docs/DECISIONS.md (D001, D003) and `contracts/protocol.ts` (`CONTRACT_VERSION` 1.0.0, pending D001/D003 ACK) first.

Product: Constellations, a campus secret-society game inside Facebook Groups. Muse is the Keeper (game master). Weekly Confession, Induction into societies of 3-5 by meaning, Hunt with 3-level riddles, in-person passphrase/found-code confirm, Sky reveal (guessed vs actual prevalence), then a Ritual quest (P1). Friendship only, 18+. Muse proposes, code enforces.

## Mission
Start with [your phase-by-phase build checklist](../phases/adam.md). It specifies paths, work, dependencies, exit evidence and handoffs for P0-P6 on the re-based timeline (P0 16:00 PST, freeze 04:30, deadline 10:30 AM PST Nov 13, team-supplied and not independently verified).

Own the single Muse adapter and the Keeper voice/prompting rules so no one else invents provider APIs. Build Muse jobs M2 (clarify), M5 (society identity), M6 (riddle chains), M7 (ritual quest, P1) and M8 (Sky narration), and the Hunt view. The Keeper is warm, mysterious, never clinical, never therapeutic.

First action: check for tags (docs/COORDINATION.md §1), then record your ACK of D001 (product and ownership) and D003 (contract `contracts/protocol.ts` v1.0.0), both pending ACK, in docs/DECISIONS.md or the PR discussion.

## Ownership
- `server/planning/`
- `server/providers/`
- `web/src/features/constellations/planning/` (shared Keeper presentation if needed)
- `web/src/features/constellations/hunt/` (riddle cards, Hunt view)
- `tests/planning/`
Also own this role document, docs/handoffs/adam.md and docs/updates/adam.md.
UI lives at `web/src/features/constellations/<area>/` inside the existing mock Facebook shell.

## Starting point
Fresh build; no Muse adapter or planning code exists on main. Build the single Muse adapter, test fake, Keeper prompts and Hunt view in the owned paths.

## Producer/consumer contract
Inputs: validated societies from Rishi; `Answer` text under random IDs plus approved `FindableDetails` from Patrik; server-computed counts from Kai (M8); approved public venue list and budget cap (M7).
Outputs: `MusePort` adapter plus test fake; `callType` evidence for M1..M8; clarify result (max one follow-up per player per round); society identity (`name`, `motto`, `sigilId`, `colorId`, `phraseA`, `phraseB`); per target per seeker `Riddle` levels 1-3 (cryptic, medium, direct); `RitualQuest`; Sky `headlines[]`.
Give Rishi the adapter and fake early; give Kai job function signatures that can run in parallel; give Will the M2 clarify endpoint contract; give Patrik every Muse text output for the guard.

## Muse jobs owned
M2 clarify, M5 society identity, M6 riddles (strongest model; must be findable in person, never reveal or closely paraphrase the confession), M7 ritual quest (P1), M8 Sky narration (receives server counts only, never raw answers; every number must match server counts exactly). Rishi owns M3/M4; Patrik owns M1.
Muse model: `muse-spark-1.3` was echoed by the provider during earlier testing on the archived branch; re-verify on this build. Observed single-call latency 17-24 s at low reasoning effort (2 calls, not a benchmark), so fan-out must be parallel. Every Muse response shown in the UI carries a chip: model, call type, latency; cached responses are labeled "Replay of a saved round."

## UI owned
Riddle cards / Hunt view: released levels only, level badge, Demo timing label on accelerated unlocks (20 s or operator tap), Muse metadata chip.

## Implementation sequence
1. Reconfirm model/endpoint with one call (`muse-spark-1.3` echoed live earlier; Wonder/Ember were not available in docs read and are untested). Record config without secrets.
2. Add the Keeper system prompt and per-job JSON schemas; invalid JSON gets one retry then a labeled fallback; provider outage is a retryable error, cached response only if labeled "Replay of a saved round."
3. Implement M5 and M6 as independently callable parallel jobs (per society, per target/seeker) so Kai can fan out; M6 uses only approved findable details; every output goes through Patrik's no-quote and sensitive-term guard before release; M6 includes a self-check field.
4. Implement M2 clarify (needs_followup, question), M8 narration validated against server counts, then M7 (venue from approved public list, under budget, public places only).
5. Hunt view renders released riddle levels and honest labels; loading, error and retry states.

## Checkpoints
H0-1 (16:00-17:00 PST, P0): check tags (COORDINATION §1), ACK D001/D003, confirm dependencies, claim shared files.
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

## Coordination
Full protocol: [docs/COORDINATION.md](../COORDINATION.md). Your handle is @adamzhang06.
- Before any work session, check open PRs and issues for tags addressed to you (COORDINATION §1) and answer them first with `ACK`, `CHANGE: <proposal>` or `DELIVERED: <commit/PR>`.
- You depend on: Rishi (@rishibagri): validated societies; Patrik (@patrikliska13): answers under random IDs, findable details, output guard; Kai (@beatopia): Sky counts and fan-out lock.
- Others depend on you: Rishi (@rishibagri): the adapter and fake; Kai (@beatopia): parallel job signatures; Will (@willapat): the M2 clarify endpoint contract; Patrik (@patrikliska13): every Muse text output for the guard.
- When blocked on any of them: stop at the phase boundary, push your verified work, open or update a `[BLOCKED]` draft PR tagging the owner's handle with the exact block (COORDINATION §2), and continue only with a labeled test-only adapter. Do not edit their paths or silently change `contracts/`.

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
Read AGENTS.md, PROJECT_KNOWLEDGE.md, docs/COORDINATION.md, docs/DECISIONS.md (D001, D003), contracts/protocol.ts (v1.0.0, pending ACK), docs/roles/adam.md and docs/handoffs/adam.md. Confirm the current branch is role/adam-planning. First check open PRs/issues for tags addressed to me (COORDINATION §1) and answer them, then record my D001/D003 ACK. Inspect existing code, preserve unrelated edits, and implement the first incomplete checkpoint in my owned paths. If I am blocked on another owner, stop at the phase boundary, push, open or update a `[BLOCKED]` draft PR tagging them with the exact block (COORDINATION §2), and continue only with a labeled test-only adapter. Use the common contracts; report a concrete interface mismatch instead of creating a private incompatible version. Keep my handoff/log updated with verified evidence. Constellations has a feature UI at web/src/features/constellations/ inside the existing mock Facebook shell.
