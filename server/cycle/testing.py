"""TEST-ONLY ADAPTERS. Not production. Not evidence of any teammate's port.

Stand-ins for interfaces owned by Patrik (answer store, M1 screen, synthetic
players) and Adam (QuestionPort, M2 clarify) so server/cycle can be developed
and tested offline against contracts/fixtures/. Nothing here calls a model.
Remove from live composition when the owning port lands.
"""

from __future__ import annotations

import json
from pathlib import Path

from .wire import DailyAnswer, PrevalenceGuess

FIXTURES = Path(__file__).resolve().parents[2] / "contracts" / "fixtures"
LABEL = "TEST-ONLY fixture adapter"


class FixtureAnswerStore:
    """TEST-ONLY in-memory stand-in for Patrik's private answer storage."""

    label = LABEL

    def __init__(self) -> None:
        self.answers: dict[tuple[str, str, int], DailyAnswer] = {}
        self.flags: dict[str, str] = {}
        self.guesses: dict[tuple[str, str], PrevalenceGuess] = {}

    def get(self, cycle_id, player_id, day):
        return self.answers.get((cycle_id, player_id, day))

    def list_for_player(self, cycle_id, player_id):
        return [a for (c, p, _), a in self.answers.items() if c == cycle_id and p == player_id]

    def save(self, answer, flag):
        self.answers[(answer.cycleId, answer.playerId, answer.day)] = answer
        self.flags[answer.answerId] = flag

    def delete(self, cycle_id, player_id, day, deleted_at):
        return self.answers.pop((cycle_id, player_id, day), None) is not None

    def save_guess(self, guess):
        self.guesses[(guess.cycleId, guess.playerId)] = guess

    def get_guess(self, cycle_id, player_id):
        return self.guesses.get((cycle_id, player_id))

    def purge_cycle(self, cycle_id):
        self.answers = {k: v for k, v in self.answers.items() if k[0] != cycle_id}
        self.guesses = {k: v for k, v in self.guesses.items() if k[0] != cycle_id}


class FixtureQuestionPort:
    """TEST-ONLY stand-in for Adam's QuestionPort.selectWeek, from week-sample.json."""

    label = LABEL

    def select_week(self, cycle_id, community_id):
        week = json.loads((FIXTURES / "week-sample.json").read_text(encoding="utf-8"))
        bank = json.loads((FIXTURES / "question-bank.json").read_text(encoding="utf-8"))
        by_id = {q["questionId"]: q for q in bank["questions"]}
        return [
            {"cycleId": cycle_id, "day": d["day"], "date": d["date"], "question": by_id[d["questionId"]]}
            for d in week["dailyQuestions"]
        ]


def fixture_screen(text, subject_type):
    """TEST-ONLY stand-in for Patrik's M1 screen: flags only the synthetic marker."""
    return "distress" if "SYNTHETIC SAFETY TEST" in text else "none"


def fixture_clarify(question, answer):
    """TEST-ONLY stand-in for Adam's M2 clarify. Short answers get one fixed follow-up."""
    if len(answer.split()) < 6:
        return {"needsFollowup": True, "question": "What made it feel that way this week?"}
    return {"needsFollowup": False, "question": ""}


class FixtureSeeder:
    """TEST-ONLY stand-in for Patrik's synthetic player creation."""

    label = LABEL

    def __init__(self) -> None:
        self.players: dict[str, dict] = {}

    def __call__(self, community_id, players):
        for player in players:
            self.players[player["playerId"]] = player
