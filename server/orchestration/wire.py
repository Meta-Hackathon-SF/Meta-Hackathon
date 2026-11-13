"""Strict runtime mirrors of the consumed protocol.ts 2.0.0 shapes.

These are boundary validators, not an alternative contract. Tests compare keys
and enums against the shared declarations and validate shared synthetic fixtures.
Validation does not authorize access or establish public-text safety.
"""

import re
from datetime import datetime
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, field_validator, model_validator

from server.app.errors import ErrorDetails


def nonblank(value: str) -> str:
    if not value.strip():
        raise ValueError("blank text")
    return value


def utc(value: str) -> str:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|\+00:00)", value):
        raise ValueError("expected UTC timestamp")
    datetime.fromisoformat(value.replace("Z", "+00:00"))
    return value


Text = Annotated[str, Field(min_length=1), AfterValidator(nonblank)]
IsoTime = Annotated[str, AfterValidator(utc)]
NonNegative = Annotated[int, Field(ge=0)]


class Wire(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


class MuseCallEvidence(Wire):
    callType: Literal["M1", "M2", "M3", "M4", "M5", "M6", "M7", "M8"]
    model: Text
    source: Literal["live", "replay"]
    generatedAt: IsoTime
    latencyMs: Annotated[float, Field(ge=0)]


class Constellation(Wire):
    constellationId: Text
    cycleId: Text
    memberIds: list[Text]
    sharedMeaning: Text
    confidence: Annotated[float, Field(ge=0, le=1)]
    isLooseMatch: bool
    name: Text
    shapeId: Text
    colorId: Text
    baselineAgrees: bool

    @model_validator(mode="after")
    def members(self):
        if not 3 <= len(self.memberIds) <= 5 or len(set(self.memberIds)) != len(self.memberIds):
            raise ValueError("invalid constellation size")
        return self


class FormationSuccess(Wire):
    status: Literal["ok"]
    constellations: list[Constellation]
    evidence: list[MuseCallEvidence]


class FormationFailure(Wire):
    status: Literal["failed"]
    error: ErrorDetails


class WeeklyCycle(Wire):
    cycleId: Text
    communityId: Text
    weekStart: str
    status: Literal["open", "locked", "forming", "revealed", "closed"]
    currentDay: Literal[1, 2, 3, 4, 5]
    locksAt: IsoTime
    revealsAt: IsoTime
    chatExpiresAt: IsoTime
    demoTiming: bool

    @field_validator("currentDay", mode="before")
    @classmethod
    def integer_day(cls, value):
        if type(value) is not int:
            raise ValueError("day must be integer")
        return value

    @model_validator(mode="after")
    def timing(self):
        start = datetime.strptime(self.weekStart, "%Y-%m-%d")
        if start.strftime("%Y-%m-%d") != self.weekStart or start.weekday() != 0:
            raise ValueError("week must start Monday")
        if type(self.currentDay) is not int:
            raise ValueError("day must be integer")
        times = [
            datetime.fromisoformat(t.replace("Z", "+00:00"))
            for t in (self.locksAt, self.revealsAt, self.chatExpiresAt)
        ]
        if not times[0] < times[1] < times[2]:
            raise ValueError("invalid cycle timing")
        return self


class SkyTheme(Wire):
    themeId: Text
    label: Text
    count: NonNegative
    actualPercent: Annotated[float, Field(ge=0, le=100)]
    guessedPercentMedian: Annotated[float, Field(ge=0, le=100)]


class SyntheticSignal(Wire):
    signalId: Text
    label: Text
    percent: Annotated[float, Field(ge=0, le=100)]
    sampleSize: Annotated[int, Field(ge=1)]
    source: Literal["synthetic"]


class SkyStats(Wire):
    cycleId: Text
    threshold: Annotated[int, Field(ge=3)]
    eligiblePlayers: NonNegative
    constellations: NonNegative
    mutualReveals: NonNegative
    themes: list[SkyTheme]
    suppressedThemes: NonNegative
    headlines: list[str]
    syntheticSignals: list[SyntheticSignal]
    evidence: list[MuseCallEvidence]

    @model_validator(mode="after")
    def privacy_threshold(self):
        if any(t.count < self.threshold or t.count > self.eligiblePlayers for t in self.themes):
            raise ValueError("invalid thresholded theme")
        if len({t.themeId for t in self.themes}) != len(self.themes):
            raise ValueError("duplicate theme")
        return self
