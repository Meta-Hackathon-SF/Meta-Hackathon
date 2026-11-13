# Demo and Q&A

Slot: 5 minutes demo, 3 minutes Q&A. Status: v3 script, rehearse once timed. Nothing here claims
a result we have not run; anything simulated is called out on screen.

## The one idea

One week, one feeling. You answer one easy question a day. Muse reads what people mean, not which
words they used, and places you with 5 or more people who feel the same. On Sunday you meet them.

## 5-minute run

| Time | Screen | Say |
| --- | --- | --- |
| 0:00 | Black screen. "I eat in my room so no one sees me alone." Then "Cooking for one is honestly depressing." A line draws between them. | "Different words. Same feeling. Neither of them knew." |
| 0:10 | Problem | "Most people our age think they are the only one. A feed shows everyone's best night, and you cannot fix that by asking people to be open in public." |
| 0:50 | Facebook Space tab or the Group card. Answer today's question by voice. | "One easy question a day. Nobody sees this, not us and not your friends." |
| 1:20 | Day result: your star, your constellation, and one line of what you share. | "These people felt this today. Muse wrote that line, and a guard checked it never quotes anyone." |
| 2:00 | Operator console, formation debug. Keywords split two players, Muse joins them. | "Keywords see no overlap. Muse sees the same feeling. This is why it needs a model." |
| 2:30 | Saturday sky, telescope zoom. | "Every dot is a real person. Nobody can tell which one you are." |
| 3:00 | Sunday: your people form the Meta logo, 24-hour room opens, two people reveal. | "You choose to be known." |
| 3:40 | Mutual reveal: Add friend, Message on Messenger (labeled Simulated Facebook). | "The room expires, the connection does not." |
| 4:10 | Why Facebook | "Groups are the community boundary, Events turn a match into a plan, real names make a reveal trustworthy. Instagram has none of the three." |
| 4:40 | Close | "Nobody should have to feel like the only one." |

## What is real and what is simulated

- Real: Muse M3 groups each day, M4 forms Sunday's groups, code enforces size (5 or more, no
  maximum), blocks, one placement per player, and no quotes. Shared-meaning lines pass the output
  guard and show only for 3 or more people.
- Simulated and labeled: the 38-player demo population (synthetic profiles), Facebook friend and
  Messenger actions ("Simulated Facebook"), and chat messages (no live source yet).
- Not claimed: scale beyond the demo population, live results on real users.

## Q&A answers

- **Why not keywords or a person?** Keyword matching scored 0.13 on our test set and Muse 0.95 to
  1.0. A person would have to read everyone's private answers, which is what we promise not to do.
- **Small Groups?** A constellation needs 5 people who answered the same day. In a 40-person club
  it may be empty on a quiet day, so it falls back to the week's pool. Larger communities work best.
- **Predators?** Group membership is the gate, adult checkbox plus consent, rooms are group-only
  with no one-to-one before a mutual reveal, rate limits on reveal requests, every message passes a
  safety screen. We do not claim identity verification beyond that.
- **Friend leak?** Friend ids from the client are no longer stored or counted, so nobody can probe
  whether a specific person is in their room.
- **Streaks and loneliness?** Streaks reward showing up, never what you disclose.
- **The name?** Meta's earlier "Facebook Spaces" was about avatars. This one is about real people.

## Stage view (built 2026-11-13, D017)
The planned staging is two phones and one laptop on the big screen.
- **Laptop:** open `/space/stage` in a browser whose player has the operator role (see docs/DEPLOYMENT.md, issue 4). It shows Phone A on the left, Phone B on the right and the Muse pipeline between them, and has the week controls at the bottom (start week, next day, add synthetic players, lock, find people, reveal). "Reveal" stays disabled while Muse is matching.
- **Each phone:** join Facebook Space, then Privacy → Demo screen → choose Phone A or Phone B. Until then the stage shows that phone as "not connected". Only these two players' answers appear as text; everyone else is a count or a dot.
- **Order that works:** start week → both phones answer each day → next day (x4) → on Friday press "Add synthetic players" → lock → find people → wait about 10 s → reveal.
- **Not guaranteed:** that the two phones land in different constellations. Muse groups by meaning; two clearly different sets of answers make it likely, nothing forces it.
- Do not merge to `main` during the demo: a redeploy erases the running week.

## Run sheet

1. Start backend and web, open the Group page, show the Space card.
2. Operator: top up the synthetic population, close day, show formation debug.
3. Play the sky, then Sunday and the reveal.
4. Keep a recorded backup of the same run.
