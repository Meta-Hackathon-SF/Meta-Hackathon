"""D012 v3 events: eventSignals opt-in, private interest + RSVP storage, bucketed
outputs only, retention. Offline, synthetic players and events."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from privacy_helpers import COMMUNITY, consent_req, join_body, join_req
from server.privacy import build_router, install_error_handlers
from server.privacy.answers import AnswerStore
from server.privacy.errors import PrivacyError
from server.privacy.events import EventStore, bucket
from server.privacy.wire import InviteState, UpdateConsentRequest

CYCLE = "cycle-v3-w1"
APPROVED = {"evt-open-mic", "evt-board-games", "evt-climbing"}


@pytest.fixture
def events(store, service):
    return EventStore(store, service, lambda event_id: event_id in APPROVED)


def player(service, name="P (synthetic)", *, signals=True):
    result = service.join(COMMUNITY, join_req(name).model_copy(update={"event_signals": signals}))
    return result.token, service.require_session(result.token)


def code(e):
    return e.value.code


def toggle_events(service, actor, on: bool, version: int):
    req = UpdateConsentRequest.model_validate({"expectedVersion": version, "matchAnswers": True,
                                               "anonymousChat": True, "isAdult": True, "eventSignals": on})
    return service.update_consent(actor, req)


# ------------------------------------------------------------ consent toggle
def test_event_signals_default_off_and_opt_in_at_join(service):
    _, off = player(service, "Off", signals=False)
    _, on = player(service, "On", signals=True)
    assert service.get_consent(off).event_signals is False
    assert service.get_consent(on).event_signals is True


def test_nothing_stored_without_opt_in(service, events, store):
    _, p = player(service, signals=False)
    for attempt in (lambda: events.set_interest(p, CYCLE, "evt-open-mic", True),
                    lambda: events.replace_interests(p, CYCLE, ["evt-open-mic"])):
        with pytest.raises(PrivacyError) as e:
            attempt()
        assert code(e) == "CONSENT_REQUIRED"
    with store.tx() as conn:
        assert conn.execute("SELECT count(*) FROM event_interests").fetchone()[0] == 0


def test_opt_in_via_consent_patch_bumps_version_and_opt_out_deletes_everything(service, events, store):
    notices = []
    service.add_listener(notices.append)
    _, p = player(service, signals=False)
    c2 = toggle_events(service, p, True, 1)
    assert (c2.version, c2.event_signals, c2.revoked_at) == (2, True, None)
    events.set_interest(p, CYCLE, "evt-open-mic", True)
    events.issue_invite("inv-1", COMMUNITY, CYCLE, "evt-board-games", [p.player_id])
    events.rsvp(p, "inv-1", "going")
    c3 = toggle_events(service, p, False, 2)
    assert (c3.version, c3.event_signals, c3.revoked_at) == (3, False, None)  # still playing
    with store.tx() as conn:
        assert conn.execute("SELECT count(*) FROM event_interests").fetchone()[0] == 0
        assert conn.execute("SELECT count(*) FROM event_invite_recipients").fetchone()[0] == 0
    assert notices[-1].kind == "event_signals_revoked"
    with pytest.raises(PrivacyError) as e:
        events.set_interest(p, CYCLE, "evt-open-mic", True)
    assert code(e) == "CONSENT_REQUIRED"


def test_event_toggle_is_version_checked_and_retry_safe(service):
    _, p = player(service, signals=False)
    first = toggle_events(service, p, True, 1)
    assert toggle_events(service, p, True, 1) == first  # retried request
    with pytest.raises(PrivacyError) as e:
        toggle_events(service, p, False, 1)  # stale
    assert code(e) == "STALE_REVISION"
    unchanged = service.update_consent(p, consent_req(2))  # eventSignals omitted: left as is
    assert unchanged.event_signals is True and unchanged.version == 2


def test_play_consent_still_required(service, events):
    _, p = player(service)
    service.update_consent(p, consent_req(1, chat=False))
    with pytest.raises(PrivacyError) as e:
        events.set_interest(p, CYCLE, "evt-open-mic", True)
    assert code(e) == "CONSENT_REQUIRED"


# ---------------------------------------------------------------- interest
def test_unknown_event_is_not_found(service, events):
    _, p = player(service)
    for bad in ("evt-private-party", "", None):
        with pytest.raises(PrivacyError) as e:
            events.set_interest(p, CYCLE, bad, True)
        assert code(e) == "NOT_FOUND"
    with pytest.raises(PrivacyError):
        events.replace_interests(p, CYCLE, ["evt-open-mic", "evt-unlisted"])
    assert events.my_interest(p, "evt-open-mic") is False  # all-or-nothing


def test_interest_is_own_only_and_replace_is_a_full_set(service, events):
    _, a = player(service, "A")
    _, b = player(service, "B")
    assert events.replace_interests(a, CYCLE, ["evt-open-mic", "evt-climbing", "evt-open-mic"]) == 2
    events.replace_interests(a, CYCLE, ["evt-climbing"])
    assert (events.my_interest(a, "evt-open-mic"), events.my_interest(a, "evt-climbing")) == (False, True)
    assert events.my_interest(b, "evt-climbing") is False


@pytest.mark.parametrize("n,expected", [(0, "none"), (1, "none"), (2, "none"), (3, "3-5"), (5, "3-5"),
                                         (6, "6-10"), (10, "6-10"), (11, "11+"), (500, "11+")])
def test_bucket_edges(n, expected):
    assert bucket(n) == expected


def test_interest_bucket_counts_only_opted_in_peers_and_never_under_three(service, events):
    peers = []
    for i in range(4):
        _, p = player(service, f"Peer {i}")
        events.set_interest(p, CYCLE, "evt-open-mic", True)
        peers.append(p)
    _, stranger = player(service, "Stranger")
    events.set_interest(stranger, CYCLE, "evt-open-mic", True)
    ids = [p.player_id for p in peers]
    assert events.interest_bucket(COMMUNITY, "evt-open-mic", ids) == "3-5"
    assert events.interest_bucket(COMMUNITY, "evt-open-mic", ids[:2]) == "none"  # 2 never shows
    toggle_events(service, peers[0], False, 1)
    toggle_events(service, peers[1], False, 1)
    assert events.interest_bucket(COMMUNITY, "evt-open-mic", ids) == "none"  # opt-outs drop out
    assert events.interest_bucket(COMMUNITY, "evt-open-mic", []) == "none"


# ------------------------------------------------------------------ invites
def test_invites_only_to_opted_in_and_rsvp_is_403_for_anyone_else(service, events):
    _, a = player(service, "A")
    _, b = player(service, "B")
    _, opted_out = player(service, "C", signals=False)
    events.issue_invite("inv-1", COMMUNITY, CYCLE, "evt-board-games", [a.player_id, opted_out.player_id])
    assert [i.invite_id for i in events.my_invites(a)] == ["inv-1"]
    assert events.my_invites(b) == [] and events.my_invites(opted_out) == []
    with pytest.raises(PrivacyError) as e:
        events.rsvp(b, "inv-1", "going")  # another session
    assert code(e) == "FORBIDDEN"
    with pytest.raises(PrivacyError) as e:
        events.rsvp(b, "inv-does-not-exist", "going")
    assert code(e) == "FORBIDDEN"  # same answer: no existence leak
    state = events.rsvp(a, "inv-1", "going")
    assert state == InviteState(invite_id="inv-1", event_id="evt-board-games", rsvp="going", status="pending")


def test_invite_state_carries_no_counts_or_people():
    assert set(InviteState.model_fields) == {"invite_id", "event_id", "rsvp", "status", "confirm_at_count"}


def test_quorum_needs_three_opted_in_going_and_cancelled_is_stale(service, events):
    goers = [player(service, f"G{i}")[1] for i in range(3)]
    events.issue_invite("inv-q", COMMUNITY, CYCLE, "evt-climbing", [g.player_id for g in goers])
    events.rsvp(goers[0], "inv-q", "going")
    events.rsvp(goers[1], "inv-q", "going")
    assert events.invite_has_quorum("inv-q") is False
    events.rsvp(goers[2], "inv-q", "not_going")
    assert events.invite_has_quorum("inv-q") is False
    events.rsvp(goers[2], "inv-q", "going")
    assert events.invite_has_quorum("inv-q") is True
    toggle_events(service, goers[2], False, 1)  # opt-out removes the RSVP
    assert events.invite_has_quorum("inv-q") is False
    events.set_invite_status("inv-q", "cancelled")
    with pytest.raises(PrivacyError) as e:
        events.rsvp(goers[0], "inv-q", "not_going")
    assert code(e) == "STALE_REVISION"
    with pytest.raises(PrivacyError):
        events.set_invite_status("inv-unknown", "confirmed")


# -------------------------------------------------------- routes and deletion
@pytest.fixture
def app(service, store, events, monkeypatch):
    monkeypatch.setenv("CST_COOKIE_INSECURE_DEV", "1")
    app = FastAPI()
    install_error_handlers(app)
    app.include_router(build_router(service, AnswerStore(store, service), events=events,
                                    current_cycle_id=lambda community: CYCLE), prefix="/api/v1")
    return app


def client(app, *, signals):
    c = TestClient(app, base_url="http://testserver")
    assert c.post(f"/api/v1/communities/{COMMUNITY}/join", json={**join_body(), "eventSignals": signals}).status_code == 201
    return c


def test_event_signals_route(app):
    on, off = client(app, signals=True), client(app, signals=False)
    r = on.put("/api/v1/me/event-signals", json={"eventIds": ["evt-open-mic", "evt-climbing"]})
    assert r.status_code == 200 and r.json() == {"stored": 2}
    assert on.get("/api/v1/session").json()["consent"]["eventSignals"] is True
    r = off.put("/api/v1/me/event-signals", json={"eventIds": ["evt-open-mic"]})
    assert r.status_code == 403 and r.json()["error"]["code"] == "CONSENT_REQUIRED"
    r = on.put("/api/v1/me/event-signals", json={"eventIds": ["evt-secret-afterparty"]})
    assert r.status_code == 404
    r = on.put("/api/v1/me/event-signals", json={"eventIds": ["evt-open-mic"], "playerId": "p_someone"})
    assert r.status_code == 400  # identity never from the body
    assert TestClient(app, base_url="http://testserver").put(
        "/api/v1/me/event-signals", json={"eventIds": []}).status_code == 401


def test_delete_my_data_removes_interest_and_rsvp_but_keeps_opt_in(service, store, events, app):
    c = client(app, signals=True)
    me = service.require_session(c.cookies["cst_session"])
    events.set_interest(me, CYCLE, "evt-open-mic", True)
    events.issue_invite("inv-d", COMMUNITY, CYCLE, "evt-open-mic", [me.player_id])
    events.rsvp(me, "inv-d", "going")
    assert c.delete("/api/v1/me/data").status_code == 202
    assert events.my_interest(me, "evt-open-mic") is False and events.my_invites(me) == []
    assert service.get_consent(me).event_signals is True


# ---------------------------------------------------------------- retention
def test_interest_and_invites_expire_fourteen_days_after_lock(service, store, events, clock):
    answers = AnswerStore(store, service)
    _, p = player(service)
    events.set_interest(p, CYCLE, "evt-open-mic", True)
    events.set_interest(p, "cycle-next", "evt-climbing", True)
    events.issue_invite("inv-r", COMMUNITY, CYCLE, "evt-board-games", [p.player_id])
    events.rsvp(p, "inv-r", "going")
    answers.mark_locked(CYCLE, "2026-11-14T20:00:00Z")
    clock.now = clock.now.replace(year=2026, month=11, day=28, hour=19, minute=59, second=59)
    assert answers.expired_cycles() == []
    assert answers.purge_expired()["eventInterests"] == 0
    clock.advance(seconds=1)
    assert answers.expired_cycles() == [CYCLE]
    assert answers.purge_expired() == {"answers": 0, "guesses": 0, "eventInterests": 1, "invites": 1}
    assert events.my_interest(p, "evt-open-mic") is False and events.my_invites(p) == []
    assert events.my_interest(p, "evt-climbing") is True  # other cycle untouched
