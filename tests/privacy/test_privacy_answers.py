"""Private answer + guess store (role task 3): author-only reads, consent and
lock guards, server-set weights, deletion and 14-day TTL. Offline, synthetic text."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from privacy_helpers import COMMUNITY, consent_req, join_body, joined
from server.privacy import build_router, install_error_handlers
from server.privacy.answers import AnswerStore
from server.privacy.errors import PrivacyError
from server.privacy.fixtures import seed_synthetic_players

CYCLE = "cycle-demo-w1"


def answer(player_id: str, day: int = 1, text: str = "Mostly the dining hall corner table", *,
           catch_up: bool = False, follow_up: bool = False, weight: float | None = None) -> dict:
    if weight is None:
        weight = min(1.1, (0.6 if catch_up else 1.0) + (0.1 if follow_up else 0.0))
    return {
        "answerId": f"a-{player_id}-{day}", "cycleId": CYCLE, "day": day, "questionId": "q-routine-meals",
        "playerId": player_id, "text": text, "source": "text", "isCatchUp": catch_up, "weight": weight,
        "followUpUsed": follow_up, "createdAt": "2026-11-11T17:00:00Z", "editedAt": None, "deletedAt": None,
    }


@pytest.fixture
def answers(store, service) -> AnswerStore:
    return AnswerStore(store, service)


def code(e) -> str:
    return e.value.code


def test_save_and_read_own_answers_only(service, answers):
    _, maya = joined(service, "Maya")
    _, dev = joined(service, "Dev")
    answers.save(answer(maya.player_id, 1), "none")
    answers.save(answer(maya.player_id, 3, "Everyone seems to already have their people"), "none")
    answers.save(answer(dev.player_id, 1, "cooking for one"), "none")
    mine = answers.list_for_player(CYCLE, maya.player_id)
    assert [a.day for a in mine] == [1, 3] and {a.player_id for a in mine} == {maya.player_id}
    assert answers.get(CYCLE, maya.player_id, 2) is None
    assert answers.get(CYCLE, dev.player_id, 1).text == "cooking for one"


def test_save_replaces_same_day(service, answers):
    _, p = joined(service)
    answers.save(answer(p.player_id, 1, "first"), "none")
    answers.save({**answer(p.player_id, 1, "second"), "editedAt": "2026-11-11T18:00:00Z"}, "none")
    got = answers.list_for_player(CYCLE, p.player_id)
    assert len(got) == 1 and got[0].text == "second" and got[0].edited_at == "2026-11-11T18:00:00Z"


@pytest.mark.parametrize("kwargs,expected", [
    ({}, 1.0), ({"catch_up": True}, 0.6), ({"follow_up": True}, 1.1), ({"catch_up": True, "follow_up": True}, 0.7),
])
def test_server_weights_accepted(service, answers, kwargs, expected):
    _, p = joined(service)
    answers.save(answer(p.player_id, **kwargs), "none")
    assert answers.get(CYCLE, p.player_id, 1).weight == pytest.approx(expected)


@pytest.mark.parametrize("weight", [1.1, 0.6, 0.5, 2.0])
def test_client_set_weight_rejected(service, answers, weight):
    _, p = joined(service)
    with pytest.raises((PrivacyError, ValueError)):
        answers.save(answer(p.player_id, weight=weight), "none")  # on-day, no follow-up => only 1.0 valid
    assert answers.get(CYCLE, p.player_id, 1) is None


@pytest.mark.parametrize("mutate", [
    lambda a: a.update(text=""), lambda a: a.update(text="x" * 401), lambda a: a.update(day=6),
    lambda a: a.update(source="email"), lambda a: a.update(isFallback=True),
    lambda a: a.update(deletedAt="2026-11-11T18:00:00Z"),
])
def test_invalid_answers_rejected(service, answers, mutate):
    _, p = joined(service)
    body = answer(p.player_id)
    mutate(body)
    with pytest.raises((PrivacyError, ValueError)):
        answers.save(body, "none")


def test_bad_flag_rejected(service, answers):
    _, p = joined(service)
    with pytest.raises(ValueError):
        answers.save(answer(p.player_id), "fine")


def test_write_needs_full_consent(service, answers):
    _, p = joined(service)
    service.update_consent(p, consent_req(1, match=False))
    with pytest.raises(PrivacyError) as e:
        answers.save(answer(p.player_id), "none")
    assert code(e) == "CONSENT_REQUIRED"
    with pytest.raises(PrivacyError):
        answers.save_guess({"cycleId": CYCLE, "playerId": p.player_id, "percent": 20})


def test_unknown_player_cannot_be_written(answers):
    with pytest.raises(PrivacyError) as e:
        answers.save(answer("p_forged"), "none")
    assert code(e) == "CONSENT_REQUIRED"


def test_lock_freezes_answers_and_guesses(service, answers):
    _, p = joined(service)
    answers.save(answer(p.player_id), "none")
    answers.mark_locked(CYCLE, "2026-11-14T20:00:00Z")
    for attempt in (
        lambda: answers.save(answer(p.player_id, 2), "none"),
        lambda: answers.delete(CYCLE, p.player_id, 1, "2026-11-14T21:00:00Z"),
        lambda: answers.save_guess({"cycleId": CYCLE, "playerId": p.player_id, "percent": 5}),
    ):
        with pytest.raises(PrivacyError) as e:
            attempt()
        assert code(e) == "CYCLE_LOCKED"
    assert answers.get(CYCLE, p.player_id, 1) is not None


def test_delete_removes_text_and_notifies(service, answers, store):
    notices = []
    service.add_listener(notices.append)
    _, p = joined(service)
    answers.save(answer(p.player_id, 1, "a private sentence to remove"), "none")
    assert answers.delete(CYCLE, p.player_id, 1, "2026-11-11T19:00:00Z") is True
    assert answers.delete(CYCLE, p.player_id, 1, "2026-11-11T19:00:00Z") is False
    assert answers.get(CYCLE, p.player_id, 1) is None
    with store.tx() as conn:
        dump = "\n".join(conn.iterdump())
    assert "a private sentence to remove" not in dump
    assert (notices[-1].kind, notices[-1].cycle_id) == ("answer_deleted", CYCLE)


def test_guesses_are_separate_and_bounded(service, answers):
    _, p = joined(service)
    answers.save_guess({"cycleId": CYCLE, "playerId": p.player_id, "percent": 20})
    answers.save_guess({"cycleId": CYCLE, "playerId": p.player_id, "percent": 35})
    assert answers.get_guess(CYCLE, p.player_id).percent == 35
    for bad in (-1, 101, 20.5, "20"):
        with pytest.raises(ValueError):
            answers.save_guess({"cycleId": CYCLE, "playerId": p.player_id, "percent": bad})
    assert answers.list_for_player(CYCLE, p.player_id) == []


def test_ttl_purges_fourteen_days_after_lock(service, answers, clock):
    _, p = joined(service)
    answers.save(answer(p.player_id), "none")
    answers.save_guess({"cycleId": CYCLE, "playerId": p.player_id, "percent": 10})
    answers.save({**answer(p.player_id), "cycleId": "cycle-next", "answerId": "a-next"}, "none")
    clock.advance(days=3)
    answers.mark_locked(CYCLE, "2026-11-14T17:00:00Z")
    clock.advance(days=14, seconds=-1)
    assert answers.purge_expired() == {"answers": 0, "guesses": 0, "eventInterests": 0, "invites": 0}
    clock.advance(seconds=1)
    assert answers.purge_expired() == {"answers": 1, "guesses": 1, "eventInterests": 0, "invites": 0}
    assert answers.get(CYCLE, p.player_id, 1) is None and answers.get_guess(CYCLE, p.player_id) is None
    assert answers.get("cycle-next", p.player_id, 1) is not None  # unlocked cycle untouched


def test_eligible_answers_exclude_flagged_revoked_and_deleted(service, answers, store):
    seed_synthetic_players(store)
    _, revoker = joined(service, "Revoker")
    answers.save(answer("p-maya", 1, "I eat in my room so no one sees me alone"), "none")
    answers.save(answer("p-ana", 2, "SYNTHETIC SAFETY TEST: I don't see the point of anything anymore"), "distress")
    answers.save(answer("p-dev", 1, "cooking for one is honestly depressing"), "none")
    answers.save(answer(revoker.player_id, 1, "revoked later"), "none")
    service.update_consent(revoker, consent_req(1, chat=False))
    answers.delete(CYCLE, "p-dev", 1, "2026-11-11T19:00:00Z")
    rows = answers.eligible_answers(CYCLE)
    assert [(r["player_id"], r["day"]) for r in rows] == [("p-maya", 1)]
    assert all("SYNTHETIC SAFETY TEST" not in r["text"] for r in rows)


def test_purge_cycle_drops_fixture_cycle(service, answers):
    _, p = joined(service)
    answers.save(answer(p.player_id), "none")
    answers.mark_locked(CYCLE, "2026-11-14T20:00:00Z")
    answers.purge_cycle(CYCLE)
    assert answers.list_for_player(CYCLE, p.player_id) == []
    answers.save(answer(p.player_id), "none")  # reset fixture cycle is writable again


def test_delete_my_data_route(service, answers):
    app = FastAPI()
    install_error_handlers(app)
    app.include_router(build_router(service, answers), prefix="/api/v1")
    notices = []
    service.add_listener(notices.append)
    me, other = TestClient(app, base_url="https://t"), TestClient(app, base_url="https://t")
    my_id = me.post(f"/api/v1/communities/{COMMUNITY}/join", json=join_body("Me")).json()["player"]["playerId"]
    other_id = other.post(f"/api/v1/communities/{COMMUNITY}/join", json=join_body("Other")).json()["player"]["playerId"]
    answers.save(answer(my_id), "none")
    answers.save_guess({"cycleId": CYCLE, "playerId": my_id, "percent": 10})
    answers.save(answer(other_id), "none")
    assert TestClient(app, base_url="https://t").delete("/api/v1/me/data").status_code == 401
    r = me.delete("/api/v1/me/data")
    assert r.status_code == 202 and r.json() == {"status": "deleted"}
    assert answers.list_for_player(CYCLE, my_id) == [] and answers.get_guess(CYCLE, my_id) is None
    assert answers.get(CYCLE, other_id, 1) is not None
    assert notices[-1].kind == "data_deleted" and notices[-1].player_id == my_id
    assert me.get("/api/v1/session").status_code == 200  # session and consent are kept
