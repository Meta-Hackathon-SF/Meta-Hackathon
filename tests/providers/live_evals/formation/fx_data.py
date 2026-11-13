"""Synthetic datasets for the formation experiments. All players are synthetic."""
from __future__ import annotations

import random

from server.matching.evaluation import gold_snapshot

SEED = 20261112


def _refs(n: int, rng: random.Random) -> list[str]:
    out: set[str] = set()
    while len(out) < n:
        out.add("r" + "".join(rng.choice("0123456789abcdef") for _ in range(6)))
    out = sorted(out)
    rng.shuffle(out)
    return out


def gold_set():
    """Repo gold set (30 players, 6 feelings x 5) with random refs and shuffled order."""
    snap, gold_by_player = gold_snapshot(30)
    rng = random.Random(SEED)
    refs = _refs(30, rng)
    old_to_new = {a["id"]: refs[i] for i, a in enumerate(snap["answers"])}
    answers = [{"id": old_to_new[a["id"]], "text": a["text"], "weight": 1.0} for a in snap["answers"]]
    rng.shuffle(answers)
    gold = {old_to_new[old]: gold_by_player[pid] for old, pid in snap["idMap"].items()}
    return {"answers": answers, "questions": [], "gold": gold}


# ---------------------------------------------------------------- E2: questions matter
E2_QUESTIONS = {
    "q1": "Where do you usually eat dinner, and who's around?",
    "q2": "Who would you call at 2am if something went wrong?",
    "q3": "What's one thing you'd drop from your week if you could?",
    "q4": "Who got in the way of your plans this week?",
    "q5": "What do you miss most right now?",
    "q6": "How often did you see friends this week?",
}
# latent -> 5 players x 2 (questionId, short answer). Surface words collide across groups
# ("nobody", "my room", "every day", "everything") so answers alone are ambiguous.
E2_PLAYERS = {
    "isolated": [
        [("q1", "my room, nobody"), ("q2", "nobody really")],
        [("q2", "no one, honestly"), ("q6", "not once")],
        [("q1", "desk, just me"), ("q6", "zero times")],
        [("q6", "never"), ("q2", "can't think of anyone")],
        [("q1", "my room, alone"), ("q2", "nobody here")],
    ],
    "peaceful_solitude": [
        [("q4", "nobody, finally"), ("q3", "nothing, it was good")],
        [("q4", "no one, it was great"), ("q1", "my room, by choice")],
        [("q4", "nobody"), ("q3", "nothing really")],
        [("q4", "not a single person"), ("q6", "didn't need to")],
        [("q3", "nothing"), ("q4", "nobody at all")],
    ],
    "overloaded": [
        [("q3", "everything, pick one"), ("q4", "my own calendar")],
        [("q3", "half of it"), ("q6", "no time")],
        [("q4", "my boss and three professors"), ("q3", "the second job")],
        [("q3", "the 8am lab"), ("q4", "deadlines, every day")],
        [("q6", "once, for ten minutes"), ("q3", "all of it")],
    ],
    "homesick": [
        [("q5", "my mom's kitchen"), ("q2", "my sister, back home")],
        [("q5", "the noise at dinner"), ("q1", "dining hall, it's not the same")],
        [("q5", "my dog"), ("q2", "my dad, three timezones away")],
        [("q2", "my best friend from high school"), ("q5", "everyone")],
        [("q5", "my old room"), ("q6", "only on video calls")],
    ],
    "connected": [
        [("q6", "every day"), ("q1", "dining hall, the whole floor")],
        [("q2", "my roommate, easily"), ("q6", "constantly")],
        [("q1", "the big table, everyone"), ("q2", "like five people")],
        [("q6", "every single day"), ("q4", "my friends, in a good way")],
        [("q2", "anyone on my floor"), ("q1", "wherever the group is")],
    ],
    "bored_restless": [
        [("q3", "the same routine"), ("q5", "surprises")],
        [("q4", "nobody, there were no plans"), ("q3", "the repetition")],
        [("q5", "spontaneous trips"), ("q6", "every day, same people same place")],
        [("q3", "Tuesdays, they're all Tuesdays"), ("q5", "being somewhere new")],
        [("q5", "having something to look forward to"), ("q4", "nobody, there was nothing planned")],
    ],
}


def e2_set():
    rng = random.Random(SEED + 2)
    refs = _refs(30, rng)
    answers, gold, i = [], {}, 0
    for latent, players in E2_PLAYERS.items():
        for pairs in players:
            ref = refs[i]
            i += 1
            gold[ref] = latent
            for qid, text in pairs:
                answers.append({"id": ref, "text": text, "weight": 1.0, "questionId": qid})
    rng.shuffle(answers)
    questions = [{"questionId": k, "text": v} for k, v in E2_QUESTIONS.items()]
    return {"answers": answers, "questions": questions, "gold": gold}


# ---------------------------------------------------------------- E3: activity
E3_STRONG = {
    "eating_alone": [
        "I eat in my room so no one sees me alone",
        "cooking for one is honestly depressing",
        "I grab food and leave before anyone sits down",
        "lunch is the worst part, I never know where to sit",
        "dinner at my desk with a show on, every night",
    ],
    "overwhelmed": [
        "three deadlines on the same day and no sleep",
        "my calendar has no gaps until Thanksgiving",
        "I keep saying yes to things and drowning",
        "work shifts plus labs plus club stuff, it's a lot",
        "I haven't had a slow morning since August",
    ],
    "missing_home": [
        "I miss my mom's cooking more than I expected",
        "nobody here knows the version of me from back home",
        "I call my little brother just to hear the noise",
        "the weather here makes me homesick every morning",
        "I still keep my old town's time on my phone",
    ],
}
CONFLICT_TOPICS = ["coffee", "books", "film", "sports", "art"]  # cross-cuts meaning
E3_TIE_TEXTS = [
    "pretty good week, nothing to complain about",
    "honestly a chill week",
    "things are fine, steady",
    "nice week overall",
    "a calm, okay week",
    "good week, felt settled",
    "it was a decent week",
    "no complaints this week",
    "week went smoothly",
    "fairly relaxed week",
    "solid week, nothing big",
    "an easy, pleasant week",
    "felt normal and fine",
    "things were good",
    "a quiet good week",
]
TIE_TOPICS = ["music", "outdoors", "gaming"]


def e3_set():
    """15 strong-meaning players (activity conflicts with meaning) + 15 tie players
    (equal meaning; activity defines the intended split)."""
    rng = random.Random(SEED + 3)
    refs = _refs(30, rng)
    opaque = {}

    def oid(kind: str, key: str) -> str:
        if (kind, key) not in opaque:
            opaque[(kind, key)] = kind[0] + "".join(rng.choice("0123456789abcdef") for _ in range(5))
        return opaque[(kind, key)]

    answers, gold, subset, activity, act_label = [], {}, {}, [], {}
    i = 0
    for latent, texts in E3_STRONG.items():
        for j, text in enumerate(texts):
            ref = refs[i]
            i += 1
            topic = CONFLICT_TOPICS[j]
            gold[ref], subset[ref], act_label[ref] = latent, "strong", topic
            answers.append({"id": ref, "text": text, "weight": 1.0})
            activity.append({"id": ref, "topics": [topic],
                             "groupIds": [oid("group", topic)], "eventIds": [oid("event", topic)]})
    for j, text in enumerate(E3_TIE_TEXTS):
        ref = refs[i]
        i += 1
        topic = TIE_TOPICS[j % 3]
        gold[ref], subset[ref], act_label[ref] = f"tie_{topic}", "tie", topic
        answers.append({"id": ref, "text": text, "weight": 1.0})
        activity.append({"id": ref, "topics": [topic],
                         "groupIds": [oid("group", topic)], "eventIds": [oid("event", topic)]})
    rng.shuffle(answers)
    rng.shuffle(activity)
    return {"answers": answers, "questions": [], "gold": gold, "subset": subset,
            "activity": activity, "activityLabel": act_label}
