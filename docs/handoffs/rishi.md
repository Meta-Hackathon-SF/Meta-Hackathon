# rishi handoff
Current step: 4 + 7/8 numbers (formation core, contract alignment, Sky prevalence) fixture-verified
Status: implementing (fixture-verified only; no live Muse call, no real snapshot yet)
Branch + commit: role/rishi-matching (see PR "feat: semantic formation core")
Completed tasks (docs/roles/rishi.md):
- 1 Archive reviewed: Group Quests matching (time windows, budgets) does not fit 2.0.0; only patterns reused (strict JSON parsing, exact-key checks, one retry, payloads never logged). No archived files restored.
- 2 Stdlib frozen-dataclass models with validators mirroring protocol.ts 2.0.0 (camelCase `to_wire`): PromptText, FormationSnapshot, MuseCallEvidence, Theme, Constellation, FormationResult. Stdlib only so it runs before Kai's pyproject lands.
- 3 Keyword baseline (weighted bag of words, cosine) + constrained backtracking partition (3-5, once each, blocks). Splits Maya and Dev on week-sample.
- 4 M3/M4 payload builders and strict parsers; FormationService pipeline.
- 5 Validator; one M4 re-solve; deterministic "Fallback grouping" (labeled, isLooseMatch) or retryable PROVIDER_UNAVAILABLE when fallback disabled.
- 6 M5 naming in parallel, fixed shape/color sets, OutputGuard check, fixed fallback name.
Changed interfaces and files: server/matching/{__init__,models,baseline,validation,prompts,ports,formation}.py; tests/matching/{conftest,adapters,test_formation}.py. No contract change.
Checks run + actual result: `python -m pytest tests/matching -q` -> 25 passed (Python 3.10, pytest 8.3.3). `ruff check --select E,F,I,UP,B,ASYNC --ignore UP038 --line-length 100` -> clean.
Fixture versus live evidence: fixture only. FakeMuse is scripted, so tests prove mechanics, validation and guards, not grouping quality. 30-player run measured with fallback path only (no Muse latency).

## Sky (task 7, added 2026-11-13)
- server/matching/sky.py: compute_themes (count, actualPercent = round(100*count/eligible), guessedPercentMedian of member guesses; suppressed if count < threshold, no member guesses, or label fails OutputGuard; suppressed labels never leave the module), M8 payload exactly M8In, strict M8 parse with number check (every number must be a server number), OutputGuard on headlines, one retry then template headlines, labeled synthetic signals (never merged), formation_debug (ids only).
- SkyService(muse, guard).compute(cycleId, formationResult, guesses, threshold, ...) -> SkyStats.to_wire() key-for-key with contracts/fixtures/sky-stats.json.
- Composition for FormationPort.computeSky(cycleId, threshold): Kai passes the committed FormationResult; Patrik supplies guesses {playerId: percent}. Ask open to @patrikliska13 for a `prevalenceGuesses(cycleId)` method on PrivacyPort.
- Contract fix (PR #16): isFallback internal only, fallback via guarded name "(Fallback grouping)" + isLooseMatch; M3/M4/M5 payloads exactly M3In/M4In/M5In; form(cycleId) requestId optional.
- Checks: `python -m pytest tests/matching -q` -> 43 passed; ruff clean. Fixture only; no live Muse call.

## Muse wiring (task 9, added 2026-11-13)
- server/matching/muse_specs.py registers M3/M4/M5/M8 with Adam's TaskRegistry via `contract_spec` (schemas from server/providers/contract.py); names and headlines also carry MUSE_VOICE.
- server/matching/live_eval.py: `python -m server.matching.live_eval --players 30 [--live]`. Offline run through Adam's FixtureMuse: 30 synthetic players -> 6 constellations of 5, no fallback, evidence M3/M4/M5/M8 all `replay`.
- Live timing pending: no MUSE_API_KEY in this environment. Run `python -m server.matching.live_eval --players 30 --live` with MUSE env set and record formationTimingsMs here.
- Kai: compose with `register_formation_specs(registry)` when building the shared adapter.
- Formation debug UI: `web/src/features/constellations/formation` exports `FormationDebug` + `parseFormationDebug` (ids only, "Operator only", Fallback grouping badge, Muse chips). @willapat mounts it in the operator console.
- Checks: pytest tests/matching -> 46 passed; ruff clean.

## Quality eval (added 2026-11-13)
- server/matching/evaluation.py: labeled synthetic gold set (6 feelings x 5 paraphrases, little word overlap) + pairwise precision/recall.
- `python -m server.matching.live_eval --gold --players 30 [--live]`. Keyword baseline on gold: precision 0.15, recall 0.15 (9/60 gold pairs; random about 0.17). The Muse number only means something with --live; the fixture Muse is scripted and reported as such.
- Partition stress: 30/10, 80/40, 80/120, 200/300 (players/blocks) all valid in 0.02 s or less.
- Still blocked for integration (not for my tasks): Patrik's OutputGuard and formationSnapshot are not on main or his branch; asked in #16.

## M4 repair (added 2026-11-13)
- server/matching/repair.py: near-valid M4 proposals (missing/duplicate/unknown ref, group of 6 or 2, blocked pair) are fixed by code instead of spending the re-solve call. Every legal Muse group is kept; evicted refs are re-placed by keyword affinity, with a swap step when groups are full. Touched groups get confidence capped at 0.49, so they read "looser this week". If fewer than half the refs survive in their Muse group, it gives up: re-solve, then Fallback grouping.
- Fuzz: 375/400 random broken proposals repaired, 0 invalid outputs. Saves one Muse round trip (about 20 s observed) whenever a live M4 is near-valid.
- `FormationResult.repaired_groups` (internal) counts groups code fixed; not a wire field.
- Checks: pytest tests/matching -> 57 passed; ruff clean.

## MatchingPort for Kai (added 2026-11-13)
- server/matching/port.py: `build_matching_port(muse=, snapshots=, guesses=, guard=)` -> object with `form(cycleId) -> dict` (exact FormationSuccess/FormationFailure wire, never raises for provider trouble) and `computeSky(cycleId, threshold) -> SkyStats dict`. Private themes stay in a ThemeStore inside matching (in-memory default; durable store pluggable).
- Verified against Kai's real `server.orchestration.wire.FormationSuccess/FormationFailure` and `domain.validate_partition` from origin/role/kai-orchestration (scratch copy, not a committed test): normal, re-solve, fallback and failure paths all pass.
- Needs from Patrik: `prevalence_guesses(cycleId) -> {playerId: percent}` (GuessSource), `formation_snapshot(cycleId)`, OutputGuard `check`.
- Checks: pytest tests/matching -> 64 passed; ruff clean.

## Interface assumptions (need ACK, not blocking)
- Patrik `@patrikliska13`: `formationSnapshot` returns `answers[].id` as one random ref per PLAYER (shared by all that player's answers), `weight` per answer, `idMap` ref->playerId, `blockedPairs` as playerIds. Players with any distress/harm flag this cycle are excluded entirely. Prevalence guesses will be needed for computeSky (shape TBD).
- Adam `@adamzhang06`: Python MusePort is `async run(*, task, requestId, promptVersion, payload, signal=None) -> {"output", "evidence"}` with evidence in MuseCallEvidence wire shape. Formation sends `instructions` inside payload; tell me if the adapter owns system prompts instead.
- Kai `@beatopia`: call `FormationService(muse, snapshots, guard).form(cycleId, requestId)`; `FormationResult.to_wire(requestId)` matches FormationPort; `constellations[].isFallback` must render "Fallback grouping".

## Requests answered
(none open on 2026-11-12)

## Blocked on
(none)

## Next action
Run live 30-player timing once a Muse key is available; swap FixtureGuard/_AllowAll for Patrik's OutputGuard when it lands on main.
