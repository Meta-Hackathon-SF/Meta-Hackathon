# Rishi: semantic formation, validation, prevalence
Branch `role/rishi-matching` · Handle `@rishibagri` · Build order steps 4 and 7 (see [docs/PLAN.md](../PLAN.md))

## You own
| Path | What |
| --- | --- |
| `server/matching/` | FormationPort: snapshot in, validated constellations out; keyword/embedding baseline; M3, M4, M5, M8 prompts (run through Adam's MusePort); validator; prevalence and SkyStats computation; synthetic aggregate signals |
| `tests/matching/` | unit and fixture tests |
| `web/src/features/constellations/formation/` | operator-only formation debug view: baseline vs Muse grouping, ids only |

Not yours: Sky UI rendering (Kai), Muse transport (Adam), storage of answers (Patrik), cycle timing (Will).

## Interfaces
Produce: `FormationPort.form(cycleId)` and `FormationPort.computeSky(cycleId, threshold)` (contracts/protocol.ts), types `Theme`, `Constellation`, `SkyStats`, `SkyTheme`, `SyntheticSignal`.
Consume: `PrivacyPort.formationSnapshot` (Patrik), `MusePort.run` (Adam), `OutputGuard.check` (Patrik), `PrevalenceGuess` rows (Will, via Patrik snapshot).
Until those land, use a labeled test-only adapter over `contracts/fixtures/week-sample.json`.

## Tasks
1. Restore and adapt from `archive/group-quests-before-pivot`: `server/matching/{feasibility,evaluation,eval_cli}.py` patterns only where they fit; rename to Constellations terms; retest.
2. Frozen Python dataclasses (standard library, no Pydantic) mirroring protocol.ts 2.0.0 for Theme, Constellation, SkyStats, with hand-written `from_dict` validators and camelCase `to_wire()`. Chosen so matching runs without installed dependencies; output is plain JSON and passes Kai's Pydantic wire validators.
3. Baseline grouper (keyword/TF-IDF or embeddings) with weights. Must split Maya and Dev in `week-sample.json` so the demo shows Muse joining them.
4. M3 theme discovery + M4 formation prompts (group by meaning, not keywords; weights as confidence hints; blocked pairs listed). Strict JSON, schema validation.
5. Validator: size 3-5, everyone placed once, no blocked pair, distress excluded, loose-match label, one re-solve then deterministic fallback labeled "Fallback grouping".
6. M5 naming per constellation in parallel; names through OutputGuard; shapeId/colorId from fixed sets.
7. `computeSky`: per theme count, actualPercent (count / eligible), median guess, threshold filter (3 demo / 25 prod), suppressed count only. M8 headlines with number-by-number check, template fallback.
8. (Step 7, cuttable) `SyntheticSignal` generator from a synthetic population, labeled, never merged with real counts.
9. Measure formation latency for 30 synthetic players; record in handoff.

## Acceptance checks
- `pytest tests/matching` green offline (fake MusePort).
- week-sample: Maya + Dev together, Omar + Ren apart, Ana excluded, injection text has no effect.
- Theme with 2 members never in SkyStats; every M8 number equals a server count.
- No name or headline quotes 5+ words of any answer (fuzz).
- 30 players formed in under 60 s on live Muse, or measured number recorded honestly.
