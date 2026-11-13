"""Real owner ports with TEST-ONLY workflow storage and scripted Muse transport.

All participants, answers and model results are synthetic. No network/model call.
"""

import asyncio
import json
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from server.app.config import Settings
from server.app.cycles import SerializedCycle
from server.app.errors import ServiceError
from server.app.main import create_app
from server.app.registry import ServiceRegistration
from server.chat import policy
from server.chat.api import build_router
from server.chat.service import ChatService, effective_now
from server.cycle import CycleService, Session
from server.cycle.wire import DailyAnswer, NewCycleRequest, PrevalenceGuess, SubmitAnswerRequest
from server.orchestration.wire import Constellation
from server.planning import (
    CycleQuestionPort,
    InMemorySelectionStore,
    QuestionService,
    load_default_bank,
)
from server.privacy import (
    AnswerStore,
    ModerationStore,
    OutputGuard,
    PrivacyError,
    PrivacyFormation,
    PrivacyService,
    PrivacyStore,
    SafetyScreener,
    actor_dependency,
    install_privacy_error_handler,
    register_safety_task,
)
from server.privacy import (
    build_router as privacy_router,
)
from server.privacy.fixtures import seed_community
from server.privacy.wire import JoinRequest, UpdateConsentRequest
from server.providers import TaskRegistry
from server.providers.fixture import FixtureMuse, ScriptedTransport
from tests.orchestration.storage_adapter import TestWorkflowRepository


class SyntheticClock:
    def __init__(self):
        self.now = datetime(2026, 11, 12, 20, tzinfo=UTC)

    def __call__(self):
        return self.now


@contextmanager
def setup():
    clock = SyntheticClock()
    privacy_store = PrivacyStore(":memory:")
    seed_community(privacy_store, "synthetic-community", "Synthetic test Group")
    privacy = PrivacyService(privacy_store, clock=clock)
    answers = AnswerStore(
        privacy_store, privacy, answer_model=DailyAnswer, guess_model=PrevalenceGuess
    )
    moderation = ModerationStore(privacy_store, privacy)
    formation = PrivacyFormation(privacy_store, answers, moderation)
    transport = ScriptedTransport().on(
        "safety_screen", lambda _data: {"flag": "none", "reason": "fixture"}
    )
    safety = SafetyScreener(FixtureMuse(register_safety_task(TaskRegistry()), transport))
    bank = load_default_bank()
    questions = QuestionService(bank, InMemorySelectionStore(), lambda _cycle: "2026-11-09")
    raw_cycles = CycleService(
        answers=answers,
        questions=CycleQuestionPort(questions),
        screen=safety.sync_screen(),
        clock=clock,
    )
    cycles = SerializedCycle(raw_cycles)
    cycle = cycles.create_cycle(
        NewCycleRequest(communityId="synthetic-community", demoTiming=True, weekStart="2026-11-09")
    )
    actors, tokens = [], []
    for index in range(4):
        joined = privacy.join(
            "synthetic-community",
            JoinRequest(
                displayName=f"Synthetic player {index}",
                matchAnswers=True,
                anonymousChat=True,
                isAdult=True,
            ),
        )
        actor = privacy.require_session(joined.token)
        actors.append(actor)
        tokens.append(joined.token)
        if index < 3:
            cycles.submit_answer(
                Session(actor.player_id, actor.community_id, False),
                cycle.cycleId,
                SubmitAnswerRequest(
                    day=1, text=f"Synthetic private weekly detail number {index}", source="text"
                ),
            )
    for status in ["locked", "forming", "revealed"]:
        cycle = cycles.advance(cycle.cycleId, status)
    repository = TestWorkflowRepository()
    lease = formation.prepare_formation(cycle.cycleId, cycle.communityId)
    constellation = Constellation(
        constellationId="synthetic-c1",
        cycleId=cycle.cycleId,
        memberIds=[a.player_id for a in actors[:3]],
        sharedMeaning="Synthetic shared routine",
        confidence=0.8,
        isLooseMatch=False,
        name="Synthetic stars",
        shapeId="arc-3",
        colorId="blue",
        baselineAgrees=True,
    )
    with repository.transaction() as state:
        policy.open_rooms(
            state.chat,
            cycle,
            [constellation],
            set(lease.player_ids),
            [],
            effective_now(cycle, clock),
        )
        room_id = next(iter(state.chat.rooms))
    chat = ChatService(
        repository=repository,
        privacy=privacy,
        formation=formation,
        moderation=moderation,
        guard=OutputGuard(),
        safety=safety,
        cycles=cycles,
        clock=clock,
    )
    try:
        yield type(
            "SyntheticEnvironment",
            (),
            dict(
                clock=clock,
                privacy_store=privacy_store,
                privacy=privacy,
                answers=answers,
                moderation=moderation,
                formation=formation,
                safety=safety,
                cycles=cycles,
                cycle=cycle,
                repository=repository,
                chat=chat,
                actors=actors,
                tokens=tokens,
                room_id=room_id,
                transport=transport,
            ),
        )()
    finally:
        repository.close()
        privacy_store.close()


def test_anonymous_room_and_real_ports_send_idempotently():
    with setup() as env:
        actor = env.actors[0]
        room = env.chat.room(actor, env.cycle.cycleId, token=env.tokens[0])
        assert sum(m["isSelf"] for m in room["members"]) == 1
        assert "playerId" not in json.dumps(room)
        first = asyncio.run(
            env.chat.send(
                actor, env.room_id, "Hello constellation", "message-1", token=env.tokens[0]
            )
        )
        second = asyncio.run(
            env.chat.send(
                actor, env.room_id, "Hello constellation", "message-1", token=env.tokens[0]
            )
        )
        assert first == second
        assert len(env.chat.messages(env.actors[1], env.room_id)) == 1
        with pytest.raises(ServiceError) as error:
            asyncio.run(env.chat.send(actor, env.room_id, "Different text", "message-1"))
        assert error.value.code == "IDEMPOTENCY_CONFLICT"
        assert len(env.transport.calls) == 4  # 3 answer screens + 1 actual chat screen


@pytest.mark.parametrize(
    "text",
    [
        "call me at 555-0100",
        "Synthetic private weekly detail number 1",
        "SYNTHETIC SAFETY TEST: I don't see the point of anything anymore",
    ],
)
def test_real_guard_and_m1_rejection_never_persist_or_stream(text):
    with setup() as env:
        with pytest.raises(ServiceError) as error:
            asyncio.run(env.chat.send(env.actors[0], env.room_id, text, "bad-message"))
        assert error.value.code == "MESSAGE_REJECTED"
        assert env.chat.messages(env.actors[1], env.room_id) == []
        assert not any(e["type"] == "chat.message" for e in env.chat.events(env.actors[1]))


def test_outsider_cannot_read_post_resolve_or_receive_events():
    with setup() as env:
        outsider = env.actors[3]
        with pytest.raises(ServiceError) as error:
            env.chat.messages(outsider, env.room_id)
        assert error.value.code == "NOT_FOUND"
        with pytest.raises(ServiceError):
            asyncio.run(env.chat.send(outsider, env.room_id, "hello", "outsider"))
        assert env.chat.resolve_handle(outsider, env.room_id, "Star 1") is None
        assert env.chat.events(outsider) == []


def test_reports_use_canonical_store_and_hide_for_reporter_then_everyone():
    with setup() as env:
        a, b, c = env.actors[:3]
        msg = asyncio.run(env.chat.send(a, env.room_id, "Synthetic hello", "hello"))
        env.chat.report(b, env.room_id, msg["handle"], msg["messageId"], "other", "report-b")
        assert env.chat.messages(b, env.room_id) == []
        assert len(env.chat.messages(c, env.room_id)) == 1
        env.chat.report(b, env.room_id, msg["handle"], msg["messageId"], "other", "report-b")
        assert env.moderation.distinct_reporters(env.room_id, msg["messageId"]) == 1
        env.chat.report(c, env.room_id, msg["handle"], msg["messageId"], "spam", "report-c")
        assert env.moderation.distinct_reporters(env.room_id, msg["messageId"]) == 2
        assert env.chat.messages(a, env.room_id) == []
        assert not any(e["type"] == "chat.message" for e in env.chat.events(a))


def test_pair_reveal_is_private_idempotent_and_cannot_authorize_third_party_contact():
    with setup() as env:
        a, b, c = env.actors[:3]
        assert env.chat.reveal(a, env.room_id, "Star 2", "a-asks") == {"result": "pending"}
        assert not any(e["type"] == "reveal.mutual" for e in env.chat.events(a))
        assert env.chat.reveal(b, env.room_id, "Star 1", "b-asks") == {"result": "revealed"}
        assert env.chat.reveal(b, env.room_id, "Star 1", "b-asks") == {"result": "revealed"}
        reveals = [e for e in env.chat.events(a) if e["type"] == "reveal.mutual"]
        assert len(reveals) == 1
        assert not any(e["type"] == "reveal.mutual" for e in env.chat.events(c))
        with pytest.raises(ServiceError) as error:
            asyncio.run(env.chat.send(a, env.room_id, "text me at 555-0100", "contact"))
        assert error.value.code == "MESSAGE_REJECTED"
        for player in reveals[0]["reveal"]["players"]:
            assert "Synthetic player" in player["displayName"]


def test_canonical_block_applies_immediately_on_read_and_replay():
    with setup() as env:
        a, b, c = env.actors[:3]
        asyncio.run(env.chat.send(a, env.room_id, "hello", "hello"))
        target = env.chat.resolve_handle(b, env.room_id, "Star 1")
        assert target == a.player_id
        env.moderation.block(b, target)
        assert env.chat.messages(b, env.room_id) == []
        assert len(env.chat.messages(c, env.room_id)) == 1
        assert not any(e["type"] == "chat.message" for e in env.chat.events(b))
        with pytest.raises(ServiceError):
            env.chat.reveal(a, env.room_id, "Star 2", "blocked-reveal")


@pytest.mark.parametrize("change", ["revoke", "logout", "delete"])
def test_current_privacy_state_rechecked_after_async_screen(change):
    async def scenario(env):
        started, resume = asyncio.Event(), asyncio.Event()
        original = env.chat.safety

        class PausedSafety:
            async def screen(self, text, subject_type):
                started.set()
                await resume.wait()
                return await original.screen(text, subject_type)

        env.chat.safety = PausedSafety()
        actor = env.actors[0]
        task = asyncio.create_task(
            env.chat.send(actor, env.room_id, "Synthetic hello", "inflight", token=env.tokens[0])
        )
        await started.wait()
        if change == "revoke":
            env.privacy.update_consent(
                actor,
                UpdateConsentRequest(
                    expectedVersion=1, matchAnswers=False, anonymousChat=True, isAdult=True
                ),
            )
        elif change == "logout":
            env.privacy.end_session(actor)
        else:
            env.answers.delete_my_data(actor.player_id)
        resume.set()
        with pytest.raises((ServiceError, PrivacyError)):
            await task
        assert env.chat.messages(env.actors[1], env.room_id) == []

    with setup() as env:
        asyncio.run(scenario(env))


def test_expiry_is_read_only_and_private_deletion_removes_replay_text():
    with setup() as env:
        a = env.actors[0]
        asyncio.run(env.chat.send(a, env.room_id, "Synthetic hello", "hello"))
        env.chat.forget_player(a.player_id)
        assert env.chat.messages(env.actors[1], env.room_id) == []
        assert not any(e["type"] == "chat.message" for e in env.chat.events(env.actors[1]))
        env.clock.now = policy.moment(env.cycle.chatExpiresAt)
        with pytest.raises(ServiceError) as error:
            asyncio.run(env.chat.send(env.actors[1], env.room_id, "Too late", "expired"))
        assert error.value.code == "ROOM_EXPIRED"
        assert env.chat.expire(env.cycle.cycleId) == 1
        env.clock.now = policy.moment(env.cycle.locksAt) + timedelta(days=14)
        env.chat.expire(env.cycle.cycleId)
        with env.repository.transaction() as state:
            assert state.chat.rooms
            assert state.chat.rooms[env.room_id].wire.status == "expired"
            # The runtime, not ChatService, owns the actual-lock retention deadline.


def test_post_system_uses_real_m1_guard_and_deduplicates():
    with setup() as env:
        payload = {
            "roomId": env.room_id,
            "handle": "Muse",
            "text": "Say a small hello",
            "kind": "system",
        }
        one = asyncio.run(env.chat.postSystem(env.room_id, payload))
        two = asyncio.run(env.chat.postSystem(env.room_id, payload))
        assert one == two and one["handle"] == "Muse"
        with pytest.raises(ServiceError):
            asyncio.run(env.chat.postSystem(env.room_id, {**payload, "text": "call 555-0100"}))


def test_http_uses_sessions_exact_shapes_and_no_private_input_echo():
    with setup() as env:
        dependency = actor_dependency(env.privacy)

        async def ready():
            return True

        privacy_routes = privacy_router(
            env.privacy, env.answers, env.moderation, env.chat.resolve_handle
        )
        app = create_app(
            settings=Settings(environment="test"),
            registrations=[
                ServiceRegistration("privacy", privacy_routes, dependency, ready),
                ServiceRegistration("chat", build_router(env.chat, dependency), dependency, ready),
            ],
        )
        install_privacy_error_handler(app)
        with TestClient(app) as client:
            path = f"/rooms/{env.room_id}/messages"
            assert client.get("/api/v1" + path).status_code == 401
            headers = {"Authorization": "Bearer " + env.tokens[0], "Idempotency-Key": "http-send"}
            response = client.post(
                "/api/v1" + path, headers=headers, json={"text": "Synthetic browser hello"}
            )
            assert response.status_code == 200
            assert response.json()["handle"] == "Star 1"
            response = client.post(
                "/api/v1" + path,
                headers={**headers, "Idempotency-Key": "forged"},
                json={"text": "hello", "playerId": "SYNTHETIC PRIVATE FORGED ID"},
            )
            assert response.status_code == 400
            assert "SYNTHETIC PRIVATE FORGED ID" not in response.text
            response = client.get("/api/v1" + path + "?after=-1", headers=headers)
            assert response.status_code == 400


def test_rejected_attempts_are_rate_limited_before_further_model_calls():
    with setup() as env:
        for index in range(6):
            with pytest.raises(ServiceError) as error:
                asyncio.run(env.chat.send(env.actors[0], env.room_id, "call 555-0100", str(index)))
            assert error.value.code == "MESSAGE_REJECTED"
        with pytest.raises(ServiceError) as error:
            asyncio.run(env.chat.send(env.actors[0], env.room_id, "hello", "seventh"))
        assert error.value.code == "RATE_LIMITED"
        assert len(env.transport.calls) == 9  # 3 setup answers + 6 bounded M1 screens
