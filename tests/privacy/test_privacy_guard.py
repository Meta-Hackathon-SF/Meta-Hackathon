"""OutputGuard (role task 5): no-quote fuzz, 30-item sensitive red-team list,
PII and contact info, chat mode, and no false positives on the shared fixtures
and the curated question bank. Offline, deterministic, synthetic text only."""

from __future__ import annotations

import json
import random
import re
from pathlib import Path

import pytest

from server.privacy.guard import REASON_ORDER, OutputGuard

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "contracts" / "fixtures"
WEEK = json.loads((FIXTURES / "week-sample.json").read_text())
ANSWERS = [a["text"] for a in WEEK["answers"]] + [WEEK["distressFixture"]["text"], WEEK["injectionFixture"]["text"]]
guard = OutputGuard()


def reasons(text, against=ANSWERS):
    return guard.check(text, against)["reasons"]


def test_reasons_match_protocol_literals():
    proto = (ROOT / "contracts" / "protocol.ts").read_text()
    block = re.search(r"reasons:\s*\(([^)]*)\)\[\]", proto).group(1)
    assert set(re.findall(r'"([^"]+)"', block)) == set(REASON_ORDER)


def test_verdict_shape():
    assert guard.check("Night Owls", ANSWERS) == {"ok": True, "reasons": []}
    v = guard.check("text me at 555-0100 about therapy", ANSWERS)
    assert set(v) == {"ok", "reasons"} and v["ok"] is False
    assert v["reasons"] == ["sensitive_term", "contact_info"]  # stable order, no duplicates


# ------------------------------------------------------- no false positives
def _public_fixture_texts() -> list[str]:
    sky = json.loads((FIXTURES / "sky-stats.json").read_text())["sky"]
    chat = json.loads((FIXTURES / "chat-room.json").read_text())["messages"]
    texts = [t["label"] for t in sky["themes"]] + sky["headlines"] + [s["label"] for s in sky["syntheticSignals"]]
    return texts + [m["text"] for m in chat if m["moderation"] == "visible"]


def _bank_texts() -> list[str]:
    bank = json.loads((FIXTURES / "question-bank.json").read_text())
    items = bank["questions"] if isinstance(bank, dict) else bank
    out = [q["text"] for q in items]
    planning_bank = ROOT / "server" / "planning" / "data" / "question-bank.json"
    if planning_bank.exists():
        data = json.loads(planning_bank.read_text())
        out += [q["text"] for q in (data["questions"] if isinstance(data, dict) else data)]
    return out


BENIGN = [
    "Night Owls", "Quiet Corner Crew", "The Late Lunch Club", "Pickup Game Seekers", "Headphones-On Diners",
    "Quiet Corner Crew (Fallback grouping)", "Constellation 2 (Fallback grouping)", "Open mic Thursday 7-9pm",
    "Coffee at 3:30 for 2 hours", "4 of 7 people here eat alone more than they let on. They guessed 12%.",
    "Library study break, Wednesday 6-8pm", "Rec center pickup soccer at 5pm", "Homework and hot chocolate",
    "Feeling at home in a new place", "The Small Wins Five", "Snack runs between labs",
]


@pytest.mark.parametrize("text", BENIGN + _public_fixture_texts() + _bank_texts())
def test_benign_public_text_passes(text):
    assert guard.check(text, ANSWERS) == {"ok": True, "reasons": []}, text


# ------------------------------------------------------------ no-quote fuzz
def _windows(n):
    for answer in ANSWERS:
        tokens = answer.split()
        for i in range(len(tokens) - n + 1):
            yield " ".join(tokens[i:i + n])


def _perturb(text: str, rng: random.Random) -> str:
    out = []
    for w in text.split():
        choice = rng.randrange(5)
        w = w.upper() if choice == 0 else w.title() if choice == 1 else w
        if choice == 2:
            w = w + rng.choice([",", ".", "!", "...", ";"])
        if choice == 3:
            w = "​".join(w)  # zero-width spaces between letters
        out.append(w)
    sep = rng.choice([" ", "  ", " - ", "\n", " "])
    return rng.choice(["", "They said: ", "Name: "]) + sep.join(out) + rng.choice(["", " together", "?"])


def test_every_five_word_window_is_caught_even_when_disguised():
    rng = random.Random(20261113)
    windows = list(_windows(5))
    assert len(windows) > 40
    for w in windows:
        for _ in range(5):
            text = _perturb(w, rng)
            assert "quote_5_words" in reasons(text), text


def test_fullwidth_and_curly_quotes_normalized():
    assert "quote_5_words" in reasons("ＩＴ Transferring in feels like showing up")
    assert "quote_5_words" in reasons("Finding a pickup game that isn’t already a clique")


def test_three_word_windows_do_not_trigger():
    for w in _windows(3):
        assert "quote_5_words" not in reasons(w), w


def test_four_word_windows_trigger_only_for_short_answers():
    # Every fixture answer has <= 12 tokens, so a 4-word run of one is a quote
    # (safety eval: short answers are easy to quote near-whole).
    for w in _windows(4):
        assert "quote_5_words" in reasons(w), w
    long_answer = ["I usually grab a bagel and sit by the big window in the east library before class"]
    assert "quote_5_words" not in guard.check("sit by the big", long_answer)["reasons"]
    assert "quote_5_words" in guard.check("sit by the big window", long_answer)["reasons"]


def test_quote_against_empty_answers_never_triggers():
    assert guard.check("I eat in my room so no one sees me alone", [])["ok"] is True


# ------------------------------------------- 30-item sensitive red-team list
RED_TEAM = [
    "The Anxiety Allies", "Depressed Diners Club", "Late-Night Therapy Talkers", "Meds and Muffins",
    "ADHD Study Sprinters", "Panic Attack Survivors", "Eating Disorder Recovery Crew", "Sober Saturday Squad",
    "Queer Coffee Circle", "Trans Students Unite", "Coming Out Club", "Bisexual Book Nook",
    "Muslim Lunch Table", "Church Choir Kids", "Atheist Night Owls", "Bible Study Buddies",
    "Ramadan Night Walkers", "Broke Until Friday", "Student Loans Support", "Can't Afford Dinner Crew",
    "Financial Aid Waiting Room", "Homeless This Semester", "Divorced Parents Club", "Grieving Since Fall",
    "Foster Care Alumni", "Domestic Violence Survivors", "Estranged From Family", "Apartment 4B Neighbors",
    "Same Hometown Crew", "Dorm Room Regulars",
]


def test_red_team_list_has_thirty_items():
    assert len(RED_TEAM) == 30 and len(set(RED_TEAM)) == 30


@pytest.mark.parametrize("text", RED_TEAM)
def test_sensitive_red_team_blocked(text):
    assert guard.check(text, [])["ok"] is False, text


@pytest.mark.parametrize("text", ["THE ANXIETY ALLIES", "the​ anxiety club", "Thérapy? no: therapy!"])
def test_sensitive_matching_survives_case_and_invisible_chars(text):
    assert "sensitive_term" in reasons(text, [])


# --------------------------------------------------------- PII and contact
@pytest.mark.parametrize("text", [
    "Meet at 123 Main Street", "Room 214 tonight?", "apt 3B", "my SSN is 123-45-6789",
    "card 4111 1111 1111 1111", "student id 20261113", "dob is in march", "unit #12",
])
def test_pii_blocked(text):
    assert "pii" in reasons(text, [])


@pytest.mark.parametrize("text", [
    "text me at 555-0100", "call (765) 555-0123", "+1 765 555 0123", "maya.k@example.edu",
    "maya dot k at example dot com", "my insta is @maya.k", "snap: mayak22", "discord mayak#1234",
    "find me on www.example.com", "https://example.com/me", "example.io", "hmu later", "dm me",
])
def test_contact_info_blocked(text):
    assert "contact_info" in reasons(text, [])


# -------------------------------------------------------------- chat mode
def test_chat_allows_topics_but_not_quotes_or_pii():
    assert guard.check_chat("honestly my anxiety was bad this week", ANSWERS, revealed=False)["ok"] is True
    assert guard.check_chat("Everyone seems to already have their people, right?", ANSWERS,
                            revealed=False)["reasons"] == ["quote_5_words"]
    assert guard.check_chat("I'm in room 214", ANSWERS, revealed=True)["reasons"] == ["pii"]


def test_chat_contact_info_only_after_mutual_reveal():
    msg = "my insta is @maya.k"
    assert guard.check_chat(msg, ANSWERS, revealed=False)["reasons"] == ["contact_info"]
    assert guard.check_chat(msg, ANSWERS, revealed=True) == {"ok": True, "reasons": []}


# --------------------------------------------------------- port adapters
def test_will_text_guard_adapter():
    tg = guard.text_guard()
    assert tg("What made that part of your week feel easier?") is True
    assert tg("Was it your therapist who suggested that?") is False


@pytest.mark.parametrize("text,against", [(None, []), (5, []), ("ok", "an answer"), ("ok", [None]), ("ok", None)])
def test_bad_inputs_raise(text, against):
    with pytest.raises(TypeError):
        guard.check(text, against)


def test_guard_does_not_mutate_inputs():
    against = list(ANSWERS)
    guard.check("Night Owls", against)
    assert against == ANSWERS


# ------------------------------------------- consumers' real call helpers
def test_works_through_adam_and_rishi_call_helpers():
    planning_ports = pytest.importorskip("server.planning.ports")
    sky = pytest.importorskip("server.matching.sky")
    assert planning_ports.guard_allows(guard, "Open mic Thursday 7-9pm", ANSWERS) is True
    assert planning_ports.guard_allows(guard, "Everyone seems to already have their people", ANSWERS) is False
    assert sky._guard_ok(guard, "Eating alone more than they let on", ANSWERS) is True
    assert sky._guard_ok(guard, "Sober Saturday Squad", ANSWERS) is False
