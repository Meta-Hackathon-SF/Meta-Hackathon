# Reasoning audit: is Muse the centre, and is it robust? (2026-11-13)

Author: Adam (`@adamzhang06`), with two read-only audit passes over matching and privacy. Main at `b49ea45`.

How each finding was checked:
- **verified**: Adam re-read the cited lines.
- **reported**: from an audit pass, not yet re-checked by Adam.

No live calls were made except the two M6 calls listed under "Fixed in this PR".

## Status update (2026-11-13T09:00Z)

Live evals have since measured most of these findings: `docs/audits/2026-11-13-live-evals.md`.
- **Muse vs keywords:** Muse decides grouping. On the gold set it scored 0.95-1.0, while keywords scored 0.13.
- **Questions, activity, topics, sensitivity:** each now has measured fixes. They need contract 2.2.0 (D014, proposed).

| Finding | State |
|---|---|
| P2 Sky no-quote | Fixed in #53 (theme labels guarded at formation; M3 gets voice rules), awaiting Rishi's review |
| P1 friend oracle | Friend count off by default in #53. Server-side id checks and the approved-eventId check at the door are on `adam/patrik-guard-fold` (in progress). Group and event counts still use client ids. |
| P3/P4 guard gaps | Measured (8/44 names, 0/14 plurals, 0/8 leet). Fold plus terms on `adam/patrik-guard-fold`; M10 sensitivity screen on `adam/patrik-muse-classifiers` (in progress) |
| Muse never sees questions or activity | Measured: questions raised P/R to 1.0 in every run, and affinity broke ties without overriding meaning. D014 plus `adam/rishi-formation-v2` (in progress). Patrik's snapshot and Kai's wiring still needed. |
| Keyword topics | Measured F1 0.47 vs Ember 0.98. M9 on `adam/patrik-muse-classifiers` (in progress); needs privacy sign-off |
| R2 identical M4 retry | Correction pass-through done; formation v2 uses it (in progress) |
| Model choice | Router with measured routes on `role/adam-planning`; Kai must switch to `build_muse_router` |
| R1 120 s deadline, R3 repair share, R4 large communities, R6 follow-up question lost, P5, P6 | Not yet addressed |

## Bottom line

Most guarantees are well enforced. Every Muse output is checked against a schema. Player text reaches Muse only as delimited untrusted data. Unknown or duplicate ids, group sizes, blocked pairs and Sky numbers are all checked by code. M1 fails closed.

But for the demo claim "AI-centred: Muse is required, code enforces", the pipeline has four gaps:

1. **Muse never sees the questions or the activity data.**
   - M3 gets `questions: []` and M4 gets answers only (`server/matching/formation.py:144,162`, verified).
   - D010 signals (Groups, Events, friends, post topics) are applied after grouping, as code closeness and display counts. They never go to Muse, so they never change who is grouped (`formation.py:291`, `closeness.py:42-48`, verified).
   - The combined app doesn't even load them: `PrivacyFormation(...)` is built without an `ActivityStore` (`server/app/weekly.py:129`, verified).
2. **Several Muse steps are decorative.** If Muse returned nothing, the same pipeline would still ship:
   - M5 names fall back to fixed colour+shape names after one 20 s attempt.
   - M8 headlines fall back to templates.
   - In parallel mode, M3 has no influence on grouping, because M4 receives `()` as its themes (`formation.py:249-251`, verified).
   - Closeness, brightness and event heat contain no Muse at all.
3. **Post topics come from a keyword list, not Muse** (`server/privacy/activity.py:32-63`, verified).
   - "I hate running" becomes `sports`, "role model" becomes `ai`, and "bible study group" becomes `study`.
   - Spanish and emoji produce nothing.
   - There is no "likes" signal anywhere, although the pitch mentions likes.
4. **Judges can't see any of the reasoning.**
   - The formation-debug endpoint always returns PROVIDER_UNAVAILABLE (`weekly.py:268-274`, verified). Baseline groups are thrown away (`formation.py:238`, reported). FormationDebug.tsx cannot render.
   - `GET /operator/calls` lists latencies only.

## Privacy and safety findings (fix before the demo)

### P1 (high, verified): friend ids let a player identify a star before reveal
- **Where:** `server/privacy/activity.py:66-72` and `server/matching/closeness.py:97-99`.
- **Problem:** the server takes `profileId`, `friendIds`, `groupIds` and `eventIds` from the request body without verifying them. The demo client sends a name slug as `profileId` and every other person as a friend (`web/.../daily/activity.ts:50-53`).
- **Attack:** an attacker lists the victim's slug as a friend and checks whether `alreadyFriends` reads 1. That tells them the victim is in their anonymous room.
- **Fix:** hide `alreadyFriends` before mutual reveal, or show it only when it is at least 2. Take ids from the server session rather than the body. Check `eventIds` against the approved catalog, as D010 point 4 requires (issue #44).
- **Owners:** Patrik, Rishi.

### P2 (high, verified): the no-quote check never runs on Sky output
- **Where:** `sky.compute_from` defaults `answer_texts=()`, and both callers omit it (`server/matching/port.py:83`, `sky.py:246`).
- **Problem:** theme labels and headlines are guarded against an empty list, so a Muse label that quotes five or more words of an answer would be published.
- **Also:** M3 is registered as not player-visible, so it doesn't get the voice rules, yet its labels are shown in the Sky.
- **Fix:** pass the snapshot answer texts into Sky, mark M3 as player-visible, and add a test.
- **Owner:** Rishi.

### P3 (high, reported): OutputGuard misses paraphrased sensitive names
- **Where:** `server/privacy/guard.py:56-102`.
- **Problem:** "Stars whose mothers died", "Night owls who take Prozac", "Ex-Mormons" and "First-gen kids on scholarship" all pass. Plurals such as "therapists" and "catholics" also pass.
- **Why it matters:** M5 names are seen by every member, so Muse is effectively the only real gate here.
- **Fix:** add plural matching and the missing terms. Then add a Muse sensitivity classifier that returns a fixed enum, with code failing closed on anything except `none`. Muse proposes, code enforces the enum.
- **Owner:** Patrik.

### P4 (medium, reported): homoglyphs, leetspeak and slang get past the guard and the M1 pre-screen
- **Examples:** "dеpression" with a Cyrillic е, "k1ll myself", "kms" and "unalive myself" all pass.
- **Fix:** fold confusable characters, map leetspeak, collapse spaced-out letters, and add the slang terms.
- **Owner:** Patrik.

### P5 (medium, reported): the no-quote check is exact 5-word matching only
- **Problem:** paraphrase isn't covered.
- **Fix:** document this honestly, or add a 4-word window for short answers.
- **Owner:** Patrik.

### P6 (low, reported): a Sky theme with a single guess publishes that person's guess as the median
- **Fix:** require at least `threshold` guesses before showing a median.
- **Owner:** Rishi.

## Robustness findings

### R1 (high, partly verified): formation can hit its 120 s ceiling before its own fallback runs
- **Verified:** the ceiling is 120 s (`server/orchestration/runtime.py:45`), and M4 allows 2 attempts of 75 s each (`formation.py:46,50`).
- **Reported:** formation also waits on the Sky M8 hook, which allows 2 attempts of 45 s each.
- **Failure:** one hung M4 attempt plus a slow M8 gets the job cancelled, so the keyword fallback never runs.
- **Fix:** use one overall deadline that keeps time back for the fallback, and don't wait on the Sky hook inside formation.
- **Owners:** Rishi, Kai.

### R2 (medium, verified): M4's second attempt resends exactly the same prompt
- **Problem:** a retry at temperature 0.4 is just a re-sample, and the matching code couldn't attach feedback.
- **Fixed on my side:** `KeywordMusePort.run(..., correction=...)` now forwards a correction to the retry.
- **Still needed:** Rishi should pass violation codes as the correction, for example "2 unknown member ids; group 3 has 6 members". Ids and counts only.
- **Owner:** Rishi.

### R3 (medium, reported): repair can re-place up to half the members by keywords and still count as a Muse result
- **Where:** `MIN_KEPT_SHARE=0.5` in `repair.py:25`.
- **Problem:** `repairedGroups` and moved members are never surfaced.
- **Fix:** raise the share to about 0.8 and show the repair in the debug view.
- **Owner:** Rishi.

### R4 (medium, reported): communities over about 80 players always get keyword grouping, silently
- **Cause:** the input schema caps answers at 400 and payloads at 256 KB.
- **Fix:** sample or cap the input, and record a reason code when this happens.
- **Owner:** Rishi.

### R5 (medium, reported): "closeness" is keyword cosine plus an activity boost
- **Problem:** pairs that Muse grouped by meaning but who share no words read "faint". Two shared Groups alone read "bright", so brightness can contradict Muse's grouping.
- **Fix:** have M4 return per-member affinity (numbers validated by code) and blend it in, or cap the boost relative to the base score.
- **Owner:** Rishi.

### R6 (medium, verified): a follow-up reply loses its question
- **Where:** the UI appends the reply to the answer (`web/.../daily/QuestionPost.tsx:211`), and the follow-up question itself isn't kept.
- **Problem:** formation sees "mostly the dining hall my roommate" without knowing that "my roommate" answered "who was usually around". The combined text is also silently cut at 400 characters.
- **Fix:** store the reply with its follow-up question, and pass both to M3/M4.
- **Owners:** Will, Patrik, Rishi; needs a contract change.

### R7 (low, reported): M5 names fall back silently, and nothing checks they are unique
- **Problem:** M5 gets one 20 s attempt, while live naming took 10-25 s. The fixed fallback names aren't labeled as fallback.
- **Owner:** Rishi.

## Fixed in this PR (Adam's paths, offline tests plus 2 live M6 calls)

### `server/providers`
- **Retry feedback:** when Muse's output fails the schema, the retry now says which schema location failed. The text is character-restricted and never echoes model or player text.
- **Correction pass-through:** `KeywordMusePort.run(correction=...)` forwards a caller's code-generated correction to the retry.
- **`ReasoningTrace`** (`trace.py`) is built into every adapter as `adapter.reasoning_trace`:
  - It records one entry per call: task, call type, prompt version, model, live/replay, outcome, attempts and latency.
  - Services can attach code verdicts as `(stage, code, count)`, using fixed-vocabulary codes only.
  - Text can't be stored; invalid notes are dropped.
  - Fixture runs are always labeled `replay`.
- **Telemetry** now also includes `source`.

### `server/planning`, M6 question generation
- **Prompt `question_generation.v2`:**
  - It grounds each question in a community signal and spreads questions across different signals.
  - It asks for questions that people answer differently.
  - It requires open, non-yes/no follow-up hints.
- **Code rules:**
  - Near-duplicates are refused (≥0.6 Jaccard overlap of content words, against the bank and pending questions).
  - Categories follow the requested mix: a category weighted 0 is refused, and none may exceed its share of `count`.
  - Every refusal is counted by reason code (`rejections`).
  - A model-written yes/no hint is removed and the question kept.
- **`basis.matchedSignals`:** code records which input signals each question actually used.
- **Live check, 2026-11-13, synthetic D010-style topic shares, 1 call per run:**
  - v2 draft: 3/3 kept, each grounded in a different signal, 15.5 s. It produced yes/no hints, which led to the hint rule.
  - Final v2: 3/3 kept, all hints open, 12.5 s.

### `server/planning`, other changes
- **`signals.aggregate_signals`** turns opted-in players' allowlisted topic labels (D010) into M6 signals:
  - nothing for fewer than 10 players;
  - a tag is kept only when at least 5 players carry it;
  - shares are rounded to 0.05;
  - at most 20 tags;
  - the thresholds can't be lowered.
- **Verdicts in the trace:** M2 records validate/guard/fallback, M6 records proposed/refused/repaired/kept/grounded, and M7 records refused reason or checked.
- **PROPOSED route `GET /operator/reasoning`** (operator only, filter by task, limit 1-300). It is mounted only when `PlanningRuntime.trace` is set, and needs Kai's ACK plus an API.md row.

### Checks
- `python -m pytest tests`: 858 passed, 2 skipped. One earlier full run had a single failure that didn't reproduce in three reruns; it is probably a known timing-sensitive test in another area.

## Demo: showing the reasoning to judges

Use one operator panel, "Muse proposes, code enforces", built only from fields that are safe today.

- **Per call** (`GET /operator/reasoning`): call type, live/replay, latency, attempts, outcome, then each code verdict. For example:
  - M6: "proposed 5 → refused 1 near_duplicate, 1 over_category_quota → kept 3, 3 grounded in signals".
  - M7: "checked venue_time_text_ok".
  - M2: "validate yes_no → fallback curated_hint".
- **Formation** (Rishi and Kai, once R3 and the debug endpoint exist):
  - baseline groups vs Muse groups, as handle indices;
  - how many pairs the keyword baseline split but Muse joined;
  - repaired groups and moved members;
  - fallback used, with its reason code;
  - per group: size, confidence bucket and loose match.
- **Sky:** visible vs suppressed theme counts, the threshold, and headlines rejected by the number check or the guard.
- **Simulation:** run one synthetic cycle live in advance, then replay its saved trace on stage, labeled "Replay of a saved cycle" (the trace sets `source: replay`). Never show answers, refs mapped to players, or closeness scores.

## Making Muse the centre (proposed, needs owners)

1. **Muse classifies posts and comments** (Patrik):
   - Muse classifies each text into ≤3 labels from a fixed allowlist, with a stance (positive, neutral or negative) and a sensitive flag.
   - Code validates the enum, drops sensitive or negative texts, and stores labels only. The raw text is discarded.
   - The keyword list stays as a labeled offline fallback.
   - This fixes "I hate running" → sports, and lets the pitch mention likes honestly if likes are added the same way.
2. **Muse sees the questions** (Rishi, Patrik): pass the question text and per-answer question ids to M3 and M4.
3. **Activity becomes soft hints to M4** (Rishi, Kai): send the allowlisted labels and shared-Group/Event counts by ref, as optional hints. Code still enforces sizes, blocks and consent. Or state plainly that D010 is "context, not matching".
4. **M4 gets the M3 themes** (Rishi): run them in sequence, or as two passes.
5. **The loop closes into next week** (Adam): `aggregate_signals` over this week's activity topics and theme tags feeds M6. Approved questions then target what the community actually cares about.
