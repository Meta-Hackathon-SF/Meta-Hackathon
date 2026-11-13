"""Facebook Space privacy: verification, sessions, consent (owner: Patrik).

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
from .formation import FormationLease, LeasedSnapshot, PrivacyFormation
from .guard import OutputGuard
from .moderation import ModerationStore
from .safety import SafetyScreener, register_safety_task
from .service import Actor, ChangeNotice, JoinResult, PrivacyService
from .store import PrivacyStore

__all__ = [
    "Actor",
    "AnswerStore",
    "ChangeNotice",
    "FormationLease",
    "LeasedSnapshot",
    "ModerationStore",
    "JoinResult",
    "OutputGuard",
    "PrivacyError",
    "PrivacyFormation",
    "PrivacyService",
    "PrivacyStore",
    "SafetyScreener",
    "actor_dependency",
    "build_router",
    "install_error_handlers",
    "install_privacy_error_handler",
    "register_safety_task",
    "session_token",
]
