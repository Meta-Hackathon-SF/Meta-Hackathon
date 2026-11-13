"""formationSnapshot + publish guard (role task 6), per Kai's CHANGE on #13.

    lease = privacy_formation.prepare_formation(cycleId, communityId)
    result = await FormationService(muse, LeasedSnapshot(lease), guard).form(cycleId)   # Rishi
    with privacy_formation.publish_guard(cycleId, lease.revision, playerIds):  # Kai's signature
        kai_short_commit()          # sync, no model call or await inside

* ``lease.snapshot`` is exactly the contract ``PrivacyPort.formationSnapshot``
  shape ``{answers, idMap, blockedPairs}``: one random ref per player per lease
  (shared by that player's answers), the server weight per answer, ``idMap``
  ref -> playerId, ``blockedPairs`` as [blockerId, blockedId] player ids among
  the snapshot's players. Only unflagged answers of currently fully consenting,
  active, non-deleted members are included. Synthetic players are included and
  stay labeled through ``is_synthetic`` in privacy; refs carry no identity.
* ``lease.revision`` is opaque and server-only (never a wire field). It changes
  when any consent, membership, eligible answer, edit, flag or block that the
  snapshot depends on changes.
* ``publish_guard`` holds privacy's write lock for the whole ``with`` body, so
  no consent change, answer write/delete or block can interleave between the
  check and Kai's commit. It raises ``STALE_REVISION`` if anything moved or a
  published player is not in the snapshot. Lock order: cycle guard -> privacy
  guard -> Kai commit. Single process only; this is not a distributed
  transaction across Kai's and privacy's stores.
"""

from __future__ import annotations

import hashlib
import json
import secrets
from collections.abc import Iterable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

from . import errors
from .answers import AnswerStore
from .moderation import ModerationStore
from .store import PrivacyStore


@dataclass(frozen=True)
class FormationLease:
    cycle_id: str
    community_id: str
    snapshot: Mapping[str, Any]   # exact contract shape; treat as read-only
    revision: str                 # opaque, server-only
    player_ids: frozenset[str]


class LeasedSnapshot:
    """Rishi's ``SnapshotSource`` for one prepared lease."""

    def __init__(self, lease: FormationLease):
        self._lease = lease

    async def formation_snapshot(self, cycle_id: str) -> Mapping[str, Any]:
        if cycle_id != self._lease.cycle_id:
            raise errors.forbidden()
        return json.loads(json.dumps(self._lease.snapshot))  # caller gets its own copy


class PrivacyFormation:
    def __init__(self, store: PrivacyStore, answers: AnswerStore, moderation: ModerationStore):
        self._store = store
        self._answers = answers
        self._moderation = moderation

    def _state(self, cycle_id: str, community_id: str) -> tuple[list, list[list[str]], str]:
        rows = self._answers.eligible_answers(cycle_id, community_id)
        players = {r["player_id"] for r in rows}
        pairs = self._moderation.blocked_pairs(community_id, players)
        digest = hashlib.sha256(json.dumps({
            "answers": [[r["player_id"], r["answer_id"], r["day"], r["weight"], r["edited_at"], r["consent_version"]]
                        for r in rows],
            "blocks": pairs,
        }, sort_keys=True).encode()).hexdigest()
        return rows, pairs, f"{community_id}|{digest}"  # opaque to callers

    def prepare_formation(self, cycle_id: str, community_id: str) -> FormationLease:
        with self._store.tx():
            rows, pairs, revision = self._state(cycle_id, community_id)
        players = sorted({r["player_id"] for r in rows})
        refs = {p: "r" + secrets.token_hex(4) for p in players}
        while len(set(refs.values())) != len(refs):  # astronomically rare collision
            refs = {p: "r" + secrets.token_hex(4) for p in players}
        snapshot = {
            "answers": [{"id": refs[r["player_id"]], "text": r["text"], "weight": r["weight"]} for r in rows],
            "idMap": {ref: player for player, ref in refs.items()},
            "blockedPairs": pairs,
        }
        return FormationLease(cycle_id, community_id, snapshot, revision, frozenset(players))

    @contextmanager
    def publish_guard(self, cycle_id: str, revision: str, player_ids: Iterable[str]) -> Iterator[None]:
        wanted = set(player_ids)
        community_id, sep, _ = revision.partition("|") if isinstance(revision, str) else ("", "", "")
        if not sep or not community_id:
            raise errors.stale()
        with self._store.tx():
            rows, _, current = self._state(cycle_id, community_id)
            if current != revision or not wanted <= {r["player_id"] for r in rows}:
                raise errors.stale()
            yield
