"""Runtime-validated stream events and private recipient envelopes.

Persistence, membership/revocation checks and transport are injected by the caller.
The default app never installs a fixture transport or this in-memory state.
"""

import json
from dataclasses import dataclass
from typing import Annotated, Literal

from pydantic import Field, TypeAdapter

from server.chat.wire import ChatMessage, Moderation, MutualReveal
from server.orchestration.wire import NonNegative, Text, WeeklyCycle, Wire


class CycleUpdated(Wire):
    type: Literal["cycle.updated"]
    seq: NonNegative
    cycle: WeeklyCycle


class ConstellationRevealed(Wire):
    type: Literal["constellation.revealed"]
    seq: NonNegative
    roomId: Text


class MessageEvent(Wire):
    type: Literal["chat.message"]
    seq: NonNegative
    message: ChatMessage


class ModeratedEvent(Wire):
    type: Literal["chat.moderated"]
    seq: NonNegative
    messageId: Text
    moderation: Moderation


class MutualEvent(Wire):
    type: Literal["reveal.mutual"]
    seq: NonNegative
    reveal: MutualReveal


class ExpiredEvent(Wire):
    type: Literal["room.expired"]
    seq: NonNegative
    roomId: Text


class SkyUpdated(Wire):
    type: Literal["sky.updated"]
    seq: NonNegative
    cycleId: Text


StreamEvent = Annotated[
    CycleUpdated
    | ConstellationRevealed
    | MessageEvent
    | ModeratedEvent
    | MutualEvent
    | ExpiredEvent
    | SkyUpdated,
    Field(discriminator="type"),
]
EVENT = TypeAdapter(StreamEvent)


@dataclass(frozen=True)
class Delivery:
    """PRIVATE outbox metadata; never serialize this object to a player."""

    event: dict
    recipients: frozenset[str]
    room_id: str


def encode_sse(event: dict) -> str:
    value = EVENT.validate_python(event).model_dump()
    data = json.dumps(value, ensure_ascii=True, separators=(",", ":"))
    return f"id: {value['seq']}\nevent: {value['type']}\ndata: {data}\n\n"


def parse_last_event_id(value: str | None) -> int:
    if value is None:
        return 0
    if not value.isascii() or not value.isdecimal() or len(value) > 19:
        from server.app.errors import ServiceError

        raise ServiceError("INVALID_INPUT")
    result = int(value)
    if result > 2**63 - 1:
        from server.app.errors import ServiceError

        raise ServiceError("INVALID_INPUT")
    return result
