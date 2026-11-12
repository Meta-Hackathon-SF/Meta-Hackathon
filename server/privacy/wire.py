"""Runtime validators for the privacy-owned wire types of contracts/protocol.ts v1.0.0.

These are not a second contract: field names and literals mirror protocol.ts and
tests/privacy/test_wire_contract.py fails if they drift. Python attributes are
snake_case; JSON is always camelCase (dump with ``by_alias=True``).

Types produced here: PrivateIntent, Consent, PublicParticipant, Candidate,
ApiError, plus the request bodies of the privacy routes in contracts/API.md.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
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
    field_validator,
    model_validator,
)
from pydantic.alias_generators import to_camel

CONTRACT_VERSION = "1.0.0"

MAX_WINDOWS = 20
MAX_WINDOW_SPAN = timedelta(days=14)
MAX_BUDGET_MINOR = 1_000_000  # sanity bound on minor units; not a product rule


class Wire(BaseModel):
    """Strict camelCase model: unknown fields rejected, no type coercion."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="forbid",
        strict=True,
        frozen=True,
    )

    def wire(self) -> dict:
        return self.model_dump(mode="json", by_alias=True)


def _utc_rfc3339(value: str) -> str:
    """RFC3339 UTC with explicit Z/+00:00; normalized to ...Z."""
    if not isinstance(value, str) or not (value.endswith("Z") or value.endswith("+00:00")):
        raise ValueError("time must be RFC3339 UTC (suffix Z)")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("time must be RFC3339 UTC (suffix Z)") from exc
    return format_time(parsed)


def format_time(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _iana_zone(value: str) -> str:
    try:
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ValueError("timeZone must be an IANA zone name") from exc
    return value


IsoTime = Annotated[str, AfterValidator(_utc_rfc3339)]
Id = Annotated[str, StringConstraints(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_\-]+$")]
Tag = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)]
Currency = Annotated[str, StringConstraints(pattern=r"^[A-Z]{3}$")]
TimeZoneName = Annotated[str, AfterValidator(_iana_zone)]
DisplayName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)]


class Window(Wire):
    start: IsoTime
    end: IsoTime

    @model_validator(mode="after")
    def _ordered(self) -> "Window":
        start, end = parse_time(self.start), parse_time(self.end)
        if not start < end:
            raise ValueError("window start must be before end")
        if end - start > MAX_WINDOW_SPAN:
            raise ValueError("window longer than 14 days")
        return self


def _availability(windows: list[Window]) -> list[Window]:
    if not 1 <= len(windows) <= MAX_WINDOWS:
        raise ValueError(f"availability needs 1-{MAX_WINDOWS} windows")
    ordered = sorted(windows, key=lambda w: parse_time(w.start))
    for prev, nxt in zip(ordered, ordered[1:]):
        if parse_time(nxt.start) < parse_time(prev.end):
            raise ValueError("availability windows must not overlap")
    return ordered


Availability = Annotated[list[Window], AfterValidator(_availability)]


class Context(Wire):
    request_id: Id
    contract_version: Literal["1.0.0"]
    mode: Literal["live", "fixture", "replay"]


class Consent(Wire):
    participant_id: Id
    community_id: Id
    version: StrictInt = Field(ge=1)
    matching: StrictBool
    model_processing: StrictBool
    public_interests: StrictBool
    revoked_at: IsoTime | None


class PublicParticipant(Wire):
    participant_id: Id
    display_name: DisplayName
    public_interests: list[Tag] = Field(max_length=10)
    is_synthetic: StrictBool


class PrivateIntent(Wire):
    participant_id: Id
    community_id: Id
    intent_version: StrictInt = Field(ge=1)
    goal: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
    interests: list[Tag] = Field(min_length=1, max_length=10)
    area_id: Id
    time_zone: TimeZoneName
    availability: Availability
    max_budget_minor: StrictInt = Field(ge=0, le=MAX_BUDGET_MINOR)
    currency: Currency
    max_duration_minutes: StrictInt = Field(ge=15, le=1440)
    group_preference: Literal["small"]
    consent_version: StrictInt = Field(ge=1)
    confirmed_at: IsoTime


class Candidate(Wire):
    """Internal only. Never serialize to a browser or peer."""

    intent: PrivateIntent
    public_profile: PublicParticipant

    @model_validator(mode="after")
    def _same_participant(self) -> "Candidate":
        if self.intent.participant_id != self.public_profile.participant_id:
            raise ValueError("candidate intent/profile participant mismatch")
        return self


class MemberVersion(Wire):
    participant_id: Id
    intent_version: StrictInt = Field(ge=1)
    consent_version: StrictInt = Field(ge=1)


ErrorCode = Literal[
    "INVALID_INPUT", "UNAUTHENTICATED", "FORBIDDEN", "NOT_FOUND",
    "CONSENT_REQUIRED", "STALE_REVISION", "CAPACITY_REACHED",
    "PROVIDER_UNAVAILABLE", "RATE_LIMITED", "IDEMPOTENCY_CONFLICT",
]


class ApiErrorBody(Wire):
    code: ErrorCode
    message: str
    request_id: Id
    retryable: StrictBool


class ApiError(Wire):
    error: ApiErrorBody


# ---------------------------------------------------------------------------
# Request bodies (contracts/API.md). Identity is never part of a body.
# ---------------------------------------------------------------------------
class WireRequest(Wire):
    """Network input: camelCase keys only (snake_case keys are rejected as extra)."""

    model_config = ConfigDict(validate_by_name=False, validate_by_alias=True)


class ConsentToggles(WireRequest):
    matching: StrictBool
    model_processing: StrictBool
    public_interests: StrictBool


class JoinCommunityRequest(WireRequest):
    display_name: DisplayName
    consent: ConsentToggles


class UpdateConsentRequest(ConsentToggles):
    expected_version: StrictInt = Field(ge=1)


class PutIntentRequest(WireRequest):
    """Confirmed intent fields. participantId/version/consentVersion/confirmedAt are server-set."""

    community_id: Id
    expected_version: StrictInt = Field(ge=0)  # 0 = create
    goal: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
    interests: list[Tag] = Field(min_length=1, max_length=10)
    area_id: Id
    time_zone: TimeZoneName
    availability: Availability
    max_budget_minor: StrictInt = Field(ge=0, le=MAX_BUDGET_MINOR)
    currency: Currency
    max_duration_minutes: StrictInt = Field(ge=15, le=1440)
    group_preference: Literal["small"]

    @field_validator("interests")
    @classmethod
    def _unique_interests(cls, value: list[str]) -> list[str]:
        lowered = [v.lower() for v in value]
        if len(set(lowered)) != len(lowered):
            raise ValueError("interests must be unique")
        return value


class UpdateAvailabilityRequest(WireRequest):
    community_id: Id
    expected_version: StrictInt = Field(ge=1)
    availability: Availability


class MembershipView(Wire):
    """Self-only view returned by GET /session and join."""

    community_id: Id
    display_name: DisplayName
    consent: Consent
    has_intent: StrictBool
    intent_version: StrictInt | None


class SessionView(Wire):
    participant_id: Id
    expires_at: IsoTime
    memberships: list[MembershipView]
