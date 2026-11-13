"""The web copy of the approved venue list must equal the server catalog."""
from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TS = ROOT / "web/src/features/constellations/nudges/venues.ts"
CATALOG = ROOT / "server/planning/data/venues.json"
ROW = re.compile(
    r"\{\s*placeId:\s*'([^']+)',\s*name:\s*'([^']+)',\s*kind:\s*'([^']+)',\s*isPublic:\s*(true|false)\s*\}"
)


class WebVenueCopyTests(unittest.TestCase):
    def test_web_venues_equal_server_catalog(self):
        rows = [
            {"placeId": p, "name": n, "kind": k, "isPublic": pub == "true"}
            for p, n, k, pub in ROW.findall(TS.read_text())
        ]
        self.assertEqual(rows, json.loads(CATALOG.read_text())["venues"])


if __name__ == "__main__":
    unittest.main()
