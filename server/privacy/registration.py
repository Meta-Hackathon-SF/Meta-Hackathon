"""Privacy registration for Kai's composed app (server/app/registry.py).

    from server.privacy.registration import privacy_registration, install_privacy_error_handler
    app = create_app(registrations=[
        privacy_registration(service, answers=answers, moderation=moderation,
                             resolve_handle=chat.resolve_handle),
        ...])
    install_privacy_error_handler(app)

Without ``answers`` the ``DELETE /me/data`` route is not mounted; without both
``moderation`` and ``resolve_handle`` the ``POST /me/blocks`` route is not
mounted. Pass them so a player can delete their data and so blocks made in a
chat reach privacy's block store (future constellations respect them).

server.app is imported lazily so privacy still imports on branches where Kai's
composition has not merged yet.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .activity import ActivityStore
from .answers import AnswerStore
from .events import EventStore
from .api import actor_dependency, build_router, install_privacy_error_handler
from .moderation import HandleResolver, ModerationStore
from .service import PrivacyService

if TYPE_CHECKING:  # pragma: no cover
    from server.app.registry import ServiceRegistration

__all__ = ["install_privacy_error_handler", "privacy_registration"]


def privacy_registration(
    service: PrivacyService,
    *,
    answers: AnswerStore | None = None,
    moderation: ModerationStore | None = None,
    resolve_handle: HandleResolver | None = None,
    activity: ActivityStore | None = None,
    events: EventStore | None = None,
    current_cycle_id=None,
) -> "ServiceRegistration":
    from server.app.registry import ServiceRegistration

    async def ready() -> bool:
        import asyncio

        return await asyncio.to_thread(service.ready)  # don't block the event loop on store I/O

    return ServiceRegistration(
        owner="privacy",
        router=build_router(service, answers, moderation, resolve_handle, activity, events, current_cycle_id),
        authorize=actor_dependency(service),
        ready=ready,
    )
