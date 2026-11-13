"""Kai API composition. No unconfigured or fixture route is mounted by default."""

from server.app.errors import ServiceError


def require_configured(value):
    """Missing production ports fail closed; tests explicitly inject their adapters."""
    if value is None:
        raise ServiceError("PROVIDER_UNAVAILABLE")
    return value
