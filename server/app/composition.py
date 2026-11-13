"""Compose only owner-published production services; no implicit fixture setup."""

from collections.abc import Sequence

from server.app.config import Settings
from server.app.main import create_app
from server.app.registry import ServiceRegistration
from server.privacy import PrivacyService, install_privacy_error_handler
from server.privacy.registration import privacy_registration


def compose(
    *,
    privacy: PrivacyService,
    settings: Settings | None = None,
    registrations: Sequence[ServiceRegistration] = (),
):
    """Caller supplies configured services and owns their lifespan/storage.

    PrivacyStore is never opened or queried by orchestration. Mounting privacy
    proves session composition only, not availability of answers/M1/OutputGuard.
    """
    app = create_app(
        settings=settings, registrations=[privacy_registration(privacy), *registrations]
    )
    install_privacy_error_handler(app)
    return app
