"""TEST ONLY v3 retention boundaries over synthetic chat data."""

import asyncio
from datetime import timedelta

import pytest

from server.chat import policy
from server.chat.lifetime import daily_expiry, purge_v3_chat_text
from tests.chat.adapters import Driver


@pytest.mark.parametrize("lock_offset,expected_offset", [(0, 8), (-7, 7)])
def test_chat_text_and_replay_copies_expire_at_earlier_deadline(lock_offset, expected_offset):
    driver = Driver()
    room = driver.state.rooms[driver.room_id]
    room.wire = room.wire.model_copy(
        update={
            "opensAt": policy.stamp(driver.now),
            "expiresAt": policy.stamp(daily_expiry(driver.now)),
        }
    )
    message = asyncio.run(driver.post(driver.players[0], "Synthetic hello", key="synthetic"))
    deadline = driver.now + timedelta(days=expected_offset)
    locked_at = driver.now + timedelta(days=lock_offset)
    assert (
        purge_v3_chat_text(
            driver.state, driver.cycle.cycleId, locked_at, deadline - timedelta(microseconds=1)
        )
        == 0
    )
    assert room.messages[message["messageId"]].text == "Synthetic hello"
    assert purge_v3_chat_text(driver.state, driver.cycle.cycleId, locked_at, deadline) == 1
    assert not room.messages and not room.message_seqs
    assert not any(delivery.event["type"] == "chat.message" for delivery in driver.state.deliveries)
    assert not driver.state.idempotency
    assert purge_v3_chat_text(driver.state, driver.cycle.cycleId, locked_at, deadline) == 1


def test_purge_does_not_affect_other_cycle():
    driver = Driver()
    message = asyncio.run(driver.post(driver.players[0], "Synthetic hello"))
    assert (
        purge_v3_chat_text(driver.state, "other-cycle", driver.now, driver.now + timedelta(days=30))
        == 0
    )
    assert message["messageId"] in driver.state.rooms[driver.room_id].messages
