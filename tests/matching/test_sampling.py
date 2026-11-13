from server.matching.models import FormationSnapshot
from server.matching.sampling import MAX_MUSE_ANSWERS, REASON_SAMPLED, sample_for_muse


def snap(players, per):
    answers = [
        {"id": f"r{p}", "text": f"answer {p} {d}", "weight": 1.0}
        for p in range(players)
        for d in range(per)
    ]
    return FormationSnapshot.from_dict(
        {
            "answers": answers,
            "idMap": {f"r{p}": f"p{p}" for p in range(players)},
            "blockedPairs": [],
        }
    )


def test_under_limit_is_untouched():
    s = snap(30, 5)
    out, reason = sample_for_muse(s)
    assert out is s and reason is None


def test_over_400_samples_evenly_and_keeps_every_player():
    s = snap(100, 5)  # 500 answers, the audit case (80+ players x 5 days)
    out, reason = sample_for_muse(s)
    assert reason == REASON_SAMPLED and len(out.answers) <= MAX_MUSE_ANSWERS
    assert set(out.refs) == set(s.refs)  # nobody dropped from Muse's view
    assert out.id_map == s.id_map and len(s.answers) == 500  # input unchanged
    assert out == sample_for_muse(s)[0]  # deterministic


def test_more_players_than_limit_never_exceeds_cap():
    out, reason = sample_for_muse(snap(450, 1))
    assert reason == REASON_SAMPLED and len(out.answers) == MAX_MUSE_ANSWERS
