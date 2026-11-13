"""Durable planning boundaries with real validators; synthetic input, no model."""

from copy import deepcopy

import pytest

from server.app.errors import ServiceError
from server.app.planning_stores import (
    DurableClarifyStore,
    DurableSelectionStore,
    StagedThemeStore,
    dump_matching_result,
    load_matching_result,
)
from server.matching.models import (
    Constellation,
    FormationResult,
    MatchingError,
    MuseCallEvidence,
    Theme,
)
from server.planning import ClarifyResult, QuestionService, load_default_bank
from tests.orchestration.storage_adapter import TestWorkflowRepository


def question_service(repository):
    async def monday(cycle_id):
        return "2026-11-09"

    return QuestionService(load_default_bank(), DurableSelectionStore(repository), monday)


def selection(
    repository, cycle="synthetic-cycle", community="synthetic-community", monday="2026-11-09"
):
    service = question_service(repository)
    service.select_week_on(cycle, community, monday)
    return DurableSelectionStore(repository).get(cycle)


def evidence(call="M2"):
    return {
        "callType": call,
        "model": "fixture:scripted-muse",
        "source": "replay",
        "generatedAt": "2026-11-15T18:00:00Z",
        "latencyMs": 12,
    }


def formation():
    return FormationResult(
        "ok",
        constellations=(
            Constellation(
                "synthetic-c1",
                "synthetic-cycle",
                ("synthetic-a", "synthetic-b", "synthetic-c"),
                "Synthetic private guarded meaning",
                0.0,
                True,
                "Synthetic (Fallback grouping)",
                "triangle",
                "ember",
                False,
                True,
            ),
        ),
        themes=(
            Theme(
                "synthetic-t1",
                "synthetic-cycle",
                "Synthetic theme",
                "Synthetic description",
                ("synthetic-a", "synthetic-b", "synthetic-c"),
                3.0,
            ),
        ),
        evidence=(MuseCallEvidence.from_dict(evidence("M5")),),
        used_fallback=True,
        repaired_groups=1,
        timings_ms={"m4Ms": 12},
    )


def test_real_question_service_uses_durable_history_and_released_projection():
    repository = TestWorkflowRepository()
    first = question_service(repository)
    week1 = first.select_week_on("synthetic-c1", "synthetic-community", "2026-11-09")
    second = question_service(repository)
    assert second.select_week_on("synthetic-c1", "synthetic-community", "2026-11-09") == week1
    week2 = second.select_week_on("synthetic-c2", "synthetic-community", "2026-11-16")
    assert not {day["question"]["questionId"] for day in week1} & {
        day["question"]["questionId"] for day in week2
    }
    assert [row["day"] for row in second.released("synthetic-c2", 2)] == [1, 2]
    store = DurableSelectionStore(repository)
    assert [row["cycleId"] for row in store.recent("synthetic-community", 1, "synthetic-c2")] == [
        "synthetic-c1"
    ]
    assert store.recent("synthetic-other-community", 4, "") == []
    assert store.recent("synthetic-community", 0, "") == []


def test_selection_is_detached_immutable_and_private_to_community():
    repository = TestWorkflowRepository()
    original = selection(repository)
    store = DurableSelectionStore(repository)
    store.put("synthetic-cycle", original)
    changed = deepcopy(original)
    changed["questions"][0]["text"] = "What is a different synthetic question?"
    with pytest.raises(ServiceError) as error:
        store.put("synthetic-cycle", changed)
    assert error.value.code == "STALE_REVISION"
    changed["communityId"] = "synthetic-foreign-community"
    with pytest.raises(ServiceError) as error:
        store.put("synthetic-cycle", changed)
    assert error.value.code == "NOT_FOUND"
    original["questions"][0]["text"] = "Changed outside the transaction?"
    assert store.get("synthetic-cycle")["questions"][0]["text"] != original["questions"][0]["text"]


@pytest.mark.parametrize(
    "mutation", ["foreign_cycle", "not_monday", "private_field", "lineage", "coercion"]
)
def test_invalid_or_private_selection_cannot_be_stored(mutation):
    repository = TestWorkflowRepository()
    record = selection(repository)
    if mutation == "foreign_cycle":
        record["cycleId"] = "foreign"
    elif mutation == "not_monday":
        record["weekStart"] = "2026-11-10"
    elif mutation == "private_field":
        record["answers"] = ["SYNTHETIC PRIVATE ANSWER"]
    elif mutation == "lineage":
        record["questionIds"][0] = "foreign"
    else:
        record["questions"][0]["active"] = "true"
    with pytest.raises(ServiceError) as error:
        DurableSelectionStore(repository).put("synthetic-cycle", record)
    assert error.value.code == "INVALID_INPUT"


def test_clarify_decision_survives_store_reconstruction_without_answer_text():
    repository = TestWorkflowRepository()
    store = DurableClarifyStore(repository)
    result = ClarifyResult(
        {"needsFollowup": True, "question": "What made that moment stand out?"}, "muse", evidence()
    )
    store.put("synthetic-answer-id", result)
    store.put("synthetic-answer-id", result)
    loaded = DurableClarifyStore(repository).get("synthetic-answer-id")
    assert loaded.output == result.output and loaded.source == "muse"
    assert loaded.evidence["callType"] == "M2"
    result.output["question"] = "Changed outside storage?"
    loaded.output["question"] = "Also changed outside storage?"
    assert store.get("synthetic-answer-id").output["question"] == "What made that moment stand out?"
    with repository.transaction() as state:
        assert set(state.records["clarifyDecisions"]["synthetic-answer-id"]) == {
            "output",
            "source",
            "evidence",
        }


@pytest.mark.parametrize(
    "result",
    [
        ClarifyResult({"needsFollowup": "true", "question": "What happened?"}, "fallback"),
        ClarifyResult(
            {"needsFollowup": True, "question": "What happened?", "answer": "private"}, "fallback"
        ),
        ClarifyResult({"needsFollowup": True, "question": "What happened?"}, "muse"),
        ClarifyResult(
            {"needsFollowup": True, "question": "What happened?"}, "muse", evidence("M7")
        ),
        ClarifyResult({"needsFollowup": False, "question": "Unexpected text"}, "none"),
        ClarifyResult({"needsFollowup": False, "question": ""}, "fallback", evidence()),
    ],
)
def test_clarify_rejects_coercion_private_fields_and_fabricated_evidence(result):
    store = DurableClarifyStore(TestWorkflowRepository())
    with pytest.raises(ServiceError) as error:
        store.put("synthetic-answer-id", result)
    assert error.value.code == "INVALID_INPUT"


def test_second_different_clarify_decision_cannot_overwrite_the_first():
    store = DurableClarifyStore(TestWorkflowRepository())
    first = ClarifyResult({"needsFollowup": False, "question": ""}, "none")
    store.put("synthetic-answer-id", first)
    with pytest.raises(ServiceError) as error:
        store.put(
            "synthetic-answer-id",
            ClarifyResult({"needsFollowup": True, "question": "What happened?"}, "fallback"),
        )
    assert error.value.code == "STALE_REVISION"
    assert store.get("synthetic-answer-id") == first


def test_private_formation_roundtrip_preserves_flags_themes_evidence_and_timings():
    result = formation()
    stored = dump_matching_result(result)
    restored = load_matching_result(stored)
    assert restored == result
    assert dump_matching_result(restored) == stored
    assert set(stored["wire"]) == {"status", "constellations", "evidence"}
    assert "isFallback" not in stored["wire"]["constellations"][0]
    assert restored.constellations[0].is_fallback is True


def test_failed_formation_roundtrip_preserves_sanitized_error_and_call_evidence():
    result = FormationResult(
        "failed",
        evidence=(MuseCallEvidence.from_dict(evidence("M3")),),
        error=MatchingError("PROVIDER_UNAVAILABLE", "Formation unavailable", retryable=True),
        timings_ms={"m3Ms": 12},
    )
    stored = dump_matching_result(result)
    restored = load_matching_result(stored)
    assert restored.status == "failed" and restored.error.code == "PROVIDER_UNAVAILABLE"
    assert restored.evidence == result.evidence and restored.timings_ms == result.timings_ms
    assert restored.to_wire("stored-formation") == result.to_wire("stored-formation")


@pytest.mark.parametrize(
    "mutation",
    ["private_prompt", "foreign_theme", "fallback_label", "bad_evidence", "duplicate_member"],
)
def test_private_formation_rejects_corrupt_saved_inputs(mutation):
    stored = dump_matching_result(formation())
    if mutation == "private_prompt":
        stored["prompt"] = "SYNTHETIC PRIVATE PROMPT"
    elif mutation == "foreign_theme":
        stored["themes"][0]["memberIds"] = ["foreign-player"]
    elif mutation == "fallback_label":
        stored["wire"]["constellations"][0]["name"] = "Missing truth label"
    elif mutation == "bad_evidence":
        stored["evidence"][0]["latencyMs"] = float("nan")
    else:
        stored["wire"]["constellations"][0]["memberIds"][1] = "synthetic-a"
    with pytest.raises(ServiceError) as error:
        load_matching_result(stored)
    assert error.value.code == "PROVIDER_UNAVAILABLE"


def test_theme_stage_has_no_persistence_side_effect_and_detaches_result():
    repository = TestWorkflowRepository()
    stage = StagedThemeStore()
    result = formation()
    stage.save("synthetic-cycle", result)
    result.timings_ms["m4Ms"] = 999
    loaded = stage.load("synthetic-cycle")
    assert loaded.timings_ms["m4Ms"] == 12
    loaded.timings_ms["m4Ms"] = 300
    assert stage.load("synthetic-cycle").timings_ms["m4Ms"] == 12
    assert stage.load("unknown-cycle") is None
    with repository.transaction() as state:
        assert state.records == {}
    with pytest.raises(ServiceError):
        stage.save("foreign-cycle", result)
