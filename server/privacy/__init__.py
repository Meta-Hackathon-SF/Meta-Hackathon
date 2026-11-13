"""Constellations privacy: verification, sessions, consent (owner: Patrik).

Public surface for other owners. Do not import privacy internals or open the
privacy store directly; use these ports.
"""

from .api import (
    actor_dependency,
    build_router,
    install_error_handlers,
    install_privacy_error_handler,
    session_token,
)
from .answers import AnswerStore
from .errors import PrivacyError
from .guard import OutputGuard
from .service import Actor, ChangeNotice, JoinResult, PrivacyService
from .store import PrivacyStore

__all__ = [
    "Actor",
    "AnswerStore",
    "ChangeNotice",
    "JoinResult",
    "OutputGuard",
    "PrivacyError",
    "PrivacyService",
    "PrivacyStore",
    "actor_dependency",
    "build_router",
    "install_error_handlers",
    "install_privacy_error_handler",
    "session_token",
]
