"""Private 2.1 formation metadata compatibility at the durable boundary."""

from dataclasses import replace

import pytest

from server.app.errors import ServiceError
from server.app.planning_stores import dump_matching_result, load_matching_result
from tests.orchestration.test_planning_stores import formation


def enriched_formation():
    result = formation()
    constellation = result.constellations[0]
    return replace(
        result,
        constellations=(
            replace(
                constellation,
                closeness=(
                    ("synthetic-a", "synthetic-b", 0.25),
                    ("synthetic-a", "synthetic-c", 0.5),
                    ("synthetic-b", "synthetic-c", 1.0),
                ),
                member_context={
                    "synthetic-a": {
                        "sharedGroupStars": 1,
                        "alreadyFriends": 0,
                        "sameEventStars": 2,
                    },
                    "synthetic-b": {
                        "sharedGroupStars": 2,
                        "alreadyFriends": 1,
                        "sameEventStars": 0,
                    },
                    "synthetic-c": {
                        "sharedGroupStars": 0,
                        "alreadyFriends": 2,
                        "sameEventStars": 1,
                    },
                },
            ),
        ),
    )


def test_legacy_formation_roundtrip_omits_empty_21_metadata():
    result = formation()
    stored = dump_matching_result(result)
    wire = stored["wire"]["constellations"][0]
    assert "closeness" not in wire
    assert "memberContext" not in wire
    assert load_matching_result(stored) == result


def test_private_21_metadata_survives_matching_result_roundtrip():
    result = enriched_formation()
    stored = dump_matching_result(result)
    wire = stored["wire"]["constellations"][0]
    assert wire["closeness"] == [
        {"a": "synthetic-a", "b": "synthetic-b", "score": 0.25},
        {"a": "synthetic-a", "b": "synthetic-c", "score": 0.5},
        {"a": "synthetic-b", "b": "synthetic-c", "score": 1.0},
    ]
    assert wire["memberContext"] == result.constellations[0].member_context
    restored = load_matching_result(stored)
    assert restored.constellations[0].closeness == result.constellations[0].closeness
    assert restored.constellations[0].member_context == result.constellations[0].member_context
    assert dump_matching_result(restored) == stored


@pytest.mark.parametrize(
    "closeness",
    [
        [{"a": "synthetic-a", "b": "foreign-player", "score": 0.5}],
        [{"a": "synthetic-a", "b": "synthetic-a", "score": 0.5}],
        [{"a": "synthetic-a", "b": "synthetic-b", "score": -0.1}],
        [{"a": "synthetic-a", "b": "synthetic-b", "score": 1.1}],
        [
            {"a": "synthetic-a", "b": "synthetic-b", "score": 0.5},
            {"a": "synthetic-b", "b": "synthetic-a", "score": 0.7},
        ],
    ],
    ids=[
        "foreign_pair_member",
        "self_pair",
        "score_below_zero",
        "score_above_one",
        "duplicate_pair",
    ],
)
def test_private_21_metadata_rejects_invalid_closeness(closeness):
    stored = dump_matching_result(formation())
    stored["wire"]["constellations"][0]["closeness"] = closeness
    with pytest.raises(ServiceError) as error:
        load_matching_result(stored)
    assert error.value.code == "PROVIDER_UNAVAILABLE"


@pytest.mark.parametrize(
    "mutation",
    ["foreign_context_member", "context_count_exceeds_others"],
    ids=["foreign_context_member", "context_count_exceeds_others"],
)
def test_private_21_metadata_rejects_invalid_member_context(mutation):
    stored = dump_matching_result(formation())
    context = {
        player: {"sharedGroupStars": 0, "alreadyFriends": 0, "sameEventStars": 0}
        for player in ("synthetic-a", "synthetic-b", "synthetic-c")
    }
    if mutation == "foreign_context_member":
        context["foreign-player"] = context.pop("synthetic-a")
    else:
        context["synthetic-a"]["sharedGroupStars"] = 3
    stored["wire"]["constellations"][0]["memberContext"] = context
    with pytest.raises(ServiceError) as error:
        load_matching_result(stored)
    assert error.value.code == "PROVIDER_UNAVAILABLE"
