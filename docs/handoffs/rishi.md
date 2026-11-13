# rishi handoff
Current step: 4 + 7/8 numbers (formation core, contract alignment, Sky prevalence) fixture-verified
Status: implementing (fixture-verified only; no live Muse call, no real snapshot yet)
Branch + commit: role/rishi-matching (see PR "feat: semantic formation core")
Completed tasks (docs/roles/rishi.md):
- 1 Archive reviewed: Group Quests matching (time windows, budgets) does not fit 2.0.0; only patterns reused (strict JSON parsing, exact-key checks, one retry, payloads never logged). No archived files restored.
- 2 Frozen Python dataclasses (not Pydantic; see docs/roles/rishi.md task 2) with hand-written validators mirroring protocol.ts 2.0.0 (camelCase `to_wire`): PromptText, FormationSnapshot, MuseCallEvidence, Theme, Constellation, FormationResult. Stdlib only so it runs before Kai's pyproject lands.
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

## Live latency fix (added 2026-11-13, after Adam's live run on #21)
- Adam's live run, 30 players, muse-spark-1.3: M3 21.5 s + M4 38.8 s sequential, M5 phase 70 s (two hung calls retried), formation 130.5 s, with Sky 149.3 s. Every output passed schemas first try; no repair needed. Missed the 60 s target by more than 2x.
- Changes: M3 and M4 run concurrently (M4 gets no themes; themes feed Sky only). `parallel_themes=False` restores the old order. M5 makes one attempt with a 20 s cap, then a fixed name with no retry. M8 Sky precompute runs alongside M5 through `on_grouped` and is cached in MatchingPort. M3/M4 timeout raised to 75 s so the adapter's own 60 s attempt can finish.
- Simulated replay of Adam's latencies at 1/100 scale (tests/matching/test_schedule.py): 59.4 s, against 130.5 s live. Thin margin. Not a live measurement.
- Risk: M4 without themes may group worse. Measure with `live_eval --gold --live` (parallel vs `parallel_themes=False`).
- Kai: `form_once` wraps form in `wait_for(60)`. Raise it to about 120 s or every live lock will cancel.
- Checks: pytest tests/matching -> 66 passed; ruff clean.

## Live rerun + debug getter (added 2026-11-13)
- Adam live rerun on #26 (one run, 30 players): M3||M4 29.2 s, naming 20.0 s (2 of 6 hit the 20 s cap and got fixed names), formation 49.2 s, Sky 19.8 s after. Under 60 s for formation. Plausible, not benchmarked. Naming cap kept at 20 s: 25 s would exceed 60 s with the first run's M4 time.
- `MatchingPort.debug(cycleId)` -> `{data: FormationDebugData, evidence, totalMs, usedFallback}`, refs only. Answers Kai's ask on #13/#26.
- live_eval now goes through MatchingPort (Sky precomputed during naming) with Patrik's real `server.privacy.OutputGuard`. Patrik's `LeasedSnapshot` fits SnapshotSource unchanged.
- Still missing from Patrik: bulk `prevalence_guesses(cycleId)` (only `get_guess(cycle, player)` exists).
- Checks: pytest tests/matching -> 69 passed; ruff clean.

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


## Review of Adam's changes (2026-11-13)
- #62 (formation v2), #53 (sky guard, friend counting off) and #60 (D014 contract 2.2.0): reviewed, ACKed with notes. Merged together with main and my pending #35: pytest 1009 passed, 2 skipped. Three lines over 100 columns in Adam's code.
- Live quality closed by Adam's evals: Muse 0.95/0.88 to 1.0/1.0 vs keyword baseline 0.13 (small runs). Themes into M4 gave no gain, and Sky is removed in v3, so day-close grouping will not call M3.
- v3 design flag (not yet in the PRD): M4 partitions into groups of 3-5 and is bounded by MAX_ANSWERS, but daily constellations have no size cap and the sky holds about 10k players. Daily clustering needs a different method: a Muse call proposes a small set of meaning tags per day, code assigns each answer to its best 1-2 tags, and each tag with 3+ players is a constellation. M4 stays for the Sunday main constellation (3-5).
- D014 builds on 2.1.0; my 3.0.0 draft will build on 2.2.0.

## v3: contract 3.0.0 draft and PRD fixes (added 2026-11-13)
- `contracts/protocol.ts` is now **3.0.0** (breaking, built on 2.2.0). Added: WeeklyCycle.answeredToday (optional until the web client sends it), DailyConstellationsView, DailyPlacement/day colors, MySkyView + SkyStarsView, FormationAttempt + ProgressEvent (`source: "trace" | "visualization"`, `isVisualization`), MainConstellationView (room-local indices, R1), EventView/EventNudge buckets (`3-5 | 6-9 | 10+`), CustomEventProposal, Invite, new StreamEvents, FormationPort v3 (`dailyPlace`, `closeDay`, `weekGraph`, `mainConstellation`, `skyLayout`). Removed from the contract: SkyStats, SkyTheme, SyntheticSignal, PrevalenceGuess, M5, M8, Constellation.name/shapeId/colorId, ChatRoom constellation title. Fixtures: `contracts/fixtures/v3-*.json`.
- PRD fixes: daily clustering method (Muse proposes tags, code assigns best 1-2, 3+ players per tag, Sunday main reuses M4); floor of 3 for anything a player sees; Patrik R1 (room-local indices in S11/chat), R2 (second degree only with 30+ eligible players), R3 (hourly-only recompute, delayed nudges); event buckets `6-9`/`10+` to match `heat_bucket`; README 2-4 to 3-5; Adam's event-id decision renumbered D015 (Patrik's live STT keeps D013).
- Deferred (follow-up PRs): remove M5/M8/guess/Sky code from `server/matching` and `server/providers` (kept so 2.x paths and tests stay green until Kai composes 3.0.0); implement the v3 producers (daily placement, day close, week graph, main constellation, sky layout, progress trace, event interest counts, cluster finder); call `AnswerStore.expired_cycles()` to purge daily-placement data on the 14-day clock.
