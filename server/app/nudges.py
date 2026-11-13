"""Operator-only M7 composition over public owner ports and guarded workflow state.

No scheduler: this is the explicit operator button. Context is private and never
stored. Durable first-proposal wins plus chat's stable command key prevent two
concurrent model proposals from publishing two different nudges.
"""

from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
from typing import Literal

from pydantic import model_validator

from server.app.errors import ServiceError
from server.chat import policy
from server.chat.service import effective_now
from server.chat.wire import ChatMessage
from server.orchestration.wire import FormationSuccess, IsoTime, MuseCallEvidence, Text, Wire
from server.planning import ChatSystemPoster, NudgeService, VenueCatalog


class TimeWindow(Wire):
    start: IsoTime
    end: IsoTime

    @model_validator(mode="after")
    def ordered(self):
        if policy.moment(self.start) >= policy.moment(self.end):
            raise ValueError("invalid time window")
        return self


class EventNudge(Wire):
    nudgeId: Text
    constellationId: Text
    title: Text
    placeId: Text
    timeWindow: TimeWindow
    why: Text
    minAttendees: Literal[3]
    evidence: MuseCallEvidence

    @model_validator(mode="after")
    def m7(self):
        if self.evidence.callType != "M7" or type(self.minAttendees) is not int:
            raise ValueError("invalid nudge evidence")
        return self


class GuardedNudges:
    def __init__(self, runtime, chat, muse, token_source):
        self.runtime, self.chat, self.token_source = runtime, chat, token_source
        self.venues = VenueCatalog.load()
        self.version = ContextVar("nudge_formation_version", default=None)
        self.service = NudgeService(
            muse,
            runtime.guard,
            self.venues,
            self.context,
            ChatSystemPoster(self),
            store=self,
            now=runtime.clock,
        )

    def _actor(self, community=None):
        actor = self.runtime.privacy.require_session(self.token_source())
        self.runtime.privacy.require_consent(actor)
        self.runtime.privacy.require_operator(actor)
        if community is not None and actor.community_id != community:
            raise ServiceError("NOT_FOUND")
        return actor

    def _material(self, state, cycle, lease, room):
        self._actor(cycle.communityId)
        self.chat._writable(room, cycle, effective_now(cycle, self.runtime.clock))
        entry = state.records.get("formations", {}).get(cycle.cycleId)
        if entry is None or entry["privacyRevision"] != lease.revision:
            raise ServiceError("STALE_REVISION")
        version = (cycle.cycleId, entry["jobId"], entry["privacyRevision"])
        if self.version.get() is not None and self.version.get() != version:
            raise ServiceError("STALE_REVISION")
        self.version.set(version)
        matches = [
            c
            for c in FormationSuccess.model_validate(entry["result"]).constellations
            if c.constellationId == room.wire.constellationId
        ]
        if (
            len(matches) != 1
            or matches[0].cycleId != cycle.cycleId
            or entry["communityId"] != cycle.communityId
            or set(matches[0].memberIds) != set(room.members)
        ):
            raise ServiceError("PROVIDER_UNAVAILABLE")
        members = set(room.members)
        if not members <= lease.player_ids or len(members) < 3:  # D016: no maximum size
            raise ServiceError("NOT_FOUND")
        texts = [
            a["text"]
            for a in lease.snapshot["answers"]
            if lease.snapshot["idMap"][a["id"]] in members
        ]
        if not texts:
            raise ServiceError("PROVIDER_UNAVAILABLE")
        return {
            "constellationId": room.wire.constellationId,
            "roomId": room.wire.roomId,
            "sharedMeaning": matches[0].sharedMeaning,
            "memberCount": len(members),
            "roomOpen": True,
            "againstAnswers": texts,
        }

    @contextmanager
    def _scope(self, constellation_id=None, *, room_id=None):
        actor = self._actor()
        with self.runtime.repository.transaction() as state:
            rooms = [
                r
                for r in state.chat.rooms.values()
                if (
                    r.wire.roomId == room_id
                    if room_id is not None
                    else r.wire.constellationId == constellation_id
                )
            ]
            if len(rooms) != 1:
                raise ServiceError("NOT_FOUND")
            cycle_id, room_id = rooms[0].wire.cycleId, rooms[0].wire.roomId
        gate = self.runtime.cycles.gate(cycle_id)
        if gate.cycle.communityId != actor.community_id:
            raise ServiceError("NOT_FOUND")
        with self.runtime.cycles.commit_guard(cycle_id, gate.revision, "revealed") as cycle:
            lease = self.runtime.formation.prepare_formation(cycle_id, cycle.communityId)
            with self.runtime.formation.publish_guard(cycle_id, lease.revision, lease.player_ids):
                with self.runtime.repository.transaction() as state:
                    room = state.chat.rooms.get(room_id)
                    if room is None:
                        raise ServiceError("NOT_FOUND")
                    ctx = self._material(state, cycle, lease, room)
                    yield state, cycle, room, ctx

    async def room_constellation(self, room_id):
        try:
            with self._scope(room_id=room_id) as (_, _, _, ctx):
                return ctx["constellationId"]
        except ServiceError as error:
            if error.code == "NOT_FOUND":
                return None
            raise

    async def context(self, constellation_id):
        try:
            with self._scope(constellation_id) as (_, _, _, ctx):
                return ctx
        except ServiceError as error:
            if error.code == "NOT_FOUND":
                return None
            raise

    def _safe(self, value, ctx):
        nudge = EventNudge.model_validate(value).model_dump()
        if nudge["constellationId"] != ctx["constellationId"] or not self.venues.get(
            nudge["placeId"]
        ):
            raise ServiceError("PROVIDER_UNAVAILABLE")
        against = [*ctx["againstAnswers"], ctx["sharedMeaning"]]
        for text in (nudge["title"], nudge["why"], self.service.chat_text(nudge)):
            if self.runtime.guard.check(text, against) != {"ok": True, "reasons": []}:
                raise ServiceError("MESSAGE_REJECTED")
        return nudge

    def get(self, constellation_id):
        with self._scope(constellation_id) as (state, _, _, ctx):
            row = self._row(state, constellation_id)
            return None if row is None else self._safe(row["nudge"], ctx)

    def _row(self, state, constellation_id):
        row = state.records.get("nudges", {}).get(constellation_id)
        if row is not None and (
            row.get("cycleId") != self.version.get()[0]
            or row.get("formationVersion") != list(self.version.get())
        ):
            raise ServiceError("STALE_REVISION")
        return row

    def put(self, constellation_id, nudge):
        with self._scope(constellation_id) as (state, cycle, _, ctx):
            nudge = self._safe(nudge, ctx)
            rows = state.records.setdefault("nudges", {})
            row = self._row(state, constellation_id)
            if row is not None and row["nudge"] != nudge:
                raise ServiceError("STALE_REVISION")
            if row is None:
                rows[constellation_id] = {
                    "cycleId": cycle.cycleId,
                    "formationVersion": list(self.version.get()),
                    "nudge": nudge,
                }

    def posted(self, constellation_id):
        with self._scope(constellation_id) as (state, _, room, _):
            row = self._row(state, constellation_id)
            if row is None or "messageId" not in row:
                return None
            message = room.messages.get(row["messageId"])
            if message is None or message.moderation != "visible":
                raise ServiceError("NOT_FOUND")
            return message.model_dump()

    def mark_posted(self, constellation_id, message):
        message = ChatMessage.model_validate(message)
        with self._scope(constellation_id) as (state, _, room, _):
            if (
                message.roomId != room.wire.roomId
                or room.messages.get(message.messageId) != message
            ):
                raise ServiceError("PROVIDER_UNAVAILABLE")
            row = self._row(state, constellation_id)
            if row is None:
                raise ServiceError("NOT_FOUND")
            row["messageId"] = message.messageId

    async def postSystem(self, roomId, message):
        def validate(state, cycle, lease, room):
            ctx = self._material(state, cycle, lease, room)
            row = self._row(state, ctx["constellationId"])
            if row is None:
                raise ServiceError("NOT_FOUND")
            nudge = self._safe(row["nudge"], ctx)
            if message["text"] != self.service.chat_text(nudge):
                raise ServiceError("INVALID_INPUT")

        return await self.chat.postSystem(roomId, message, validate=validate)

    async def propose_and_post(self, constellation_id, *, request_id=None):
        token = self.version.set(None)
        try:
            result = await self.service.propose_and_post(constellation_id, request_id=request_id)
            with self._scope(constellation_id) as (_, _, _, ctx):
                self._safe(result["nudge"], ctx)
            return deepcopy(result)
        finally:
            self.version.reset(token)
