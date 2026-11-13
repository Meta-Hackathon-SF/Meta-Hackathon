"""Chat slice of protocol.ts 2.0.0. CamelCase, strict runtime validation."""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import Field, model_validator

from server.orchestration.wire import IsoTime, Text, Wire


class Player(Wire):
    playerId: Text
    displayName: Text
    avatarColor: Text
    isSynthetic: bool


class AnonymousHandle(Wire):
    roomId: Text
    handle: Text
    starColor: Text
    isSelf: bool


class ChatRoom(Wire):
    roomId: Text
    constellationId: Text
    cycleId: Text
    status: Literal["open", "expired", "closed"]
    opensAt: IsoTime
    expiresAt: IsoTime
    members: list[AnonymousHandle]

    @model_validator(mode="after")
    def consistency(self):
        if any(m.roomId != self.roomId for m in self.members):
            raise ValueError("wrong room")
        if len({m.handle for m in self.members}) != len(self.members):
            raise ValueError("duplicate handle")
        if sum(m.isSelf for m in self.members) > 1:
            raise ValueError("invalid viewer projection")
        if datetime.fromisoformat(self.opensAt.replace("Z", "+00:00")) >= datetime.fromisoformat(
            self.expiresAt.replace("Z", "+00:00")
        ):
            raise ValueError("invalid expiry")
        return self


Moderation = Literal["visible", "hidden_pending", "removed"]


class ChatMessage(Wire):
    messageId: Text
    roomId: Text
    handle: Text
    text: Annotated[str, Field(min_length=1, max_length=500)]
    createdAt: IsoTime
    moderation: Moderation
    kind: Literal["player", "muse_nudge", "system"]


class RevealRequest(Wire):
    roomId: Text
    fromPlayerId: Text
    toHandle: Text
    createdAt: IsoTime


class MutualReveal(Wire):
    roomId: Text
    players: Annotated[list[Player], Field(min_length=2, max_length=2)]
    revealedAt: IsoTime

    @model_validator(mode="after")
    def distinct(self):
        if self.players[0].playerId == self.players[1].playerId:
            raise ValueError("reveal requires two players")
        return self


class Report(Wire):
    reportId: Text
    roomId: Text
    messageId: Text | None
    reporterId: Text
    reportedHandle: Text
    reason: Literal["harassment", "self_harm", "spam", "personal_info", "other"]
    createdAt: IsoTime
