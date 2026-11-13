"""formationSnapshot lease + publish guard (role task 6) and block/report storage.
Offline, synthetic fixture players only."""

from __future__ import annotations

import asyncio
import threading
import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from privacy_helpers import COMMUNITY, consent_req, join_body, joined
from server.privacy import build_router, install_error_handlers
from server.privacy.answers import AnswerStore
from server.privacy.errors import PrivacyError
from server.privacy.fixtures import seed_community, seed_synthetic_players
from server.privacy.formation import LeasedSnapshot, PrivacyFormation
from server.privacy.moderation import ModerationStore

CYCLE = "cycle-demo-w1"


def answer(pid, day=1, text="Mostly the dining hall corner table", catch_up=False):
    return {"answerId": f"a-{pid}-{day}", "cycleId": CYCLE, "day": day, "questionId": "q", "playerId": pid,
            "text": text, "source": "text", "isCatchUp": catch_up, "weight": 0.6 if catch_up else 1.0,
            "followUpUsed": False, "createdAt": "2026-11-11T17:00:00Z", "editedAt": None, "deletedAt": None}


@pytest.fixture
def parts(store, service):
    answers = AnswerStore(store, service)
    moderation = ModerationStore(store, service)
    return answers, moderation, PrivacyFormation(store, answers, moderation)


@pytest.fixture
def week(store, parts):
    """The synthetic week: 8 players, blocks, distress answer flagged."""
    answers, moderation, formation = parts
    seed_synthetic_players(store)
    import json
    from pathlib import Path
    data = json.loads((Path(__file__).resolve().parents[2] / "contracts/fixtures/week-sample.json").read_text())
    for a in data["answers"]:
        answers.save(answer(a["playerId"], a["day"], a["text"], a["isCatchUp"]), "none")
    d = data["distressFixture"]
    answers.save(answer(d["playerId"], d["day"], d["text"]), "distress")
    with store.tx() as conn:  # fixture block (Omar blocks Ren), seeded directly for synthetic players
        for b in data["blocks"]:
            conn.execute("INSERT INTO blocks VALUES (?, ?, ?, '2026-11-10T00:00:00Z')",
                         (COMMUNITY, b["blockerId"], b["blockedId"]))
    return data


# --------------------------------------------------------------- snapshot
def test_snapshot_is_exact_contract_shape(parts, week):
    _, _, formation = parts
    lease = formation.prepare_formation(CYCLE, COMMUNITY)
    snap = lease.snapshot
    assert set(snap) == {"answers", "idMap", "blockedPairs"}
    assert all(set(a) == {"id", "text", "weight"} for a in snap["answers"])
    assert set(snap["idMap"].values()) == set(lease.player_ids)
    assert {a["id"] for a in snap["answers"]} == set(snap["idMap"])
    assert snap["blockedPairs"] == [["p-omar", "p-ren"]]
    assert "p-ana" not in lease.player_ids  # distress fixture excluded
    assert all("SYNTHETIC SAFETY TEST" not in a["text"] for a in snap["answers"])
    assert all(not a["id"].startswith("p-") for a in snap["answers"])  # refs carry no identity
    jordan = snap["idMap"]
    weights = {(jordan[a["id"]], a["weight"]) for a in snap["answers"]}
    assert ("p-jordan", 0.6) in weights  # catch-up weight preserved


def test_refs_are_random_per_lease(parts, week):
    _, _, formation = parts
    a, b = formation.prepare_formation(CYCLE, COMMUNITY), formation.prepare_formation(CYCLE, COMMUNITY)
    assert set(a.snapshot["idMap"]) != set(b.snapshot["idMap"])
    assert a.revision == b.revision  # same data, same revision


def test_snapshot_passes_rishis_validator(parts, week):
    models = pytest.importorskip("server.matching.models")
    _, _, formation = parts
    lease = formation.prepare_formation(CYCLE, COMMUNITY)
    snap = asyncio.run(LeasedSnapshot(lease).formation_snapshot(CYCLE))
    parsed = models.FormationSnapshot.from_dict(snap)
    assert set(parsed.refs) == set(snap["idMap"])
    assert len(parsed.blocked_ref_pairs()) == 1


def test_leased_snapshot_rejects_other_cycle_and_is_a_copy(parts, week):
    _, _, formation = parts
    lease = formation.prepare_formation(CYCLE, COMMUNITY)
    source = LeasedSnapshot(lease)
    with pytest.raises(PrivacyError):
        asyncio.run(source.formation_snapshot("cycle-other"))
    copy = asyncio.run(source.formation_snapshot(CYCLE))
    copy["answers"].clear()
    assert lease.snapshot["answers"]


def test_snapshot_scoped_to_community(store, service, parts, week):
    answers, _, formation = parts
    seed_community(store, "community-other", "Other Group (synthetic)")
    from privacy_helpers import join_req
    other = service.require_session(service.join("community-other", join_req("Elsewhere")).token)
    answers.save({**answer(other.player_id), "cycleId": CYCLE}, "none")
    lease = formation.prepare_formation(CYCLE, COMMUNITY)
    assert other.player_id not in lease.player_ids
    assert len(lease.snapshot["answers"]) == len(set((a["id"], a["text"]) for a in lease.snapshot["answers"]))


# ----------------------------------------------------------- publish guard
def test_guard_passes_when_nothing_changed_and_runs_body_once(parts, week):
    _, _, formation = parts
    lease = formation.prepare_formation(CYCLE, COMMUNITY)
    ran = []
    with formation.publish_guard(CYCLE, lease.revision, ["p-maya", "p-dev", "p-jordan"]):
        ran.append(True)
    assert ran == [True]


def _stale(formation, lease, players=("p-maya",)):
    with pytest.raises(PrivacyError) as e:
        with formation.publish_guard(CYCLE, lease.revision, list(players)):
            pytest.fail("commit body must not run on a stale lease")
    assert e.value.code == "STALE_REVISION"


def test_guard_stale_after_answer_deleted(parts, week):
    answers, _, formation = parts
    lease = formation.prepare_formation(CYCLE, COMMUNITY)
    answers.delete(CYCLE, "p-dev", 1, "2026-11-12T00:00:00Z")
    _stale(formation, lease)


def test_guard_stale_after_answer_edited(parts, week):
    answers, _, formation = parts
    lease = formation.prepare_formation(CYCLE, COMMUNITY)
    answers.save({**answer("p-maya", 1, "changed my mind"), "editedAt": "2026-11-12T00:00:00Z"}, "none")
    _stale(formation, lease)


def test_guard_stale_after_consent_revoked(service, parts, week):
    answers, _, formation = parts
    _, real = joined(service, "Real")
    answers.save(answer(real.player_id), "none")
    lease = formation.prepare_formation(CYCLE, COMMUNITY)
    service.update_consent(real, consent_req(1, match=False))
    _stale(formation, lease, [real.player_id])


def test_guard_stale_after_new_block(service, parts, week):
    answers, moderation, formation = parts
    _, real = joined(service, "Real")
    answers.save(answer(real.player_id), "none")
    lease = formation.prepare_formation(CYCLE, COMMUNITY)
    moderation.block(real, "p-maya")
    _stale(formation, lease)


def test_guard_rejects_players_not_in_snapshot_and_forged_revision(parts, week):
    _, _, formation = parts
    lease = formation.prepare_formation(CYCLE, COMMUNITY)
    _stale(formation, lease, ["p-ana"])  # flagged player
    for bad in ("", "nonsense", f"{COMMUNITY}|deadbeef", None):
        with pytest.raises(PrivacyError):
            with formation.publish_guard(CYCLE, bad, ["p-maya"]):
                pass


def test_guard_holds_lock_against_concurrent_consent_change(service, parts, week):
    answers, _, formation = parts
    _, real = joined(service, "Real")
    answers.save(answer(real.player_id), "none")
    lease = formation.prepare_formation(CYCLE, COMMUNITY)
    order = []

    def revoke():
        service.update_consent(real, consent_req(1, chat=False))
        order.append("revoked")

    with formation.publish_guard(CYCLE, lease.revision, [real.player_id]):
        t = threading.Thread(target=revoke)
        t.start()
        time.sleep(0.15)          # revocation must wait for the guard
        order.append("committed")
    t.join(2)
    assert order == ["committed", "revoked"]
    _stale(formation, lease, [real.player_id])  # and the next publish sees it


def test_privacy_calls_inside_guard_are_nested_not_deadlocked(service, parts, week):
    answers, moderation, formation = parts
    lease = formation.prepare_formation(CYCLE, COMMUNITY)
    with formation.publish_guard(CYCLE, lease.revision, ["p-maya"]):
        assert moderation.blocked_by("p-omar", COMMUNITY) == {"p-ren"}
        assert answers.get(CYCLE, "p-maya", 1) is not None


def test_failed_commit_body_rolls_back_nested_privacy_writes(service, parts, week):
    answers, moderation, formation = parts
    _, real = joined(service, "Real")
    lease = formation.prepare_formation(CYCLE, COMMUNITY)
    with pytest.raises(RuntimeError):
        with formation.publish_guard(CYCLE, lease.revision, ["p-maya"]):
            moderation.block(real, "p-maya")
            raise RuntimeError("Kai commit failed")
    assert moderation.blocked_by(real.player_id, COMMUNITY) == frozenset()


# ------------------------------------------------------------------ blocks
def test_block_rules_and_no_existence_leak(service, store, parts, week):
    _, moderation, _ = parts
    seed_community(store, "community-other", "Other Group (synthetic)")
    _, me = joined(service, "Me")
    moderation.block(me, me.player_id)            # self: ignored
    moderation.block(me, "p_does_not_exist")      # unknown: ignored
    moderation.block(me, None)                    # unresolved handle: ignored
    moderation.block(me, "p-maya")
    moderation.block(me, "p-maya")                # idempotent
    assert moderation.blocked_by(me.player_id, COMMUNITY) == {"p-maya"}
    assert moderation.blocked_by("p-maya", COMMUNITY) == frozenset()  # one-directional view


def test_block_route_always_204(service, parts, week):
    _, moderation, _ = parts
    app = FastAPI()
    install_error_handlers(app)
    handles = {("room-orion", "Star 2"): "p-maya"}
    app.include_router(build_router(service, moderation=moderation,
                                    resolve_handle=lambda actor, room, handle: handles.get((room, handle))),
                       prefix="/api/v1")
    c = TestClient(app, base_url="https://t")
    me = c.post(f"/api/v1/communities/{COMMUNITY}/join", json=join_body("Me")).json()["player"]["playerId"]
    for body in ({"roomId": "room-orion", "handle": "Star 2"}, {"roomId": "room-orion", "handle": "Star 9"},
                 {"roomId": "room-nope", "handle": "Star 2"}):
        r = c.post("/api/v1/me/blocks", json=body)
        assert r.status_code == 204 and r.content == b""
    assert moderation.blocked_by(me, COMMUNITY) == {"p-maya"}
    assert c.post("/api/v1/me/blocks", json={"roomId": "room-orion", "handle": "Star 2", "playerId": "p-x"}).status_code == 400
    assert TestClient(app, base_url="https://t").post("/api/v1/me/blocks", json={"roomId": "r", "handle": "h"}).status_code == 401


# ----------------------------------------------------------------- reports
def test_reports_idempotent_counted_and_operator_only(service, store, parts):
    from server.privacy.fixtures import grant_operator
    _, moderation, _ = parts
    a_token, a = joined(service, "A")
    _, b = joined(service, "B")
    r1 = moderation.report(a, "room-orion", "m-2", "Star 3", "personal_info")
    assert moderation.report(a, "room-orion", "m-2", "Star 3", "spam") == r1  # repeat tap
    assert moderation.distinct_reporters("room-orion", "m-2") == 1
    moderation.report(b, "room-orion", "m-2", "Star 3", "harassment")
    assert moderation.distinct_reporters("room-orion", "m-2") == 2
    assert moderation.reported_message_ids(a.player_id, "room-orion") == {"m-2"}
    assert moderation.reported_message_ids(b.player_id, "room-other") == frozenset()
    with pytest.raises(PrivacyError) as e:
        moderation.report_queue(a)
    assert e.value.code == "FORBIDDEN"
    grant_operator(store, a.player_id, COMMUNITY)
    operator = service.require_session(a_token)  # operator flag is read per request
    assert [r.reason for r in moderation.report_queue(operator)] == ["personal_info", "harassment"]


@pytest.mark.parametrize("args", [
    ("room", "m", "Star 1", "rude"), ("room", "m", "", "spam"), ("", "m", "Star 1", "spam"),
    ("room", 5, "Star 1", "spam"), ("room", "m", "x" * 41, "spam"),
])
def test_report_validation(service, parts, args):
    _, moderation, _ = parts
    _, a = joined(service, "A")
    with pytest.raises(PrivacyError) as e:
        moderation.report(a, *args)
    assert e.value.code == "INVALID_INPUT"
