# Facebook Space
### You're not the only one feeling this. Facebook Space shows you who's been feeling it right next to you.

Most people our age feel like the only one carrying a private feeling, and they are almost never the only one. Facebook Space is a weekly game inside Facebook Groups that lets a Group find that out. Monday to Friday, Muse asks one honest question a day. Once you answer, you see the constellations you are in that day, drawn in that day's color. The only number shown is how many people answered today. On Saturday you see all your constellations for the week across the whole sky. On Sunday your closest 2 to 4 people appear as your main constellation, drawn as the Meta logo, with a 24-hour anonymous group chat. Names are revealed only when people both choose to. Friendship only, 18+.

**v3 redesign:** the full spec is [docs/PRD-v3.md](docs/PRD-v3.md) (decision D012, contract 3.0.0, proposed). Constellations and rooms have no names, and there are no percentages, Sky stats or prevalence guesses. Anonymity is the design.

**Current state (2026-11-13):** main runs the 2.1.0 weekly game end to end on test data: mock Facebook shell (`web/`, labeled "Simulated Facebook"), Kai's composed FastAPI app (`server/app`), the daily loop, formation (49.2 s live for 30 players, one run), anonymous chat with moderation and mutual reveal, nudges, and the operator console. `pytest tests` passes (842). Not yet done: v3 redesign, deployment, a full live run on phones.

| Part | Status |
| --- | --- |
| Mock Facebook shell + feed tests (`web/`) | Existing. Mock data only. |
| Contract 2.1.0 (`contracts/protocol.ts`) + fixtures | On main; D009/D010 merged ahead of owner ACKs |
| 2.1.0 server: cycle, privacy, Muse adapter, formation, chat, nudges, composition | On main, test-verified; not deployed |
| Contract 3.0.0 (v3 redesign, D012) | Proposed in [docs/PRD-v3.md](docs/PRD-v3.md); not yet in `contracts/` |
| v3: daily constellations, Saturday sky, Sunday Meta logo, 24 h chat, events | Planned (work board below) |

A specification is not evidence of a working journey. See [PROJECT_KNOWLEDGE.md](PROJECT_KNOWLEDGE.md).

## Start here
**Coding agents: paste the master prompt in [docs/START_HERE.md](docs/START_HERE.md).** Then take your tasks from the work board below and your role file in `docs/roles/`.

Build order: [docs/PLAN.md](docs/PLAN.md). Deadline used in planning: November 13, 2026, 10:30 AM PST (team-supplied, not independently verified). Feature freeze 04:30 AM PST Nov 13.

## Product boundary
`web/` is the mock Facebook shell. Keep it and its feed tests. Facebook Space lives in its own UI under `web/src/features/constellations/<area>/` (code name: constellations), reached from the Facebook Space shortcut in the left sidebar (`/space`) and its card on the home feed (Will owns routing). Feature CSS stays scoped. The shell's mock users and localStorage are not the product backend.

## Work board (v3)
Check a box only when the acceptance line is true on your branch, with a command or test you can name. Update this board in the same PR as the work. Per-role detail stays in `docs/roles/<name>.md`; if the two disagree, this board and [docs/PRD-v3.md](docs/PRD-v3.md) win.

### Rishi (`@rishibagri`, branch `role/rishi-matching`)
Matching, formation, sky layout, event interest. Largest share.

Done:
- [x] Formation core (`server/matching`). Accepts: formation tests pass offline.
- [x] Validation and repair (size, everyone once, blocks). Accepts: validator rejects bad groupings in tests.
- [x] Muse task registration for formation. Accepts: M3/M4 callable through the adapter.
- [x] MatchingPort for Kai. Accepts: Kai composes it without importing matching internals.
- [x] Live formation in 49.2 s (Adam's run). Accepts: recorded in the handoff; a baseline, not a target.
- [x] Event allowlist fix. Accepts: nudge outside the allowlist is rejected.

To do:
- [ ] Contract 3.0.0 draft and D012. Owns `contracts/protocol.ts`, `docs/DECISIONS.md`. Accepts: typechecks, fixtures updated, every owner has an ACK or CHANGE.
- [ ] Instant daily placement, code only, under 1 s. Owns `server/matching`. Accepts: a new answer returns that day's constellations in under 1 s with no Muse call.
- [ ] Day-close formation of daily constellations (M3 batched). Owns `server/matching`. Accepts: closing a day produces constellations of 2+ people, each person placed, blocks respected.
- [ ] Week co-membership graph. Owns `server/matching`. Accepts: shared-constellation counts per pair are reproducible from the day results.
- [ ] Sunday main constellation: 2+ shared constellations or high closeness, groups of 3 to 5, blocks, repair, fallback, plus Meta-logo anchors. Owns `server/matching`. Accepts: validator passes; every player is in one group or labeled unplaced; fallback is labeled "Fallback grouping".
- [ ] Sky layout: week-randomized star indices over about 10k positions, plus second-degree constellations (max 2 per star, caps). Owns `server/matching`. Accepts: your index differs week to week; no star exceeds 2 second-degree groups; the cap holds on a 10k fixture.
- [ ] Formation progress stream with real candidate edges. Owns `server/matching`. Accepts: edges shown are ones the algorithm actually scored, not decoration.
- [ ] Event constellation-interest counts and nudge eligibility (bucketed, 3+ only, allowlist from #44). Owns `server/matching`. Accepts: a count under 3 is never returned; an event outside the allowlist is never eligible.
- [ ] Custom-event cluster finder (repeat matches over 3 weeks). Owns `server/matching`. Accepts: a seeded cluster of 3+ repeat matches is found; a one-off match is not.
- [ ] Remove M5 naming, M8 Sky narration and the guess from matching. Owns `server/matching`. Accepts: grep finds no naming, prevalence or guess code; tests green.
- [x] Live quality run. Done by Adam's live evals (`docs/audits/2026-11-13-live-evals.md`, synthetic gold set, 30 players): Muse scored pairwise precision/recall 0.95/0.88 (Spark), 0.98/0.89 (Ember), 1.0/1.0 (Wonder) against 0.13 for the keyword baseline. Small runs (1-3 per model), directional only.

### Adam (`@adamzhang06`, branch `role/adam-planning`)
Muse adapter, event data, copy jobs.
- [ ] `eventId` on catalog events (#44). Owns the event catalog. Accepts: every approved event has a stable `eventId` used by nudges and interest counts.
- [ ] `EventView` and events list backend. Owns `server/planning`. Accepts: list returns only approved events with bucketed counts, never raw ones.
- [ ] Nudge copy job (M7). Accepts: output is strict JSON, passes the allowlist and guard, and is a labeled fallback on failure.
- [ ] `custom_event` proposals (M7) and operator approval queue backend. Accepts: Muse proposes, nothing is visible until an operator approves, and 3+ RSVPs are required to run.
- [ ] Remove M5 and M8 task specs. Accepts: no naming or Sky narration spec remains in the Muse registry or docs.

### Will (`@willapat`, branch `role/will-voice-ui`)
Daily experience, screens, operator controls.
- [ ] `answeredToday` count. Owns the daily-answer UI. Accepts: shown after answering as the only number on screen.
- [ ] Remove the guess UI and route. Accepts: no guess screen, route or copy remains; feed tests still green.
- [ ] Day colors. Accepts: each weekday has one color used consistently across screens.
- [ ] Daily constellation reveal screen. Accepts: after answering, shows all your constellations that day, unnamed, in that day's color.
- [ ] Your-week screen. Accepts: lists the week's daily constellations without names or percentages.
- [ ] Close-day operator control. Accepts: operator can close a day, labeled "Demo timing".
- [ ] Custom-event approval UI. Accepts: operator sees Muse proposals, approves or rejects, and the decision is logged.

### Patrik (`@patrikliska13`, branch `role/patrik-privacy`)
Consent, private storage, retention, guards.
- [x] `eventSignals` consent toggle. Accepts: no interest or RSVP is stored for a player who has not opted in. (`tests/privacy/test_privacy_events.py::test_nothing_stored_without_opt_in`)
- [x] Interest and RSVP private storage. Accepts: another session gets 403; only bucketed counts leave the privacy module. (`test_invites_only_to_opted_in_and_rsvp_is_403_for_anyone_else`, `test_interest_bucket_counts_only_opted_in_peers_and_never_under_three`)
- [x] Retention for the new tables. Accepts: interest, RSVP and daily-placement data expire with the rest (14 days after lock); a TTL test proves it. (`test_interest_and_invites_expire_fourteen_days_after_lock`; daily placement is Rishi's table: purge it via `AnswerStore.expired_cycles()`)
- [x] Privacy review of second-degree constellations and events. Accepts: written review in the handoff; no path lets a player infer who another player is. (docs/handoffs/patrik.md: no direct path; risks R1 star-index linkage, R2 small-community graph, R3 bucket differencing, each with an owner fix)
- [x] OutputGuard on nudge and custom-event copy. Accepts: a fuzz test with known answers finds no 5-word overlap; sensitive terms are rejected. (`OutputGuard.check_event_copy`; `tests/privacy/test_privacy_guard_events.py`)

### Kai (`@beatopia`, branch `role/kai-orchestration`)
Jobs, chat, sky UI, API composition.
- [ ] Job runner for day close, lock, reveal and 24-hour expiry. Accepts: each job runs once, is idempotent, and a post to an expired chat returns `ROOM_EXPIRED`.
- [ ] Saturday sky canvas (about 10k stars, no zoom). Accepts: renders your constellations plus low-opacity second-degree ones at demo frame rate on a laptop.
- [ ] Loading screen on SSE `formation.progress`. Accepts: shows the real candidate edges as they arrive; falls back to a labeled visualization if the stream drops.
- [ ] Sunday Meta-logo reveal. Accepts: the main constellation is drawn on the logo anchors for 2 to 4 people.
- [ ] 24-hour chat change. Accepts: the chat expires 24 hours after reveal; mutual reveal still works; contact info is still blocked.
- [ ] New route composition: `/sky/stars`, `/sky/mine`, `/main`, `/events`, invites. Accepts: each route is auth-checked and returns only the caller's own data.

### Shared
- [ ] Hosting per [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md). Accepts: the app runs on the chosen hosts and the checklist there is complete.
- [ ] Rehearsal of the full week. Accepts: one timed run-through using [docs/DEMO.md](docs/DEMO.md), with failures logged.
- [ ] Backup video. Accepts: a recording of the full journey, with every simulated element labeled.

### Cut order
Freeze is 04:30 AM PST Nov 13. If time runs short, cut in this order: (1) custom events become proposal plus approval only; (2) the progress stream becomes a labeled visualization; (3) second-degree constellations; (4) instant placement falls back to day-close only. **Never cut:** anonymity, consent, safety, OutputGuard, 24-hour expiry, mutual reveal, labels.

## The problem
Young people tend to feel like the only one feeling something: lonely, pretending to be fine, missing home, behind everyone else, eating alone. Almost nobody says it out loud, so each person sees only other people's public side and assumes their own inner life is unusual. It usually isn't. Many people in the same Group privately feel the same thing, and each of them thinks they are the exception (pluralistic ignorance). That belief keeps people quiet, and quiet keeps it going.

The research below shows the same pattern. People consistently underestimate how many peers share their private feelings and experiences. The friend-count study is one example: first-year students believed peers had more friends than they did, and felt they belonged less after seeing highly social photos of peers on Facebook. Facebook shows everyone's best night. Facebook Space shows everyone's real week.

| Finding | Number | Source |
| --- | --- | --- |
| First-year students who believe peers have more friends vs fewer | 48% vs 31% (study 1); 55% vs 26% (study 2) | Whillans et al. 2017, via WEF |
| Own close friends vs what students guessed peers had | 3.63 vs 4.15 | NPR via KUER |
| Believing peers are ahead lowers well-being, even for students with above-average friends | Holds after controlling for friend count | The Conversation |
| Young adults 19 to 29 who feel very or fairly lonely (Meta-Gallup, highest of any age) | 27% | Scripps News |
| Correcting the misperception plus action prompts (Stanford, Columbia, Princeton; Nature Human Behaviour) | +0.44 close friends vs control (self-reported; no significant spring well-being difference) | Silicon Canals |
| Young adults on Facebook daily (US and Canada, per Meta) | 40M+, one in four use Marketplace | Fortune |

Figures are quoted from the PRD with the sources it names. We have not independently re-verified them.

## First-use matching and calibration (planned)

A new player starts with a provisional constellation, even before they have answered enough daily questions. With their permission, initial connections are based on available Meta platform activity: videos they like, accounts and creators they follow, their comments, and other interests they choose to share. Activity sharing is optional and separate from the required game consent; the prototype does not claim access to real Meta activity APIs.

Daily-question answers then help calibrate the match around what the player means and experiences, beyond their activity-based interests. Until enough daily-question information is available, the constellation and connection view keeps this disclaimer visible:

> **Calibration is not complete yet.** Your initial connections are based on the Meta activity you chose to share. Answer daily questions to help us understand you better and refine your constellation.

Once there is enough daily-question information, those answers become the primary basis for connections and the disclaimer is removed. The readiness criterion and this onboarding flow still need implementation; no answer-count threshold is specified here. Activity signals and private answers are never shown to other players, and identity still requires mutual reveal.

## How a week works (v3)
1. **Join.** Facebook Space tab inside a Group, or QR. One screen explains what is private and what is shared. Three consent toggles (match me, anonymous chat, 18+) are required before any answer. Event signals are a separate optional toggle (`eventSignals`).
2. **Daily answer (Mon-Fri).** One question per day. Answer by voice or text, 1 to 400 characters. Muse may ask one follow-up. Every answer is screened for distress or harm first; flagged answers are excluded everywhere and the player sees a private support card.
3. **Daily reveal.** Right after you answer, code places you instantly (under 1 s) and you see the constellations you are in that day, in that day's color. You may be in several. They have no names. The only number on screen is how many people answered today. When the day closes, Muse-assisted formation (M3, batched) settles the day's constellations.
4. **Saturday.** The week locks. You see all your constellations from the week, plus low-opacity second-degree constellations, across the whole sky of about 10k stars. No zoom. Your star position is randomized each week. A loading screen shows the algorithm trying real candidate connections.
5. **Sunday.** Your main constellation forms from the closest 2 to 4 people: 2 or more shared constellations, or very similar answers. It is drawn as the Meta logo, with a 24-hour anonymous group chat. Every message is screened; contact info is blocked; report and block are one tap. The chat expires 24 hours after it opens.
6. **Mutual reveal.** Anyone can ask to reveal. Names appear only for people who both asked. A one-sided request reveals nothing.
7. **Events.** You get a nudge to an approved event when people from your constellations are going. Counts are bucketed and shown only at 3 or more. Every few weeks, a cluster of repeat matches can get a custom event: Muse proposes, an operator approves, and it runs only with 3+ RSVPs. Public places only.

Operator console runs the demo week (advance day, close day, lock, reveal, synthetic top-up, reset) and shows model metadata and latency for every Muse call.

## Example week
- **Maya**, first-year, 18. Moved 900 miles, eats most meals alone. Monday she writes "I eat in my room so no one sees me alone". She answers, and sees two constellations in Monday's color. Wednesday she catches up on Tuesday's question.
- **Dev**, transfer, 20. Writes "cooking for one is honestly depressing". A keyword baseline splits Maya and Dev. Muse puts them in a shared constellation, twice that week.
- **Jordan**, international, 19. Answers by voice. Three-day streak.
- **Sam**, sophomore with friends. Plays for fun and is the density that makes the game work for Maya.

Saturday, Maya sees her week's constellations and a faint second ring of people one step away, across the whole sky. Sunday, Maya and Dev share a main constellation drawn as the Meta logo, with one other person, and a chat that lasts 24 hours. They both tap reveal. Thursday's open mic was nudged to them because several people from their constellations were going.

## Why Facebook
Facebook already has the communities, and a Group carries existing trust. Facebook Space runs inside Groups young adults already belong to and gives them a weekly habit. This prototype simulates the shell. We claim no Groups, Messenger or Events API access.

## Why only AI
No human can read a week of private answers from thousands of people, match them by meaning, and moderate every anonymous chat. No chatbot sees more than one person. Code cannot understand what an answer means. Deterministic code validates every output and owns every guarantee.

## Muse
Muse makes the judgment calls. **Muse proposes, code enforces.**

| # | Job | Owner | Output (strict JSON) | Code check after |
| --- | --- | --- | --- | --- |
| M1 | Safety screen (answers and chat) | Patrik | `{flag, reason}` | Flagged content excluded everywhere |
| M2 | Follow-up | Adam | `{needsFollowup, question}` | Max one per answer |
| M3 | Theme discovery (day close, batched) | Rishi | `{themes}` | Labels pass no-quote check |
| M4 | Constellation formation (daily and Sunday main) | Rishi | `{constellations: [{memberIds, sharedMeaning, confidence}]}` | Size limits, everyone placed, blocks respected |
| M5 | Removed in v3 (constellation naming) | | | |
| M6 | Question generation | Adam | `{questions}` | Schema, guard, operator approval |
| M7 | Event nudge and custom-event proposal | Adam | `{title, eventId or placeId, timeWindow, why}` | Venue allowlist, 3+ people, guard, operator approval for custom events |
| M8 | Removed in v3 (Sky narration) | | | |

Daily placement is code only, with no Muse call. Prompts carry random per-call ids and text only. Invalid JSON gets one retry, then a labeled fallback.

**Model and latency:** `muse-spark-1.3` answered 2 live calls earlier on 2026-11-12 through the archived adapter; the provider echoed the model name. Re-verify on the restored adapter. Observed single-call latency 17 to 24 s at low reasoning effort (2 calls, not a benchmark). A live formation run took 49.2 s (Adam's run, recorded in the handoff). Every Muse output in the UI carries a chip with model, call type and latency.

## Baseline to beat
A keyword or embedding baseline groups answers without Muse. The demo shows one live case where the baseline splits two people who meant the same thing and Muse joins them. No measured improvement is claimed unless measured.

## Architecture
See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md). React/Vite/TypeScript frontend (existing). Python FastAPI + PostgreSQL server (D002), composed by Kai; each owner mounts their own router.

## Contracts
- [contracts/protocol.ts](contracts/protocol.ts) `CONTRACT_VERSION = "2.0.0"` (D006, pending ACK); v3 is 3.0.0 (D012, proposed, in [docs/PRD-v3.md](docs/PRD-v3.md)) · [fixtures](contracts/fixtures)
- [API](contracts/API.md) · [Weekly workflow](contracts/WORKFLOW.md) · [Privacy](contracts/PRIVACY.md) · [Decisions](docs/DECISIONS.md) · [Demo](docs/DEMO.md)

## Local setup
```sh
git clone https://github.com/willapat/Meta-Hackathon.git
cd Meta-Hackathon
git fetch origin
git switch --track origin/role/rishi-matching   # substitute your branch
```

Frontend shell (from `web/`, Node 22.12+):
```sh
npm ci
npm run dev
npm run lint && npm run build && npm run test:e2e
```
Playwright may need `npx playwright install chromium`. The existing e2e tests exercise the mock shell, not the feature.

No server exists on main yet, so there is no server setup. Kai adds server setup instructions when the FastAPI app is restored (step 2, proposed in D002). A running process is not evidence of a working journey.

## Hosting (plan, not deployed)
Supabase Postgres for the workflow database (decided). Web host and API host are still open; the API needs one always-on container because it runs background jobs, live chat streams and a SQLite privacy file, so it can't run as serverless functions. Requirements, settings, cookie setup and blockers: [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

## Coordination
Full protocol: [docs/COORDINATION.md](docs/COORDINATION.md). Every agent follows it.

1. **Check for tags first.** Before any work session, look for open PRs, issues and PR comments that mention you or request your review. Answer them (`ACK`, `CHANGE: <proposal>` or `DELIVERED: <commit/PR>`) before your own next deliverable, and log them under "Requests answered" in your handoff.
2. **When blocked, stop and tag.** If your next deliverable needs another owner's interface, a contract change, a data shape, an ACK or an endpoint that is not yet on main or their branch: stop at the phase boundary, push your verified work, open or update a draft PR titled `[BLOCKED] <phase>: <what you need>` with one `Needs from @<handle>` block per owner (What, Why, Proposed shape, Fallback meanwhile), record it in your handoff, and continue only with independent work using a labeled test-only adapter.
3. Never invent another owner's interface, edit their paths or silently change `contracts/`. A tag is a request, not an authorization.

Handles and branches are listed per owner on the work board above. Canonical table: [docs/COORDINATION.md](docs/COORDINATION.md).

## Truth labels
| Item | Label |
| --- | --- |
| Facebook shell | "Simulated Facebook" |
| Seeded players and answers | "Synthetic player" |
| Synthetic aggregate counts | "Synthetic signal" |
| Operator-advanced days | "Demo timing" |
| Cached Muse output | "Replay of a saved cycle" |
| Deterministic formation fallback | "Fallback grouping" |
| Muse output | Live chip: model, call type, latency |

Typing always works if the microphone fails. A provider outage shows a retryable operator error or a labeled replay. Never silently relax consent, size, block or threshold constraints.

## Privacy and safety
No player ever sees another player's answers. They see anonymous constellations, moderated chat, bucketed counts, and real names only after a mutual reveal. Enforced by server code.

| Rule | Enforced by | Test |
| --- | --- | --- |
| Answers readable only by author and server | Privacy module access checks | Another session gets 403 on every answer route |
| Prompts contain only random ids and text | Prompt builder strips profile fields | Unit test on every prompt payload |
| No Muse output contains 5+ consecutive words from any answer | OutputGuard | Fuzz test with known answers |
| No sensitive categories (health, sexuality, religion, finances, family trauma, home location) in Muse public text | Sensitive-term filter | Red-team list of 30 |
| Every chat message screened; no contact info before mutual reveal | M1 + OutputGuard | Contact-info message rejected |
| Report hides instantly; block prevents future matches | Chat + privacy modules | Reported message gone for reporter |
| Chats expire 24 hours after opening | Expiry job | Post to expired chat returns ROOM_EXPIRED |
| Identity only on mutual reveal | Reveal transaction | One-sided request leaks nothing |
| Event and interest counts shown only bucketed, at 3 or more | Server aggregation | A count of 2 never renders |
| Event signals stored only with the `eventSignals` opt-in | Consent check | No interest row for a non-consenting player |
| Flagged distress content excluded from all outputs | M1 flag + server filter | Seeded distress answer never appears |
| Delete anytime; data expires 14 days after lock | Deletion + TTL job | Deleted answer absent from re-run |
| Friendship only, 18+, public places only | Consent, venue allowlist | Nudge outside allowlist rejected |

Distress: a private card shows campus counseling and the 988 Suicide and Crisis Lifeline (US). The game never counsels.

## Demo success criteria
1. 6+ real people answer daily questions from their own phones, including one catch-up.
2. After answering, each player sees the constellations they are in that day, in that day's color, with only the answered-today count shown.
3. The Saturday sky shows a player's constellations and faint second-degree ones across the whole sky, and the loading screen shows the algorithm trying real connections, with the measured time shown.
4. Sunday reveal draws a main constellation as the Meta logo and opens a 24-hour anonymous chat; moderation visibly blocks a contact-info message.
5. Two players mutually reveal on stage.
6. An event nudge appears with a bucketed count of 3 or more, and one custom-event proposal is approved by the operator.
7. Muse model name and latency visible on every Muse output.
8. Every synthetic or simulated element is labeled.

Run sheet: [docs/DEMO.md](docs/DEMO.md).

## Product metrics (no targets claimed)
| Stage | Metric |
| --- | --- |
| Habit | Daily answer rate; median streak; catch-up share |
| Reveal | Share who open the Sunday main constellation |
| Connect | Share of chats with 2+ active members; mutual reveals per chat |
| Meet | Share of nudges and custom events with 3+ attendees |
| Retain | Share answering again the next week |

## Non-goals
Real Facebook APIs; romantic matching; showing anyone's answers; counseling; percentages, prevalence stats or names for constellations; leaderboards or seasons (vision only); any impact claim without measurement.

## Pitch (30 seconds)
Most people our age feel like they're the only one feeling something: lonely, faking fine, missing home, behind. They aren't, but nobody says it out loud. Facebook Space is a weekly game in Facebook Groups. Every weekday Muse asks one honest question, and the moment you answer you see the constellations of people who meant the same thing. On Saturday your whole week lights up across the sky. On Sunday your closest few people appear as the Meta logo, with an anonymous chat that lasts a day. Reveal yourself only when you both want to. No names, no scores, no stats. Just proof you were never the only one.

## Provenance
The team referenced the documentation organization of dor-calhacks: shared entry instructions, contracts, role handoffs and an evidence ledger. This project is newly authored; no prior hackathon application code was copied. The Facebook Space direction comes from the team's PRD of Nov 12, 2026, redesigned as v3 on the same day ([docs/PRD-v3.md](docs/PRD-v3.md), D012). Archived Group Quests infrastructure on `archive/group-quests-before-pivot` is the team's own earlier hackathon code; reusable parts are restored per owner and retested. The weekly-game direction was approved on Nov 12, 2026 (D005).
