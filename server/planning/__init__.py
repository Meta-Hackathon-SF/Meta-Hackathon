"""Constellations planning (owner: Adam): question bank, weekly selection, M2 follow-up.

See README.md. Other owners import from this package root only.
"""
from server.providers import TaskRegistry

from .clarify import (
    CLARIFY_PROMPT_VERSION,
    ClarifyResult,
    ClarifyService,
    InMemoryClarifyStore,
    register_clarify_task,
)
from .errors import BankError, PlanningError
from .ports import ChatPostPort, OutputGuardPort, WeekStartLookup
from .questions import QuestionBank, load_default_bank, question_problems, validate_question
from .selection import InMemorySelectionStore, QuestionService, SelectionStore, pick_week


def register_planning_tasks(registry: TaskRegistry) -> TaskRegistry:
    """Register every Muse task planning owns. Kai calls this once at startup."""
    register_clarify_task(registry)
    return registry


__all__ = [
    "BankError",
    "CLARIFY_PROMPT_VERSION",
    "ChatPostPort",
    "ClarifyResult",
    "ClarifyService",
    "InMemoryClarifyStore",
    "InMemorySelectionStore",
    "OutputGuardPort",
    "PlanningError",
    "QuestionBank",
    "QuestionService",
    "SelectionStore",
    "WeekStartLookup",
    "load_default_bank",
    "pick_week",
    "question_problems",
    "register_clarify_task",
    "register_planning_tasks",
    "validate_question",
]
