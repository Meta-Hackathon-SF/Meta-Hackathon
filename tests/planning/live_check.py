"""MANUAL live check of planning's real prompts (M2, M7, M6). PAID calls; not a test.

    python3 -m tests.planning.live_check            # 4 calls, hard cap 6 including retries
    python3 -m tests.planning.live_check m2-vague   # only the named calls: m2-vague m2-specific m7 m6

Not collected by pytest. Inputs are synthetic (shared fixtures). Uses the real
Muse adapter and Patrik's real OutputGuard when server.privacy is importable
(otherwise the TEST-ONLY double; the output names which one ran). Prints model text to the terminal only; nothing is written to disk.
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
from datetime import datetime, timedelta, timezone

from server.planning import (
    ClarifyService, InMemorySelectionStore, NudgeService, PlanningError, QuestionGenerator,
    QuestionService, VenueCatalog, load_default_bank, register_planning_tasks,
)
from server.providers import ProviderError, TaskRegistry, build_muse_adapter, load_muse_config
from server.providers.config import load_env_file
from server.providers.transport import MetaChatCompletionsTransport

from .doubles import FIXTURES, TestOnlyChat, TestOnlyOutputGuard, TestOnlyWeekStart

MAX_PROVIDER_CALLS = 6


class CappedTransport:
    """Refuses to spend past the cap, retries included."""

    def __init__(self, inner) -> None:
        self.inner, self.calls = inner, 0

    async def complete(self, request):
        if self.calls >= MAX_PROVIDER_CALLS:
            raise ProviderError("invalid_request", "live check call cap reached")
        self.calls += 1
        return await self.inner.complete(request)


async def main() -> int:
    load_env_file()
    config = load_muse_config()
    if config is None:
        print("not configured")
        return 2
    transport = CappedTransport(MetaChatCompletionsTransport(config))
    muse = build_muse_adapter(register_planning_tasks(TaskRegistry()), config, transport=transport,
                              telemetry=lambda _r: None)
    try:  # Patrik's real guard when its dependencies are installed
        from server.privacy import OutputGuard
        guard, guard_name = OutputGuard(), "server.privacy.OutputGuard (real)"
    except ImportError:
        guard, guard_name = TestOnlyOutputGuard(), "TEST-ONLY double"
    bank = load_default_bank()
    week = json.loads((FIXTURES / "week-sample.json").read_text())
    answers = [a["text"] for a in week["answers"] if a["playerId"] in ("p-maya", "p-dev", "p-jordan")]
    report: list[dict] = []
    only = set(sys.argv[1:])

    def wanted(name: str) -> bool:
        return not only or name in only

    clarify = ClarifyService(muse, guard)
    cases = [("vague", bank.get("q-joys-small-win"), "idk, coffee I guess"),
             ("specific", bank.get("q-routine-meals"),
              "Mostly the dining hall corner table with headphones in, usually on my own between labs")]
    for label, question, answer in cases:
        if not wanted(f"m2-{label}"):
            continue
        started = time.monotonic()
        res = await clarify.follow_up(answer_id=f"live-{label}", question=question, answer_text=answer,
                                      request_id=f"live-m2-{label}")
        report.append({"call": f"M2 {label}", "source": res.source, "output": res.output,
                       "evidence": res.evidence, "wallS": round(time.monotonic() - started, 1)})

    async def context(_cid):
        return {"constellationId": "c-live", "roomId": "room-live", "memberCount": 3, "roomOpen": True,
                "sharedMeaning": "They end up having most meals on their own and would rather not.",
                "againstAnswers": answers}

    now = datetime(2026, 11, 18, 18, 0, tzinfo=timezone.utc)  # fixture campus events fall in this window
    chat = TestOnlyChat()
    nudges = NudgeService(muse, guard, VenueCatalog.load(), context, chat, now=lambda: now)
    if wanted("m7"):
        started = time.monotonic()
        outcome = await nudges.propose_detailed("c-live", request_id="live-m7", window=(now, now + timedelta(hours=72)))
        row = {"call": "M7", "reason": outcome.reason, "nudge": outcome.nudge, "wallS": round(time.monotonic() - started, 1)}
        if outcome.nudge:
            row["chatText"] = nudges.chat_text(outcome.nudge)
        report.append(row)

    questions = QuestionService(bank, InMemorySelectionStore(), TestOnlyWeekStart())
    generator = QuestionGenerator(muse, guard, questions)
    if wanted("m6"):
        started = time.monotonic()
        try:
            gen = await generator.generate(
                count=3, request_id="live-m6", category_mix={"belonging": 2, "small_joys": 1, "routine": 1},
                # Synthetic D010-style community topic shares (as signals.aggregate_signals would emit).
                aggregate_signals=[{"tag": "music", "share": 0.45}, {"tag": "coffee", "share": 0.35},
                                   {"tag": "outdoors", "share": 0.3}, {"tag": "study", "share": 0.6}],
                recent_question_ids=[q["questionId"] for q in bank.questions][:12])
            report.append({"call": "M6", "kept": gen.pending, "rejected": gen.rejected, "rejections": gen.rejections,
                           "basis": gen.basis, "evidence": gen.evidence,
                           "wallS": round(time.monotonic() - started, 1)})
        except PlanningError as exc:
            report.append({"call": "M6", "error": exc.code, "message": exc.message})

    print(json.dumps({"guard": guard_name, "providerCalls": transport.calls, "report": report}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
