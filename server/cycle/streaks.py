"""Streak computation (owner: Will). Pure functions, no I/O.

Rules (contracts/WORKFLOW.md, docs/roles/will.md):
- A streak counts consecutive question days (Mon-Fri) answered ON the day.
  Weekends are not question days, so they never break it.
- A catch-up answer never extends a streak. A caught-up day is neutral: it
  adds nothing and does not break the run (acceptance fixture: Mon and Tue on
  the day, Wed caught up -> current 2 after Wed ends).
- A day that ended with no answer at all resets current to 0.
- Today's question, while still open and unanswered, is pending: it neither
  counts nor breaks.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Literal

DayState = Literal["on_day", "catch_up", "missed", "pending"]


def compute_streak(days: Sequence[tuple[str, DayState]]) -> tuple[int, int, str | None]:
    """``days``: (IsoDate, state) for every released question day, oldest first.

    Returns (current, longest, lastOnDayDate).
    """
    run = 0
    longest = 0
    last_on_day: str | None = None
    for day_date, state in days:
        if state == "on_day":
            run += 1
            last_on_day = day_date
            longest = max(longest, run)
        elif state == "missed":
            run = 0
        # catch_up and pending leave the run unchanged
    return run, longest, last_on_day
