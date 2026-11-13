"""D012 v3: OutputGuard on nudge and custom-event copy. Fuzz with known answers
(no 5-word overlap gets through), sensitive red-team, headcounts and names.
Offline, synthetic text only."""

from __future__ import annotations

import json
import random
from pathlib import Path

import pytest

from server.privacy.guard import OutputGuard

ROOT = Path(__file__).resolve().parents[2]
WEEK = json.loads((ROOT / "contracts/fixtures/week-sample.json").read_text())
VENUES = json.loads((ROOT / "contracts/fixtures/venues.json").read_text())
ANSWERS = [a["text"] for a in WEEK["answers"]] + [WEEK["injectionFixture"]["text"]]
NAMES = [p["displayName"] for p in WEEK["players"]]
TEMPLATES = [
    "People from your constellations are going to {title}.",
    "{title} at {venue}, Thursday 7-9pm. People from your constellations are going.",
    "New: {title} at {venue}. Saturday 2-4pm, easy to leave early.",
]
guard = OutputGuard()


def copy_for(title: str, i: int = 0) -> str:
    venue = VENUES["venues"][i % len(VENUES["venues"])]["name"]
    return TEMPLATES[i % len(TEMPLATES)].format(title=title, venue=venue)


@pytest.mark.parametrize("i,event", list(enumerate(VENUES["campusEvents"])))
def test_real_catalog_copy_passes(i, event):
    for k in range(len(TEMPLATES)):
        assert guard.check_event_copy(copy_for(event["title"], i + k), ANSWERS, names=NAMES) == {"ok": True, "reasons": []}


def test_allowed_bucket_wording_passes_only_with_the_matching_bucket():
    text = "3-5 people from your constellations are going to Open mic night."
    assert guard.check_event_copy(text, ANSWERS, bucket="3-5")["ok"] is True
    assert guard.check_event_copy(text, ANSWERS, bucket="6-10")["reasons"] == ["pii"]
    assert guard.check_event_copy("11+ people are going to Pickup soccer.", ANSWERS, bucket="11+")["ok"] is True
    assert guard.check_event_copy(text, ANSWERS)["reasons"] == ["pii"]  # no bucket given: no counts at all


@pytest.mark.parametrize("text", [
    "2 people from your constellations are going to Open mic night.",
    "Seven friends are going to Board game hour.",
    "A couple of others are going to Pickup soccer.",
    "4 players interested in Board game hour.",
    "Only 1 of you is going.",
    "Go if 3 of you are in.",                   # today's 2.1.0 chat copy: a count, not a bucket
    "12 students are attending Open mic night.",
])
def test_headcounts_are_rejected(text):
    assert "pii" in guard.check_event_copy(text, ANSWERS)["reasons"]


@pytest.mark.parametrize("text", [
    "Open mic night, Thursday 7-9pm.", "Board game hour at 3pm in the Library Commons.",
    "Pickup soccer on Nov 14, 5:30-7pm.", "Doors at 6, music until 9.",
])
def test_times_and_dates_are_not_headcounts(text):
    assert guard.check_event_copy(text, ANSWERS)["ok"] is True


@pytest.mark.parametrize("name", NAMES)
def test_player_names_are_rejected(name):
    first = name.replace(" (synthetic)", "")
    text = f"{first} and others from your constellations are going to Open mic night."
    assert guard.check_event_copy(text, ANSWERS, names=NAMES)["reasons"] == ["pii"]


def test_fuzz_no_five_word_answer_window_survives():
    """Every 5-word window of every known answer, disguised and embedded in real
    copy at random positions, is rejected."""
    rng = random.Random(1113)
    checked = 0
    for answer in ANSWERS:
        tokens = answer.split()
        for start in range(len(tokens) - 4):
            window = tokens[start:start + 5]
            for _ in range(4):
                disguised = " ".join(w.upper() if rng.random() < 0.3 else w for w in window)
                disguised = disguised.replace(" ", rng.choice([" ", "  ", ", ", "​ "]))
                base = copy_for(rng.choice(VENUES["campusEvents"])["title"], rng.randrange(9))
                cut = rng.randrange(len(base) + 1)
                text = base[:cut] + " " + disguised + " " + base[cut:]
                assert "quote_5_words" in guard.check_event_copy(text, ANSWERS)["reasons"], text
                checked += 1
    assert checked > 150


def test_four_word_fragments_of_long_answers_are_allowed():
    """#58 rule (c): 4-word runs count as quotes only against short answers
    (<= 12 tokens); against longer answers only 5-word runs do."""
    long_answer = ["I usually grab dinner late after my lab because the dining hall is calmer then"]
    tokens = long_answer[0].split()
    for start in range(len(tokens) - 3):
        text = copy_for("Open mic night") + " " + " ".join(tokens[start:start + 4])
        assert "quote_5_words" not in guard.check_event_copy(text, long_answer)["reasons"], text


def test_four_word_fragments_of_short_answers_are_quotes():
    short = ["I eat alone in my room"]
    assert "quote_5_words" in guard.check_event_copy(copy_for("Open mic night") + " alone in my room", short)["reasons"]


SENSITIVE_TITLES = [
    "Anxiety support circle", "Depression check-in", "Therapy-free hangout", "ADHD study sprint",
    "Sober social", "Eating disorder recovery walk", "Queer coffee", "Trans student mixer",
    "Coming out story night", "Bible study", "Muslim students lunch", "Church choir practice",
    "Atheist debate night", "Ramadan iftar", "Student loans workshop", "Can't afford dinner club",
    "Financial aid Q&A", "Divorced parents meetup", "Grief walk", "Foster care alumni lunch",
    "Domestic violence survivors", "Hometown night", "Dorm room movie night", "Apartment hunting crew",
    "Panic attack recovery", "Bipolar peer group", "Homeless outreach shift", "Bankruptcy basics",
    "Funeral planning talk", "Mental health check-in",
]


def test_red_team_list_is_thirty():
    assert len(set(SENSITIVE_TITLES)) == 30


@pytest.mark.parametrize("title", SENSITIVE_TITLES)
def test_sensitive_event_copy_is_rejected(title):
    assert "sensitive_term" in guard.check_event_copy(copy_for(title), ANSWERS)["reasons"]


def test_contact_info_and_private_addresses_rejected():
    assert "contact_info" in guard.check_event_copy("RSVP at maya@example.edu", ANSWERS)["reasons"]
    assert "pii" in guard.check_event_copy("Meet at 123 Main Street, apt 4", ANSWERS)["reasons"]


def test_bad_inputs_raise():
    with pytest.raises(TypeError):
        guard.check_event_copy(None, ANSWERS)
    with pytest.raises(TypeError):
        guard.check_event_copy("ok", "not a list")
