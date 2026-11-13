"""Shared synthetic fixtures are input to real runtime validators."""

import json
import re
from pathlib import Path

import pytest
from pydantic import ValidationError

from server.chat import wire

FIXTURES = Path(__file__).parents[2] / "contracts/fixtures"


def test_shared_chat_fixture_exact_keys_and_values():
    fixture = json.loads((FIXTURES / "chat-room.json").read_text())
    assert wire.ChatRoom.model_validate(fixture["room"]).model_dump() == fixture["room"]
    for message in fixture["messages"]:
        assert wire.ChatMessage.model_validate(message).model_dump() == message


@pytest.mark.parametrize(
    "name",
    [
        "Player",
        "AnonymousHandle",
        "ChatRoom",
        "ChatMessage",
        "Report",
        "RevealRequest",
        "MutualReveal",
    ],
)
def test_keys_match_shared_protocol(name):
    text = (FIXTURES.parents[0] / "protocol.ts").read_text()
    body = re.search(r"export interface " + name + r" \{(.*?)\n\}", text, re.S)[1]
    body = re.sub(r"//[^\n]*", "", body)
    assert set(re.findall(r"(\w+)\s*:", body)) == set(getattr(wire, name).model_fields)


def test_hidden_identity_or_private_answer_fields_cannot_enter_room_message():
    fixture = json.loads((FIXTURES / "chat-room.json").read_text())
    for extra in [{"playerId": "private"}, {"answer": "private"}, {"text": "x" * 501}]:
        with pytest.raises(ValidationError):
            wire.ChatMessage.model_validate({**fixture["messages"][0], **extra})
