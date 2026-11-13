"""Ports planning consumes from other owners (contracts/protocol.ts 2.0.0).

Planning never imports another owner's package. The composition root (Kai)
injects real implementations; tests inject the labeled test-only doubles in
tests/planning/doubles.py.
"""
from __future__ import annotations

from typing import Any, Awaitable, Callable, Protocol

GUARD_REASONS = frozenset({"quote_5_words", "sensitive_term", "pii", "contact_info"})


class OutputGuardPort(Protocol):
    """Patrik's OutputGuard.check(text, againstAnswers) -> {ok, reasons}."""

    def check(self, text: str, against_answers: list[str]) -> dict[str, Any]: ...


def guard_allows(guard: OutputGuardPort, text: str, against_answers: list[str]) -> bool:
    """True only for a well-formed ``{"ok": true}`` verdict. Anything else fails closed."""
    try:
        verdict = guard.check(text, against_answers)
    except Exception:
        return False
    return isinstance(verdict, dict) and verdict.get("ok") is True


class ChatPostPort(Protocol):
    """Kai's ChatPort.postSystem(roomId, message) -> ChatMessage."""

    async def post_system(self, room_id: str, message: dict[str, Any]) -> dict[str, Any]: ...


# Will's cycle data: weekStart (YYYY-MM-DD, a Monday) for a cycle id.
WeekStartLookup = Callable[[str], Awaitable[str]]


class SensitivityPort(Protocol):
    """Patrik's ``SensitivityScreen`` (D014 M10): ``await allowed(texts)`` returns one
    bool per text, True only for a clean "none". Runs after OutputGuard, never
    instead of it. Fails closed on provider errors (the screen returns False)."""

    async def allowed(self, texts: list[str]) -> list[bool]: ...


async def sensitivity_allows(screen: "SensitivityPort | None", texts: list[str]) -> bool:
    """True when no screen is configured or every text is allowed. Any error blocks."""
    if screen is None:
        return True
    try:
        verdicts = await screen.allowed(list(texts))
    except Exception:
        return False
    return isinstance(verdicts, list) and len(verdicts) == len(texts) and all(v is True for v in verdicts)
