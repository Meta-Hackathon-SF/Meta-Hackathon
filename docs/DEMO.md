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
- Simulated and labeled: the 108-player demo population (100-person synthetic cast plus 8 fixture players, D018), Facebook friend and
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

## Stage view (D017, D019)
Two phones and one laptop on the big screen. The laptop drives the whole week; the phones only join and type one answer.

1. **Laptop:** sign in to Facebook Space, then open `/space/stage`. Leave it open on the big screen.
2. **Phones:** each presenter opens the site and joins Facebook Space. They appear on the stage by themselves within two seconds, the first to join as Phone A. If the wrong account shows up, press **Phones** on the stage to re-detect, or use Privacy → Demo screen on the phone to pick a side or hide.
3. **Start demo week.** 100 synthetic players arrive with their Monday answers; the phones' Monday answer is filled in.
4. **Next day** four times (Tuesday to Friday). The bars and dots grow; the phones' answers are filled in for them.
5. **Friday:** the stage shows each presenter the exact line to type under their phone, with the day's question. They type it and post. The Safety step lights up: Muse screened it.
6. **Lock the week and match.** Muse reads the week (Themes, Groups); the button says "Muse is matching…" until the constellations exist. Plan for 20 seconds to 2 minutes.
7. **Reveal Sunday.** Each phone panel draws its own constellation map and name; the community sky regroups every player into constellations and outlines Phone A's and Phone B's.
8. **Start again** resets the week (same phones).

Do not merge to `main` during the demo: a redeploy erases the running week. Different constellations are likely, not guaranteed.

### What each phone types
The stage shows the right line for the week's questions; this is the full script for reference (Monday to Thursday are filled in automatically).

| Question | Phone A (films, nobody to talk to after) | Phone B (pickup games and the team chat) |
| --- | --- | --- |
| Where did you eat most of your meals this week, and who was usually around? | Mostly in my room with a movie on my laptop, honestly. | The dining hall after pickup, the whole team takes the long table. |
| What's something you pretended to be fine with this week? | That I liked watching the new season finale alone at 1am. | That I was fine sitting out the game with a sore ankle. |
| What small thing made your day better recently? | Someone in class quoted my favorite movie and I almost cried. | Hit the game winner in pickup and the group chat went off. |
| What could you teach someone in ten minutes? | Why the best scene in a movie is usually the quiet one. | How to serve a volleyball so it actually goes over. |
| If this weekend went perfectly, what would you be doing? | A double feature with a few people who actually want to talk after. | A tournament all Saturday and tacos with the team after. |
| What's the hardest part of being new here that nobody talks about? | I finish a great film and have nobody to talk to about it. | When the season ends I have no idea what to do with my evenings. |
| What does a good friend do that most people forget? | Watches the thing you recommended and texts you about it. | Shows up to your game even when it is cold out. |
| What are you usually doing at 11pm on a weeknight? | Rewatching the same comfort show for the fourth time. | Arguing in the team chat about who owes who a rematch. |
| What rabbit hole have you fallen into lately? | Director commentary tracks. All of them. Every film. | Old championship highlights at 2x speed. |
| What do you miss about where you came from? | Movie nights on the couch with my sister arguing about endings. | My club team back home. We practiced together since we were ten. |
| What's your go-to thing to do when you need to recharge? | Headphones, a blanket and a film I already know by heart. | A pickup game where nobody keeps score too seriously. |
| What's one thing you want to try this semester but haven't yet? | Going to the film club screening instead of watching alone. | Starting a weekly ultimate game on the quad. |
| What does the first hour of your day usually look like? | Coffee and reading reviews of whatever I watched last night. | Early run, then breakfast with whoever from the team is awake. |
| Where do you usually end up between classes or shifts, and what do you do there? | The library basement with subtitles on, half a movie at a time. | The rec center courts, shooting around with whoever shows up. |
| How do your Sundays usually go? | Slow morning, then two movies in a row and nobody to text after. | Intramural games all afternoon, then everyone crashes at the dining hall. |
| When did you last laugh with someone here, and what set it off? | A guy behind me in the theater laughed at the same tiny joke. | Our goalie slid into the snack table at practice. |
| What's something you almost said yes to this week? | Asking someone from class to see the new release with me. | Joining a second intramural team. Still might. |
| What's one thing people here would have to know to really know you? | I remember people by which movie they reminded me of. | I get really competitive, then I am the first to say good game. |
| What could you talk about for an hour without getting bored? | Endings. Which ones work, which ones betray the whole film. | The perfect pickup lineup and why it always falls apart. |
| What have you been making, building or practicing lately? | A list of movies I would show someone on a first watch night. | Practicing my jump serve every single day. |
| What's a small thing someone can do that earns your respect right away? | Putting their phone away for the whole movie. | Calling their own fouls in pickup. |
| What's something you changed your mind about in the last year? | Rewatching is not wasting time, it is how I find new things. | Losing with good people is better than winning with jerks. |
| What do you wish people made more time for? | Sitting through the credits and talking about it after. | Playing outside, even badly, with a bunch of people. |
| What would you like to be different about your weeks a month from now? | One night a week where I watch something with other people. | A game on the calendar every night of the week. |
| What song or sound has been on repeat for you lately, and when do you play it? | The soundtrack from the last film I loved, on every walk. | The warmup playlist from our locker room, before every game. |
| What spot around here do you like more than most people seem to? | The empty lecture hall with the big screen after six. | The sand courts at sunset when a game is going. |
| What turned out to be harder than you expected this term? | Finding people who want to talk about movies, not just watch them. | Keeping up with class when I have games four nights a week. |
| What do you wish were easier to ask people for? | Asking someone to watch something with me without it being weird. | Asking strangers on the court if they need one more player. |
| What would you like to learn from someone here? | How to pick a movie a whole group will actually like. | How to actually throw a forehand in ultimate. |
| What are you looking forward to in the next few weeks? | The film club screening next week, if I actually go. | Intramural playoffs and the pickup volleyball night. |
| What habit have you been trying to start or stop, and how is it going? | Stopping the second episode at 1am. Going badly. | Stretching after games. I keep forgetting. |
| What's your go-to small treat after a long day? | Popcorn and a movie I have seen ten times. | A cold drink from the vending machine after a game. |

## Run sheet

1. Start backend and web, open the Group page, show the Space card.
2. Operator: top up the synthetic population, close day, show formation debug.
3. Play the sky, then Sunday and the reveal.
4. Keep a recorded backup of the same run.
