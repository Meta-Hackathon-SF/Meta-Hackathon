"""Ports the cycle service consumes from other owners (owner of this file: Will).

These are the Python shapes this package calls. They mirror contracts/protocol.ts
where a port exists there (QuestionPort, PrivacyPort.screen, MusePort clarify)
and PROPOSE a shape where the contract names an owner but no interface yet
(Patrik's answer store, Kai's lock/reveal trigger). Proposed shapes are tracked
in docs/handoffs/will.md "Blocked on"; until the owner delivers, only the
labeled test-only adapters in server/cycle/testing.py implement them.

No cross-owner imports: the composition root (Kai) passes adapters in.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Literal, Protocol

from .wire import DailyAnswer, DailyQuestion, M2Out, PrevalenceGuess, SafetyLevel, WeeklyCycle


@dataclass(frozen=True)
class Session:
    """Result of Patrik's PrivacyPort.requireSession. Never built from client input."""

    playerId: str
    communityId: str
    isOperator: bool


class AnswerStore(Protocol):
    """PROPOSED to Patrik: private answer + guess storage. Author-only reads."""

    def get(self, cycle_id: str, player_id: str, day: int) -> DailyAnswer | None:
        """The player's own non-deleted answer for that day, if any."""

    def list_for_player(self, cycle_id: str, player_id: str) -> list[DailyAnswer]:
        """The player's own non-deleted answers in the cycle."""

    def save(self, answer: DailyAnswer, flag: SafetyLevel) -> None:
        """Insert or replace by (cycleId, playerId, day). ``flag`` is the M1
        result for this text; flagged answers must stay out of every snapshot."""

    def delete(self, cycle_id: str, player_id: str, day: int, deleted_at: str) -> bool:
        """Delete the player's answer; False when there was none."""

    def save_guess(self, guess: PrevalenceGuess) -> None:
        """Stored apart from answers."""

    def get_guess(self, cycle_id: str, player_id: str) -> PrevalenceGuess | None: ...

    def purge_cycle(self, cycle_id: str) -> None:
        """Operator reset of a fixture cycle: drop its answers and guesses."""


class QuestionPort(Protocol):
    """Adam: contracts/protocol.ts QuestionPort.selectWeek."""

    def select_week(self, cycle_id: str, community_id: str) -> Sequence[DailyQuestion | dict]: ...


# Patrik: PrivacyPort.screen(text, "answer") -> SafetyLevel (M1).
SafetyScreen = Callable[[str, Literal["answer"]], SafetyLevel]
# Adam: MusePort.run(task="clarify") reduced to (question text, answer text) -> M2Out.
Clarify = Callable[[str, str], M2Out | dict]
# Patrik: OutputGuard.check(text, againstAnswers).ok for the M2 follow-up question.
TextGuard = Callable[[str], bool]


class CycleHooks(Protocol):
    """PROPOSED to Kai: called after a transition is committed."""

    def on_changed(self, cycle: WeeklyCycle) -> None:
        """Any change; Kai emits StreamEvent cycle.updated."""

    def on_locked(self, cycle: WeeklyCycle) -> None:
        """Saturday lock; Kai enqueues the formation job."""

    def on_revealed(self, cycle: WeeklyCycle) -> None:
        """Sunday reveal; Kai opens rooms and publishes the Sky."""


class NoHooks:
    def on_changed(self, cycle: WeeklyCycle) -> None: ...
    def on_locked(self, cycle: WeeklyCycle) -> None: ...
    def on_revealed(self, cycle: WeeklyCycle) -> None: ...


# PROPOSED to Patrik: create/ensure labeled synthetic players (isSynthetic=true)
# in a community before the operator top-up writes their fixture answers.
SyntheticSeeder = Callable[[str, list[dict]], None]
