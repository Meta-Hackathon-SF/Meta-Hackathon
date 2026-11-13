"""Offline mechanics only; synthetic guards do not certify Patrik's moderation."""

import asyncio
from datetime import timedelta

import pytest

from server.app.errors import ServiceError
from server.chat import policy
from server.orchestration.stream import encode_sse, parse_last_event_id

from .adapters import Driver


def test_room_is_anonymous_self_projection_and_open_is_idempotent():
    d = Driver()
    before = len(d.state.deliveries)
    policy.open_rooms(d.state, d.cycle, d.constellations, d.eligible, [], d.now)
    assert len(d.state.rooms) == 1 and len(d.state.deliveries) == before
    for actor in d.players:
        room = d.room(actor)
        assert sum(m["isSelf"] for m in room["members"]) == 1
        assert "playerId" not in str(room) and "displayName" not in str(room)
        assert "sharedMeaning" not in str(room)
    with pytest.raises(ServiceError) as error:
        d.room("synthetic-outsider")
    assert error.value.code == "NOT_FOUND"


def test_every_chat_kind_uses_m1_and_guard_and_publication_hides_private_fields():
    async def scenario():
        d = Driver()
        for kind in ["player", "system", "muse_nudge"]:
            message = await d.post(d.players[0], "Hello constellation", key=kind, kind=kind)
            assert set(message) == {
                "messageId",
                "roomId",
                "handle",
                "text",
                "createdAt",
                "moderation",
                "kind",
            }
        assert d.privacy.calls == 3 and d.guard.calls == 6
        assert len(d.messages(d.players[1])) == 3

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "text", ["text me at 555-0100", "synthetic@example.invalid", "quote", "distress"]
)
def test_rejected_or_flagged_text_never_reaches_messages_outbox_or_idempotency(text):
    async def scenario():
        d = Driver()
        value = d.answers[0] if text == "quote" else d.distress if text == "distress" else text
        with pytest.raises(ServiceError) as error:
            await d.post(d.players[0], value)
        assert error.value.code == "MESSAGE_REJECTED"
        assert d.messages(d.players[0]) == []
        assert not d.state.idempotency
        assert not any(e["type"] == "chat.message" for e in d.events(d.players[0]))

    asyncio.run(scenario())


def test_guard_outage_fails_closed_without_provider_error_text():
    async def scenario():
        d = Driver()
        d.guard.unavailable = True
        with pytest.raises(ServiceError) as error:
            await d.post(d.players[0], "hello")
        assert str(error.value) == "PROVIDER_UNAVAILABLE"
        assert d.messages(d.players[0]) == []

    asyncio.run(scenario())


def test_duplicate_concurrent_messages_replay_once_and_conflicting_key_is_rejected():
    async def scenario():
        d = Driver()
        values = await asyncio.gather(*(d.post(d.players[0], "hello") for _ in range(4)))
        assert len({v["messageId"] for v in values}) == 1
        assert len(d.messages(d.players[1])) == 1
        with pytest.raises(ServiceError) as error:
            await d.post(d.players[0], "changed body")
        assert error.value.code == "IDEMPOTENCY_CONFLICT"

    asyncio.run(scenario())


def test_revocation_during_screening_prevents_commit_and_replay():
    async def scenario():
        d = Driver()
        d.privacy.pause = asyncio.Event()
        actor = d.players[0]
        task = asyncio.create_task(d.post(actor, "hello"))
        await d.privacy.started.wait()
        d.eligible.remove(actor)
        d.revision += 1
        d.privacy.pause.set()
        with pytest.raises(ServiceError):
            await task
        assert d.events(actor) == []
        assert d.messages(d.players[1]) == []

    asyncio.run(scenario())


def test_answer_change_during_screening_drops_stale_result():
    async def scenario():
        d = Driver()
        d.privacy.pause = asyncio.Event()
        task = asyncio.create_task(d.post(d.players[0], "hello"))
        await d.privacy.started.wait()
        d.revision += 1
        d.privacy.pause.set()
        with pytest.raises(ServiceError) as error:
            await task
        assert error.value.code == "STALE_REVISION"
        assert d.messages(d.players[1]) == []

    asyncio.run(scenario())


def test_rate_limit_is_per_actor_and_counts_rejected_attempts():
    async def scenario():
        d = Driver()
        for i in range(6):
            with pytest.raises(ServiceError):
                await d.post(d.players[0], "555-0100", str(i))
        with pytest.raises(ServiceError) as error:
            await d.post(d.players[0], "hello", "seventh")
        assert error.value.code == "RATE_LIMITED"
        assert (await d.post(d.players[1], "hello"))["text"] == "hello"
        d.now += timedelta(seconds=60)
        assert (await d.post(d.players[0], "hello", "after-window"))["text"] == "hello"

    asyncio.run(scenario())


def test_report_hides_immediately_and_two_distinct_reporters_auto_hide():
    async def scenario():
        d = Driver()
        a, b, c = d.players
        message = await d.post(a, "hello")
        await d.report(b, message)
        await d.report(b, message)
        assert d.messages(b) == [] and len(d.messages(c)) == 1
        assert not any(e["type"] == "chat.message" for e in d.events(b))
        await d.report(c, message)
        assert d.messages(a) == []
        room = d.state.rooms[d.room_id]
        assert len(room.reports) == 2
        assert room.messages[message["messageId"]].moderation == "hidden_pending"

    asyncio.run(scenario())


def test_block_hides_messages_and_mutual_identity_events_for_blocker():
    async def scenario():
        d = Driver()
        a, b, c = d.players
        await d.post(a, "hello")
        await d.reveal(a, b)
        await d.reveal(b, a)
        d.block(b, a)
        assert d.messages(b) == [] and len(d.messages(c)) == 1
        assert not any(e["type"] in {"chat.message", "reveal.mutual"} for e in d.events(b))
        with pytest.raises(ServiceError):
            await d.reveal(a, b)

    asyncio.run(scenario())


def test_one_sided_reveal_never_discloses_identity_duplicate_pair_emits_once():
    async def scenario():
        d = Driver()
        a, b, c = d.players
        assert await d.reveal(a, b) == {"result": "pending"}
        assert await d.reveal(a, b) == {"result": "pending"}
        assert not any(e["type"] == "reveal.mutual" for e in d.events(a))
        assert not any(e["type"] == "reveal.mutual" for e in d.events(b))
        results = await asyncio.gather(d.reveal(b, a), d.reveal(b, a), d.reveal(a, b))
        assert all(v == {"result": "revealed"} for v in results)
        assert len([e for e in d.events(a) if e["type"] == "reveal.mutual"]) == 1
        assert not any(e["type"] == "reveal.mutual" for e in d.events(c))
        pair = next(e for e in d.events(a) if e["type"] == "reveal.mutual")
        assert all(p["isSynthetic"] for p in pair["reveal"]["players"])

    asyncio.run(scenario())


def test_expiry_exact_boundary_read_only_pending_reveals_die_and_ttl_removes_all_text():
    async def scenario():
        d = Driver()
        a, b, _ = d.players
        await d.post(a, "hello")
        await d.reveal(a, b)
        d.now = policy.moment(d.cycle.chatExpiresAt)
        assert d.room(a)["status"] == "expired"
        assert len(d.messages(a)) == 1
        with pytest.raises(ServiceError) as error:
            await d.post(a, "after expiry", "expired")
        assert error.value.code == "ROOM_EXPIRED"
        with pytest.raises(ServiceError):
            await d.reveal(b, a)
        assert policy.expire(d.state, d.cycle.cycleId, d.now) == 1
        assert policy.expire(d.state, d.cycle.cycleId, d.now) == 0
        assert not d.state.rooms[d.room_id].requests
        d.now = policy.moment(d.cycle.locksAt) + timedelta(days=14)
        assert policy.delete_at_ttl(d.state, d.cycle, d.now) == 1
        assert not d.state.rooms and not d.state.idempotency and not d.state.deliveries

    asyncio.run(scenario())


def test_sse_reconnect_by_seq_nonmember_filtering_and_no_payload_line_injection():
    async def scenario():
        d = Driver()
        a, b, _ = d.players
        await d.post(a, "hello\nevent: forged", "first")
        first = d.events(b)[-1]
        await d.post(a, "another hello", "second")
        replayed = d.events(b, first["seq"])
        assert len(replayed) == 1
        assert replayed[0]["message"]["text"] == "another hello"
        assert d.events("synthetic-outsider") == []
        assert (
            len([line for line in encode_sse(first).splitlines() if line.startswith("event:")]) == 1
        )
        assert parse_last_event_id(str(first["seq"])) == first["seq"]
        d.eligible.remove(b)
        assert d.events(b) == []

    asyncio.run(scenario())


@pytest.mark.parametrize("value", ["-1", "1.0", "1\nevent: injected", "9" * 20, "??", ""])
def test_invalid_last_event_id(value):
    with pytest.raises(ServiceError):
        parse_last_event_id(value)


def test_mismatched_profile_mapping_cannot_reveal_someone_else():
    async def scenario():
        d = Driver()
        a, b, c = d.players
        await d.reveal(a, b)
        d.profiles[b] = d.profiles[c]
        with pytest.raises(ServiceError):
            await d.reveal(b, a)
        assert not any(e["type"] == "reveal.mutual" for e in d.events(a))

    asyncio.run(scenario())


def test_identity_filter_defends_against_corrupt_persisted_recipient_list():
    from dataclasses import replace

    async def scenario():
        d = Driver()
        a, b, c = d.players
        await d.reveal(a, b)
        await d.reveal(b, a)
        d.state.deliveries = [
            replace(item, recipients=frozenset(d.players))
            if item.event["type"] == "reveal.mutual"
            else item
            for item in d.state.deliveries
        ]
        assert not any(e["type"] == "reveal.mutual" for e in d.events(c))
        assert any(e["type"] == "reveal.mutual" for e in d.events(a))

    asyncio.run(scenario())


def test_outbox_rejects_identity_publication_to_the_whole_room():
    async def scenario():
        d = Driver()
        a, b, _ = d.players
        await d.reveal(a, b)
        await d.reveal(b, a)
        event = next(e for e in d.events(a) if e["type"] == "reveal.mutual")
        with pytest.raises(ServiceError) as error:
            d.state.emit({k: v for k, v in event.items() if k != "seq"}, set(d.players), d.room_id)
        assert error.value.code == "FORBIDDEN"

    asyncio.run(scenario())
