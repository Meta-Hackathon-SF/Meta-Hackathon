"""D014 M9 activity_classification + M10 sensitivity_screen, and the snapshot
questionId. Offline: Adam's labeled FixtureMuse over a scripted transport stands
in for the provider (the real adapter pipeline: allowlist, input + output
schema validation, one retry). No paid call. Synthetic texts only."""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from privacy_helpers import COMMUNITY, consent_body, join_body
from server.privacy import build_router, install_error_handlers
from server.privacy.activity import ActivityStore
from server.privacy.answers import AnswerStore
from server.privacy.fixtures import seed_synthetic_players
from server.privacy.formation import LeasedSnapshot, PrivacyFormation
from server.privacy.moderation import ModerationStore
from server.privacy.sensitivity import (
    BATCH_MAX as SENS_BATCH,
    SENSITIVITY_CATEGORIES,
    SENSITIVITY_PROMPT_VERSION,
    SensitivityScreen,
    register_sensitivity_task,
)
from server.privacy.topics import (
    ACTIVITY_PROMPT_VERSION,
    ACTIVITY_TOPICS,
    BATCH_MAX,
    STANCES,
    ActivityClassifier,
    ActivityTopics,
    register_activity_task,
    validate_batch,
)

providers = pytest.importorskip("server.providers")
from server.providers import ProviderError, TaskRegistry  # noqa: E402
from server.providers import contract as pc  # noqa: E402
from server.providers.fixture import FixtureMuse, ScriptedTransport  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
WEEK = json.loads((ROOT / "contracts" / "fixtures" / "week-sample.json").read_text())
PLAYER_IDS = [p["playerId"] for p in WEEK["players"]]
SECRET = "my private post about the dining hall and board games"


def run(coro):
    return asyncio.run(coro)


def labels_for(text: str) -> tuple[bool, list[dict]]:
    """Scripted 'model': deterministic labels from markers in synthetic text."""
    if "clinic" in text:
        return True, [{"topic": "food", "stance": "positive"}]
    out = []
    if "board games" in text:
        out.append({"topic": "gaming", "stance": "positive"})
    if "dining hall" in text:
        out.append({"topic": "food", "stance": "neutral"})
    if "hate jazz" in text:
        out.append({"topic": "music", "stance": "negative"})
    return False, out


def m9_handler(seen: list | None = None):
    def handler(inp):
        if seen is not None:
            seen.append(inp)
        if any("FAILBATCH" in t["text"] for t in inp["texts"]):
            raise ProviderError("unavailable", "scripted outage")
        results = []
        for t in inp["texts"]:
            sensitive, labs = labels_for(t["text"])
            results.append({"id": t["id"], "sensitive": sensitive, "labels": labs})
        return {"results": results}
    return handler


def m9_muse(handler=None, *steps):
    transport = ScriptedTransport()
    if steps:
        transport.queue("activity_classification", *steps)
    if handler:
        transport.on("activity_classification", handler)
    return FixtureMuse(register_activity_task(TaskRegistry()), transport), transport


def m10_muse(handler=None, *steps):
    transport = ScriptedTransport()
    if steps:
        transport.queue("sensitivity_screen", *steps)
    if handler:
        transport.on("sensitivity_screen", handler)
    return FixtureMuse(register_sensitivity_task(TaskRegistry()), transport), transport


# ------------------------------------------------------------ registration
def test_tasks_registered_with_contract_schemas():
    reg = register_sensitivity_task(register_activity_task(TaskRegistry()))
    m9 = reg.get("activity_classification", ACTIVITY_PROMPT_VERSION)
    m10 = reg.get("sensitivity_screen", SENSITIVITY_PROMPT_VERSION)
    assert m9.input_schema == pc.IN_SCHEMAS["activity_classification"]
    assert m9.output_schema == pc.OUT_SCHEMAS["activity_classification"]
    assert (m9.temperature, m9.max_output_tokens) == (0.0, 6000)
    assert m10.input_schema == pc.IN_SCHEMAS["sensitivity_screen"]
    assert m10.output_schema == pc.OUT_SCHEMAS["sensitivity_screen"]
    assert m10.temperature == 0.0
    # scratch eval task names / prompt versions are not used in production
    assert reg.get("safety_screen", "topics.exp.v1") is None
    assert reg.get("constellation_naming", "sens.exp.v1") is None


def test_enums_match_contract():
    assert ACTIVITY_TOPICS == pc.ACTIVITY_TOPICS
    assert STANCES == pc.STANCES
    assert SENSITIVITY_CATEGORIES == pc.SENSITIVITY_CATEGORIES
    assert BATCH_MAX <= pc.M9_IN["properties"]["texts"]["maxItems"]
    assert SENS_BATCH <= pc.M10_IN["properties"]["items"]["maxItems"]


# ------------------------------------------------------------ M9 validation
def test_validate_batch_rules():
    sent = ["a", "b", "c", "d", "e", "f"]
    out = {"results": [
        {"id": "a", "sensitive": False, "labels": [{"topic": "music", "stance": "positive"},
                                                   {"topic": "coffee", "stance": "neutral"},
                                                   {"topic": "film", "stance": "negative"}]},
        {"id": "b", "sensitive": True, "labels": [{"topic": "food", "stance": "positive"}]},
        {"id": "c", "sensitive": False, "labels": [{"topic": "art", "stance": "positive"}]},
        {"id": "c", "sensitive": False, "labels": [{"topic": "art", "stance": "positive"}]},  # duplicate
        {"id": "zz", "sensitive": False, "labels": [{"topic": "ai", "stance": "positive"}]},  # never sent
        {"id": "e", "sensitive": False, "labels": [{"topic": "religion", "stance": "positive"},  # off-enum
                                                   {"topic": "books", "stance": "loves"},        # bad stance
                                                   {"topic": "books", "stance": "neutral"}]},
        {"id": "f", "sensitive": False, "labels": [{"topic": "ai", "stance": "positive"},
                                                   {"topic": "vr", "stance": "positive"},
                                                   {"topic": "design", "stance": "positive"},
                                                   {"topic": "coding", "stance": "positive"}]},  # 4th ignored
    ]}
    v = validate_batch(sent, out)
    assert v.kept["a"] == ("coffee", "music")       # negative stance dropped
    assert v.kept["b"] == ()                         # sensitive drops the whole text
    assert v.kept["c"] == ()                         # duplicate id fails closed
    assert v.kept["d"] == ()                         # missing id: no labels
    assert v.kept["e"] == ("books",)                 # enum recheck
    assert v.kept["f"] == ("ai", "design", "vr")     # at most 3
    assert "zz" not in v.kept
    assert (v.unknown_ids, v.duplicate_ids, v.missing_ids, v.bad_labels, v.sensitive) == (1, 1, 1, 2, 1)


@pytest.mark.parametrize("output", [None, {}, {"results": "x"}, {"results": [1, None, "a"]}])
def test_validate_batch_garbage_gives_nothing(output):
    v = validate_batch(["a"], output)
    assert v.kept == {"a": ()}


def test_classify_end_to_end_keeps_only_safe_positive_labels():
    muse, _ = m9_muse(m9_handler())
    topics = run(ActivityClassifier(muse).classify([
        SECRET, "I hate jazz honestly", "the clinic moved my appointment, so no dining hall"]))
    assert topics == ["food", "gaming"]


def test_payload_has_random_ids_and_text_only():
    seen: list = []
    muse, transport = m9_muse(m9_handler(seen))
    classifier = ActivityClassifier(muse)
    run(classifier.classify([SECRET]))
    run(classifier.classify([SECRET]))
    assert len(seen) == 2
    for inp in seen:
        assert set(inp) == {"texts"}
        assert all(set(t) == {"id", "text"} for t in inp["texts"])
    assert seen[0]["texts"][0]["id"] != seen[1]["texts"][0]["id"]
    blob = json.dumps([c.user for c in transport.calls])
    for pid in PLAYER_IDS:
        assert pid not in blob
    assert "p-" not in json.dumps([t["id"] for i in seen for t in i["texts"]])


def test_batches_of_at_most_eight():
    seen: list = []
    muse, _ = m9_muse(m9_handler(seen))
    texts = [f"synthetic post {i} about board games" for i in range(20)]
    assert run(ActivityClassifier(muse).classify(texts)) == ["gaming"]
    assert sorted(len(i["texts"]) for i in seen) == [4, 8, 8]
    ids = [t["id"] for i in seen for t in i["texts"]]
    assert len(set(ids)) == 20  # every text its own random id


def test_blank_texts_are_not_sent():
    seen: list = []
    muse, _ = m9_muse(m9_handler(seen))
    assert run(ActivityClassifier(muse).classify(["", "   "])) == []
    assert seen == []


def test_provider_failure_returns_nothing_and_never_keywords():
    muse, _ = m9_muse(None, ProviderError("unavailable", "down"), ProviderError("unavailable", "down"))
    assert run(ActivityClassifier(muse).classify([SECRET])) == []
    muse, _ = m9_muse(None, ProviderError("unavailable", "down"), ProviderError("unavailable", "down"))
    result = run(ActivityTopics(muse).derive([SECRET]))
    assert result.topics == [] and result.source == "muse_unavailable"  # keywords would give food+gaming


def test_partial_batch_failure_returns_nothing():
    muse, _ = m9_muse(m9_handler())
    texts = [f"post {i} about board games" for i in range(8)] + ["FAILBATCH dining hall"]
    assert run(ActivityClassifier(muse).classify(texts)) == []


def test_malformed_output_twice_fails_closed():
    muse, _ = m9_muse(None, "not json", {"results": [{"id": "x"}]})
    assert run(ActivityClassifier(muse).classify([SECRET])) == []


def test_keyword_fallback_is_labeled_and_only_without_muse():
    assert not ActivityTopics(None).uses_muse
    result = run(ActivityTopics(None).derive([SECRET]))
    assert result.source == "keyword_fallback" and result.topics == ["food", "gaming"]
    assert run(ActivityTopics(None).derive([])).source == "no_texts"
    muse, _ = m9_muse(m9_handler())
    assert ActivityTopics(muse).uses_muse
    assert run(ActivityTopics(muse).derive([SECRET])).source == "muse"
    with pytest.raises(ValueError):
        ActivityClassifier(None)


def test_trace_notes_counts_only():
    muse, _ = m9_muse(None, {"results": []})
    run(ActivityClassifier(muse).classify([SECRET]))
    entries = json.dumps(muse.reasoning_trace.__dict__["_entries"], default=str)
    assert "missing_ids" in entries and "dining" not in entries


# ------------------------------------------------------------ route
@pytest.fixture
def stores(store, service):
    return AnswerStore(store, service), ModerationStore(store, service), ActivityStore(store)


def app_with(service, stores, muse):
    answers, _, activity = stores
    app = FastAPI()
    install_error_handlers(app)
    app.include_router(build_router(service, answers, activity=activity, activity_muse=muse), prefix="/api/v1")
    return app


def client(app):
    c = TestClient(app, base_url="https://testserver")
    assert c.post(f"/api/v1/communities/{COMMUNITY}/join", json=join_body()).status_code == 201
    return c


def body(texts):
    return {"useActivity": True, "groupIds": ["g-hackathon"], "eventIds": [], "friendIds": [], "texts": texts}


def dump(store):
    with store.tx() as conn:
        return json.dumps([dict(r) for r in conn.execute("SELECT * FROM activity_signals")])


def test_route_uses_muse_and_keeps_text_transient(service, stores, store, caplog):
    seen: list = []
    muse, transport = m9_muse(m9_handler(seen))
    c = client(app_with(service, stores, muse))
    caplog.set_level(logging.DEBUG)
    texts = [SECRET, "the clinic moved my appointment"]
    r = c.put("/api/v1/me/activity", json=body(texts))
    assert r.status_code == 200
    assert r.json() == {"useActivity": True, "topics": ["food", "gaming"]}
    assert r.headers["X-Topic-Source"] == "muse"
    assert len(seen) == 1
    for t in texts:
        assert t not in r.text and t not in caplog.text
    stored = dump(store)
    for fragment in ("dining hall", "board games", "private post", "clinic", "appointment"):
        assert fragment not in stored
    player = c.get("/api/v1/session").json()["player"]["playerId"]
    assert player not in json.dumps([x.user for x in transport.calls])


def test_route_provider_failure_stores_no_topics(service, stores, store):
    muse, _ = m9_muse(None, *[ProviderError("unavailable", "down")] * 2)
    c = client(app_with(service, stores, muse))
    r = c.put("/api/v1/me/activity", json=body([SECRET]))
    assert r.status_code == 200 and r.json()["topics"] == []
    assert r.headers["X-Topic-Source"] == "muse_unavailable"
    assert json.loads(json.loads(dump(store))[0]["topics"]) == []


def test_route_without_muse_uses_labeled_keyword_fallback(service, stores):
    c = client(app_with(service, stores, None))
    r = c.put("/api/v1/me/activity", json=body([SECRET]))
    assert r.json()["topics"] == ["food", "gaming"]
    assert r.headers["X-Topic-Source"] == "keyword_fallback"


def test_route_checks_consent_before_any_text_leaves(service, stores):
    seen: list = []
    muse, _ = m9_muse(m9_handler(seen))
    c = client(app_with(service, stores, muse))
    v = c.get("/api/v1/session").json()["consent"]["version"]
    c.patch("/api/v1/me/consent", json=consent_body(v, match=False))
    assert c.put("/api/v1/me/activity", json=body([SECRET])).status_code == 403
    off = c.put("/api/v1/me/activity", json={"useActivity": False, "texts": [SECRET]})
    assert off.json() == {"useActivity": False, "topics": []}
    assert seen == []


# ------------------------------------------------------------ M10
def m10_handler(seen: list | None = None, *, category=lambda text: "none"):
    def handler(inp):
        if seen is not None:
            seen.append(inp)
        if any("FAILBATCH" in i["text"] for i in inp["items"]):
            raise ProviderError("unavailable", "scripted outage")
        return {"results": [{"id": i["id"], "category": category(i["text"])} for i in inp["items"]]}
    return handler


def cat(text):
    return "mental_health" if "therapy" in text else "none"


def test_sensitivity_allows_only_none_in_order():
    muse, _ = m10_muse(m10_handler(category=cat))
    texts = ["The Late Breakfast Club", "Stars after therapy", "Sunday trail walkers"]
    assert run(SensitivityScreen(muse).allowed(texts)) == [True, False, True]
    assert run(SensitivityScreen(muse).is_allowed("Sunday trail walkers")) is True


def test_sensitivity_duplicate_missing_and_unknown_ids_block():
    def handler(inp):
        a, b, c = (i["id"] for i in inp["items"])
        return {"results": [{"id": a, "category": "none"}, {"id": a, "category": "none"},  # duplicate
                            {"id": "i000", "category": "none"},                             # never sent
                            {"id": c, "category": "none"}]}                                 # b missing
    muse, _ = m10_muse(handler)
    assert run(SensitivityScreen(muse).allowed(["one", "two", "three"])) == [False, False, True]


def test_sensitivity_duplicate_with_conflicting_categories_blocks():
    def handler(inp):
        i = inp["items"][0]["id"]
        return {"results": [{"id": i, "category": "none"}, {"id": i, "category": "religion"}]}
    muse, _ = m10_muse(handler)
    assert run(SensitivityScreen(muse).allowed(["Sunday crew"])) == [False]


def test_sensitivity_provider_error_or_no_muse_blocks_everything():
    muse, _ = m10_muse(None, *[ProviderError("unavailable", "down")] * 2)
    assert run(SensitivityScreen(muse).allowed(["a", "b"])) == [False, False]
    assert run(SensitivityScreen(None).allowed(["a", "b"])) == [False, False]
    muse, _ = m10_muse(None, "not json", "still not json")
    assert run(SensitivityScreen(muse).allowed(["a"])) == [False]


def test_sensitivity_batches_of_forty_and_one_failure_blocks_all():
    seen: list = []
    muse, _ = m10_muse(m10_handler(seen))
    texts = [f"label {i}" for i in range(85)]
    assert run(SensitivityScreen(muse).allowed(texts)) == [True] * 85
    assert sorted(len(i["items"]) for i in seen) == [5, 40, 40]
    muse, _ = m10_muse(m10_handler())
    assert run(SensitivityScreen(muse).allowed(texts + ["FAILBATCH"])) == [False] * 86


def test_sensitivity_unsendable_texts_block_and_are_not_sent():
    seen: list = []
    muse, _ = m10_muse(m10_handler(seen))
    assert run(SensitivityScreen(muse).allowed(["", "  ", "x" * 301, "ok text"])) == [False, False, False, True]
    assert [i["text"] for s in seen for i in s["items"]] == ["ok text"]
    assert run(SensitivityScreen(muse).allowed([])) == []


def test_sensitivity_payload_random_ids_and_text_only():
    seen: list = []
    muse, transport = m10_muse(m10_handler(seen))
    screen = SensitivityScreen(muse)
    run(screen.allowed(["Night owls"]))
    run(screen.allowed(["Night owls"]))
    assert all(set(i) == {"items"} and all(set(x) == {"id", "text"} for x in i["items"]) for i in seen)
    assert seen[0]["items"][0]["id"] != seen[1]["items"][0]["id"]
    blob = json.dumps([c.user for c in transport.calls])
    assert not any(pid in blob for pid in PLAYER_IDS)


def test_sensitivity_sync_helper_with_and_without_running_loop():
    muse, _ = m10_muse(m10_handler(category=cat))
    allowed = SensitivityScreen(muse).sync_allowed()
    assert allowed(["Breakfast club", "therapy pals"]) == [True, False]

    async def inside_loop():
        return allowed(["Breakfast club"])
    assert run(inside_loop()) == [True]


# ------------------------------------------------------------ snapshot questionId
QID_BY_DAY = {q["day"]: q["questionId"] for q in WEEK["dailyQuestions"]}


def save_week(store, answers):
    seed_synthetic_players(store)
    for a in WEEK["answers"]:
        answers.save({"answerId": f"a-{a['playerId']}-{a['day']}", "cycleId": "cycle-demo-w1", "day": a["day"],
                      "questionId": QID_BY_DAY[a["day"]], "playerId": a["playerId"], "text": a["text"],
                      "source": "text", "isCatchUp": a["isCatchUp"], "weight": 0.6 if a["isCatchUp"] else 1.0,
                      "followUpUsed": False, "createdAt": "2026-11-11T17:00:00Z", "editedAt": None,
                      "deletedAt": None}, "none")


def test_snapshot_answers_carry_stored_question_id(store, stores):
    answers, moderation, _ = stores
    save_week(store, answers)
    snap = PrivacyFormation(store, answers, moderation).prepare_formation("cycle-demo-w1", COMMUNITY).snapshot
    assert "questions" not in snap  # no source injected: never guessed
    assert all("questionId" not in a for a in snap["answers"])  # nothing to resolve it against (#62)
    texts = {q: f"Synthetic question text for {q}?" for q in QID_BY_DAY.values()}
    snap = PrivacyFormation(store, answers, moderation, question_texts=lambda c, k: texts) \
        .prepare_formation("cycle-demo-w1", COMMUNITY).snapshot
    by_text = {a["text"]: a["questionId"] for a in snap["answers"]}
    for a in WEEK["answers"]:
        assert by_text[a["text"]] == QID_BY_DAY[a["day"]]


def test_snapshot_questions_from_injected_source(store, stores):
    answers, moderation, _ = stores
    save_week(store, answers)
    texts = {q: f"Synthetic question text for {q}?" for q in QID_BY_DAY.values()}
    texts["q-unused"] = "Not answered by anyone this week?"
    texts[QID_BY_DAY[1]] = "x" * 141  # over the Question.text bound: dropped, not truncated
    calls = []

    def source(cycle_id, community_id):
        calls.append((cycle_id, community_id))
        return texts

    formation = PrivacyFormation(store, answers, moderation, question_texts=source)
    lease = formation.prepare_formation("cycle-demo-w1", COMMUNITY)
    qs = lease.snapshot["questions"]
    answered = {QID_BY_DAY[a["day"]] for a in WEEK["answers"]}
    assert calls == [("cycle-demo-w1", COMMUNITY)]
    assert {q["questionId"] for q in qs} == answered - {QID_BY_DAY[1]}
    tagged = {a.get("questionId") for a in lease.snapshot["answers"]}
    assert tagged - {None} == {q["questionId"] for q in qs}  # day-1 text dropped, so its answers carry no id
    assert all(set(q) == {"questionId", "text"} for q in qs)
    models = pytest.importorskip("server.matching.models")
    parsed = models.FormationSnapshot.from_dict(run(LeasedSnapshot(lease).formation_snapshot("cycle-demo-w1")))
    assert set(parsed.refs) == set(lease.snapshot["idMap"])


def test_snapshot_question_source_failure_propagates(store, stores):
    answers, moderation, _ = stores
    save_week(store, answers)

    def broken(cycle_id, community_id):
        raise RuntimeError("cycle store unavailable")

    with pytest.raises(RuntimeError):
        PrivacyFormation(store, answers, moderation, question_texts=broken).prepare_formation(
            "cycle-demo-w1", COMMUNITY)


# ---- D014 sign-off conditions: redaction before Muse (Patrik) ---------------
from server.privacy.guard import MODEL_TEXT_MAX_CHARS, redact_for_model  # noqa: E402
from server.privacy.topics import ActivityClassifier  # noqa: E402

PII_POST = ("Climbing with @jordan.k tonight! text me 765-555-0123 or jo.k@example.edu, "
            "pics at https://example.com/album and www.climb.gym, meet at 123 Main Street")


@pytest.mark.parametrize("raw,leaks", [
    ("ping @maya_22 about board games", ["@maya_22"]),
    ("email me: maya.k@example.edu", ["maya.k@example.edu"]),
    ("maya dot k at example dot com", ["example dot com"]),
    ("call (765) 555-0123 or +1 765 555 0123", ["555-0123", "555 0123"]),
    ("photos on https://example.com/x and example.io", ["https://example.com/x", "example.io"]),
    ("we live at 42 Elm Street", ["42 Elm Street"]),
    ("card 4111 1111 1111 1111", ["4111 1111 1111 1111"]),
])
def test_redact_removes_other_peoples_details(raw, leaks):
    out = redact_for_model(raw)
    for leak in leaks:
        assert leak.lower() not in out.lower(), out


def test_redact_keeps_topic_words_and_caps_length():
    assert redact_for_model("loved the jazz concert and coffee after") == "loved the jazz concert and coffee after"
    assert len(redact_for_model("music " * 1000)) == MODEL_TEXT_MAX_CHARS
    with pytest.raises(TypeError):
        redact_for_model(None)


def test_m9_payload_is_redacted_before_it_reaches_muse():
    seen = []

    class CaptureMuse:
        async def run(self, request):
            seen.append(request.payload)
            ids = [t["id"] for t in request.payload["texts"]]

            class R:
                output = {"results": [{"id": i, "sensitive": False,
                                       "labels": [{"topic": "sports", "stance": "positive"}]} for i in ids]}
            return R()

    topics = asyncio.run(ActivityClassifier(CaptureMuse()).classify([PII_POST]))
    sent = json.dumps(seen)
    for leak in ("@jordan.k", "765-555-0123", "jo.k@example.edu", "example.com", "climb.gym", "123 Main Street"):
        assert leak not in sent, leak
    assert "Climbing" in sent and topics == ["sports"]
