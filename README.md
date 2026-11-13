# Constellations
### Everyone thinks they're alone in the dark. Constellations shows you who's been shining next to you the whole time.

A weekly game inside Facebook Groups. Monday to Friday, Muse asks one honest question a day. On Saturday the week locks. On Sunday each player wakes up in a constellation: 3 to 5 people from their Group whose answers meant the same thing, in an anonymous, moderated chat that lasts one week. Names are revealed only when two people both choose to. The Sky shows the whole Group what people guessed about each other next to what was true. Friendship only, 18+.

**Current state (2026-11-12):** main holds the mock Facebook web UI (`web/`, labeled "Simulated Facebook"), docs, contract 2.0.0 and shared fixtures. The weekly-game runtime is **not built**. Archived Group Quests server code (FastAPI app, Muse adapter, privacy/session code, voice boundary) lives on `archive/group-quests-before-pivot` and is restored by each owner into their own paths, then retested (build step 2).

| Part | Status |
| --- | --- |
| Mock Facebook shell + feed tests (`web/`) | Existing. Mock data only. |
| Contract `contracts/protocol.ts` 2.0.0 + `contracts/fixtures/` | Authored, typechecks; pending D006 ACK |
| Server, Muse adapter, cycle, formation, chat, Sky, operator console | Planned (docs/PLAN.md) |

A specification is not evidence of a working journey. See [PROJECT_KNOWLEDGE.md](PROJECT_KNOWLEDGE.md).

## Start here
**Coding agents: paste the master prompt in [docs/START_HERE.md](docs/START_HERE.md).**

| Owner | Owns | Tasks | Branch |
| --- | --- | --- | --- |
| Rishi | Semantic formation, validation, prevalence computation, synthetic signals | [rishi.md](docs/roles/rishi.md) | `role/rishi-matching` |
| Adam | Muse adapter, question bank, generation and selection, follow-ups, event nudges | [adam.md](docs/roles/adam.md) | `role/adam-planning` |
| Will | Weekly cycle, daily-answer experience, voice, streaks, operator controls, Groups tab | [will.md](docs/roles/will.md) | `role/will-voice-ui` |
| Patrik | Verification, sessions, private answer storage, safety screening, output guards | [patrik.md](docs/roles/patrik.md) | `role/patrik-privacy` |
| Kai | Anonymous chat, expiration, mutual reveal, realtime delivery, API composition, Sky UI | [kai.md](docs/roles/kai.md) | `role/kai-orchestration` |

Build order: [docs/PLAN.md](docs/PLAN.md). Steps 6 (event nudges) and 7 (question generation, synthetic signals) are the first cuts.

Deadline used in planning: November 13, 2026, 10:30 AM PST (team-supplied, not independently verified). Feature freeze 04:30 AM.

## Product boundary
`web/` is the mock Facebook shell. Keep it and its feed tests. Constellations lives in its own UI under `web/src/features/constellations/<area>/`, reached from a Constellations tab inside a Group (Will owns routing). Feature CSS stays scoped. The shell's mock users and localStorage are not the product backend.

## The problem
Young adults arriving somewhere new mostly believe everyone else has already found their people. That belief is usually wrong, and it stops them reaching out. Social life happens in public while being alone is invisible, so everyone sees others' best moments. Each person is privately willing to talk but assumes others are less open (pluralistic ignorance).

In the same research, first-year students felt they belonged less after viewing highly social photos of peers on Facebook. Facebook shows everyone's best night. Constellations shows everyone's real week.

| Finding | Number | Source |
| --- | --- | --- |
| First-year students who believe peers have more friends vs fewer | 48% vs 31% (study 1); 55% vs 26% (study 2) | Whillans et al. 2017, via WEF |
| Own close friends vs what students guessed peers had | 3.63 vs 4.15 | NPR via KUER |
| Believing peers are ahead lowers well-being, even for students with above-average friends | Holds after controlling for friend count | The Conversation |
| Young adults 19 to 29 who feel very or fairly lonely (Meta-Gallup, highest of any age) | 27% | Scripps News |
| Correcting the misperception plus action prompts (Stanford, Columbia, Princeton; Nature Human Behaviour) | +0.44 close friends vs control (self-reported; no significant spring well-being difference) | Silicon Canals |
| Young adults on Facebook daily (US and Canada, per Meta) | 40M+, one in four use Marketplace | Fortune |

Figures are quoted from the PRD with the sources it names. We have not independently re-verified them.

## How a week works
1. **Join.** Constellations tab inside a Group, or QR. One screen explains what is private and what is shared. Three consent toggles (match me, anonymous chat, 18+) are required before any answer.
2. **Daily answer (Mon-Fri).** One question per day from the question bank. Answer by voice or text, 1 to 400 characters. Muse may ask one follow-up. Answering on the day counts at full weight and builds a streak.
3. **Catch-up.** Missed a day? Answer it any time before Saturday lock. Catch-up answers count at lower weight and never extend a streak.
4. **Guess.** Each player guesses what percent of the Group feels like them this week.
5. **Safety triage.** Every answer is screened for distress or harm first. Flagged answers are excluded everywhere; the player sees a private support card.
6. **Saturday lock.** Answers freeze. Muse groups players into constellations of 3 to 5 by meaning across the week's weighted answers, then names each one. Code validates size, placement and blocks. Weak fits get an honest "looser this week" label.
7. **Sunday reveal.** Each player sees their constellation's name and shape and joins its anonymous chat as "Star 1-5". Every message is screened; contact info is blocked; report and block are one tap. The room expires at the next Saturday lock.
8. **Mutual reveal.** Either player can ask to reveal. Names appear only when both asked each other. A one-sided request reveals nothing.
9. **Event nudge.** Mid-week, Muse suggests one public campus event or venue that fits what the constellation shares. Public places only, 3 or more people.
10. **The Sky.** The Group sees every constellation as stars, themes shared by 3+ people (25+ in production), and guessed vs actual prevalence. Synthetic aggregate signals are labeled.

Operator console runs the demo week (advance day, lock, reveal, synthetic top-up, reset) and shows model metadata and latency for every Muse call.

## Example week
- **Maya**, first-year, 18. Moved 900 miles, eats most meals alone. Monday she writes "I eat in my room so no one sees me alone". Wednesday she catches up on Tuesday's question.
- **Dev**, transfer, 20. Writes "cooking for one is honestly depressing". A keyword baseline splits Maya and Dev. Muse puts them in the same constellation.
- **Jordan**, international, 19. Answers by voice. Three-day streak.
- **Sam**, sophomore with friends. Plays for fun and is the density that makes the game work for Maya.

Sunday, Maya and Dev are "Star 1" and "Star 3" in the same room. Muse nudges the room toward Thursday's open mic. After two days of chat they both tap reveal. The Sky shows the Group guessed 12% eat alone. It was 57%.

## Why Facebook
Facebook already has the communities, and a Group carries existing trust. Constellations runs inside Groups young adults already belong to and gives them a weekly habit. This prototype simulates the shell. We claim no Groups, Messenger or Events API access.

## Why only AI
No human can read a week of private answers from thousands of people, match them by meaning, and moderate every anonymous room. No chatbot sees more than one person. Code cannot understand what an answer means. Deterministic code validates every output and owns every guarantee.

## Muse
Muse makes the judgment calls. **Muse proposes, code enforces.**

| # | Job | Owner | Output (strict JSON) | Code check after |
| --- | --- | --- | --- | --- |
| M1 | Safety screen (answers and chat) | Patrik | `{flag, reason}` | Flagged content excluded everywhere |
| M2 | Follow-up | Adam | `{needsFollowup, question}` | Max one per answer |
| M3 | Theme discovery | Rishi | `{themes}` | Labels pass no-quote check |
| M4 | Constellation formation | Rishi | `{constellations: [{memberIds, sharedMeaning, confidence}]}` | 3-5, everyone once, blocks respected |
| M5 | Constellation naming | Rishi | `{name, shapeId, colorId}` | Fixed sets; guard |
| M6 | Question generation | Adam | `{questions}` | Schema, guard, operator approval |
| M7 | Event nudge | Adam | `{title, placeId, timeWindow, why}` | Venue allowlist, 3+ people, guard |
| M8 | Sky narration | Rishi | `{headlines}` | Every number equals a server count |

Prompts carry random per-call ids and text only. Invalid JSON gets one retry, then a labeled fallback.

**Model and latency:** `muse-spark-1.3` answered 2 live calls earlier on 2026-11-12 through the archived adapter; the provider echoed the model name. Re-verify on the restored adapter. Observed single-call latency 17 to 24 s at low reasoning effort (2 calls, not a benchmark). Formation for 30 players under 60 s needs M1 at submit time and parallel M5. Every Muse output in the UI carries a chip with model, call type and latency.

## Baseline to beat
A keyword or embedding baseline groups answers without Muse. The demo shows one live case where the baseline splits two people who meant the same thing and Muse joins them. No measured improvement is claimed unless measured.

## Architecture
See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md). React/Vite/TypeScript frontend (existing). Python FastAPI + PostgreSQL server (D002), composed by Kai; each owner mounts their own router.

## Contracts
- [contracts/protocol.ts](contracts/protocol.ts) `CONTRACT_VERSION = "2.0.0"` (D006, pending ACK) · [fixtures](contracts/fixtures)
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

No server exists yet, so there is no server setup. Kai adds server setup instructions when the baseline lands (proposed in D002). A running process is not evidence of a working journey.

Server setup is added by Kai when the FastAPI app is restored (step 2).

## Coordination
Full protocol: [docs/COORDINATION.md](docs/COORDINATION.md). Every agent follows it.

1. **Check for tags first.** Before any work session, look for open PRs, issues and PR comments that mention you or request your review. Answer them (`ACK`, `CHANGE: <proposal>` or `DELIVERED: <commit/PR>`) before your own next deliverable, and log them under "Requests answered" in your handoff.
2. **When blocked, stop and tag.** If your next deliverable needs another owner's interface, a contract change, a data shape, an ACK or an endpoint that is not yet on main or their branch: stop at the phase boundary, push your verified work, open or update a draft PR titled `[BLOCKED] <phase>: <what you need>` with one `Needs from @<handle>` block per owner (What, Why, Proposed shape, Fallback meanwhile), record it in your handoff, and continue only with independent work using a labeled test-only adapter.
3. Never invent another owner's interface, edit their paths or silently change `contracts/`. A tag is a request, not an authorization.

| Owner | GitHub handle | Branch |
| --- | --- | --- |
| Rishi | `@rishibagri` | `role/rishi-matching` |
| Adam | `@adamzhang06` | `role/adam-planning` |
| Will | `@willapat` | `role/will-voice-ui` |
| Patrik | `@patrikliska13` | `role/patrik-privacy` |
| Kai | `@beatopia` | `role/kai-orchestration` |

Canonical table: [docs/COORDINATION.md](docs/COORDINATION.md).

## Truth labels
| Item | Label |
| --- | --- |
| Facebook shell | "Simulated Facebook" |
| Seeded players and answers | "Synthetic player" |
| Synthetic aggregate statistics | "Synthetic signal" |
| Operator-advanced days | "Demo timing" |
| Cached Muse output | "Replay of a saved cycle" |
| Deterministic formation fallback | "Fallback grouping" |
| Muse output | Live chip: model, call type, latency |

Typing always works if the microphone fails. A provider outage shows a retryable operator error or a labeled replay. Never silently relax consent, size, block or threshold constraints.

## Privacy and safety
No player ever sees another player's answers. They see constellation identities, moderated chat, thresholded aggregates, and real names only after a mutual reveal. Enforced by server code.

| Rule | Enforced by | Test |
| --- | --- | --- |
| Answers readable only by author and server | Privacy module access checks | Another session gets 403 on every answer route |
| Prompts contain only random ids and text | Prompt builder strips profile fields | Unit test on every prompt payload |
| No Muse output contains 5+ consecutive words from any answer | OutputGuard | Fuzz test with known answers |
| No sensitive categories (health, sexuality, religion, finances, family trauma, home location) in Muse public text | Sensitive-term filter | Red-team list of 30 |
| Every chat message screened; no contact info before mutual reveal | M1 + OutputGuard | Contact-info message rejected |
| Report hides instantly; block prevents future matches | Chat + privacy modules | Reported message gone for reporter |
| Rooms expire weekly | Expiry job | Post to expired room returns ROOM_EXPIRED |
| Identity only on mutual reveal | Reveal transaction | One-sided request leaks nothing |
| Sky themes only above threshold (3 demo, 25 production) | Server aggregation | 2-member theme never renders |
| Flagged distress content excluded from all outputs | M1 flag + server filter | Seeded distress answer never appears |
| Delete anytime; data expires 14 days after lock | Deletion + TTL job | Deleted answer absent from re-run |
| Friendship only, 18+, public places only | Consent, venue allowlist | Nudge outside allowlist rejected |

Distress: a private card shows campus counseling and the 988 Suicide and Crisis Lifeline (US). The game never counsels.

## Demo success criteria
1. 6+ real people answer daily questions from their own phones, including one catch-up.
2. Saturday lock forms constellations of 3 to 5 by meaning, with names, and the measured time is shown.
3. Sunday reveal opens anonymous rooms; moderation visibly blocks a contact-info message.
4. Two players mutually reveal on stage.
5. The Sky shows guessed vs actual prevalence for themes at 3+.
6. Muse model name and latency visible on every Muse output.
7. Every synthetic or simulated element is labeled.

Run sheet: [docs/DEMO.md](docs/DEMO.md).

## Product metrics (no targets claimed)
| Stage | Metric |
| --- | --- |
| Habit | Daily answer rate; median streak; catch-up share |
| Reveal | Share who open Sunday reveal |
| Connect | Share of rooms with 2+ active members; mutual reveals per room |
| Meet | Share of nudges with 3+ attendees |
| Retain | Share answering again the next week |

## Non-goals
Real Facebook APIs; romantic matching; showing anyone's answers; counseling; leaderboards or seasons (vision only); any impact claim without measurement.

## Pitch (30 seconds)
Nearly half of first-year students believe everyone else already has more friends than they do. Facebook shows them everyone's best night, so nobody reaches out. Constellations shows everyone's real week. Every weekday Muse asks one honest question. On Sunday you wake up in a constellation with the three to five people whose week meant the same thing as yours, in an anonymous chat that lasts seven days. Reveal yourself only when you both want to. Then the whole Group sees the sky: what people guessed about each other, next to what was true.

## Provenance
The team referenced the documentation organization of dor-calhacks: shared entry instructions, contracts, role handoffs and an evidence ledger. This project is newly authored; no prior hackathon application code was copied. The Constellations direction comes from the team's PRD of Nov 12, 2026. Archived Group Quests infrastructure on `archive/group-quests-before-pivot` is the team's own earlier hackathon code; reusable parts are restored per owner and retested. The weekly-game direction was approved on Nov 12, 2026 (D005).
