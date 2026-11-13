# Demo and Q&A (weekly game)
Status: rehearsal plan; not yet built. Slot: 5 minutes demo + 3 minutes Q&A. Judging: AI Integration 30%, Product 25%, Execution 25%, Originality 20% (confirm with organizers).

The real product runs over a week. The demo compresses one week with operator controls labeled "Demo timing". Same code path as real time.

## Five minutes
| Time | Beat | On screen | Owner |
| --- | --- | --- | --- |
| 0:00-0:30 | Problem: young people feel like the only one feeling something, and people systematically underestimate how many peers share their private feelings (e.g. first-years think peers have more friends, Whillans et al. 2017 via WEF). Facebook shows everyone's best night; Facebook Space shows everyone's real week. | Slide, "Simulated Facebook" | Presenter |
| 0:30-1:10 | Room scans QR, joins the Group's Facebook Space tab, accepts consent (match me, anonymous chat, 18+). | Phones | Will, Patrik |
| 1:10-2:00 | Monday's question. Room answers by voice or text; one Muse follow-up. Streak chip appears. Operator advances to Wednesday: catch-up list shows missed days. Everyone moves the guess slider. | Phones + operator console | Will |
| 2:00-2:40 | Saturday lock. Formation runs live. Baseline split example: keywords separate "I eat in my room so no one sees me alone" and "cooking for one is depressing"; Muse joins them. Real latency on screen. | Formation debug view, Muse chip | Rishi |
| 2:40-3:40 | Sunday reveal. Each phone: constellation name and shape, anonymous room with "Star 1-5". Live chat; a contact-info message gets blocked; a report hides a message. Muse posts an event nudge. | Phones | Kai, Patrik, Adam |
| 3:40-4:10 | Two volunteers both tap "reveal me"; names appear only for them. | Stage pair | Kai |
| 4:10-4:45 | Sky on projector: themes at 3+ only, guessed vs actual ("You guessed 12%. It was 57%."), synthetic signals labeled. | Projector Sky | Kai (UI), Rishi (numbers) |
| 4:45-5:00 | Muse proposes, code enforces. Close line. | Slide | Presenter |

Cut order if behind: event nudge, then synthetic signals, then catch-up beat. Never cut consent, model chip, labels.

## Stage view (built 2026-11-13, D016)
The planned staging is two phones and one laptop on the big screen.
- **Laptop:** open `/space/stage` in a browser whose player has the operator role (see docs/DEPLOYMENT.md, issue 4). It shows Phone A on the left, Phone B on the right and the Muse pipeline between them, and has the week controls at the bottom (start week, next day, add synthetic players, lock, find people, reveal). "Reveal" stays disabled while Muse is matching.
- **Each phone:** join Facebook Space, then Privacy → Demo screen → choose Phone A or Phone B. Until then the stage shows that phone as "not connected". Only these two players' answers appear as text; everyone else is a count or a dot.
- **Order that works:** start week → both phones answer each day → next day (x4) → on Friday press "Add synthetic players" → lock → find people → wait about 10 s → reveal.
- **Not guaranteed:** that the two phones land in different constellations. Muse groups by meaning; two clearly different sets of answers make it likely, nothing forces it.
- Do not merge to `main` during the demo: a redeploy erases the running week.

## Labels
"Simulated Facebook" shell · "Synthetic player" seeded people · "Synthetic signal" aggregate stats · "Demo timing" advanced days · "Replay of a saved cycle" cached Muse output · "Fallback grouping" deterministic formation fallback.

## Q&A prep
- **Better than keywords?** Show the baseline split. No measured improvement claimed.
- **Who sees my answer?** Only you and the server. Others see constellation identity, moderated chat, and thresholded aggregates. Prompts carry random ids and text only. No 5-word quotes in any Muse output. Delete anytime; 14-day expiry.
- **Anonymous chat abuse?** Every message screened (M1 + guard), contact info blocked before mutual reveal, report hides instantly, block prevents future matches, rooms expire weekly.
- **Distress?** Excluded everywhere; private card with campus counseling and 988 (US). The game never counsels.
- **Why AI?** Matching a week of private answers by meaning for every member, every week, safely. Code enforces every guarantee.
- **Latency?** 17-24 s per call observed (2 calls). Formation parallelized; say the measured number.
- **Impact?** None claimed. Metrics we would track: daily answer rate, streak length, Sunday open rate, chat replies, mutual reveals, event nudge attendance.

## Fallbacks
Too few players: synthetic top-up (labeled). Provider outage: retry once, then labeled replay. Mic fails: typing. Wi-Fi: hotspot, then backup video. Flagged answer: private card only, never on projector.
