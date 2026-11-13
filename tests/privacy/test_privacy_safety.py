"""M1 safety screening (role task 4). Offline: Adam's labeled FixtureMuse with a
scripted transport stands in for the provider. No paid call."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from server.privacy.errors import PrivacyError
from server.privacy.safety import SAFETY_PROMPT_VERSION, SafetyScreener, code_screen, register_safety_task

providers = pytest.importorskip("server.providers")
from server.providers import ProviderError, TaskRegistry  # noqa: E402
from server.providers.fixture import FixtureMuse, ScriptedTransport, decode_user_message  # noqa: E402

WEEK = json.loads((Path(__file__).resolve().parents[2] / "contracts" / "fixtures" / "week-sample.json").read_text())
DISTRESS = WEEK["distressFixture"]["text"]
INJECTION = WEEK["injectionFixture"]["text"]


def make(*steps, handler=None):
    transport = ScriptedTransport()
    if steps:
        transport.queue("safety_screen", *steps)
    if handler:
        transport.on("safety_screen", handler)
    muse = FixtureMuse(register_safety_task(TaskRegistry()), transport)
    return SafetyScreener(muse), transport


def run(coro):
    return asyncio.run(coro)


def test_task_registered_with_contract_schemas():
    registry = register_safety_task(TaskRegistry())
    spec = registry.get("safety_screen", SAFETY_PROMPT_VERSION)
    assert spec.input_schema is not None and spec.temperature == 0.0


def test_model_flag_is_returned_and_reason_discarded():
    screener, transport = make({"flag": "none", "reason": "ordinary venting"})
    assert run(screener.screen("cooking for one is honestly depressing", "answer")) == "none"
    screener, _ = make({"flag": "distress", "reason": "possible crisis"})
    assert run(screener.screen("i feel like disappearing", "chat_message")) == "distress"


def test_prompt_carries_random_id_and_text_only():
    seen = []

    def handler(inp):
        seen.append(inp)
        return {"flag": "none", "reason": "ok"}

    screener, transport = make(handler=handler)
    run(screener.screen("Mostly the dining hall corner table", "answer"))
    run(screener.screen("Mostly the dining hall corner table", "answer"))
    assert set(seen[0]) == {"text", "subjectType"} and set(seen[0]["text"]) == {"id", "text"}
    assert seen[0]["text"]["id"] != seen[1]["text"]["id"]  # random per call
    user = transport.calls[0].user
    assert "p-" not in json.dumps(decode_user_message(user)["input"])  # no player ids


def test_seeded_distress_fixture_never_reaches_the_model():
    screener, transport = make(handler=lambda inp: {"flag": "none", "reason": "x"})
    assert run(screener.screen(DISTRESS, "answer")) == WEEK["distressFixture"]["expectedFlag"]
    assert transport.calls == []


@pytest.mark.parametrize("text,expected", [
    ("sometimes i want to die", "distress"), ("I've been cutting myself again", "distress"),
    ("everyone would be better off without me", "distress"), ("I'm going to bring a gun tomorrow", "harm"),
    ("i will kill him", "harm"), ("Dining hall with my floor", "none"), ("this exam is killing me lol", "none"),
    ("I feel lonely most nights", "none"), ("that party was the bomb", "none"),
    ("I'll take a stab at the problem set", "none"),
])
def test_code_prescreen(text, expected):
    assert code_screen(text) == expected


def test_model_cannot_downgrade_code_flag():
    screener, transport = make(handler=lambda inp: {"flag": "none", "reason": "fine"})
    assert run(screener.screen("honestly i want to die", "chat_message")) == "distress"


def test_injection_text_is_data():
    screener, transport = make(handler=lambda inp: {"flag": "none", "reason": "not a crisis"})
    assert run(screener.screen(INJECTION, "answer")) == "none"
    assert INJECTION not in transport.calls[0].developer  # player text never becomes instructions


@pytest.mark.parametrize("step", [
    ProviderError("unavailable", "down"), ProviderError("rate_limited", "slow"),
    {"flag": "maybe", "reason": "x"}, "not json",
])
def test_provider_failure_or_bad_output_is_retryable_error(step):
    screener, _ = make(step, step)  # adapter retries once
    with pytest.raises(PrivacyError) as e:
        run(screener.screen("what a week", "chat_message"))
    assert e.value.code == "PROVIDER_UNAVAILABLE" and e.value.retryable is True


def test_unconfigured_model_fails_closed_but_code_flags_still_work():
    screener = SafetyScreener(None)
    with pytest.raises(PrivacyError) as e:
        run(screener.screen("what a week", "answer"))
    assert e.value.code == "PROVIDER_UNAVAILABLE"
    assert run(screener.screen("i want to die", "answer")) == "distress"


@pytest.mark.parametrize("text,subject", [("", "answer"), ("   ", "answer"), (None, "answer"), ("hi", "email")])
def test_invalid_input(text, subject):
    screener, _ = make()
    with pytest.raises(PrivacyError) as e:
        run(screener.screen(text, subject))
    assert e.value.code == "INVALID_INPUT"


def test_sync_adapter_for_will_cycle_service():
    screener, _ = make({"flag": "none", "reason": "ok"})
    screen = screener.sync_screen()
    assert screen("Dining hall with my floor", "answer") == "none"

    async def inside_loop():
        return screen(DISTRESS, "answer")

    assert run(inside_loop()) == "distress"
