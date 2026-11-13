"""Manual live smoke check: ONE real Muse ``clarify`` (M2) call on a SYNTHETIC answer.

    python3 -m server.providers.smoke        # reads server/providers/muse.env if present

Not part of the offline test suite (costs a paid call). Prints only sanitized
metadata: evidence (callType, provider-reported model, latency, source),
attempts and whether a follow-up was proposed. The model's text is not printed.
Exit code 0 = validated live response, 2 = not configured, 1 = provider error.
"""
from __future__ import annotations

import asyncio
import json
import sys
import uuid

from . import MuseRequest, ProviderError, TaskRegistry, build_muse_adapter, contract_spec, load_muse_config
from .config import DEFAULT_ENV_FILE, load_env_file
from .voice import MUSE_VOICE

SMOKE_PROMPT_VERSION = "clarify.smoke.v1"
SMOKE_INSTRUCTIONS = (
    "Task: decide whether one short, gentle follow-up question would help us "
    "understand this player's answer to the daily question. Set needsFollowup "
    "false and question \"\" when the answer is already clear.\n\n" + MUSE_VOICE
)
SYNTHETIC_PAYLOAD = {
    "question": "Where did you eat most of your meals this week, and who was usually around?",
    "answer": {"id": "smoke-synthetic", "text": "Synthetic test answer: mostly the dining hall, corner table."},
}


async def main() -> int:
    load_env_file()  # optional git-ignored server/providers/muse.env
    try:
        config = load_muse_config()
    except ValueError as exc:
        print(json.dumps({"status": "invalid_config", "message": str(exc)}))
        return 2
    if config is None:
        print(json.dumps({"status": "not_configured",
                          "hint": f"set MUSE_API_KEY in {DEFAULT_ENV_FILE} or the environment"}))
        return 2
    records: list[dict] = []
    registry = TaskRegistry()
    registry.register(contract_spec("clarify", SMOKE_PROMPT_VERSION, SMOKE_INSTRUCTIONS, max_output_tokens=4000))
    muse = build_muse_adapter(registry, config, telemetry=records.append)
    try:
        result = await muse.run(MuseRequest(
            task="clarify", request_id=f"smoke-{uuid.uuid4().hex[:8]}",
            prompt_version=SMOKE_PROMPT_VERSION, payload=SYNTHETIC_PAYLOAD,
        ))
    except ProviderError as exc:
        print(json.dumps({"status": "error", "kind": exc.kind, "code": exc.api_code,
                          "retryable": exc.retryable, "message": exc.message, "telemetry": records}))
        return 1
    print(json.dumps({
        "status": "ok",
        "config": config.describe(),
        "evidence": result.evidence,
        "attempts": result.attempts,
        "needsFollowup": result.output["needsFollowup"],
        "telemetry": records,
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
