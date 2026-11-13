"""contracts/protocol.ts 3.0.0 v3 types match the v3 fixtures and the PRD privacy floors (R1-R3)."""

from __future__ import annotations

import base64
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = (ROOT / "contracts" / "protocol.ts").read_text(encoding="utf-8")
FIX = ROOT / "contracts" / "fixtures"


def load(name: str) -> dict:
    return json.loads((FIX / name).read_text(encoding="utf-8"))


def ts_keys(name: str) -> set[str]:
    match = re.search(r"export interface " + name + r"\b[^{]*\{", PROTOCOL)
    assert match, f"{name} missing from protocol.ts"
    depth, i = 1, match.end()
    while depth:
        depth += {"{": 1, "}": -1}.get(PROTOCOL[i], 0)
        i += 1
    body = re.sub(r"//[^\n]*", "", PROTOCOL[match.end():i - 1])
    body = re.sub(r"/\*.*?\*/", "", body, flags=re.S)
    for _ in range(3):
        body = re.sub(r"\{[^{}]*\}", "", body)
    return set(re.findall(r"(\w+)\??\s*:", body))


def ts_union(name: str) -> set[str]:
    match = re.search(r"export type " + name + r"\s*=([^;]*);", PROTOCOL)
    assert match, name
    return set(re.findall(r'"([^"]+)"', match.group(1)))


def test_version_is_3_0_0_and_fixtures_declare_it():
    assert 'CONTRACT_VERSION = "3.0.0"' in PROTOCOL
    for path in FIX.glob("v3-*.json"):
        assert load(path.name)["contractVersion"] == "3.0.0", path.name


def test_daily_view_keys_and_privacy():
    data = load("v3-daily-constellations.json")
    for view in (data["view"], data["pending"]):
        assert set(view) == ts_keys("DailyConstellationsView")
        for c in view["constellations"]:
            assert set(c) == ts_keys("DailyConstellationView")
            assert len(c["starIndices"]) >= 3 and view["myStarIndex"] in c["starIndices"]
    assert len(data["view"]["constellations"]) <= 3
    assert data["pending"]["constellations"] == []
    # sharedMeaning joined the daily view (guard-checked, null under 3 members); names and sizes stay out.
    assert not {"name", "label", "size"} & set(data["view"]["constellations"][0])
    for c in data["view"]["constellations"]:
        assert c["sharedMeaning"] is None or isinstance(c["sharedMeaning"], str)


def test_sky_views_and_second_degree_floor():
    data = load("v3-sky.json")
    assert set(data["stars"]) == ts_keys("SkyStarsView")
    for mine in (data["mine"], data["mineSmallCommunity"]):
        assert set(mine) == ts_keys("MySkyView")
        for group in mine["mine"] + mine["secondDegree"]:
            assert len(group["starIndices"]) >= 3  # R2 floor
    assert data["mineSmallCommunity"]["secondDegree"] == []  # R2: under 30 players


def test_progress_marker_is_consistent():
    data = load("v3-formation-progress.json")
    for ev in (data["trace"], data["visualization"]):
        assert set(ev) == ts_keys("ProgressEvent")
        assert ev["isVisualization"] == (ev["source"] == "visualization")
        for a in ev["attempts"]:
            assert set(a) == ts_keys("FormationAttempt")  # no scores, no reasons
            assert a["outcome"] in ts_union("ProgressPhase") | {"tried", "kept", "dropped"}


def test_main_uses_room_local_indices_and_size():
    data = load("v3-main.json")
    main = data["response"]["main"]
    assert set(main) == ts_keys("MainConstellationView")
    assert 3 <= len(main["roomIndices"]) <= 5 and main["myRoomIndex"] in main["roomIndices"]
    assert {a["index"] for a in main["anchors"]} == set(main["roomIndices"])
    assert "starIndices" not in main  # R1: never the sky index
    assert data["noMatch"] == {"main": None, "reason": "no_match"}
    assert data["noMatch"]["reason"] in ts_union("MainConstellationReason")


def test_event_buckets_are_bucketed_only():
    data = load("v3-event-nudge.json")
    buckets = ts_union("InterestBucket")
    assert buckets == {"3-5", "6-9", "10+"}
    for event in data["events"]:
        assert set(event) == ts_keys("EventView")
        assert event["constellationInterestBucket"] in buckets | {"none"}
    assert set(data["nudge"]) == ts_keys("EventNudgeView")
    assert data["nudge"]["interestBucket"] in buckets


def test_custom_event_and_invite_shapes():
    data = load("v3-custom-event.json")
    assert set(data["input"]) == ts_keys("CustomEventProposalIn")
    assert set(data["proposal"]) == ts_keys("CustomEventProposal")
    assert set(data["invite"]) == ts_keys("Invite")
    assert data["proposal"]["status"] == "pending" and data["invite"]["confirmAtCount"] == 3
    assert not {"memberIds", "playerIds", "answers"} & set(data["input"])


def test_formation_port_v3_methods_and_removed_items():
    port = PROTOCOL[PROTOCOL.index("export interface FormationPort"):]
    port = port[:port.index("\n}\n")]
    for method in ("dailyPlace", "closeDay", "weekGraph", "mainConstellation", "skyLayout"):
        assert method + "(" in port
    assert "computeSky" not in port and "form(" not in port
    for retired in ("SkyStats", "SkyTheme", "SyntheticSignal", "PrevalenceGuess", "M5In", "M8In"):
        assert re.search(r"@deprecated[^\n]*\n(?:.*\n)?export (interface|type) " + retired, PROTOCOL), retired


def test_stream_events_and_consent():
    for event in ("daily.updated", "day.closed", "formation.progress", "main.revealed",
                  "event.nudge", "invite.created"):
        assert f'"{event}"' in PROTOCOL
    assert "eventSignals" in ts_keys("Consent") and "answeredToday" in ts_keys("WeeklyCycle")
