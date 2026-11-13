"""Runtime validators match contracts/protocol.ts 2.0.0 and reject hostile input."""

from __future__ import annotations

import re
from pathlib import Path
from typing import get_args

import pytest
from pydantic import ValidationError

from privacy_helpers import consent_body, join_body
from server.privacy import wire

PROTOCOL = Path(__file__).resolve().parents[2] / "contracts" / "protocol.ts"


def ts_fields(name: str) -> set[str]:
    text = PROTOCOL.read_text()
    match = re.search(r"export interface " + name + r"\b[^{]*\{", text)
    assert match, f"{name} missing from protocol.ts"
    depth, i = 1, match.end()
    while depth:
        depth += {"{": 1, "}": -1}.get(text[i], 0)
        i += 1
    body = re.sub(r"//.*", "", text[match.end():i - 1])
    body = re.sub(r"\{[^{}]*\}", "", body)
    return set(re.findall(r"(\w+)\??\s*:", body))


def ts_union(name: str) -> set[str]:
    match = re.search(r"export type " + name + r"\s*=([^;]*);", PROTOCOL.read_text())
    assert match, f"{name} missing from protocol.ts"
    return set(re.findall(r'"([^"]+)"', match.group(1)))


def py_fields(model) -> set[str]:
    return {f.alias or n for n, f in model.model_fields.items()}


@pytest.mark.parametrize("ts_name,model", [
    ("Player", wire.Player), ("Consent", wire.Consent), ("ApiError", wire.ApiError),
    ("DailyAnswer", wire.DailyAnswer), ("PrevalenceGuess", wire.PrevalenceGuess),
])
def test_fields_match_protocol(ts_name, model):
    assert py_fields(model) == ts_fields(ts_name)


def test_api_error_body_and_codes_match_protocol():
    assert py_fields(wire.ApiErrorBody) == {"code", "message", "requestId", "retryable"}
    assert set(get_args(wire.ErrorCode)) == ts_union("ErrorCode")


def test_contract_version_matches():
    assert f'CONTRACT_VERSION = "{wire.CONTRACT_VERSION}"' in PROTOCOL.read_text()


def test_consent_toggles_are_the_consent_booleans():
    bools = {"matchAnswers", "anonymousChat", "isAdult"}
    assert py_fields(wire.ConsentToggles) == bools
    assert bools <= ts_fields("Consent")


def test_join_round_trips_camel_case():
    req = wire.JoinRequest.model_validate(join_body("  Maya  "))
    assert req.display_name == "Maya"
    assert req.wire() == join_body("Maya")


@pytest.mark.parametrize("mutate,why", [
    (lambda b: b.update(playerId="p_someone_else"), "forged identity"),
    (lambda b: b.update(isOperator=True), "self-granted operator"),
    (lambda b: b.update(communityId="other"), "community comes from the path"),
    (lambda b: b.update(match_answers=True), "snake_case key"),
    (lambda b: b.update(isAdult="true"), "string coerced to bool"),
    (lambda b: b.update(isAdult=1), "int coerced to bool"),
    (lambda b: b.pop("isAdult"), "missing 18+ answer"),
    (lambda b: b.update(displayName=""), "empty name"),
    (lambda b: b.update(displayName="   "), "blank name"),
    (lambda b: b.update(displayName="x" * 41), "name too long"),
    (lambda b: b.update(displayName="Ma‮ya"), "bidi control char"),
    (lambda b: b.update(displayName="a\nb"), "newline"),
    (lambda b: b.update(displayName=7), "non-string name"),
])
def test_join_rejects(mutate, why):
    body = join_body()
    mutate(body)
    with pytest.raises(ValidationError):
        wire.JoinRequest.model_validate(body)


@pytest.mark.parametrize("mutate", [
    lambda b: b.update(expectedVersion=0),
    lambda b: b.update(expectedVersion="1"),
    lambda b: b.update(expectedVersion=1.0),
    lambda b: b.pop("expectedVersion"),
    lambda b: b.update(version=9),
    lambda b: b.update(revokedAt=None),
    lambda b: b.update(playerId="p_x"),
])
def test_consent_update_rejects(mutate):
    body = consent_body(1)
    mutate(body)
    with pytest.raises(ValidationError):
        wire.UpdateConsentRequest.model_validate(body)


def test_player_color_and_consent_grants_play():
    with pytest.raises(ValidationError):
        wire.Player(player_id="p", display_name="A", avatar_color="red", is_synthetic=False)
    c = wire.Consent(player_id="p", community_id="c", match_answers=True, anonymous_chat=True,
                     is_adult=False, version=1, revoked_at=None)
    assert not c.grants_play


def test_weights_and_safety_levels_match_protocol():
    text = PROTOCOL.read_text()
    assert "WEIGHTS = { onDay: 1.0, catchUp: 0.6, followUpBonus: 0.1, max: 1.1 }" in text
    assert set(get_args(wire.SafetyLevel)) == ts_union("SafetyLevel")
