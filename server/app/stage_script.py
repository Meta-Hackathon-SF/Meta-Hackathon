"""Scripted answers for the two stage phones (demo only).

The demo shows two presenters' phones. To keep the demo short, Monday to
Thursday are filled in from this script when the operator starts the demo
week, and the presenters type only Friday's answer live (the stage shows them
the line to type). The questions are picked per week, so every bank question
has a line.

The two scripts mean clearly different things so Muse has a real reason to put
the phones in different constellations: Phone A watches films alone and wants
people to talk them over with; Phone B lives for pickup games and the team
chat. Matching is not told this; the answers are all it sees.
"""

PHONE_A: dict[str, str] = {
    "q-routine-meals": "Mostly in my room with a movie on my laptop, honestly.",
    "q-belonging-pretend": "That I liked watching the new season finale alone at 1am.",
    "q-joys-small-win": "Someone in class quoted my favorite movie and I almost cried.",
    "q-interests-teach": "Why the best scene in a movie is usually the quiet one.",
    "q-hopes-weekend": "A double feature with a few people who actually want to talk after.",
    "q-challenges-hard-part": "I finish a great film and have nobody to talk to about it.",
    "q-values-good-friend": "Watches the thing you recommended and texts you about it.",
    "q-routine-late-night": "Rewatching the same comfort show for the fourth time.",
    "q-interests-rabbit-hole": "Director commentary tracks. All of them. Every film.",
    "q-belonging-home": "Movie nights on the couch with my sister arguing about endings.",
    "q-joys-comfort": "Headphones, a blanket and a film I already know by heart.",
    "q-hopes-try": "Going to the film club screening instead of watching alone.",
    "q-routine-first-hour": "Coffee and reading reviews of whatever I watched last night.",
    "q-routine-between": "The library basement with subtitles on, half a movie at a time.",
    "q-routine-sunday": "Slow morning, then two movies in a row and nobody to text after.",
    "q-belonging-last-laugh": "A guy behind me in the theater laughed at the same tiny joke.",
    "q-belonging-almost": "Asking someone from class to see the new release with me.",
    "q-belonging-know-you": "I remember people by which movie they reminded me of.",
    "q-interests-hours": "Endings. Which ones work, which ones betray the whole film.",
    "q-interests-making": "A list of movies I would show someone on a first watch night.",
    "q-values-respect": "Putting their phone away for the whole movie.",
    "q-values-changed-mind": "Rewatching is not wasting time, it is how I find new things.",
    "q-values-time": "Sitting through the credits and talking about it after.",
    "q-hopes-different": "One night a week where I watch something with other people.",
    "q-joys-song": "The soundtrack from the last film I loved, on every walk.",
    "q-joys-place": "The empty lecture hall with the big screen after six.",
    "q-challenges-harder": "Finding people who want to talk about movies, not just watch them.",
    "q-challenges-easier": "Asking someone to watch something with me without it being weird.",
    "q-hopes-learn": "How to pick a movie a whole group will actually like.",
    "q-hopes-looking-forward": "The film club screening next week, if I actually go.",
    "q-challenges-habit": "Stopping the second episode at 1am. Going badly.",
    "q-joys-treat": "Popcorn and a movie I have seen ten times.",
}

PHONE_B: dict[str, str] = {
    "q-routine-meals": "The dining hall after pickup, the whole team takes the long table.",
    "q-belonging-pretend": "That I was fine sitting out the game with a sore ankle.",
    "q-joys-small-win": "Hit the game winner in pickup and the group chat went off.",
    "q-interests-teach": "How to serve a volleyball so it actually goes over.",
    "q-hopes-weekend": "A tournament all Saturday and tacos with the team after.",
    "q-challenges-hard-part": "When the season ends I have no idea what to do with my evenings.",
    "q-values-good-friend": "Shows up to your game even when it is cold out.",
    "q-routine-late-night": "Arguing in the team chat about who owes who a rematch.",
    "q-interests-rabbit-hole": "Old championship highlights at 2x speed.",
    "q-belonging-home": "My club team back home. We practiced together since we were ten.",
    "q-joys-comfort": "A pickup game where nobody keeps score too seriously.",
    "q-hopes-try": "Starting a weekly ultimate game on the quad.",
    "q-routine-first-hour": "Early run, then breakfast with whoever from the team is awake.",
    "q-routine-between": "The rec center courts, shooting around with whoever shows up.",
    "q-routine-sunday": "Intramural games all afternoon, then everyone crashes at the dining hall.",
    "q-belonging-last-laugh": "Our goalie slid into the snack table at practice.",
    "q-belonging-almost": "Joining a second intramural team. Still might.",
    "q-belonging-know-you": "I get really competitive, then I am the first to say good game.",
    "q-interests-hours": "The perfect pickup lineup and why it always falls apart.",
    "q-interests-making": "Practicing my jump serve every single day.",
    "q-values-respect": "Calling their own fouls in pickup.",
    "q-values-changed-mind": "Losing with good people is better than winning with jerks.",
    "q-values-time": "Playing outside, even badly, with a bunch of people.",
    "q-hopes-different": "A game on the calendar every night of the week.",
    "q-joys-song": "The warmup playlist from our locker room, before every game.",
    "q-joys-place": "The sand courts at sunset when a game is going.",
    "q-challenges-harder": "Keeping up with class when I have games four nights a week.",
    "q-challenges-easier": "Asking strangers on the court if they need one more player.",
    "q-hopes-learn": "How to actually throw a forehand in ultimate.",
    "q-hopes-looking-forward": "Intramural playoffs and the pickup volleyball night.",
    "q-challenges-habit": "Stretching after games. I keep forgetting.",
    "q-joys-treat": "A cold drink from the vending machine after a game.",
}

SCRIPTS = {"A": PHONE_A, "B": PHONE_B}
