"""Manual live smoke check: ONE real Muse extraction call on a SYNTHETIC transcript.

    MUSE_API_KEY=... python3 -m server.providers.smoke

Not part of the offline test suite (costs a paid call). Prints only sanitized
metadata: model id reported by the provider, latency, attempts, missing fields.
Exit code 0 = validated live response, 2 = not configured, 1 = provider error.
"""
from __future__ import annotations

import asyncio
import json
import sys
import uuid

from server.planning import Area, CommunityContext, IntentExtractor, PlanningError, register_planning_tasks
from server.providers import TaskRegistry, build_muse_adapter, load_muse_config

SYNTHETIC_TRANSCRIPT = (
    "Synthetic test note: I'd like to meet a few people who like board games. "
    "I'm free Saturday between 2 and 5pm near North Campus, free activities only, about an hour."
)


async def main() -> int:
    config = load_muse_config()
    if config is None:
        print(json.dumps({"status": "not_configured", "hint": "set MUSE_API_KEY (or MODEL_API_KEY)"}))
        return 2
    records: list[dict] = []
    muse = build_muse_adapter(register_planning_tasks(TaskRegistry()), config, telemetry=records.append)
    extractor = IntentExtractor(muse)
    community = CommunityContext("c-smoke-synthetic", [Area("area-north", "North Campus")], "USD", "America/Los_Angeles")
    consent = {"communityId": community.community_id, "modelProcessing": True, "revokedAt": None}
    try:
        outcome = await extractor.extract(transcript=SYNTHETIC_TRANSCRIPT, community=community,
                                          consent=consent, request_id=f"smoke-{uuid.uuid4().hex[:8]}")
    except PlanningError as exc:
        print(json.dumps({"status": "error", "code": exc.code, "retryable": exc.retryable,
                          "message": exc.message, "telemetry": records}))
        return 1
    r = outcome.result
    print(json.dumps({
        "status": "ok",
        "config": config.describe(),
        "evidence": r["evidence"],
        "missingFields": r["missingFields"],
        "extractedFieldCount": 6 - len(r["missingFields"]),
        "rejectedByValidator": outcome.rejected,
        "telemetry": records,
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
