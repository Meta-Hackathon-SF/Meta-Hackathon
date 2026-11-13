"""Private support-card cue uses the real M1 boundary and unchanged ApiError shape.

Every input/model result is synthetic. No real player data or live model call.
"""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from server.app.errors import ERRORS, SUPPORT_CARD_MESSAGE, ApiError, ServiceError
from tests.orchestration.runtime_helpers import runtime_environment
from tests.orchestration.test_runtime import call, revealed


@pytest.mark.parametrize("flag", ["distress", "harm"])
def test_actual_m1_flag_returns_only_a_fixed_private_support_cue(flag, caplog):
    with runtime_environment() as env, TestClient(env.app, base_url="https://testserver") as client:
        players, _cycle_id, _job_id, room_id = revealed(env, client)
        private_reason = "SYNTHETIC PRIVATE MODEL REASON"
        env.transport.handlers["safety_screen"] = lambda _payload: {
            "flag": flag,
            "reason": private_reason,
        }
        text = "Synthetic screened safety example"
        response = call(
            client, players[0], "POST", f"/rooms/{room_id}/messages", json={"text": text}
        )
        assert response.status_code == 422
        error = ApiError.model_validate(response.json()).error
        assert error.code == "MESSAGE_REJECTED"
        assert error.message == SUPPORT_CARD_MESSAGE
        assert error.retryable is False
        assert error.requestId == response.headers["X-Request-Id"]
        assert set(response.json()["error"]) == {"code", "message", "requestId", "retryable"}
        assert text not in response.text and private_reason not in response.text
        assert flag not in response.text
        assert private_reason not in caplog.text and text not in caplog.text
        assert call(client, players[1], "GET", f"/rooms/{room_id}/messages").json() == []
        actor = env.app.state.privacy.require_session(players[1].token)
        assert not any(e["type"] == "chat.message" for e in env.app.state.chat.events(actor))


@pytest.mark.parametrize("contact_suffix", ["", " text me at 555-0100"])
def test_shared_distress_fixture_gets_support_cue_without_entering_the_model(contact_suffix):
    fixture = json.loads(
        (Path(__file__).parents[2] / "contracts/fixtures/week-sample.json").read_text()
    )
    text = fixture["distressFixture"]["text"] + contact_suffix
    with runtime_environment() as env, TestClient(env.app, base_url="https://testserver") as client:
        players, _cycle_id, _job_id, room_id = revealed(env, client)
        before = len(env.transport.calls)
        response = call(
            client, players[0], "POST", f"/rooms/{room_id}/messages", json={"text": text}
        )
        assert response.status_code == 422
        assert response.json()["error"]["message"] == SUPPORT_CARD_MESSAGE
        assert text not in response.text and len(env.transport.calls) == before
        assert call(client, players[1], "GET", f"/rooms/{room_id}/messages").json() == []


def test_contact_guard_rejection_keeps_the_original_generic_message():
    with runtime_environment() as env, TestClient(env.app, base_url="https://testserver") as client:
        players, _cycle_id, _job_id, room_id = revealed(env, client)
        response = call(
            client, players[0], "POST", f"/rooms/{room_id}/messages", json={"text": "call 555-0100"}
        )
        assert response.status_code == 422
        assert response.json()["error"]["message"] == ERRORS["MESSAGE_REJECTED"][1]
        assert response.json()["error"]["message"] != SUPPORT_CARD_MESSAGE


@pytest.mark.parametrize(
    "code,key",
    [
        ("FORBIDDEN", "support_card"),
        ("MESSAGE_REJECTED", "SYNTHETIC PRIVATE OVERRIDE"),
        ("MESSAGE_REJECTED", ""),
    ],
)
def test_arbitrary_or_wrong_code_message_overrides_are_rejected(code, key):
    with pytest.raises(ValueError, match="Unknown safe API message key"):
        ServiceError(code, message_key=key)
