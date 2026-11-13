"""TEST ONLY driver: no real authentication, persistence, moderation or model.

The server imports none of this. These adapters model the privacy transaction
and cycle gates requested in PR #13; they are NOT an approved production port.
"""

import asyncio
import re
from copy import deepcopy
from datetime import UTC, datetime

from server.app.errors import ServiceError
from server.chat import policy
from server.chat.wire import Player
from server.orchestration.wire import Constellation, WeeklyCycle
from tests.orchestration.adapters import FIXTURES, cycle_wire, formation_wire


class SyntheticPrivacy:
    def __init__(self):
        self.pause = None
        self.started = asyncio.Event()
        self.calls = 0

    async def screen(self, text, subjectType):
        self.calls += 1
        self.started.set()
        if self.pause:
            await self.pause.wait()
        return "distress" if "SYNTHETIC SAFETY TEST" in text else "none"


class SyntheticGuard:
    def __init__(self):
        self.calls = 0
        self.unavailable = False

    def check(self, text, againstAnswers):
        self.calls += 1
        if self.unavailable:
            raise RuntimeError("SYNTHETIC PRIVATE GUARD FAILURE")
        reasons = []
        if re.search(r"[\w.+-]+@[\w.-]+\.\w+|\b\d{3}[- ]?\d{4}\b", text):
            reasons.append("contact_info")
        words = re.findall(r"\w+", text.lower())
        for answer in againstAnswers:
            private_words = re.findall(r"\w+", answer.lower())
            if any(
                words[i : i + 5] == private_words[j : j + 5]
                for i in range(len(words) - 4)
                for j in range(len(private_words) - 4)
            ):
                reasons.append("quote_5_words")
        return {"ok": not reasons, "reasons": reasons}


class Driver:
    def __init__(self):
        import json

        self.state = policy.ChatState()
        self.lock = asyncio.Lock()
        self.privacy = SyntheticPrivacy()
        self.guard = SyntheticGuard()
        self.revision = 1
        self.now = datetime(2026, 11, 15, 18, 0, 0, tzinfo=UTC)
        self.cycle = WeeklyCycle.model_validate({**cycle_wire(), "status": "revealed"})
        self.constellations = [
            Constellation.model_validate(c) for c in formation_wire()["constellations"]
        ]
        self.eligible = set(self.constellations[0].memberIds)
        self.profiles = {
            p: Player(
                playerId=p,
                displayName=f"{p} (Synthetic player)",
                avatarColor="#7c9cff",
                isSynthetic=True,
            )
            for p in self.eligible
        }
        fixture = json.loads((FIXTURES / "week-sample.json").read_text())
        self.answers = [a["text"] for a in fixture["answers"]]
        self.distress = fixture["distressFixture"]["text"]
        policy.open_rooms(self.state, self.cycle, self.constellations, self.eligible, [], self.now)
        self.room_id = next(iter(self.state.rooms))
        self.players = sorted(self.eligible)

    def room(self, actor):
        return policy.room_for(self.state, self.room_id, actor, self.eligible, self.now)

    def messages(self, actor, after=0):
        return policy.messages_for(self.state, self.room_id, actor, self.eligible, self.now, after)

    def events(self, actor, after=0):
        return policy.events_for(self.state, actor, self.eligible, self.now, after)

    async def post(self, actor, text, key="synthetic-key", kind="player"):
        route = f"/rooms/{self.room_id}/messages"
        async with self.lock:
            room = policy.member(self.state, self.room_id, actor, self.eligible)
            policy.writable(room, self.now)
            fingerprint, previous = policy.replay_command(
                self.state, actor, route, key, {"text": text, "kind": kind}
            )
            if previous is not None:
                current = room.messages.get(previous["messageId"])
                if current is None or not policy.visible(room, current, actor):
                    raise ServiceError("NOT_FOUND")
                return current.model_dump()
            policy.reserve_attempt(room, actor, self.now)
            revision, answers = self.revision, deepcopy(self.answers)
        # Provider call is deliberately outside the transaction/lock.
        await policy.moderate(self.privacy, self.guard, text, answers)
        async with self.lock:
            room = policy.member(self.state, self.room_id, actor, self.eligible)
            policy.writable(room, self.now)
            if self.revision != revision:
                raise ServiceError("STALE_REVISION")
            _, previous = policy.replay_command(
                self.state, actor, route, key, {"text": text, "kind": kind}
            )
            if previous is not None:
                return previous
            checked = self.guard.check(text, self.answers)
            if checked != {"ok": True, "reasons": []}:
                raise ServiceError("MESSAGE_REJECTED")
            return policy.commit_message(
                self.state, room, actor, text, self.now, key, fingerprint, kind=kind
            )

    async def report(self, actor, message, reason="other"):
        async with self.lock:
            room = policy.member(self.state, self.room_id, actor, self.eligible)
            policy.report(
                self.state, room, actor, message["handle"], message["messageId"], reason, self.now
            )

    async def reveal(self, actor, target):
        async with self.lock:
            # Model a transaction rollback if profile lookup/validation fails.
            original = deepcopy(self.state)
            try:
                room = policy.member(self.state, self.room_id, actor, self.eligible)
                if target not in self.eligible:
                    raise ServiceError("NOT_FOUND")
                return policy.request_reveal(
                    self.state, room, actor, room.members[target], self.profiles, self.now
                )
            except Exception:
                self.state = original
                raise

    def block(self, actor, target):
        room = policy.member(self.state, self.room_id, actor, self.eligible)
        policy.block_room(room, actor, target)
        # Represents the NOT YET DELIVERED canonical privacy block write, test-only.
        self.revision += 1
