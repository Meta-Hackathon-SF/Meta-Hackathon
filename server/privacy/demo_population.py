"""Demo population: 30 SYNTHETIC players with daily answers, posts and comments.

Every player is labeled synthetic (``is_synthetic=1`` and "(synthetic)" in the
name) and is never counted as a real participant. All text here is written for
the demo; none of it comes from real people.

    from server.privacy.demo_population import seed_demo_population
    seed_demo_population(store, answers, community_id, cycle_id, {1: "q-...", ...})

    # feed copy for the web shell
    python -m server.privacy.demo_population --export-feed web/src/data/population.json

Five themes, six players each, so formation has clear groups to find:
night builders, dinner company, home cooking, outdoors, music and stage.
Answers exist for every question in contracts/fixtures/question-bank.json; the
seeder picks the ones the cycle actually asks.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Iterable, Mapping
from pathlib import Path

from .answers import AnswerStore
from .fixtures import seed_players
from .store import PrivacyStore

# ---------------------------------------------------------------- answers
# theme -> questionId -> two variants (players in a theme alternate them).
ANSWERS: dict[str, dict[str, tuple[str, str]]] = {
    "night_builders": {
        "q-routine-meals": ("Mostly at my desk in the lab, eating whatever I grabbed on the way. Usually just me and a laptop.",
                            "Late dinners in the engineering building, usually with whoever is still around debugging."),
        "q-belonging-pretend": ("Pretended I understood the group project plan when I was totally lost.",
                                "Acted like staying up until 3 to finish a build was no big deal."),
        "q-joys-small-win": ("My code compiled on the first try at 1am and I actually cheered out loud.",
                             "Someone left a sticky note saying my demo was cool."),
        "q-interests-teach": ("How to use git without losing your work. Ten minutes, I promise.",
                              "How to make a simple website from scratch with nothing installed."),
        "q-hopes-weekend": ("A small hackathon with friends, pizza at midnight, and shipping something silly.",
                            "Building a tiny game with two other people and actually finishing it."),
        "q-challenges-hard-part": ("Everyone seems to already have a study group and I don't know how to ask to join one.",
                                   "Working late means I miss all the evening stuff where people meet."),
        "q-values-good-friend": ("Checks in when you've gone quiet for a few days.",
                                 "Sends you the random article they know you'll like."),
        "q-routine-late-night": ("Coding with headphones on, usually some side project.",
                                 "Fixing bugs and drinking way too much tea."),
        "q-interests-rabbit-hole": ("Old video game consoles and how they squeezed so much out of tiny chips.",
                                    "Mechanical keyboards. I now own three. I need one."),
        "q-belonging-home": ("My old robotics team. We built stuff together every weekend.",
                             "Having a crew that stayed up late working on things with me."),
        "q-joys-comfort": ("Putting on a playlist and building something small just for fun.",
                           "Retro games, a snack, and no notifications."),
        "q-hopes-try": ("Joining a hackathon team instead of watching from the side.",
                        "Showing a project at a demo night."),
    },
    "dinner_company": {
        "q-routine-meals": ("The dining hall, usually at a corner table by myself with my phone.",
                            "Grabbing food to go and eating in my room because walking in alone feels weird."),
        "q-belonging-pretend": ("Said I already ate when people asked if I wanted to come to dinner, then regretted it.",
                                "Pretended I liked eating alone so it wouldn't look like I had no one to sit with."),
        "q-joys-small-win": ("Someone in my class asked if they could sit with me at lunch.",
                             "A long dinner where nobody looked at their phone."),
        "q-interests-teach": ("How to find the best thing on the dining hall menu every night.",
                              "How to start a conversation with the person next to you in line."),
        "q-hopes-weekend": ("A big group dinner that goes on way too long.",
                            "Trying a new restaurant downtown with a few people."),
        "q-challenges-hard-part": ("Walking into a full dining hall and not knowing where to sit.",
                                   "Meals are when you notice you don't have a group yet."),
        "q-values-good-friend": ("Saves you a seat without being asked.",
                                 "Texts 'dinner?' at 6pm like it's obvious you're coming."),
        "q-routine-late-night": ("Watching shows and snacking, wishing someone was around to talk to.",
                                 "Scrolling food videos and planning meals I'll eat alone."),
        "q-interests-rabbit-hole": ("Watching people review every dish at random restaurants.",
                                    "Ranking every dining hall dessert. Strong opinions."),
        "q-belonging-home": ("Family dinners where everyone talked over each other.",
                             "Eating with people every night without having to plan it."),
        "q-joys-comfort": ("A long walk to get bubble tea.",
                           "Cooking instant noodles and calling a friend from back home."),
        "q-hopes-try": ("Starting a weekly dinner with people from my floor.",
                        "Asking someone from class to grab food after."),
    },
    "home_cooking": {
        "q-routine-meals": ("Cooking for one in the shared kitchen, mostly rice and whatever is on sale.",
                            "Meal prepping on Sundays, then eating the same thing all week."),
        "q-belonging-pretend": ("Pretended the cafeteria food was fine when I really miss real cooking.",
                                "Said I didn't mind cooking alone every night."),
        "q-joys-small-win": ("Finally got my grandma's soup recipe to taste right.",
                             "Someone in the kitchen asked what I was making because it smelled amazing."),
        "q-interests-teach": ("How to make fried rice that doesn't turn mushy.",
                              "How to make a good sauce out of five cheap things."),
        "q-hopes-weekend": ("A potluck where everyone brings a dish from where they grew up.",
                            "Farmers market in the morning, cooking with friends at night."),
        "q-challenges-hard-part": ("Nobody tells you how much you'll miss the food you grew up with.",
                                   "Cooking a big meal and having no one to share it with."),
        "q-values-good-friend": ("Shows up with food when you're having a long week.",
                                 "Remembers your favorite snack."),
        "q-routine-late-night": ("Making tomorrow's lunch and listening to a podcast.",
                                 "Watching cooking videos and writing down recipes I'll try."),
        "q-interests-rabbit-hole": ("Fermenting things. My shelf has three jars of kimchi now.",
                                    "Bread. So much bread. Sourdough starter named Gary."),
        "q-belonging-home": ("My mom's cooking and the whole kitchen smelling like garlic.",
                             "Weekend markets with my dad and the street food there."),
        "q-joys-comfort": ("Cooking something slow and complicated with music on.",
                           "Baking cookies and giving most of them away."),
        "q-hopes-try": ("Hosting a dinner for people I just met.",
                        "Joining a cooking club."),
    },
    "outdoors": {
        "q-routine-meals": ("Packing sandwiches and eating outside on the lawn between classes.",
                            "Quick meals so I can get out on the trails before dark."),
        "q-belonging-pretend": ("Pretended I was fine staying inside all weekend when I really wanted to go hiking.",
                                "Acted like I didn't care that nobody wanted to come climbing."),
        "q-joys-small-win": ("Caught the sunset from the hill behind the library.",
                             "Found a trail ten minutes from campus that nobody uses."),
        "q-interests-teach": ("How to tie three knots that actually matter.",
                              "How to read a trail map so you never get lost."),
        "q-hopes-weekend": ("A sunrise hike with a few people and breakfast after.",
                            "Climbing gym in the morning and a long bike ride after."),
        "q-challenges-hard-part": ("Not having a car and not knowing anyone who wants to go outside.",
                                   "Everyone's plans are indoors and I get restless."),
        "q-values-good-friend": ("Says yes to the early alarm even though they hate mornings.",
                                 "Waits for you at the top without making it a thing."),
        "q-routine-late-night": ("Planning routes for the weekend.",
                                 "Stretching and going to bed early so I can get up for a run."),
        "q-interests-rabbit-hole": ("Bird calls. I can name like twelve now.",
                                    "Watching videos of people climbing huge walls."),
        "q-belonging-home": ("Being ten minutes from the woods.",
                             "Weekend camping trips with my cousins."),
        "q-joys-comfort": ("A long walk with no headphones.",
                           "Bouldering until my hands give up."),
        "q-hopes-try": ("An overnight camping trip with people from here.",
                        "Joining the climbing club's beginner night."),
    },
    "music_stage": {
        "q-routine-meals": ("Quick meals between rehearsals, usually with the band.",
                            "Eating while practicing chords on the couch, usually alone."),
        "q-belonging-pretend": ("Pretended I wasn't nervous when someone asked me to sing.",
                                "Said I didn't care about the open mic when I really wanted to sign up."),
        "q-joys-small-win": ("A stranger hummed along to a song I was playing outside.",
                             "Finally nailed the bridge of a song I've been stuck on for weeks."),
        "q-interests-teach": ("Three chords that let you play half the songs you know.",
                              "How to make a beat on your phone."),
        "q-hopes-weekend": ("A jam session in someone's living room that turns into a sing-along.",
                            "Going to a small show and then talking about it for hours."),
        "q-challenges-hard-part": ("Finding people to play music with when you don't know anyone.",
                                   "Everyone seems confident on stage except me."),
        "q-values-good-friend": ("Comes to your show even when it's tiny.",
                                 "Sends you a song and says 'this made me think of you'."),
        "q-routine-late-night": ("Writing lyrics in my notes app.",
                                 "Playing guitar quietly so I don't wake my roommate."),
        "q-interests-rabbit-hole": ("Old vinyl records from the 70s.",
                                    "How film scores make you feel things."),
        "q-belonging-home": ("My old band and our terrible garage shows.",
                             "Singing in the car with my sister."),
        "q-joys-comfort": ("Headphones on, playing an album start to finish.",
                           "Playing piano in an empty practice room."),
        "q-hopes-try": ("Signing up for the open mic.",
                        "Starting a band with people I meet here."),
    },
}

# The other 20 questions in the planning bank: one answer per theme.
_MORE: dict[str, dict[str, str]] = {
    "night_builders": {
        "q-routine-first-hour": "Snooze twice, coffee, then checking if last night's build passed.",
        "q-routine-between": "The lab, finishing whatever I broke the night before.",
        "q-routine-sunday": "Sleeping in, then a long coding session on a side project.",
        "q-belonging-last-laugh": "When our demo crashed live and the whole team just started laughing.",
        "q-belonging-almost": "Almost joined a hackathon team, then chickened out.",
        "q-belonging-know-you": "I get really excited about tiny projects nobody asked for.",
        "q-interests-hours": "How old video games were made with almost no memory.",
        "q-interests-making": "A little app that tells you when the laundry machines are free.",
        "q-values-respect": "Admitting when you don't know something.",
        "q-values-changed-mind": "That working alone is faster. It isn't, it's just quieter.",
        "q-values-time": "Building silly things just for fun.",
        "q-hopes-different": "Having a team to build things with instead of doing it all alone.",
        "q-joys-song": "Lo-fi beats, every night while I code.",
        "q-joys-place": "The empty study room on the third floor after 10pm.",
        "q-challenges-harder": "Finding people who want to build stuff outside of class.",
        "q-challenges-easier": "Asking someone to pair on a bug with me.",
        "q-hopes-learn": "Design. My apps work but they look terrible.",
        "q-hopes-looking-forward": "The hackathon next weekend.",
        "q-challenges-habit": "Trying to stop coding past 2am. Going badly.",
        "q-joys-treat": "Energy drink and a new episode of a dev podcast.",
    },
    "dinner_company": {
        "q-routine-first-hour": "Grabbing breakfast to go and eating it on the walk to class.",
        "q-routine-between": "Sitting in the dining hall, hoping someone I know walks in.",
        "q-routine-sunday": "Brunch if I can find someone to go with, otherwise laundry.",
        "q-belonging-last-laugh": "Someone at dinner told a story about a lost cat and we couldn't stop laughing.",
        "q-belonging-almost": "Almost asked my lab partner to get dinner.",
        "q-belonging-know-you": "I love long dinners where nobody is in a hurry.",
        "q-interests-hours": "Every restaurant in town and what to order there.",
        "q-interests-making": "A list of the best cheap eats near campus.",
        "q-values-respect": "Inviting the person who's sitting alone.",
        "q-values-changed-mind": "That eating alone is fine. It's fine sometimes, not every night.",
        "q-values-time": "Sitting down for a real meal together.",
        "q-hopes-different": "A regular dinner crew I don't have to plan with.",
        "q-joys-song": "Cooking-show music, weirdly. It makes me hungry.",
        "q-joys-place": "The window table at the noodle place downtown.",
        "q-challenges-harder": "Finding people to eat with who aren't already in a group.",
        "q-challenges-easier": "Asking 'want to grab food?' without it feeling awkward.",
        "q-hopes-learn": "How to cook one meal well enough to invite people over.",
        "q-hopes-looking-forward": "A big group dinner someone is planning on Friday.",
        "q-challenges-habit": "Trying to stop skipping dinner when I'd have to eat alone.",
        "q-joys-treat": "Bubble tea, always.",
    },
    "home_cooking": {
        "q-routine-first-hour": "Making real breakfast. Eggs, rice, the works.",
        "q-routine-between": "The shared kitchen, prepping something for later.",
        "q-routine-sunday": "Farmers market, then meal prep for the whole week.",
        "q-belonging-last-laugh": "My roommate tried to flip a pancake and it hit the ceiling.",
        "q-belonging-almost": "Almost invited my whole floor over for dumplings.",
        "q-belonging-know-you": "Food is how I show people I care.",
        "q-interests-hours": "Spices and what each one does.",
        "q-interests-making": "Trying to get my family's dumpling recipe right.",
        "q-values-respect": "Washing their own dishes in the shared kitchen.",
        "q-values-changed-mind": "That cooking for one isn't worth it. It is, just make leftovers.",
        "q-values-time": "Cooking together instead of ordering in.",
        "q-hopes-different": "Cooking for people, not just for myself.",
        "q-joys-song": "Old songs my parents played while cooking.",
        "q-joys-place": "The farmers market on Saturday mornings.",
        "q-challenges-harder": "Finding the ingredients I grew up with.",
        "q-challenges-easier": "Asking people to come eat what I made.",
        "q-hopes-learn": "Someone's family recipe from a place I've never been.",
        "q-hopes-looking-forward": "The potluck we're trying to plan.",
        "q-challenges-habit": "Trying to cook every day instead of snacking.",
        "q-joys-treat": "A warm bowl of soup I made on Sunday.",
    },
    "outdoors": {
        "q-routine-first-hour": "A run before anyone else is awake.",
        "q-routine-between": "Outside on the lawn, even when it's cold.",
        "q-routine-sunday": "A long hike if the weather is good.",
        "q-belonging-last-laugh": "Someone fell in a creek on a hike and laughed harder than all of us.",
        "q-belonging-almost": "Almost asked my lab group to go climbing.",
        "q-belonging-know-you": "I get grumpy if I stay inside too long.",
        "q-interests-hours": "Trails, gear, and where to see the best sunsets.",
        "q-interests-making": "A map of every good trail near campus.",
        "q-values-respect": "Showing up on time for a 6am start.",
        "q-values-changed-mind": "That I need a big trip to feel outside. A walk is enough.",
        "q-values-time": "Being outside without a phone.",
        "q-hopes-different": "More weekends outside with people instead of alone.",
        "q-joys-song": "Rain sounds, honestly.",
        "q-joys-place": "The hill behind the library at sunset.",
        "q-challenges-harder": "Getting anywhere without a car.",
        "q-challenges-easier": "Asking people to join a hike without it feeling like a big ask.",
        "q-hopes-learn": "How to climb outdoors, not just at the gym.",
        "q-hopes-looking-forward": "The camping trip in two weeks.",
        "q-challenges-habit": "Trying to stretch after runs. I always forget.",
        "q-joys-treat": "Hot chocolate after a cold walk.",
    },
    "music_stage": {
        "q-routine-first-hour": "Playlist on, getting ready while singing too loud.",
        "q-routine-between": "Practice rooms in the music building.",
        "q-routine-sunday": "Long practice session, then a small show if there is one.",
        "q-belonging-last-laugh": "Our jam session turned into everyone singing the wrong lyrics.",
        "q-belonging-almost": "Almost signed up for the open mic. Next week, for real.",
        "q-belonging-know-you": "Music is basically my whole personality.",
        "q-interests-hours": "Why some songs give you chills.",
        "q-interests-making": "Writing my first full song.",
        "q-values-respect": "Clapping for someone who's clearly nervous on stage.",
        "q-values-changed-mind": "That you need to be great to play for people. You don't.",
        "q-values-time": "Going to small shows and supporting people.",
        "q-hopes-different": "Playing with other people every week.",
        "q-joys-song": "An old soul record I found at the thrift store. Every morning.",
        "q-joys-place": "Practice room 4. The piano is perfect.",
        "q-challenges-harder": "Finding people to play music with.",
        "q-challenges-easier": "Asking someone to come to my show.",
        "q-hopes-learn": "How to record songs properly.",
        "q-hopes-looking-forward": "The open mic on Thursday.",
        "q-challenges-habit": "Practicing every day instead of only when I feel like it.",
        "q-joys-treat": "A new album and a long walk.",
    },
}
for _theme, _extra in _MORE.items():
    for _qid, _text in _extra.items():
        ANSWERS[_theme].setdefault(_qid, (_text, _text))

# --------------------------------------------------------- players + feed
COLORS = ["#4c6ef5", "#12b886", "#f59f00", "#e64980", "#7950f2", "#15aabf"]
_NAMES = {
    "night_builders": ["Theo Park", "Nia Brooks", "Ravi Shah", "Lena Ortiz", "Sam Okafor", "Ivy Chen"],
    "dinner_company": ["Mila Novak", "Jonah Reed", "Priya Nair", "Leo Martin", "Zoe Adams", "Kenji Sato"],
    "home_cooking": ["Ana Silva", "Marco Rossi", "Hana Kim", "Omar Haddad", "Lucy Tran", "Ben Weiss"],
    "outdoors": ["Ella Hart", "Noah Price", "Aisha Bello", "Finn Murphy", "Rosa Diaz", "Eli Cohen"],
    "music_stage": ["Jade Wu", "Caleb Stone", "Maya Lopez", "Ollie Grant", "Sara Iqbal", "Toby Lane"],
}
_GROUPS = {
    "night_builders": ["g-hackathon-builders", "g-xr-student-collective"],
    "dinner_company": ["g-hackathon-builders"],
    "home_cooking": ["g-campus-cooks"],
    "outdoors": ["g-campus-outdoors"],
    "music_stage": ["g-xr-student-collective", "g-campus-music"],
}
_EVENTS = {  # approved catalog ids (contracts/fixtures/venues.json)
    "night_builders": ["ev-board-games"],
    "dinner_company": ["ev-board-games", "ev-film-club"],
    "home_cooking": ["ev-film-club"],
    "outdoors": ["ev-volleyball"],
    "music_stage": ["ev-open-mic"],
}
# One post per player, in name order.
_POSTS = {
    "night_builders": [
        "Anyone else still in the lab? Ordering pizza, there's room for two more 🍕",
        "Shipped my first side project tonight. It's tiny and a little broken but it's mine.",
        "Looking for 1-2 people for the weekend hackathon. I can do backend, need someone who likes design.",
        "New keyboard day. My roommate is not thrilled about the clicky switches.",
        "Late-night study room on floor 3 is the best kept secret on campus.",
        "Made a little game where you catch falling stars. Link in comments if you want to try it!",
    ],
    "dinner_company": [
        "Dining hall at 6? I'll be at the long table by the windows if anyone wants to join.",
        "Hot take: the Tuesday pasta is the best meal of the week.",
        "Is there a group that does dinner together? Asking for me.",
        "Found a cheap noodle place downtown. Need people to go with so I can order more dishes.",
        "Dessert ranking of every dining hall so far. Fight me in the comments.",
        "Trying to start a Sunday brunch thing. Low effort, just show up.",
    ],
    "home_cooking": [
        "Made my grandma's soup in the shared kitchen and three people asked for the recipe 🥣",
        "Weekly meal prep done. Five boxes of the same curry. No regrets.",
        "Potluck idea: everyone brings one dish from where they grew up. Who's in?",
        "Sourdough starter update: Gary is thriving.",
        "Farmers market haul this morning. Peaches are back!",
        "Baked way too many cookies. Floor 2 kitchen, come take some.",
    ],
    "outdoors": [
        "Sunrise hike Saturday, easy trail, back by 10. Bringing extra snacks.",
        "Found a quiet trail ten minutes from campus. Who wants to explore it this weekend?",
        "Climbing gym beginner night was so fun. Going again Thursday!",
        "Pickup volleyball on the lawn at 4, all levels welcome.",
        "That sunset from the library hill tonight 🌅",
        "Planning a bike ride along the coast next weekend. Slow pace, lots of stops.",
    ],
    "music_stage": [
        "Open mic is Thursday. Who's signing up? I'll go if you go.",
        "Looking for people to jam with. I play guitar badly but enthusiastically.",
        "Found a crate of old records at the thrift store 🎶",
        "Practice room 4 has the good piano. You're welcome.",
        "Wrote a song about the campus shuttle being late. It's a banger.",
        "Small show at the café Friday night. Come say hi!",
    ],
}
_COMMENTS = {
    "night_builders": ["I'm in, saving you a seat!", "This is so cool, show us at demo night", "Count me in for the hackathon",
                       "Same, I'm here until midnight most days", "Teach me git please"],
    "dinner_company": ["Saving you a seat 🙌", "I'll be there at 6!", "Yes please, I always eat alone on Tuesdays",
                       "Count me in for brunch", "Strong agree on the pasta"],
    "home_cooking": ["Recipe please!!", "I'll bring dumplings", "Coming over right now", "Potluck, yes!",
                     "Can you teach me to make that?"],
    "outdoors": ["I'll bring the snacks", "Down for Saturday!", "Can a total beginner come?", "See you on the lawn",
                 "Count me in for the bike ride"],
    "music_stage": ["I'll go if you go 🎤", "I play bass, let's jam", "Need to hear this song", "See you Friday!",
                    "Room 4 forever"],
}


def _slug(name: str) -> str:
    return name.lower().replace(" ", "-")


def players() -> list[dict]:
    out = []
    for theme, names in _NAMES.items():
        for i, name in enumerate(names):
            out.append({
                "playerId": f"p-demo-{_slug(name)}",
                "displayName": f"{name} (synthetic)",
                "avatarColor": COLORS[i % len(COLORS)],
                "isSynthetic": True,
                "theme": theme,
                "variant": i % 2,
                "groupIds": _GROUPS[theme],
                "eventIds": _EVENTS[theme],
                "post": _POSTS[theme][i],
            })
    return out


def feed() -> list[dict]:
    """Feed posts for the web shell: one per player, each with 2-3 comments from
    players in the same theme (so the people who'd match already talk)."""
    posts = []
    ps = players()
    by_theme: dict[str, list[dict]] = {}
    for p in ps:
        by_theme.setdefault(p["theme"], []).append(p)
    for theme, members in by_theme.items():
        for i, p in enumerate(members):
            commenters = [members[(i + k) % len(members)] for k in (1, 2, 3)][: 2 + i % 2]
            comments = [{"id": f"c-{p['playerId']}-{k}", "authorName": c["displayName"], "authorColor": c["avatarColor"],
                         "text": _COMMENTS[theme][(i + k) % len(_COMMENTS[theme])]} for k, c in enumerate(commenters)]
            posts.append({"id": f"post-{p['playerId']}", "authorName": p["displayName"], "authorColor": p["avatarColor"],
                          "theme": theme, "text": p["post"], "comments": comments,
                          "reactionCount": 3 + (i * 7) % 23, "minutesAgo": 15 + i * 37 + len(theme) * 5})
    # interleave themes so the feed doesn't show one group in a block
    posts.sort(key=lambda x: x["minutesAgo"])
    return posts


def topup_rows(question_by_day: Mapping[int, str]) -> list[dict]:
    """Answer rows ``{playerId, day, text}`` for the cycle's questions, in the
    shape ``CycleService.synthetic_topup`` already saves."""
    rows = []
    for p in players():
        for day, qid in sorted(question_by_day.items()):
            pair = ANSWERS[p["theme"]].get(qid)
            if pair:
                rows.append({"playerId": p["playerId"], "day": day, "text": pair[p["variant"]]})
    return rows


def seed_demo_population(
    store: PrivacyStore,
    answers: AnswerStore,
    community_id: str,
    cycle_id: str,
    question_by_day: Mapping[int, str],
    days: Iterable[int] = (1, 2, 3, 4, 5),
    *,
    activity=None,
    now: str = "2026-11-09T18:00:00Z",
) -> list[str]:
    """Seed the 30 synthetic players as consenting members with an answer for
    each given day (using the cycle's questionId for that day). With an
    ``ActivityStore`` also stores their Groups, events and post topics. Idempotent."""
    ps = players()
    ids = seed_players(store, community_id, ps)
    for p in ps:
        for day in days:
            qid = question_by_day.get(day)
            if qid is None or qid not in ANSWERS[p["theme"]]:
                continue
            answers.save({
                "answerId": f"a-{p['playerId']}-{cycle_id}-{day}", "cycleId": cycle_id, "day": day, "questionId": qid,
                "playerId": p["playerId"], "text": ANSWERS[p["theme"]][qid][p["variant"]], "source": "text",
                "isCatchUp": False, "weight": 1.0, "followUpUsed": False, "createdAt": now, "editedAt": None,
                "deletedAt": None,
            }, "none")
        if activity is not None:
            from .activity import ActivityRequest
            req = ActivityRequest.model_validate({"useActivity": True, "groupIds": p["groupIds"],
                                                  "eventIds": p["eventIds"], "texts": [p["post"]]})
            activity.put(p["playerId"], community_id, req, now)
    return ids


def _main() -> None:
    ap = argparse.ArgumentParser(description="Export the synthetic demo feed for the web shell.")
    ap.add_argument("--export-feed", type=Path, required=True)
    args = ap.parse_args()
    args.export_feed.write_text(json.dumps({"label": "Synthetic demo population. Not real people.", "posts": feed()},
                                           indent=1, ensure_ascii=False) + "\n")
    print(f"wrote {len(feed())} posts to {args.export_feed}")


if __name__ == "__main__":
    _main()
