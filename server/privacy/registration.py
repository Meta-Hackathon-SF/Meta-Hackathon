"""Privacy registration for Kai's composed app (server/app/registry.py).

    from server.privacy.registration import privacy_registration, install_privacy_error_handler
    app = create_app(registrations=[privacy_registration(service), ...])
    install_privacy_error_handler(app)

server.app is imported lazily so privacy still imports on branches where Kai's
composition has not merged yet.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .api import actor_dependency, build_router, install_privacy_error_handler
from .service import PrivacyService

if TYPE_CHECKING:  # pragma: no cover
    from server.app.registry import ServiceRegistration

__all__ = ["install_privacy_error_handler", "privacy_registration"]


def privacy_registration(service: PrivacyService) -> "ServiceRegistration":
    from server.app.registry import ServiceRegistration

    async def ready() -> bool:
        import asyncio

        return await asyncio.to_thread(service.ready)  # don't block the event loop on DB I/O

    return ServiceRegistration(
        owner="privacy",
        router=build_router(service),
        authorize=actor_dependency(service),
        ready=ready,
    )
