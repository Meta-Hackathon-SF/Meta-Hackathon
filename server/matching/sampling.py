"""Bound the answers Muse sees so M3/M4 never exceed the provider input schema.

Adam's contract caps M3/M4 at MAX_MUSE_ANSWERS answers. Past that, formation used to fall back to
keyword grouping silently (audit #72). Instead: keep a deterministic, even per-player sample so
every player still appears, and record a reason code. Baseline and guards still use every answer.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import replace

from server.matching.models import FormationSnapshot

MAX_MUSE_ANSWERS = 400  # mirrors server/providers/contract.py MAX_ANSWERS
REASON_SAMPLED = "answers_sampled"


def sample_for_muse(
    snap: FormationSnapshot, limit: int = MAX_MUSE_ANSWERS
) -> tuple[FormationSnapshot, str | None]:
    """Return (snapshot of at most `limit` answers, reason or None); each ref keeps one."""
    if len(snap.answers) <= limit:
        return snap, None
    by_ref: dict[str, list] = defaultdict(list)
    for a in snap.answers:
        by_ref[a.id].append(a)
    per_player = max(1, limit // max(1, len(by_ref)))
    kept = []
    for ref in sorted(by_ref):
        kept.extend(
            sorted(by_ref[ref], key=lambda a: (a.text, getattr(a, "question_id", "") or ""))[
                :per_player
            ]
        )
    return replace(snap, answers=tuple(kept[:limit])), REASON_SAMPLED
