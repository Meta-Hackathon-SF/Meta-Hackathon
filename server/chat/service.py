"""Chat transactions using the owners' real privacy and cycle service ports.

The repository is explicit: no fixture or process-local production fallback.
Every operation acquires cycle -> privacy publication guard -> workflow store.
M1 executes outside those locks and database transactions.
"""

import json
from collections.abc import Callable
from contextlib import contextmanager
from datetime import UTC, datetime
from hashlib import sha256

from server.app.errors import ServiceError
from server.chat import policy
from server.chat.wire import Player
from server.privacy import Actor


def effective_now(cycle, clock: Callable[[], datetime]) -> datetime:
    """Only an operator-owned demo cycle may project its server clock forward."""
    now = clock()
    if cycle.demoTiming and cycle.status in {"revealed", "closed"}:
        at = cycle.chatExpiresAt if cycle.status == "closed" else cycle.revealsAt
        now = max(now, policy.moment(at))
    return now


class ChatService:
    def __init__(
        self,
        *,
        repository,
        privacy,
        formation,
        moderation,
        guard,
        safety,
        cycles,
        clock: Callable[[], datetime] | None = None,
    ):
        self.repository = repository
        self.privacy = privacy
        self.formation = formation
        self.moderation = moderation
        self.guard = guard
        self.safety = safety
        self.cycles = cycles
        self.clock = clock or (lambda: datetime.now(UTC))

    def _actor(self, actor, token=None):
        if not isinstance(actor, Actor):
            raise ServiceError("UNAUTHENTICATED")
        if token is not None:
            refreshed = self.privacy.require_session(token)
            if (refreshed.player_id, refreshed.community_id) != (
                actor.player_id,
                actor.community_id,
            ):
                raise ServiceError("UNAUTHENTICATED")
            actor = refreshed
        self.privacy.require_consent(actor)
        return actor

    def _location(self, room_id):
        with self.repository.transaction() as state:
            room = state.chat.rooms.get(room_id)
            if room is None:
                raise ServiceError("NOT_FOUND")
            return room.wire.cycleId

    @contextmanager
    def _scope(self, cycle_id, actor=None, token=None, *, expected=None):
        if actor is not None:
            actor = self._actor(actor, token)
        gate = self.cycles.gate(cycle_id)
        if actor is not None and gate.cycle.communityId != actor.community_id:
            raise ServiceError("NOT_FOUND")
        revision = gate.revision if expected is None else expected
        with self.cycles.commit_guard(cycle_id, revision) as cycle:
            lease = self.formation.prepare_formation(cycle_id, cycle.communityId)
            with self.formation.publish_guard(cycle_id, lease.revision, lease.player_ids):
                if actor is not None:
                    actor = self._actor(actor, token)
                with self.repository.transaction() as state:
                    yield state, cycle, lease, actor

    def _room(self, state, room_id, actor, lease):
        room = policy.member(state.chat, room_id, actor.player_id, set(lease.player_ids))
        if room.wire.cycleId != lease.cycle_id:
            raise ServiceError("NOT_FOUND")
        self._refresh(room, lease.community_id)
        return room

    def _refresh(self, room, community_id):
        for first, second in self.moderation.blocked_pairs(community_id, set(room.members)):
            policy.block_room(room, first, second)
        for message_id, message in room.messages.items():
            if (
                message.moderation == "visible"
                and self.moderation.distinct_reporters(room.wire.roomId, message_id) >= 2
            ):
                room.messages[message_id] = message.model_copy(
                    update={"moderation": "hidden_pending"}
                )

    @staticmethod
    def _writable(room, cycle, now):
        if cycle.status == "closed":
            raise ServiceError("ROOM_EXPIRED")
        if cycle.status != "revealed":
            raise ServiceError("NOT_FOUND")
        policy.writable(room, now)

    @staticmethod
    def _answers(lease):
        return [row["text"] for row in lease.snapshot["answers"]]

    @staticmethod
    def _all_revealed(room, actor_id, eligible):
        # A room message reaches every eligible room member. One mutual pair
        # cannot authorize contact disclosure to a third unrevealed member.
        others = set(room.members) & set(eligible) - {actor_id}
        return bool(others) and all(frozenset({actor_id, p}) in room.reveals for p in others)

    def _check_text(self, text, answers, *, room, actor_id, eligible, kind):
        if kind == "player":
            result = self.guard.check_chat(
                text, answers, revealed=self._all_revealed(room, actor_id, eligible)
            )
        else:
            result = self.guard.check(text, answers)
        if not isinstance(result, dict) or result != {"ok": True, "reasons": []}:
            raise ServiceError("MESSAGE_REJECTED")

    def room(self, actor, cycle_id, *, token=None):
        with self._scope(cycle_id, actor, token) as (state, cycle, lease, current):
            if cycle.status not in {"revealed", "closed"}:
                raise ServiceError("NOT_FOUND")
            rooms = [
                room
                for room in state.chat.rooms.values()
                if room.wire.cycleId == cycle_id and current.player_id in room.members
            ]
            if len(rooms) != 1:
                raise ServiceError("NOT_FOUND")
            room = self._room(state, rooms[0].wire.roomId, current, lease)
            return policy.room_for(
                state.chat,
                room.wire.roomId,
                current.player_id,
                set(lease.player_ids),
                effective_now(cycle, self.clock),
            )

    def messages(self, actor, room_id, after=0, *, token=None):
        if type(after) is not int or after < 0:
            raise ServiceError("INVALID_INPUT")
        with self._scope(self._location(room_id), actor, token) as (state, cycle, lease, current):
            room = self._room(state, room_id, current, lease)
            hidden = self.moderation.reported_message_ids(current.player_id, room_id)
            active_handles = {
                handle for player, handle in room.members.items() if player in lease.player_ids
            }
            return [
                message
                for message in policy.messages_for(
                    state.chat,
                    room_id,
                    current.player_id,
                    set(lease.player_ids),
                    effective_now(cycle, self.clock),
                    after,
                )
                if message["messageId"] not in hidden
                and (message["kind"] != "player" or message["handle"] in active_handles)
            ]

    async def send(self, actor, room_id, text, key, *, token=None):
        return await self._post(actor, room_id, text, key, token=token, kind="player")

    async def _post(self, actor, room_id, text, key, *, token=None, kind):
        if not isinstance(text, str) or not text.strip() or not 1 <= len(text) <= 500:
            raise ServiceError("INVALID_INPUT")
        cycle_id = self._location(room_id)
        actor_id = actor.player_id if actor is not None else "__system__"
        route = f"/rooms/{room_id}/messages"
        body = {"text": text} if kind == "player" else {"text": text, "kind": kind}
        revision = self.cycles.gate(cycle_id).revision
        with self._scope(cycle_id, actor, token, expected=revision) as (
            state,
            cycle,
            lease,
            current,
        ):
            room = (
                self._room(state, room_id, current, lease)
                if current is not None
                else state.chat.rooms[room_id]
            )
            self._writable(room, cycle, effective_now(cycle, self.clock))
            fingerprint, previous = policy.replay_command(state.chat, actor_id, route, key, body)
            if previous is not None:
                message = room.messages.get(previous["messageId"])
                if (
                    message is None
                    or message.moderation != "visible"
                    or (current is not None and not policy.visible(room, message, actor_id))
                ):
                    raise ServiceError("NOT_FOUND")
                return message.model_dump()
            policy.reserve_attempt(room, actor_id, effective_now(cycle, self.clock))
            privacy_revision = lease.revision
        # Safety precedes the publication guard so distress still receives the
        # private support cue when the same message also contains contact info.
        try:
            flag = await self.safety.screen(text, "chat_message")
            if flag not in {"none", "distress", "harm"}:
                raise ServiceError("PROVIDER_UNAVAILABLE")
            if flag != "none":
                raise ServiceError("MESSAGE_REJECTED", message_key="support_card")
        except ServiceError:
            raise
        except Exception as error:
            code = getattr(error, "code", "PROVIDER_UNAVAILABLE")
            raise ServiceError(
                code if code in {"PROVIDER_UNAVAILABLE", "RATE_LIMITED"} else "PROVIDER_UNAVAILABLE"
            ) from None
        with self._scope(cycle_id, actor, token, expected=revision) as (
            state,
            cycle,
            lease,
            current,
        ):
            if lease.revision != privacy_revision:
                raise ServiceError("STALE_REVISION")
            room = (
                self._room(state, room_id, current, lease)
                if current is not None
                else state.chat.rooms[room_id]
            )
            self._writable(room, cycle, effective_now(cycle, self.clock))
            _, previous = policy.replay_command(state.chat, actor_id, route, key, body)
            if previous is not None:
                return previous
            self._check_text(
                text,
                self._answers(lease),
                room=room,
                actor_id=actor_id,
                eligible=lease.player_ids,
                kind=kind,
            )
            return policy.commit_message(
                state.chat,
                room,
                actor_id,
                text,
                effective_now(cycle, self.clock),
                key,
                fingerprint,
                kind=kind,
            )

    async def postSystem(self, roomId, message):
        if (
            not isinstance(message, dict)
            or set(message) != {"roomId", "handle", "text", "kind"}
            or message["roomId"] != roomId
            or message["handle"] != "Muse"
            or message["kind"] not in {"system", "muse_nudge"}
        ):
            raise ServiceError("INVALID_INPUT")
        key = sha256(json.dumps(message, sort_keys=True).encode()).hexdigest()
        return await self._post(None, roomId, message["text"], key, kind=message["kind"])

    def report(self, actor, room_id, handle, message_id, reason, key, *, token=None):
        cycle_id = self._location(room_id)
        route = f"/rooms/{room_id}/reports"
        body = {"handle": handle, "messageId": message_id, "reason": reason}
        with self._scope(cycle_id, actor, token) as (state, cycle, lease, current):
            room = self._room(state, room_id, current, lease)
            self._writable(room, cycle, effective_now(cycle, self.clock))
            fingerprint, previous = policy.replay_command(
                state.chat, current.player_id, route, key, body
            )
            if previous is not None:
                return
            # Validate ownership/message lineage before the privacy store write.
            policy.report(
                state.chat,
                room,
                current.player_id,
                handle,
                message_id,
                reason,
                effective_now(cycle, self.clock),
            )
            self.moderation.report(current, room_id, message_id, handle, reason)
            self._refresh(room, lease.community_id)
            state.chat.idempotency[(current.player_id, route, key)] = (fingerprint, {"ok": True})

    def reveal(self, actor, room_id, to_handle, key, *, token=None):
        route = f"/rooms/{room_id}/reveal"
        with self._scope(self._location(room_id), actor, token) as (state, cycle, lease, current):
            room = self._room(state, room_id, current, lease)
            self._writable(room, cycle, effective_now(cycle, self.clock))
            target = next((p for p, handle in room.members.items() if handle == to_handle), None)
            if target not in lease.player_ids:
                raise ServiceError("NOT_FOUND")
            fingerprint, _ = policy.replay_command(
                state.chat, current.player_id, route, key, {"toHandle": to_handle}
            )
            own = self.privacy.session_view(current).player.wire()
            profiles = state.records.setdefault("chatProfiles", {})
            profiles[current.player_id] = Player.model_validate(own).model_dump()
            result = policy.request_reveal(
                state.chat,
                room,
                current.player_id,
                to_handle,
                {pid: Player.model_validate(value) for pid, value in profiles.items()},
                effective_now(cycle, self.clock),
            )
            state.chat.idempotency[(current.player_id, route, key)] = (fingerprint, result)
            return result

    def resolve_handle(self, actor, room_id, handle):
        try:
            with self._scope(self._location(room_id), actor) as (state, _cycle, lease, current):
                room = self._room(state, room_id, current, lease)
                return next(
                    (p for p, h in room.members.items() if h == handle and p in lease.player_ids),
                    None,
                )
        except Exception:
            # Privacy's /me/blocks must not enumerate rooms, sessions or handles.
            return None

    def events(self, actor, after=0, *, token=None):
        current = self._actor(actor, token)
        with self.repository.transaction() as state:
            cycle_ids = {
                room.wire.cycleId
                for room in state.chat.rooms.values()
                if current.player_id in room.members
            }
        results = {}
        for cycle_id in cycle_ids:
            with self._scope(cycle_id, current, token) as (state, cycle, lease, verified):
                scoped_seqs = set()
                hidden = set()
                for room in state.chat.rooms.values():
                    if room.wire.cycleId != cycle_id or verified.player_id not in room.members:
                        continue
                    self._refresh(room, lease.community_id)
                    hidden |= self.moderation.reported_message_ids(
                        verified.player_id, room.wire.roomId
                    )
                    scoped_seqs |= {
                        d.event["seq"]
                        for d in state.chat.deliveries
                        if d.room_id == room.wire.roomId
                    }
                for event in policy.events_for(
                    state.chat,
                    verified.player_id,
                    set(lease.player_ids),
                    effective_now(cycle, self.clock),
                    after,
                ):
                    if event["seq"] not in scoped_seqs:
                        continue
                    if event["type"] == "chat.message":
                        if event["message"]["messageId"] in hidden:
                            continue
                        if event["message"]["kind"] == "player":
                            room = state.chat.rooms[event["message"]["roomId"]]
                            author = next(
                                (
                                    p
                                    for p, h in room.members.items()
                                    if h == event["message"]["handle"]
                                ),
                                None,
                            )
                            if author not in lease.player_ids:
                                continue
                    results[event["seq"]] = event
        return [results[seq] for seq in sorted(results)]

    def expire(self, cycle_id):
        with self._scope(cycle_id) as (state, cycle, _lease, _actor):
            count = policy.expire(state.chat, cycle_id, effective_now(cycle, self.clock))
            # Full data retention follows the runtime's first actual lock time;
            # it must not run again against this cycle's scheduled calendar time.
            retained = {p for room in state.chat.rooms.values() for p in room.members}
            profiles = state.records.get("chatProfiles", {})
            state.records["chatProfiles"] = {
                p: value for p, value in profiles.items() if p in retained
            }
            return count

    def forget_player(self, player_id, cycle_id=None):
        """Delete author links/text after the approved privacy deletion notice."""
        with self.repository.transaction() as state:
            state.records.get("chatProfiles", {}).pop(player_id, None)
            removed_messages = set()
            affected_rooms = set()
            for room in state.chat.rooms.values():
                if player_id not in room.members or (cycle_id and room.wire.cycleId != cycle_id):
                    continue
                affected_rooms.add(room.wire.roomId)
                handle = room.members.pop(player_id)
                room.wire = room.wire.model_copy(
                    update={"members": [m for m in room.wire.members if m.handle != handle]}
                )
                for message_id, message in list(room.messages.items()):
                    if message.handle == handle:
                        removed_messages.add(message_id)
                        del room.messages[message_id]
                        room.message_seqs.pop(message_id, None)
                room.blocked = {pair for pair in room.blocked if player_id not in pair}
                room.attempts.pop(player_id, None)
                room.reports = [
                    r
                    for r in room.reports
                    if r.reporterId != player_id
                    and r.reportedHandle != handle
                    and r.messageId not in removed_messages
                ]
                room.requests = {pair for pair in room.requests if player_id not in pair}
                room.reveals = {
                    pair: reveal for pair, reveal in room.reveals.items() if player_id not in pair
                }
            state.chat.deliveries = [
                d
                for d in state.chat.deliveries
                if not (
                    d.room_id in affected_rooms
                    and d.event["type"] == "reveal.mutual"
                    and any(p["playerId"] == player_id for p in d.event["reveal"]["players"])
                )
                and not (
                    d.event["type"] == "chat.message"
                    and d.event["message"]["messageId"] in removed_messages
                )
            ]
            state.chat.idempotency = {
                key: value
                for key, value in state.chat.idempotency.items()
                if key[0] != player_id and value[1].get("messageId") not in removed_messages
            }
