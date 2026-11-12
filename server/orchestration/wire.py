"""Strict runtime validation of the workflow slice of protocol.ts v1.0.0.

Only shared camelCase shapes are accepted. These validators establish wire and
lineage validity, not authorization, candidate feasibility or public-text safety;
the privacy/planning ports must establish those before persistence/publication.
"""

import re
from datetime import datetime
from typing import Annotated, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictInt,
    StringConstraints,
    ValidationError,
    field_validator,
    model_validator,
)

from server.app.errors import ServiceError


class WorkflowError(ServiceError):
    """A shared error code with no untrusted values in its public message."""


def _nonblank(value: str) -> str:
    if not value.strip():
        raise ValueError("must not be blank")
    return value


def _utc(value: str) -> str:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|\+00:00)", value):
        raise ValueError("expected RFC3339 UTC")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError("expected RFC3339 UTC") from error
    return parsed.isoformat().replace("+00:00", "Z")


def _zone(value: str) -> str:
    # UTC is always a valid IANA name, including minimal Windows installations
    # without the optional timezone database. Other names need real zone data.
    if value != "UTC":
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as error:
            raise ValueError("expected an IANA time zone") from error
    return value


Text = Annotated[str, StringConstraints(min_length=1), AfterValidator(_nonblank)]
IsoTime = Annotated[str, AfterValidator(_utc)]
Positive = Annotated[StrictInt, Field(ge=1)]
Nonnegative = Annotated[StrictInt, Field(ge=0)]


class Wire(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)


class Window(Wire):
    start: IsoTime
    end: IsoTime

    @model_validator(mode="after")
    def ordered(self) -> "Window":
        if datetime.fromisoformat(self.start) >= datetime.fromisoformat(self.end):
            raise ValueError("start must precede end")
        return self


class ModelEvidence(Wire):
    model: Text
    source: Literal["live", "replay"]
    generatedAt: IsoTime
    latencyMs: Nonnegative


class MemberVersion(Wire):
    participantId: Text
    intentVersion: Positive
    consentVersion: Positive


class GroupProposal(Wire):
    proposalId: Text
    communityId: Text
    revision: Positive
    memberIds: Annotated[list[Text], Field(min_length=3, max_length=5)]
    memberVersions: Annotated[list[MemberVersion], Field(min_length=3, max_length=5)]
    feasibleWindows: Annotated[list[Window], Field(min_length=1)]
    sharedInterests: list[Text]
    publicRationale: Text
    evidence: ModelEvidence

    @model_validator(mode="after")
    def members_correspond(self) -> "GroupProposal":
        ids = self.memberIds
        version_ids = [member.participantId for member in self.memberVersions]
        if len(set(ids)) != len(ids) or len(set(version_ids)) != len(version_ids):
            raise ValueError("members must be unique")
        if set(ids) != set(version_ids):
            raise ValueError("member versions must match proposal members")
        return self


class QuestPlan(Wire):
    planId: Text
    proposalId: Text
    revision: Positive
    basedOnRevision: Positive | None
    memberVersions: Annotated[list[MemberVersion], Field(min_length=3, max_length=5)]
    title: Text
    activity: Text
    collaborationTask: Text
    venueId: Text
    start: IsoTime
    end: IsoTime
    timeZone: Annotated[str, AfterValidator(_zone)]
    costPerPersonMinor: Nonnegative
    currency: Annotated[str, StringConstraints(min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")]
    minimumSize: Literal[3]
    maximumSize: Literal[5]
    publicRationale: Text
    opener: Text
    evidence: ModelEvidence

    @field_validator("minimumSize", "maximumSize", mode="before")
    @classmethod
    def literal_sizes_are_integers(cls, value: object) -> object:
        if type(value) is not int:
            raise ValueError("group size must be an integer")
        return value

    @model_validator(mode="after")
    def consistent_plan(self) -> "QuestPlan":
        if datetime.fromisoformat(self.start) >= datetime.fromisoformat(self.end):
            raise ValueError("start must precede end")
        if self.basedOnRevision is not None and self.basedOnRevision >= self.revision:
            raise ValueError("revision lineage must point backwards")
        ids = [member.participantId for member in self.memberVersions]
        if len(set(ids)) != len(ids):
            raise ValueError("member versions must be unique")
        return self


class AcceptanceCommand(Wire):
    revision: Positive
    choice: Literal["accept", "decline"]


class PublicParticipant(Wire):
    participantId: Text
    displayName: Text
    publicInterests: list[Text]
    isSynthetic: StrictBool


class AcceptanceRecord(Wire):
    questId: Text
    participantId: Text
    revision: Positive
    choice: Literal["accept", "decline"]
    recordedAt: IsoTime


class EventRecord(Wire):
    eventId: Text
    questId: Text
    planId: Text
    revision: Positive
    status: Literal["scheduled", "cancelled", "completed"]
    title: Text
    venueId: Text
    start: IsoTime
    end: IsoTime
    acceptedMemberIds: Annotated[list[Text], Field(max_length=5)]
    conversationId: Text

    @model_validator(mode="after")
    def coherent_event(self) -> "EventRecord":
        if datetime.fromisoformat(self.start) >= datetime.fromisoformat(self.end):
            raise ValueError("start must precede end")
        if len(set(self.acceptedMemberIds)) != len(self.acceptedMemberIds):
            raise ValueError("accepted members must be unique")
        if self.status == "scheduled" and len(self.acceptedMemberIds) < 3:
            raise ValueError("scheduled event requires quorum")
        return self


class QuestSnapshot(Wire):
    questId: Text
    communityId: Text
    revision: Positive
    status: Literal[
        "forming", "proposed", "planning", "scheduled", "revision_pending", "completed", "cancelled"
    ]
    members: Annotated[list[PublicParticipant], Field(max_length=5)]
    acceptedCount: Annotated[StrictInt, Field(ge=0, le=5)]
    capacity: Literal[5]
    minimumSize: Literal[3]
    event: EventRecord | None

    @field_validator("capacity", "minimumSize", mode="before")
    @classmethod
    def literal_sizes_are_integers(cls, value: object) -> object:
        if type(value) is not int:
            raise ValueError("group size must be an integer")
        return value

    @model_validator(mode="after")
    def coherent_snapshot(self) -> "QuestSnapshot":
        ids = [member.participantId for member in self.members]
        if len(set(ids)) != len(ids) or self.acceptedCount > len(ids):
            raise ValueError("snapshot members and count are inconsistent")
        if self.event is not None and (
            self.event.questId != self.questId or self.event.revision > self.revision
        ):
            raise ValueError("event does not belong to this quest revision")
        if self.status == "scheduled" and (
            self.event is None
            or self.event.status != "scheduled"
            or self.event.revision != self.revision
            or self.acceptedCount != len(self.event.acceptedMemberIds)
            or not set(self.event.acceptedMemberIds) <= set(ids)
        ):
            raise ValueError("scheduled snapshot must carry the accepted event")
        return self


class ParticipantSender(Wire):
    kind: Literal["participant"]
    participantId: Text


class AssistantSender(Wire):
    kind: Literal["assistant"]


class ConversationMessage(Wire):
    messageId: Text
    conversationId: Text
    createdAt: IsoTime
    sender: Annotated[ParticipantSender | AssistantSender, Field(discriminator="kind")]
    text: Text


def _validate(model: type[Wire], raw: object) -> dict:
    try:
        return model.model_validate(raw).model_dump(mode="json")
    except (ValidationError, ValueError, TypeError):
        raise WorkflowError("INVALID_INPUT") from None


def validate_proposal(raw: object) -> dict:
    return _validate(GroupProposal, raw)


def validate_plan(raw: object) -> dict:
    return _validate(QuestPlan, raw)


def validate_acceptance(raw: object) -> dict:
    return _validate(AcceptanceCommand, raw)


def validate_acceptance_record(raw: object) -> dict:
    return _validate(AcceptanceRecord, raw)


def validate_snapshot(raw: object) -> dict:
    return _validate(QuestSnapshot, raw)


def validate_message(raw: object) -> dict:
    return _validate(ConversationMessage, raw)


def validate_plan_for_proposal(raw_plan: object, raw_proposal: object) -> dict:
    """Check public shape/lineage/window containment; feasibility still needs ports."""
    plan = validate_plan(raw_plan)
    proposal = validate_proposal(raw_proposal)
    if plan["proposalId"] != proposal["proposalId"]:
        raise WorkflowError("INVALID_INPUT")
    if plan["revision"] != proposal["revision"]:
        raise WorkflowError("STALE_REVISION")
    if sorted(plan["memberVersions"], key=lambda member: member["participantId"]) != sorted(
        proposal["memberVersions"], key=lambda member: member["participantId"]
    ):
        raise WorkflowError("STALE_REVISION")
    start, end = datetime.fromisoformat(plan["start"]), datetime.fromisoformat(plan["end"])
    if not any(
        datetime.fromisoformat(window["start"]) <= start
        and end <= datetime.fromisoformat(window["end"])
        for window in proposal["feasibleWindows"]
    ):
        raise WorkflowError("INVALID_INPUT")
    return plan
