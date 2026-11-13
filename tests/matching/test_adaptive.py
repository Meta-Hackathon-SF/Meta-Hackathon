from server.matching.adaptive import adaptive_weights
from server.matching.models import FormationSnapshot


def snap(texts, activity=None):
    refs = [f"r{i}" for i in range(len(texts))]
    data = {
        "answers": [{"id": r, "text": t, "weight": 1.0} for r, t in zip(refs, texts, strict=True)],
        "idMap": {r: f"p{i}" for i, r in enumerate(refs)},
        "blockedPairs": [],
    }
    if activity:
        data["activity"] = {r: {"groupIds": ["g"]} for r in activity}
    return FormationSnapshot.from_dict(data)


def test_short_answers_lower_keyword_weight_and_long_answers_raise_it():
    short = adaptive_weights(snap(["nobody", "every day", "alone"]))
    long = adaptive_weights(snap(["eating alone in the dining hall headphones before class"] * 3))
    assert short.keyword < long.keyword <= 1.0 and short.keyword >= 0.5


def test_activity_trust_follows_optin_coverage():
    none = adaptive_weights(snap(["a b c"] * 4))
    half = adaptive_weights(snap(["a b c"] * 4, activity=["r0", "r1"]))
    assert none.activity == 0.0 and half.activity == 1.0 and half.optin_coverage == 0.5
