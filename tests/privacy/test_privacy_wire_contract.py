"""Runtime validators match contracts/protocol.ts and reject hostile input. No DB."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from pydantic import ValidationError

from privacy_helpers import intent_body, window
from server.privacy import wire

PROTOCOL = Path(__file__).resolve().parents[2] / "contracts" / "protocol.ts"


def ts_fields(name: str) -> set[str]:
    text = PROTOCOL.read_text()
    match = re.search(r"export interface " + name + r"\s*\{", text)
    assert match, f"{name} missing from protocol.ts"
    depth, i = 1, match.end()
    while depth:
        depth += {"{": 1, "}": -1}.get(text[i], 0)
        i += 1
    body = re.sub(r"//.*", "", text[match.end():i - 1])
    body = re.sub(r"\{[^{}]*\}", "", body)  # drop nested inline object types
    return set(re.findall(r"(\w+)\??\s*:", body))


def py_fields(model) -> set[str]:
    return {f.alias or n for n, f in model.model_fields.items()}


@pytest.mark.parametrize(
    "ts_name,model",
    [
        ("PrivateIntent", wire.PrivateIntent),
        ("Consent", wire.Consent),
        ("PublicParticipant", wire.PublicParticipant),
        ("Candidate", wire.Candidate),
        ("MemberVersion", wire.MemberVersion),
        ("Context", wire.Context),
        ("Window", wire.Window),
    ],
)
def test_fields_match_protocol(ts_name, model):
    assert py_fields(model) == ts_fields(ts_name)


def test_contract_version_matches():
    assert f'CONTRACT_VERSION = "{wire.CONTRACT_VERSION}"' in PROTOCOL.read_text()


def test_valid_intent_request_round_trips_camel_case():
    req = wire.PutIntentRequest.model_validate(intent_body())
    out = req.wire()
    assert "maxBudgetMinor" in out and "max_budget_minor" not in out


@pytest.mark.parametrize(
    "mutate,why",
    [
        (lambda b: b.update(participantId="p_someone_else"), "forged identity field"),
        (lambda b: b.update(intentVersion=7), "server-owned version"),
        (lambda b: b.update(consentVersion=1), "server-owned consent version"),
        (lambda b: b.update(max_budget_minor=5), "snake_case key"),
        (lambda b: b.update(maxBudgetMinor=-1), "negative budget"),
        (lambda b: b.update(maxBudgetMinor="1200"), "string coerced to int"),
        (lambda b: b.update(maxBudgetMinor=12.5), "fractional minor units"),
        (lambda b: b.update(currency="usd"), "currency case"),
        (lambda b: b.update(timeZone="Mars/Olympus"), "unknown zone"),
        (lambda b: b.update(groupPreference="large"), "group preference literal"),
        (lambda b: b.update(interests=[]), "empty interests"),
        (lambda b: b.update(interests=["a", "A"]), "duplicate interests"),
        (lambda b: b.update(availability=[]), "missing availability"),
        (lambda b: b.update(availability=[{"start": "2026-11-14T18:00:00-08:00",
                                           "end": "2026-11-14T20:00:00-08:00"}]), "non-UTC time"),
        (lambda b: b.update(availability=[{"start": "2026-11-14T20:00:00Z",
                                           "end": "2026-11-14T18:00:00Z"}]), "start after end"),
        (lambda b: b.update(availability=[{"start": "2026-11-14T18:00:00Z",
                                           "end": "2026-11-14T18:00:00Z"}]), "empty half-open window"),
        (lambda b: b.update(availability=[
            {"start": "2026-11-14T18:00:00Z", "end": "2026-11-14T20:00:00Z"},
            {"start": "2026-11-14T19:00:00Z", "end": "2026-11-14T21:00:00Z"}]), "overlap"),
        (lambda b: b.update(goal="x" * 501), "goal too long"),
    ],
)
def test_intent_request_rejects(mutate, why):
    body = intent_body()
    mutate(body)
    with pytest.raises(ValidationError):
        wire.PutIntentRequest.model_validate(body)


def test_adjacent_half_open_windows_allowed():
    a = window(1, 18, 2)
    b = {"start": a["end"], "end": window(1, 22, 1)["end"]}
    req = wire.PutIntentRequest.model_validate(intent_body(availability=[b, a]))
    assert [w.start for w in req.availability] == [a["start"], b["start"]]  # sorted


def test_candidate_profile_must_match_intent():
    intent = wire.PrivateIntent.model_validate({
        **{k: v for k, v in intent_body().items() if k not in ("expectedVersion",)},
        "participantId": "p_a", "intentVersion": 1, "consentVersion": 1,
        "confirmedAt": "2026-11-12T20:00:00Z",
    })
    profile = wire.PublicParticipant(participant_id="p_b", display_name="B",
                                     public_interests=[], is_synthetic=False)
    with pytest.raises(ValidationError):
        wire.Candidate(intent=intent, public_profile=profile)


def test_public_participant_has_no_private_fields():
    private = {"goal", "availability", "maxBudgetMinor", "maxDurationMinutes", "areaId", "timeZone"}
    assert not private & py_fields(wire.PublicParticipant)
