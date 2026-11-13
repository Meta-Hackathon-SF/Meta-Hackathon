"""contract.py must mirror contracts/protocol.ts 2.0.0 and accept the shared fixtures."""
from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

from server.providers import CALL_TYPES, IN_SCHEMAS, OUT_SCHEMAS, TASKS, contract_spec
from server.providers import contract as c
from server.providers.schema import SchemaViolation, validate

ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = (ROOT / "contracts" / "protocol.ts").read_text(encoding="utf-8")
FIXTURES = ROOT / "contracts" / "fixtures"


def ts_union(name: str) -> list[str]:
    body = re.search(rf"export type {name} =(.*?);", PROTOCOL, re.S)
    assert body, name
    return re.findall(r'"([^"]+)"', body.group(1))


def ts_interface_keys(name: str) -> set[str]:
    """Top-level keys of an interface, ignoring nested object literals and comments."""
    start = PROTOCOL.index(f"export interface {name} {{") + len(f"export interface {name} {{")
    depth, i = 1, start
    while depth:
        depth += {"{": 1, "}": -1}.get(PROTOCOL[i], 0)
        i += 1
    text = re.sub(r"//.*", "", PROTOCOL[start:i - 1])
    while re.search(r"\{[^{}]*\}", text):
        text = re.sub(r"\{[^{}]*\}", "", text)
    return set(re.findall(r"(\w+)\??:", text))


class ProtocolDriftTests(unittest.TestCase):
    def test_contract_version_is_current(self):
        self.assertIn('CONTRACT_VERSION = "2.1.0"', PROTOCOL)

    def test_task_list_and_call_types_match_protocol(self):
        tasks = ts_union("MuseTask")
        self.assertEqual(set(tasks), set(TASKS))
        self.assertEqual([CALL_TYPES[t] for t in tasks], ts_union("MuseCallType"))
        job_map = re.search(r"export interface MuseJobMap \{(.*?)\n\}", PROTOCOL, re.S).group(1)
        for task, in_name, out_name in re.findall(r"(\w+): \{ in: (\w+); out: (\w+) \}", job_map):
            self.assertEqual(in_name, CALL_TYPES[task] + "In")
            self.assertEqual(out_name, CALL_TYPES[task] + "Out")

    def test_top_level_keys_match_protocol_interfaces(self):
        for task in TASKS:
            m = CALL_TYPES[task]
            self.assertEqual(set(IN_SCHEMAS[task]["properties"]), ts_interface_keys(m + "In"), m + "In")
            self.assertEqual(set(OUT_SCHEMAS[task]["properties"]), ts_interface_keys(m + "Out"), m + "Out")

    def test_enums_match_protocol(self):
        self.assertEqual(list(c.QUESTION_CATEGORIES), ts_union("QuestionCategory"))
        self.assertEqual(list(c.SENSITIVITIES), ts_union("Sensitivity"))
        self.assertEqual(list(c.SAFETY_LEVELS), ts_union("SafetyLevel"))
        venue = re.search(r"export interface Venue \{(.*?)\}", PROTOCOL).group(1)
        self.assertEqual(list(c.VENUE_KINDS), re.findall(r'"([^"]+)"', venue))
        self.assertEqual(set(c.VENUE["properties"]), {"placeId", "name", "kind", "isPublic"})
        self.assertEqual(set(c.PROMPT_TEXT["properties"]), {"id", "text", "weight"})

    def test_every_contract_spec_registers(self):
        for task in TASKS:
            spec = contract_spec(task, "t.v1", "test")
            self.assertEqual(spec.schema_name, task)


class FixtureConformanceTests(unittest.TestCase):
    def test_venue_fixture_fits_m7_input(self):
        doc = json.loads((FIXTURES / "venues.json").read_text())
        payload = {
            "sharedMeaning": "People who end up eating on their own more than they planned to.",
            "venues": doc["venues"],
            "window": {"start": "2026-11-18T00:00:00Z", "end": "2026-11-21T00:00:00Z"},
            "campusEvents": doc["campusEvents"],
        }
        validate(payload, c.M7_IN)
        payload["venues"][0]["isPublic"] = False
        with self.assertRaises(SchemaViolation):
            validate(payload, c.M7_IN)

    def test_question_bank_rows_fit_m6_output_item(self):
        doc = json.loads((FIXTURES / "question-bank.json").read_text())
        item = c.M6_OUT["properties"]["questions"]["items"]
        for q in doc["questions"]:
            row = {k: q[k] for k in ("text", "category", "sensitivity", "signalTags", "followUpHint")}
            validate(row, item)

    def test_examples_accept_and_reject(self):
        validate({"flag": "distress", "reason": ""}, c.M1_OUT)
        validate({"needsFollowup": False, "question": ""}, c.M2_OUT)
        validate({"themes": [], "answers": [{"id": "a", "text": "t", "weight": 0.6}],
                  "blockedPairs": [["a", "b"]]}, c.M4_IN)
        validate({"eligiblePlayers": 7, "constellations": 2, "themes": [
            {"label": "x", "count": 4, "actualPercent": 57, "guessedPercentMedian": 12}]}, c.M8_IN)
        bad = [
            ({"flag": "severe", "reason": ""}, c.M1_OUT),
            ({"needsFollowup": "yes", "question": ""}, c.M2_OUT),
            ({"themes": [], "answers": [{"id": "a", "text": "t"}], "blockedPairs": [["a"]]}, c.M4_IN),
            ({"sharedMeaning": "x", "size": 6}, c.M5_IN),
            ({"sharedMeaning": "x", "size": 4, "memberNames": ["Maya"]}, c.M5_IN),
            ({"answer": {"id": "a", "text": "t", "playerId": "p-maya"}, "question": "q"}, c.M2_IN),
            ({"questions": [{"text": "Too short", "category": "routine", "sensitivity": "low",
                             "signalTags": ["x"], "followUpHint": None}]}, c.M6_OUT),
            ({"questions": [{"text": "A long enough question to ask?", "category": "routine",
                             "sensitivity": "high", "signalTags": ["x"], "followUpHint": None}]}, c.M6_OUT),
        ]
        for value, schema in bad:
            with self.assertRaises(SchemaViolation, msg=str(value)):
                validate(value, schema)


if __name__ == "__main__":
    unittest.main()
