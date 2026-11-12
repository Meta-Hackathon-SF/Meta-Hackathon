"""Synthetic request builders for privacy tests. No real participant data."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from server.privacy.wire import JoinCommunityRequest, PutIntentRequest, UpdateConsentRequest

COMMUNITY = "demo-campus"
AREA = "demo-campus-central"


def z(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def window(day_offset: int = 1, start_hour: int = 18, hours: int = 3) -> dict:
    base = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    start = base + timedelta(days=day_offset, hours=start_hour)
    return {"start": z(start), "end": z(start + timedelta(hours=hours))}


def intent_body(expected: int = 0, **overrides) -> dict:
    body = {
        "communityId": COMMUNITY,
        "expectedVersion": expected,
        "goal": "meet people for a low-key evening activity",
        "interests": ["board games", "coffee"],
        "areaId": AREA,
        "timeZone": "America/Los_Angeles",
        "availability": [window()],
        "maxBudgetMinor": 1200,
        "currency": "USD",
        "maxDurationMinutes": 120,
        "groupPreference": "small",
    }
    body.update(overrides)
    return body


def intent_req(expected: int = 0, **overrides) -> PutIntentRequest:
    return PutIntentRequest.model_validate(intent_body(expected, **overrides))


def join_req(name: str = "Tester", *, matching=True, model=True, public=True) -> JoinCommunityRequest:
    return JoinCommunityRequest.model_validate({
        "displayName": name,
        "consent": {"matching": matching, "modelProcessing": model, "publicInterests": public},
    })


def consent_req(expected: int, *, matching=True, model=True, public=True) -> UpdateConsentRequest:
    return UpdateConsentRequest.model_validate({
        "expectedVersion": expected, "matching": matching,
        "modelProcessing": model, "publicInterests": public,
    })


def eligible_member(service, name: str = "Tester", **consent):
    """Guest session -> join demo community -> confirmed intent."""
    token, actor, _ = service.create_guest_session()
    service.join(actor, COMMUNITY, join_req(name, **consent))
    service.put_intent(actor, intent_req())
    return token, actor
