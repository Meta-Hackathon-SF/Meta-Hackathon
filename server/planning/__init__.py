"""Facebook Space planning (owner: Adam): question bank, weekly selection, M2 follow-up, M7 event nudges, M6 question generation.

See README.md. Other owners import from this package root only; the FastAPI
router lives in ``server.planning.api`` so the rest stays standard-library only.
"""
from server.providers import TaskRegistry

from .adapters import ChatSystemPoster, CycleQuestionPort, SyncClarify, run_sync
from .clarify import (
    CLARIFY_PROMPT_VERSION,
    ClarifyResult,
    ClarifyService,
    InMemoryClarifyStore,
    register_clarify_task,
)
from .errors import BankError, PlanningError
from .generation import (
    GENERATION_PROMPT_VERSION,
    GenerationResult,
    InMemoryPendingQuestions,
    QuestionGenerator,
    register_generation_task,
)
from .nudges import (
    NUDGE_PROMPT_VERSION,
    InMemoryNudgeStore,
    NudgeOutcome,
    NudgeService,
    register_nudge_task,
)
from .ports import ChatPostPort, OutputGuardPort, WeekStartLookup
from .questions import QuestionBank, load_default_bank, question_problems, validate_question
from .selection import InMemorySelectionStore, QuestionService, SelectionStore, pick_week
from .venues import VenueCatalog


def register_planning_tasks(registry: TaskRegistry) -> TaskRegistry:
    """Register every Muse task planning owns. Kai calls this once at startup."""
    register_clarify_task(registry)
    register_nudge_task(registry)
    register_generation_task(registry)
    return registry


__all__ = [
    "BankError",
    "CLARIFY_PROMPT_VERSION",
    "ChatPostPort",
    "ClarifyResult",
    "ClarifyService",
    "ChatSystemPoster",
    "CycleQuestionPort",
    "InMemoryClarifyStore",
    "GENERATION_PROMPT_VERSION",
    "GenerationResult",
    "InMemoryNudgeStore",
    "InMemoryPendingQuestions",
    "InMemorySelectionStore",
    "NUDGE_PROMPT_VERSION",
    "NudgeOutcome",
    "NudgeService",
    "OutputGuardPort",
    "PlanningError",
    "QuestionBank",
    "QuestionGenerator",
    "QuestionService",
    "SelectionStore",
    "SyncClarify",
    "VenueCatalog",
    "WeekStartLookup",
    "load_default_bank",
    "pick_week",
    "question_problems",
    "register_clarify_task",
    "run_sync",
    "register_generation_task",
    "register_nudge_task",
    "register_planning_tasks",
    "validate_question",
]
