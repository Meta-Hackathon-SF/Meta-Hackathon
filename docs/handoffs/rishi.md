# rishi handoff
Current step: 4 (formation core) started early against fixtures; step 2 foundation for my area done
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

## Interface assumptions (need ACK, not blocking)
- Patrik `@patrikliska13`: `formationSnapshot` returns `answers[].id` as one random ref per PLAYER (shared by all that player's answers), `weight` per answer, `idMap` ref->playerId, `blockedPairs` as playerIds. Players with any distress/harm flag this cycle are excluded entirely. Prevalence guesses will be needed for computeSky (shape TBD).
- Adam `@adamzhang06`: Python MusePort is `async run(*, task, requestId, promptVersion, payload, signal=None) -> {"output", "evidence"}` with evidence in MuseCallEvidence wire shape. Formation sends `instructions` inside payload; tell me if the adapter owns system prompts instead.
- Kai `@beatopia`: call `FormationService(muse, snapshots, guard).form(cycleId, requestId)`; `FormationResult.to_wire(requestId)` matches FormationPort; `constellations[].isFallback` must render "Fallback grouping".

## Requests answered
(none open on 2026-11-12)

## Blocked on
(none)

## Next action
Task 7 computeSky (prevalence, threshold, M8 with number check), then formation debug view, then live timing once Adam's adapter lands.
