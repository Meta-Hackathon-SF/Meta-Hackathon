"""Runtime validators mirroring contracts/protocol.ts 2.0.0 (owner: Will).

Field names are the wire names (camelCase) so ``model_dump(mode="json")`` is
exactly the JSON the contract declares. Request models forbid extra fields:
a client that sends ``weight``, ``playerId`` or ``isCatchUp`` gets
INVALID_INPUT; those values are always server-set.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

CONTRACT_VERSION = "2.0.0"

CycleStatus = Literal["open", "locked", "forming", "revealed", "closed"]
STATUS_ORDER: tuple[CycleStatus, ...] = ("open", "locked", "forming", "revealed", "closed")
CycleDay = Literal[1, 2, 3, 4, 5]
SafetyLevel = Literal["none", "distress", "harm"]
QuestionCategory = Literal[
    "routine", "belonging", "interests", "values", "hopes", "small_joys", "challenges"
]

# contracts/protocol.ts WEIGHTS. Server-set; never read from a request.
WEIGHTS = {"onDay": 1.0, "catchUp": 0.6, "followUpBonus": 0.1, "max": 1.1}

Id = Annotated[str, StringConstraints(min_length=1, max_length=128)]
AnswerText = Annotated[str, StringConstraints(min_length=1, max_length=400)]

_ISO_TIME = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$")


def _check_time(value: str | None) -> str | None:
    if value is None:
        return value
    if not _ISO_TIME.match(value):
        raise ValueError("must be RFC3339 UTC ending in Z")
    datetime.fromisoformat(value.replace("Z", "+00:00"))
    return value


def _check_date(value: str | None) -> str | None:
    if value is not None:
        date.fromisoformat(value)
    return value


class Wire(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Question(Wire):
    questionId: Id
    text: Annotated[str, StringConstraints(min_length=10, max_length=140)]
    category: QuestionCategory
    sensitivity: Literal["low", "medium"]
    signalTags: list[str]
    followUpHint: str | None
    source: Literal["curated", "generated"]
    active: bool


class WeeklyCycle(Wire):
    cycleId: Id
    communityId: Id
    weekStart: str
    status: CycleStatus
    currentDay: CycleDay
    locksAt: str
    revealsAt: str
    chatExpiresAt: str
    demoTiming: bool

    _dates = field_validator("weekStart")(_check_date)
    _times = field_validator("locksAt", "revealsAt", "chatExpiresAt")(_check_time)


class DailyQuestion(Wire):
    cycleId: Id
    day: CycleDay
    date: str
    question: Question

    _dates = field_validator("date")(_check_date)


class DailyAnswer(Wire):
    """PRIVATE: author + server only. Never serialize to another player."""

    answerId: Id
    cycleId: Id
    day: CycleDay
    questionId: Id
    playerId: Id
    text: AnswerText
    source: Literal["voice", "text"]
    isCatchUp: bool
    weight: float = Field(ge=0.0, le=WEIGHTS["max"])
    followUpUsed: bool
    createdAt: str
    editedAt: str | None
    deletedAt: str | None

    _times = field_validator("createdAt", "editedAt", "deletedAt")(_check_time)


class Streak(Wire):
    playerId: Id
    communityId: Id
    current: int = Field(ge=0)
    longest: int = Field(ge=0)
    lastOnDayDate: str | None

    _dates = field_validator("lastOnDayDate")(_check_date)


class CatchUpState(Wire):
    cycleId: Id
    missedDays: list[CycleDay]
    closesAt: str

    _times = field_validator("closesAt")(_check_time)


class PrevalenceGuess(Wire):
    cycleId: Id
    playerId: Id
    percent: int = Field(ge=0, le=100)


class M2Out(Wire):
    needsFollowup: bool
    question: str


# ---- Requests (client input; extra fields rejected) -----------------------
class SubmitAnswerRequest(Wire):
    day: CycleDay
    text: AnswerText
    source: Literal["voice", "text"]

    @field_validator("text")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("text must not be blank")
        return value


class EditAnswerRequest(Wire):
    text: AnswerText
    # True when this edit is the player's reply to the one follow-up the server
    # issued. The server grants the bonus only if it really issued one.
    answersFollowUp: bool = False

    @field_validator("text")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("text must not be blank")
        return value


class GuessRequest(Wire):
    percent: int = Field(ge=0, le=100)


class DayTarget(Wire):
    day: CycleDay


class AdvanceRequest(Wire):
    """Omit ``to`` for the next step (next day, then lock, form, reveal, close)."""

    to: CycleStatus | DayTarget | None = None


class NewCycleRequest(Wire):
    communityId: Id
    demoTiming: bool = True
    weekStart: str | None = None

    _dates = field_validator("weekStart")(_check_date)


# ---- Responses -------------------------------------------------------------
class CurrentCycleResponse(Wire):
    cycle: WeeklyCycle
    question: DailyQuestion | None  # today's; None once the cycle is no longer open
    streak: Streak
    catchUp: CatchUpState


class AnswerResponse(Wire):
    answer: DailyAnswer  # the caller's own answer
    supportCard: bool  # True -> UI shows the private support card (Patrik's copy)
