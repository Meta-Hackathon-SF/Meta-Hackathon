"""Adapters from planning's services onto the call shapes other owners chose.

Will's cycle service (server/cycle/ports.py) consumes synchronous callables:
    QuestionPort.select_week(cycle_id, community_id) -> 5 DailyQuestion
    Clarify(question_text, answer_text) -> {needsFollowup, question}
These classes satisfy exactly those shapes. They import nothing from
server/cycle; the composition root passes them in.
"""
from __future__ import annotations

import asyncio
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from typing import Any, Callable, Coroutine, TypeVar

from .clarify import ClarifyService
from .questions import QuestionBank
from .selection import QuestionService

T = TypeVar("T")


def run_sync(coro: Coroutine[Any, Any, T]) -> T:
    """Run a coroutine to completion from synchronous code.

    Meant for sync FastAPI handlers (they run in a worker thread with no event
    loop). If a loop is already running in this thread the coroutine runs in a
    helper thread; that blocks the caller, so async code should ``await`` the
    service directly instead.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


def _monday_of(day: date) -> date:
    return day - timedelta(days=day.weekday())


class CycleQuestionPort:
    """Sync ``QuestionPort`` for the cycle service.

    The cycle service creates the cycle id, then asks for five questions and
    overwrites ``cycleId`` and ``date`` on what it gets back. ``week_start`` may
    therefore be omitted: dates then count from the Monday of the current week,
    which the cycle service replaces. Selection rules and the four-cycle
    no-repeat history are the same as ``QuestionService.select_week``.
    """

    def __init__(self, service: QuestionService, *,
                 week_start: Callable[[str], str] | None = None,
                 today: Callable[[], date] = date.today) -> None:
        self._service = service
        self._week_start = week_start
        self._today = today

    def select_week(self, cycle_id: str, community_id: str) -> list[dict[str, Any]]:
        monday = (self._week_start(cycle_id) if self._week_start is not None
                  else _monday_of(self._today()).isoformat())
        return self._service.select_week_on(cycle_id, community_id, monday)


class ChatSystemPoster:
    """``ChatPostPort`` over a chat service that spells the method ``postSystem``.

    Kai's chat service (server/chat/service.py on role/kai-orchestration) exposes
    ``async postSystem(roomId, message)`` and accepts only
    ``{roomId, handle: "Muse", text, kind: "system" | "muse_nudge"}``, which is
    exactly what ``NudgeService.propose_and_post`` sends. This only renames the
    call; it imports nothing from server/chat and adds no fields.
    """

    def __init__(self, chat: Any) -> None:
        if not callable(getattr(chat, "postSystem", None)):
            raise TypeError("chat must provide async postSystem(roomId, message)")
        self._chat = chat

    async def post_system(self, room_id: str, message: dict[str, Any]) -> dict[str, Any]:
        return await self._chat.postSystem(room_id, message)


class SyncClarify:
    """Sync ``Clarify(question_text, answer_text) -> M2Out`` for the cycle service.

    Stateless: the cycle service already enforces one follow-up per answer,
    skips flagged answers and stores the result. This runs M2 through the Muse
    adapter, validates the proposal and applies OutputGuard. Provider failure
    or a rejected proposal returns the curated ``followUpHint`` when ``bank``
    knows the question, otherwise no follow-up; it does not raise.
    """

    def __init__(self, service: ClarifyService, bank: QuestionBank | None = None) -> None:
        self._service = service
        self._hints = {q["text"]: q["followUpHint"] for q in bank.questions} if bank is not None else {}
        self.last_source: str | None = None  # "muse" | "fallback"; for operator display only

    def __call__(self, question_text: str, answer_text: str) -> dict[str, Any]:
        question = {"text": question_text, "followUpHint": self._hints.get(question_text)}
        result = run_sync(self._service.decide(question, answer_text, f"clarify-{uuid.uuid4().hex[:12]}"))
        self.last_source = result.source
        return dict(result.output)
