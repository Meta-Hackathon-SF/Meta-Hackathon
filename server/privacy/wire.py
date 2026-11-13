"""Runtime validators for the privacy-owned wire types of contracts/protocol.ts 2.0.0.

These are not a second contract: field names and literals mirror protocol.ts and
tests/privacy/test_privacy_wire_contract.py fails if they drift. Python
attributes are snake_case; JSON is always camelCase (``.wire()``).

Produced here: Player, Consent, ApiError, and the request/response bodies of the
"Session, consent, safety" routes in contracts/API.md.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timezone
from typing import Annotated, Literal

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictInt,
    StrictStr,
)
from pydantic.alias_generators import to_camel

CONTRACT_VERSION = "2.0.0"


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


class WireRequest(Wire):
    """Network input: camelCase keys only (snake_case keys are rejected as extra)."""

    model_config = ConfigDict(validate_by_name=False, validate_by_alias=True)


def format_time(value: datetime) -> str:
    """RFC3339 UTC, second precision, ``Z`` suffix."""
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _display_name(value: str) -> str:
    value = unicodedata.normalize("NFC", value).strip()
    if not 1 <= len(value) <= 40:
        raise ValueError("displayName must be 1-40 characters")
    if any(unicodedata.category(ch) in {"Cc", "Cf", "Co", "Cs"} for ch in value):
        raise ValueError("displayName contains control characters")
    return value


Id = Annotated[StrictStr, Field(min_length=1, max_length=128)]
DisplayName = Annotated[StrictStr, AfterValidator(_display_name)]
IsoTime = StrictStr
_COLOR = re.compile(r"^#[0-9a-f]{6}$")
AvatarColor = Annotated[StrictStr, Field(pattern=_COLOR.pattern)]

ErrorCode = Literal[
    "INVALID_INPUT", "UNAUTHENTICATED", "FORBIDDEN", "NOT_FOUND",
    "CONSENT_REQUIRED", "STALE_REVISION", "PROVIDER_UNAVAILABLE", "RATE_LIMITED",
    "IDEMPOTENCY_CONFLICT", "CYCLE_LOCKED", "ROOM_EXPIRED", "MESSAGE_REJECTED",
]


# ---------------------------------------------------------------------------
# protocol.ts types (Patrik)
# ---------------------------------------------------------------------------
class Player(Wire):
    """PUBLIC only to self, or to the other player after a mutual reveal."""

    player_id: Id
    display_name: DisplayName
    avatar_color: AvatarColor
    is_synthetic: StrictBool


class Consent(Wire):
    """PRIVATE: self + privacy module."""

    player_id: Id
    community_id: Id
    match_answers: StrictBool
    anonymous_chat: StrictBool
    is_adult: StrictBool
    version: StrictInt = Field(ge=1)
    revoked_at: IsoTime | None

    @property
    def grants_play(self) -> bool:
        """All three toggles are required to play (contracts/PRIVACY.md)."""
        return self.match_answers and self.anonymous_chat and self.is_adult


class ApiErrorBody(Wire):
    code: ErrorCode
    message: StrictStr
    request_id: Id
    retryable: StrictBool


class ApiError(Wire):
    error: ApiErrorBody


# ---------------------------------------------------------------------------
# Route bodies (contracts/API.md "Session, consent, safety"). Identity is never
# part of a body: a client-supplied playerId is rejected as an unknown field.
# ---------------------------------------------------------------------------
class ConsentToggles(WireRequest):
    match_answers: StrictBool
    anonymous_chat: StrictBool
    is_adult: StrictBool


class JoinRequest(ConsentToggles):
    display_name: DisplayName


class UpdateConsentRequest(ConsentToggles):
    expected_version: StrictInt = Field(ge=1)


class SessionView(Wire):
    """Response of POST /communities/:id/join and GET /session."""

    player: Player
    consent: Consent
    is_operator: StrictBool
