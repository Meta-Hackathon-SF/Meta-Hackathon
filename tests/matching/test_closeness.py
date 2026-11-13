"""D009 brightness bands and D010 context counts: code-only, offline, synthetic."""
from __future__ import annotations

from server.matching.closeness import (MAX_BOOST, activity_boost, bands_for_viewer, member_context,
                                       pair_closeness)
from server.matching.models import ActivitySignals, FormationSnapshot


def snap(answers, activity=None):
    refs = sorted({r for r, _ in answers})
    return FormationSnapshot.from_dict({
        "answers": [{"id": r, "text": t, "weight": 1.0} for r, t in answers],
        "idMap": {r: "p-" + r for r in refs},
        "blockedPairs": [],
        **({"activity": activity} if activity else {}),
    })


ANSWERS = [("a", "board games with my floor in the dining hall"),
           ("b", "board games and dining hall dinners with friends"),
           ("c", "dining hall breakfast alone before class"),
           ("d", "long walks in the park with music")]


def test_closer_answers_are_brighter_and_self_has_no_band():
    s = snap(ANSWERS)
    close = pair_closeness(s, s.refs)
    bands = bands_for_viewer("p-a", ["p-a", "p-b", "p-c", "p-d"], close)
    assert "p-a" not in bands
    assert bands["p-b"] == "bright" and bands["p-d"] == "faint"


def test_scores_are_bounded_and_private_ids_only():
    s = snap(ANSWERS)
    for a, b, score in pair_closeness(s, s.refs):
        assert 0.0 <= score <= 1.0 and a < b and a.startswith("p-")


def test_shared_group_brightens_but_answers_dominate():
    act = {"c": {"groupIds": ["g-1", "g-2"], "eventIds": ["e-1"], "friendIds": [], "topics": ["food"]},
           "a": {"groupIds": ["g-1", "g-2"], "eventIds": ["e-1"], "friendIds": [], "topics": ["food"]}}
    plain = dict(((x, y), s) for x, y, s in pair_closeness(snap(ANSWERS), ["a", "b", "c", "d"]))
    boosted = dict(((x, y), s) for x, y, s in pair_closeness(snap(ANSWERS, act), ["a", "b", "c", "d"]))
    assert boosted[("p-a", "p-c")] > plain[("p-a", "p-c")]
    assert boosted[("p-a", "p-c")] - plain[("p-a", "p-c")] <= MAX_BOOST + 1e-9
    assert boosted[("p-a", "p-b")] == plain[("p-a", "p-b")]  # no activity for b: unchanged


def test_boost_is_zero_without_opt_in_on_both_sides():
    assert activity_boost(None, ActivitySignals(group_ids=("g",))) == 0.0
    assert activity_boost(ActivitySignals(group_ids=("g",) * 1), ActivitySignals(group_ids=("g",))) > 0


def test_ties_share_a_band_and_unrelated_is_faint():
    close = (("p-a", "p-b", 0.5), ("p-a", "p-c", 0.5), ("p-a", "p-d", 0.0))
    bands = bands_for_viewer("p-a", ["p-a", "p-b", "p-c", "p-d"], close)
    assert bands["p-b"] == bands["p-c"] == "bright" and bands["p-d"] == "faint"


def test_context_counts_only_and_mutual_friends():
    act = {"a": {"profileId": "fb-a", "groupIds": ["g-1"], "eventIds": ["e-1"], "friendIds": ["fb-b"], "topics": []},
           "b": {"profileId": "fb-b", "groupIds": ["g-1"], "eventIds": [], "friendIds": ["fb-a"], "topics": []},
           "c": {"profileId": "fb-c", "groupIds": [], "eventIds": ["e-1"], "friendIds": [], "topics": []}}
    ctx = member_context(snap(ANSWERS, act), ["a", "b", "c", "d"])
    assert ctx["p-a"] == {"sharedGroupStars": 1, "alreadyFriends": 1, "sameEventStars": 1}
    assert ctx["p-d"] == {"sharedGroupStars": 0, "alreadyFriends": 0, "sameEventStars": 0}
    assert all(set(v) == {"sharedGroupStars", "alreadyFriends", "sameEventStars"} for v in ctx.values())


def test_snapshot_rejects_activity_for_unknown_ref_or_free_text():
    import pytest
    from server.matching.models import ValidationError
    with pytest.raises(ValidationError):
        snap(ANSWERS, {"zz": {"groupIds": []}})
    with pytest.raises(ValidationError):
        snap(ANSWERS, {"a": {"topics": ["x" * 41]}})


def test_event_heat_thresholds_and_buckets():
    from server.matching.closeness import event_heat, heat_bucket
    assert heat_bucket(2) is None and heat_bucket(3) == "3-5" and heat_bucket(6) == "6-9" and heat_bucket(12) == "10+"
    answers = [("v", "board games in the dining hall")] + [(f"s{i}", "board games in the dining hall") for i in range(4)] \
        + [("x", "quiet solo hikes")]
    act = {f"s{i}": {"eventIds": ["e-games"] + (["e-rare"] if i < 2 else [])} for i in range(4)}
    act["x"] = {"eventIds": ["e-games"]}
    rows = event_heat(snap(answers, act), "v")
    assert rows == [{"eventId": "e-games", "bucket": "3-5"}]  # e-rare has 2: hidden; x not similar
    assert "p-s0" not in str(rows)
