"""Post-deploy route check: does every Muse task reach the model the router says?

    python -m server.providers.route_check            # table only, no calls (free)
    python -m server.providers.route_check --live     # one tiny call per task (~$0.05)

Live mode sends one fixed ping per task through the production router (same key,
routes, timeouts and fallbacks), with a throwaway prompt version, and reports the
model that actually served it, latency, attempts, whether it fell back and the
estimated cost. It never sends player data. Exit code 0 = every task answered on
its primary model, 1 = some task fell back or failed, 2 = no key or bad MUSE_ROUTES.
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
from typing import Any, Callable

from .config import load_env_file, load_muse_config
from .errors import ProviderError
from .port import TASKS, MuseRequest, TaskRegistry, TaskSpec
from .router import MuseRouter, routes_from_env

PROMPT_VERSION = "route_check.v1"
_IN = {"type": "object", "additionalProperties": False, "required": ["ping"],
       "properties": {"ping": {"type": "string", "minLength": 1, "maxLength": 20}}}
_OUT = {"type": "object", "additionalProperties": False, "required": ["ok"],
        "properties": {"ok": {"type": "boolean"}}}


def route_table(routes: dict[str, Any], base_model: str) -> list[dict[str, Any]]:
    rows = []
    for task in sorted(TASKS):
        r = routes.get(task)
        rows.append({"task": task,
                     "model": r.model if r else base_model,
                     "effort": r.effort if r else None,
                     "timeoutS": r.timeout_s if r else None,
                     "attempts": r.max_attempts if r else None,
                     "fallbacks": list(r.fallbacks) if r else [],
                     "routed": r is not None})
    return rows


def ping_registry() -> TaskRegistry:
    reg = TaskRegistry()
    for task in sorted(TASKS):
        reg.register(TaskSpec(task=task, prompt_version=PROMPT_VERSION,  # type: ignore[arg-type]
                              instructions='Health check. Reply with {"ok": true}.',
                              output_schema=_OUT, input_schema=_IN, schema_name="route_check",
                              max_output_tokens=400, temperature=None))
    return reg


async def check(router: MuseRouter, routes: dict[str, Any], *,
                clock: Callable[[], float] = time.monotonic) -> list[dict[str, Any]]:
    rows = []
    for task in sorted(TASKS):
        expected = routes[task].model if task in routes else None
        started = clock()
        row: dict[str, Any] = {"task": task, "expected": expected}
        try:
            result = await router.run(MuseRequest(task=task, request_id=f"route-check-{task}",  # type: ignore[arg-type]
                                                  prompt_version=PROMPT_VERSION, payload={"ping": "ok"}))
            row.update(served=result.evidence["model"], latencyMs=result.evidence["latencyMs"],
                       attempts=result.attempts, ok=True)
        except ProviderError as exc:
            row.update(served=None, error=exc.kind, ok=False)
        row["wallMs"] = int((clock() - started) * 1000)
        entry = next((e for e in router.reasoning_trace.list(limit=300) if e["requestId"] == f"route-check-{task}"), {})
        row["fellBack"] = any(c["code"].startswith("fallback_after") for c in entry.get("checks", []))
        row["estCostUsd"] = entry.get("estCostUsd")
        row["onPrimary"] = row["ok"] and (expected is None or row.get("served") == expected) and not row["fellBack"]
        rows.append(row)
    return rows


async def main(argv: list[str]) -> int:
    load_env_file()
    try:
        routes = routes_from_env()
        config = load_muse_config()
    except ValueError as exc:
        print(json.dumps({"status": "invalid_config", "message": str(exc)}))
        return 2
    base = config.model if config else "unconfigured"
    print(json.dumps({"routes": route_table(routes, base)}, indent=1))
    if "--live" not in argv:
        return 0
    if config is None:
        print(json.dumps({"status": "not_configured"}))
        return 2
    router = MuseRouter(ping_registry(), config, routes)
    rows = await check(router, routes)
    print(json.dumps({"check": rows, "totalEstCostUsd": round(sum(r["estCostUsd"] or 0 for r in rows), 5)}, indent=1))
    return 0 if all(r["onPrimary"] for r in rows) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:])))
