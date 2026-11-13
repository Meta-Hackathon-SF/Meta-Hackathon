"""Synthetic request builders for privacy tests. No real participant data."""

from __future__ import annotations

from server.privacy.wire import JoinRequest, UpdateConsentRequest

COMMUNITY = "community-demo"  # seeded by db/privacy/001_privacy.sql, matches contracts/fixtures


def join_body(name: str = "Tester (synthetic)", *, match=True, chat=True, adult=True) -> dict:
    return {"displayName": name, "matchAnswers": match, "anonymousChat": chat, "isAdult": adult}


def join_req(name: str = "Tester (synthetic)", **toggles) -> JoinRequest:
    return JoinRequest.model_validate(join_body(name, **toggles))


def consent_body(expected: int, *, match=True, chat=True, adult=True) -> dict:
    return {"expectedVersion": expected, "matchAnswers": match, "anonymousChat": chat, "isAdult": adult}


def consent_req(expected: int, **toggles) -> UpdateConsentRequest:
    return UpdateConsentRequest.model_validate(consent_body(expected, **toggles))


def joined(service, name: str = "Tester (synthetic)"):
    """Join the demo community. Returns (token, actor)."""
    result = service.join(COMMUNITY, join_req(name))
    return result.token, service.require_session(result.token)
