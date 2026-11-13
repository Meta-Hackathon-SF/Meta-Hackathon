"""formationSnapshot + publish guard (role task 6), per Kai's CHANGE on #13.

    lease = privacy_formation.prepare_formation(cycleId, communityId)
    result = await FormationService(muse, LeasedSnapshot(lease), guard).form(cycleId)   # Rishi
    with privacy_formation.publish_guard(cycleId, lease.revision, playerIds):  # Kai's signature
        kai_short_commit()          # sync, no model call or await inside

* ``lease.snapshot`` is the contract ``PrivacyPort.formationSnapshot`` shape
  ``{answers, idMap, blockedPairs}``: one random ref per player per lease
  (shared by that player's answers), the server weight per answer and, per
  D014 (contract 2.2.0, signed off by Patrik), the answer's stored
  ``questionId`` (``AnswerText``, only when that question's text is in the
  snapshot, so every id resolves), plus a top-level
  ``questions: [{questionId, text}]`` when a ``question_texts`` source is
  injected (the texts live in the cycle/planning services, not here), ``idMap``
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
from collections.abc import Callable, Iterable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

from . import errors
from .activity import ActivityStore
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


QUESTION_TEXT_MAX = 140  # protocol.ts Question.text bound

# (cycleId, communityId) -> {questionId: text} for that cycle's released
# questions. Must read stored DailyQuestions; never select or generate new ones.
QuestionTexts = Callable[[str, str], Mapping[str, str]]


class PrivacyFormation:
    def __init__(self, store: PrivacyStore, answers: AnswerStore, moderation: ModerationStore,
                 activity: ActivityStore | None = None, *, question_texts: QuestionTexts | None = None):
        self._store = store
        self._answers = answers
        self._moderation = moderation
        self._activity = activity  # D010: optional; absent -> snapshot has no activity
        self._question_texts = question_texts  # D014: optional; absent -> no top-level questions

    def _state(self, cycle_id: str, community_id: str) -> tuple[list, list[list[str]], str, dict]:
        rows = self._answers.eligible_answers(cycle_id, community_id)
        players = {r["player_id"] for r in rows}
        pairs = self._moderation.blocked_pairs(community_id, players)
        signals = self._activity.for_players(community_id, players) if self._activity else {}
        digest = hashlib.sha256(json.dumps({
            "answers": [[r["player_id"], r["answer_id"], r["day"], r["question_id"], r["weight"], r["edited_at"],
                         r["consent_version"]] for r in rows],
            "blocks": pairs,
            "activity": {p: s.wire() for p, s in sorted(signals.items())},
        }, sort_keys=True).encode()).hexdigest()
        return rows, pairs, f"{community_id}|{digest}", dict(signals)  # revision is opaque to callers

    def prepare_formation(self, cycle_id: str, community_id: str) -> FormationLease:
        with self._store.tx():
            rows, pairs, revision, signals = self._state(cycle_id, community_id)
        players = sorted({r["player_id"] for r in rows})
        refs = {p: "r" + secrets.token_hex(4) for p in players}
        while len(set(refs.values())) != len(refs):  # astronomically rare collision
            refs = {p: "r" + secrets.token_hex(4) for p in players}
        questions: list[dict[str, str]] | None = None
        if self._question_texts is not None:
            questions = self._questions(cycle_id, community_id, {r["question_id"] for r in rows})
        # An answer carries its questionId only when that question's text is in
        # the snapshot, so every questionId resolves (Rishi's validator, #62).
        listed = {q["questionId"] for q in questions or []}
        snapshot: dict[str, Any] = {
            "answers": [{"id": refs[r["player_id"]], "text": r["text"], "weight": r["weight"],
                         **({"questionId": r["question_id"]} if r["question_id"] in listed else {})}
                        for r in rows],
            "idMap": {ref: player for player, ref in refs.items()},
            "blockedPairs": pairs,
        }
        if questions is not None:
            snapshot["questions"] = questions
        if signals:  # D010: keyed by the same random refs; omitted entirely when nobody opted in
            snapshot["activity"] = {refs[p]: s.wire() for p, s in signals.items() if p in refs}
        return FormationLease(cycle_id, community_id, snapshot, revision, frozenset(players))

    def _questions(self, cycle_id: str, community_id: str, wanted: set[str]) -> list[dict[str, str]]:
        """Public question texts for the questionIds in this snapshot only.
        A source failure propagates (the formation job retries); it is never
        replaced by guessed texts."""
        texts = self._question_texts(cycle_id, community_id)  # type: ignore[misc]
        if not isinstance(texts, Mapping):
            raise TypeError("question_texts must return {questionId: text}")
        out = []
        for qid in sorted(wanted):
            text = texts.get(qid)
            if isinstance(text, str) and 0 < len(text) <= QUESTION_TEXT_MAX:
                out.append({"questionId": qid, "text": text})
        return out

    @contextmanager
    def publish_guard(self, cycle_id: str, revision: str, player_ids: Iterable[str]) -> Iterator[None]:
        wanted = set(player_ids)
        community_id, sep, _ = revision.partition("|") if isinstance(revision, str) else ("", "", "")
        if not sep or not community_id:
            raise errors.stale()
        with self._store.tx():
            rows, _, current, _ = self._state(cycle_id, community_id)
            if current != revision or not wanted <= {r["player_id"] for r in rows}:
                raise errors.stale()
            yield
