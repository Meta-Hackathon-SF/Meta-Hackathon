# Live reasoning evals: does Muse drive the game? (2026-11-13)

Author: Adam (`@adamzhang06`). Four eval agents ran in parallel through one shared, capped harness (`tests/providers/live_evals/evalkit.py`). All inputs were synthetic.

- **Every call** went through the production `MuseAdapter`, which does schema validation, retries and evidence logging.
- **Prompts:** the real ones for existing tasks; experiment prompts were registered under separate prompt versions.
- **Spend:** about $1.21 over 285 calls, all valid on first try or after one retry (`ledger-2026-11-13.jsonl`, counts only).
- **Ledger fields:** agent, model, task, prompt version, outcome, attempts, latency, token counts and estimated cost. No payloads or outputs.
- **Reproducing:** scripts, corpora and results are in `tests/providers/live_evals/`. They are manual and paid, and pytest never collects them.

Treat cells with 1-4 runs as directional, not statistically strong.

## Models on the team key (GET /v1/models, 2026-11-13)

| Model | Price per 1M tokens (in / out) | Small-call latency | Notes |
|---|---|---|---|
| `muse-ember-1.0` | $0.10 / $0.50 | 0.9-3 s | Occasional ~68 s stall (provider queueing) |
| `muse-spark-1.3` | $1.25 / $4.25 | 7-16 s | Previous default |
| `muse-wonder-1.0` | $4.00 / $20.00 | 3-11 s, once 74 s | Preview; latency varies widely |

- Prices are from https://dev.meta.ai/docs/pricing-rate-limits. Contributor-mode models stay rejected, because Meta trains on their prompts.
- Reasoning tokens are about 95% of output tokens on every model.

## A. Formation (M4 grouping)

Scores are pairwise precision (P) and recall (R) against gold labels.

| Experiment | Result |
|---|---|
| Repo gold set (30 players, 6 meanings, paraphrases with little word overlap) | Keyword baseline 0.13. Spark 0.95 / 0.88 (2 runs). Ember 0.98 / 0.89 (3). Wonder 1.0 / 1.0 (1). **Muse decides grouping; keywords score at chance.** |
| Short, question-dependent answers ("nobody", "every day") | Answers only: Spark 0.72-0.96 / 0.52-0.83, Ember 0.53-0.60, Wonder 0.67 / 0.48. **With questionId + question text: 1.0 / 1.0 on all three models** (5 runs), and fewer reasoning tokens. |
| Activity hints | Tie players (same generic meaning): 0.20 before; 1.0 with hints in 11 of 12 runs. Strong-meaning players were never moved by conflicting activity (0 of 30 pairs). Server-computed affinity pairs did as well as raw topics while sending Muse less. |
| Themes into M4 | No gain (0.96 / 0.83) at 2.5x the cost and +15 s, so the parallel schedule stays. |
| Validity stress (32 players, blocked pairs) | 5 of 5 valid first try: no invented ids, wrong sizes or blocked pairs. |

Failure modes seen:
- **Over-splitting:** 6 of 17 runs used size-3 groups that split one meaning.
- **Ignored hints:** Spark ignored the hints once.
- **Uncalibrated confidence:** wrong groupings also reported 0.7-0.9.
- **Near-paraphrase:** `sharedMeaning` sometimes came close to an answer's wording.

## B. Post topics (proposed M9 `activity_classification`)

81 synthetic texts, plus a 38-text holdout written after the prompt was frozen. Hard cases include negation, sarcasm, other languages, emoji, injection and "liked:" items.

| System | F1 | Sensitive texts that still produced a topic | $ per 100 texts |
|---|---|---|---|
| Keyword list (today) | 0.47 / 0.42 | **18 of 20 / 7 of 14** (e.g. "study" from "Bible study group") | 0 |
| Ember low | 0.98 / 0.98-1.00 | 0 / 0 (34 of 34 flagged, 0 of 85 false flags) | $0.006 |
| Spark low | 0.99 / 0.96 | 0 / 1 (missed "liked: Campus Food Pantry") | ~$0.10 |

Ember was consistent across two runs (79/81 and 37/38 identical). Adding OutputGuard on top of the keyword list made it worse.

## C. Safety

Part 1, the real OutputGuard (offline):
- **Paraphrased sensitive names blocked:** 8 of 44.
- **Variants blocked:** 0 of 14 plurals, 1 of 8 homoglyphs, 0 of 8 leetspeak.
- **No-quote check:** one look-alike letter per 5-word window gets past it.
- **Code pre-screen:** misses "kms", "k1ll myself" and "unalive".
- **A folding prototype:** 45 of 49 sensitive and 23 of 25 variants blocked, with 0 of 35 benign false positives.

Part 2, the proposed M10 `sensitivity_screen` (fixed enum, fail closed):
- **Spark low:** 114 of 114 caught, 0 false positives, 8 of 8 injections resisted.
- **Ember low:** 113 of 114.

Part 3, production M1 `safety.v1`:
- **Ember low:** exact on all 56 calls, 1.2 s, $0.0002 each.
- **Spark low:** missed one indirect case ("wish I could just not exist for a bit").
- **The pre-screen alone** catches only 3 of 18 risky cases; Muse is the real screen.

## D. Model routing (real services and prompts, 74 calls)

| Task | Best | Why |
|---|---|---|
| M1 safety | Ember low | Exact, 1.2 s, hot path |
| M2 clarify | Ember minimal | 10 of 10 valid, p50 0.9 s, $0.0001 (Spark low p50 7.3 s) |
| M5 naming | Wonder low | Rated 4.5 of 5 vs Spark 3.5; precomputed before reveal |
| M6 questions | Spark low | Good; Wonder not clearly better |
| M7 nudge | Spark low | Better venue fit than Ember |
| M8 Sky | Wonder low | Spark failed the number or guard checks in 3 of 6 runs (mixed up percents and counts). **Never Spark for M8.** |
| M4 grouping | Ember low with questions (pending E-formation-v2 confirmation) | On par with Spark, 3-5x faster, ~10x cheaper; weakest without questions |

These are implemented as `MEASURED_ROUTES` in `server/providers/router.py`, with fallbacks on timeout, rate limit, outage or malformed output. Fallbacks never run past the caller's deadline. M3 and M4 stay on the base model until questions reach the formation payload.

## What changed because of this

| Change | Where | Status |
|---|---|---|
| Model router with measured routes; Wonder and Ember support; token and cost logging | `server/providers` | On `role/adam-planning`. Kai must build the port with `build_muse_router`. |
| Contract 2.2.0 (D014): questionId, questions and affinity for M3/M4; M9 and M10 | `contracts/protocol.ts`, `server/providers/contract.py` | **PROPOSED, needs ACKs** |
| Sky no-quote fix; client-asserted friend count switched off | `server/matching` (#53) | Awaiting Rishi's review |
| Formation v2: questions, affinity, correction on re-solve, sharedMeaning guard | `adam/rishi-formation-v2` | In progress, for Rishi's review |
| Guard folding, terms, pre-screen, approved event ids at `PUT /me/activity` | `adam/patrik-guard-fold` | In progress, for Patrik's review |
| M9 topic classifier, M10 sensitivity screen, snapshot questionId | `adam/patrik-muse-classifiers` | In progress, for Patrik's review and **privacy sign-off** (post text would go to Muse transiently) |
