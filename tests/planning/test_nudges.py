"""M7 event nudges over the fixture Muse and TEST-ONLY guard/chat doubles (offline)."""
from __future__ import annotations

import asyncio
import copy
import json
import unittest
from datetime import datetime, timezone

from server.planning import BankError, NudgeService, PlanningError, VenueCatalog, register_planning_tasks
from server.providers import MUSE_VOICE, ProviderError, TaskRegistry
from server.providers.fixture import FixtureMuse, ScriptedTransport, decode_user_message

from .doubles import FIXTURES, TestOnlyChat, TestOnlyOutputGuard

VENUES_DOC = json.loads((FIXTURES / "venues.json").read_text())
WEEK = json.loads((FIXTURES / "week-sample.json").read_text())
NOW = datetime(2026, 11, 18, 18, 0, tzinfo=timezone.utc)  # Wednesday mid-week
ANSWERS = [a["text"] for a in WEEK["answers"] if a["playerId"] in ("p-maya", "p-dev", "p-jordan")]
MEANING = "They end up having most meals on their own and would rather not."
GOOD = {
    "title": "Open mic night",
    "placeId": "v-cafe",
    "timeWindow": {"start": "2026-11-19T03:00:00Z", "end": "2026-11-19T05:00:00Z"},
    "why": "Low stakes, something to watch, and easy to leave whenever you like.",
}
EVENT_NUDGE_KEYS = {"nudgeId", "constellationId", "title", "placeId", "timeWindow", "why", "minAttendees", "evidence"}


def run(coro):
    return asyncio.run(coro)


class Context:
    def __init__(self, **over):
        self.rooms = {"c-1": {"constellationId": "c-1", "roomId": "room-orion", "sharedMeaning": MEANING,
                              "memberCount": 4, "roomOpen": True, "againstAnswers": list(ANSWERS), **over}}

    async def __call__(self, constellation_id):
        row = self.rooms.get(constellation_id)
        return dict(row) if row else None


def make(*steps, context=None):
    transport = ScriptedTransport()
    if steps:
        transport.queue("event_nudge", *steps)
    muse = FixtureMuse(register_planning_tasks(TaskRegistry()), transport)
    guard, chat, ctx = TestOnlyOutputGuard(), TestOnlyChat(), context or Context()
    ids = iter(f"{i:032x}" for i in range(1, 100))
    svc = NudgeService(muse, guard, VenueCatalog.load(), ctx, chat, now=lambda: NOW, new_id=lambda: next(ids))
    return svc, transport, guard, chat, ctx


def changed(**over):
    out = copy.deepcopy(GOOD)
    out.update(over)
    return out


class VenueCatalogTests(unittest.TestCase):
    def test_event_ids_are_the_approved_allowlist(self):
        catalog = VenueCatalog.load()
        self.assertEqual(catalog.event_ids(), {"ev-open-mic", "ev-volleyball", "ev-board-games", "ev-film-club"})
        self.assertEqual(catalog.event("ev-open-mic")["placeId"], "v-cafe")
        self.assertIsNone(catalog.event("ev-invented"))
        for e in catalog.events_between(datetime(2026, 11, 1, tzinfo=timezone.utc), datetime(2026, 12, 1, tzinfo=timezone.utc)):
            self.assertEqual(set(e), {"title", "placeId", "start"})

    def test_default_catalog_equals_shared_fixture(self):
        catalog = VenueCatalog.load()
        self.assertEqual(list(catalog.venues), VENUES_DOC["venues"])
        self.assertEqual(list(catalog.campus_events), VENUES_DOC["campusEvents"])
        self.assertTrue(all(v["isPublic"] is True for v in catalog.venues))

    def test_bad_catalogs_rejected(self):
        def doc(**over):
            d = copy.deepcopy(VENUES_DOC)
            d.update(over)
            return d

        private = copy.deepcopy(VENUES_DOC["venues"])
        private[0]["isPublic"] = False
        addressed = copy.deepcopy(VENUES_DOC["venues"])
        addressed[0]["address"] = "12 Elm St"
        bad = [
            doc(contractVersion="1.0.0"), doc(venues=[]), doc(venues=private), doc(venues=addressed),
            doc(venues=VENUES_DOC["venues"] + [VENUES_DOC["venues"][0]]),
            doc(campusEvents=[{"eventId": "ev-party", "title": "House party", "placeId": "v-someones-flat", "start": "2026-11-19T03:00:00Z"}]),
            doc(campusEvents=[{"eventId": "ev-mic", "title": "Open mic", "placeId": "v-cafe", "start": "Thursday evening"}]),
            doc(campusEvents=[{"title": "Open mic", "placeId": "v-cafe", "start": "2026-11-19T03:00:00Z"}]),           # no id
            doc(campusEvents=[{"eventId": "Open Mic!", "title": "Open mic", "placeId": "v-cafe", "start": "2026-11-19T03:00:00Z"}]),
            doc(campusEvents=[{"eventId": "ev-a", "title": "A", "placeId": "v-cafe", "start": "2026-11-19T03:00:00Z"},
                              {"eventId": "ev-a", "title": "B", "placeId": "v-rec", "start": "2026-11-19T04:00:00Z"}]),  # duplicate id
        ]
        for d in bad:
            with self.assertRaises(BankError):
                VenueCatalog.from_doc(d)


class NudgeTests(unittest.TestCase):
    def test_valid_proposal_becomes_event_nudge(self):
        svc, transport, guard, _, _ = make(GOOD)
        nudge = run(svc.propose("c-1"))
        self.assertEqual(set(nudge), EVENT_NUDGE_KEYS)
        self.assertEqual(nudge["minAttendees"], 3)
        self.assertEqual(nudge["placeId"], "v-cafe")
        self.assertEqual(nudge["constellationId"], "c-1")
        self.assertEqual(nudge["evidence"]["callType"], "M7")
        self.assertEqual(nudge["evidence"]["source"], "replay")
        self.assertEqual(set(nudge["evidence"]), {"model", "source", "generatedAt", "latencyMs", "callType"})
        # title, why and the final chat line were each guarded against answers + sharedMeaning
        self.assertEqual(len(guard.calls), 3)
        for _, against in guard.calls:
            self.assertEqual(against, [*ANSWERS, MEANING])

    def test_prompt_holds_meaning_venues_window_and_events_only(self):
        svc, transport, _, _, _ = make(GOOD)
        run(svc.propose("c-1"))
        sent = transport.calls[0]
        payload = decode_user_message(sent.user)["input"]
        self.assertEqual(set(payload), {"sharedMeaning", "venues", "window", "campusEvents"})
        self.assertEqual(payload["venues"], VENUES_DOC["venues"])
        self.assertEqual(payload["window"], {"start": "2026-11-18T18:00:00Z", "end": "2026-11-21T18:00:00Z"})
        self.assertEqual(payload["campusEvents"],
                         [{k: e[k] for k in ("title", "placeId", "start")} for e in VENUES_DOC["campusEvents"]
                          if "2026-11-18T18:00:00Z" <= e["start"] < "2026-11-21T18:00:00Z"])
        for answer in ANSWERS:
            self.assertNotIn(answer, sent.user + sent.developer)
        for private in ("room-orion", "c-1", "p-maya"):
            self.assertNotIn(private, sent.user)
        self.assertIn(MUSE_VOICE, sent.developer)

    def test_non_allowlisted_place_rejected(self):
        for place in ("v-someones-flat", "Maya's dorm", "V-CAFE", "v-cafe "):
            svc, _, _, chat, _ = make(changed(placeId=place))
            outcome = run(svc.propose_detailed("c-1"))
            self.assertIsNone(outcome.nudge, place)
            self.assertEqual(outcome.reason, "place_not_allowlisted")
            with self.assertRaises(PlanningError):
                run(svc.propose_and_post("c-1"))
            self.assertEqual(chat.posted, [])

    def test_bad_time_windows_rejected(self):
        cases = {
            "time_malformed": {"start": "Thursday 7pm", "end": "2026-11-19T05:00:00Z"},
            "time_length": {"start": "2026-11-19T03:00:00Z", "end": "2026-11-19T09:00:00Z"},
            "time_outside_window": {"start": "2026-11-25T03:00:00Z", "end": "2026-11-25T05:00:00Z"},
        }
        for reason, window in cases.items():
            svc, _, _, _, _ = make(changed(timeWindow=window))
            self.assertEqual(run(svc.propose_detailed("c-1")).reason, reason)
        svc, _, _, _, _ = make(changed(timeWindow={"start": "2026-11-19T05:00:00Z", "end": "2026-11-19T03:00:00Z"}))
        self.assertEqual(run(svc.propose_detailed("c-1")).reason, "time_length")
        svc, _, _, _, _ = make(changed(timeWindow={"start": "2026-11-18T17:00:00Z", "end": "2026-11-18T19:00:00Z"}))
        self.assertEqual(run(svc.propose_detailed("c-1")).reason, "time_outside_window")

    def test_text_must_pass_output_guard(self):
        quoting = "Come along, since you eat in my room so no one sees me alone anyway."
        cases = [
            changed(why=quoting),                                         # 5+ words of an answer
            changed(why="Good for people having most meals on their own and lonely."),  # sharedMeaning words
            changed(why="Easier than therapy, and it is free."),          # sensitive term
            changed(title="Text 555-0100 to join"),                       # contact info
            changed(why="Line one.\nLine two."),
        ]
        for out in cases:
            svc, _, _, chat, _ = make(out)
            outcome = run(svc.propose_detailed("c-1"))
            self.assertIsNone(outcome.nudge, out)
            self.assertIn(outcome.reason, ("guard_rejected_text", "text_shape"))

    def test_small_closed_or_unknown_constellation_gets_no_call(self):
        for ctx in (Context(memberCount=2), Context(roomOpen=False)):
            svc, transport, _, _, _ = make(GOOD, context=ctx)
            self.assertIsNone(run(svc.propose("c-1")))
            self.assertEqual(transport.calls, [])
        svc, transport, _, _, _ = make(GOOD)
        self.assertIsNone(run(svc.propose("c-unknown")))
        self.assertEqual(transport.calls, [])
        with self.assertRaises(PlanningError) as ctx_err:
            run(svc.propose_and_post("c-unknown"))
        self.assertEqual(ctx_err.exception.code, "NOT_FOUND")

    def test_provider_failure_yields_no_nudge_and_no_invented_fallback(self):
        svc, transport, _, chat, _ = make("not json", "{nope")
        outcome = run(svc.propose_detailed("c-1"))
        self.assertIsNone(outcome.nudge)
        self.assertEqual(outcome.reason, "provider_malformed_output")
        self.assertEqual(len(transport.calls), 2)  # exactly one retry
        svc, _, _, chat, _ = make(ProviderError("unavailable", "x", status=503))
        with self.assertRaises(PlanningError) as ctx:
            run(svc.propose_and_post("c-1"))
        self.assertEqual(ctx.exception.code, "PROVIDER_UNAVAILABLE")
        self.assertTrue(ctx.exception.retryable)
        self.assertEqual(chat.posted, [])

    def test_one_nudge_per_constellation(self):
        svc, transport, _, _, _ = make(GOOD, changed(title="Pickup soccer", placeId="v-rec"))
        first = run(svc.propose("c-1"))
        self.assertEqual(run(svc.propose("c-1")), first)
        self.assertEqual(len(transport.calls), 1)

    def test_post_once_as_muse_nudge_with_code_built_text(self):
        svc, _, _, chat, _ = make(GOOD)
        result = run(svc.propose_and_post("c-1"))
        room_id, message = chat.posted[0]
        self.assertEqual(room_id, "room-orion")
        self.assertEqual(set(message), {"roomId", "handle", "text", "kind"})
        self.assertEqual(message["kind"], "muse_nudge")
        self.assertEqual(message["handle"], "Muse")
        self.assertEqual(message["text"], "Open mic night at Campus Cafe, Wednesday 7pm-9pm. "
                         "Low stakes, something to watch, and easy to leave whenever you like. Go if 3 of you are in.")
        self.assertLessEqual(len(message["text"]), 500)
        self.assertEqual(result["message"]["moderation"], "visible")
        again = run(svc.propose_and_post("c-1"))
        self.assertEqual(again["message"], result["message"])
        self.assertEqual(len(chat.posted), 1)

    def test_room_closed_between_proposal_and_post(self):
        svc, _, _, chat, ctx = make(GOOD)
        run(svc.propose("c-1"))
        ctx.rooms["c-1"]["roomOpen"] = False
        with self.assertRaises(PlanningError) as err:
            run(svc.propose_and_post("c-1"))
        self.assertEqual(err.exception.code, "NOT_FOUND")
        self.assertEqual(chat.posted, [])


if __name__ == "__main__":
    unittest.main()


class CamelChatDouble:
    """TEST ONLY. Mirrors the input check in Kai's ChatService.postSystem
    (role/kai-orchestration b1192cb): exact keys, handle Muse, kind allowlist."""

    __test__ = False

    def __init__(self):
        self.posted = []

    async def postSystem(self, roomId, message):
        if (set(message) != {"roomId", "handle", "text", "kind"} or message["roomId"] != roomId
                or message["handle"] != "Muse" or message["kind"] not in {"system", "muse_nudge"}):
            raise ValueError("INVALID_INPUT")
        self.posted.append((roomId, dict(message)))
        return {**message, "messageId": "m-camel-1", "createdAt": "2026-11-18T18:00:01Z", "moderation": "visible"}


class ChatSystemPosterTests(unittest.TestCase):
    def test_nudge_posts_through_camel_case_chat_with_exact_keys(self):
        from server.planning import ChatSystemPoster

        transport = ScriptedTransport()
        transport.queue("event_nudge", GOOD)
        muse = FixtureMuse(register_planning_tasks(TaskRegistry()), transport)
        chat = CamelChatDouble()
        ids = iter(f"{i:032x}" for i in range(1, 100))
        svc = NudgeService(muse, TestOnlyOutputGuard(), VenueCatalog.load(), Context(),
                           ChatSystemPoster(chat), now=lambda: NOW, new_id=lambda: next(ids))
        out = run(svc.propose_and_post("c-1"))
        self.assertEqual(len(chat.posted), 1)
        room_id, message = chat.posted[0]
        self.assertEqual(room_id, "room-orion")
        self.assertEqual(message["kind"], "muse_nudge")
        self.assertEqual(out["message"]["messageId"], "m-camel-1")
        # Posting again for the same constellation does not post twice.
        run(svc.propose_and_post("c-1"))
        self.assertEqual(len(chat.posted), 1)

    def test_rejects_chat_without_post_system(self):
        from server.planning import ChatSystemPoster

        with self.assertRaises(TypeError):
            ChatSystemPoster(TestOnlyChat())


class NudgeSensitivityTests(unittest.TestCase):
    def test_sensitive_nudge_text_is_refused_and_screen_errors_fail_closed(self):
        class Screen:
            def __init__(self, ok=True, boom=False):
                self.ok, self.boom, self.seen = ok, boom, []

            async def allowed(self, texts):
                self.seen.append(list(texts))
                if self.boom:
                    raise RuntimeError("down")
                return [self.ok] * len(texts)

        for screen, expected in ((Screen(ok=True), "ok"), (Screen(ok=False), "sensitive_text"), (Screen(boom=True), "sensitive_text")):
            transport = ScriptedTransport().queue("event_nudge", GOOD)
            muse = FixtureMuse(register_planning_tasks(TaskRegistry()), transport)
            ids = iter(f"{i:032x}" for i in range(1, 100))
            svc = NudgeService(muse, TestOnlyOutputGuard(), VenueCatalog.load(), Context(), TestOnlyChat(),
                               now=lambda: NOW, new_id=lambda: next(ids), sensitivity=screen)
            out = run(svc.propose_detailed("c-1"))
            self.assertEqual(out.reason, expected)
            self.assertEqual(screen.seen, [[GOOD["title"], GOOD["why"]]])
