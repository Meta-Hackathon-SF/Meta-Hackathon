"""Shared harness for the live reasoning evals. MANUAL and PAID: never part of pytest.

    PYTHONPATH=. python tests/providers/live_evals/formation/e1.py   # needs server/providers/muse.env
    # from a script in a subfolder:
    import sys; sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from evalkit import live_port, ledger_total

    port = live_port(agent="A-formation", model="muse-wonder-1.0", effort="low", cap_usd=2.0)
    result = await port.run(MuseRequest(...))   # same MusePort as the app

Every call (live) is appended to ledger.jsonl as counts only: agent, model, task,
promptVersion, outcome, attempts, latencyMs, tokens, estCostUsd. Never payloads or
outputs. Before each call the agent's spend and the GLOBAL spend are checked;
over a cap -> BudgetExceeded, no call is made.
"""
from __future__ import annotations

import json
import os
import tempfile
import threading
from pathlib import Path

from server.providers import TaskRegistry, build_muse_adapter
from server.providers.config import MuseConfig, load_env_file, load_muse_config

# Outside the repo by default; the 2026-11-13 run's ledger is committed as ledger-2026-11-13.jsonl.
LEDGER = Path(os.environ.get("MUSE_EVAL_LEDGER", Path(tempfile.gettempdir()) / "muse-eval-ledger.jsonl"))
GLOBAL_CAP_USD = 4.50
_lock = threading.Lock()


class BudgetExceeded(RuntimeError):
    pass


def _rows():
    if not LEDGER.exists():
        return []
    return [json.loads(line) for line in LEDGER.read_text().splitlines() if line.strip()]


def ledger_total(agent: str | None = None) -> float:
    return round(sum(r.get("estCostUsd") or 0.0 for r in _rows() if agent is None or r.get("agent") == agent), 6)


def ledger_calls(agent: str | None = None) -> int:
    return sum(1 for r in _rows() if agent is None or r.get("agent") == agent)


def _base_config() -> MuseConfig:
    load_env_file()
    cfg = load_muse_config()
    if cfg is None:
        raise RuntimeError("no Muse key configured")
    return cfg


class _CappedPort:
    def __init__(self, agent: str, adapter, cap_usd: float):
        self._agent, self._adapter, self._cap = agent, adapter, cap_usd
        self.reasoning_trace = adapter.reasoning_trace
        self.configured = adapter.configured

    async def run(self, request):
        with _lock:
            if ledger_total() >= GLOBAL_CAP_USD:
                raise BudgetExceeded(f"global cap ${GLOBAL_CAP_USD} reached")
            if ledger_total(self._agent) >= self._cap:
                raise BudgetExceeded(f"{self._agent} cap ${self._cap} reached")
        return await self._adapter.run(request)


def live_port(*, agent: str, model: str, effort: str | None = "low", cap_usd: float,
              registry: TaskRegistry | None = None, timeout_s: float = 90.0, max_attempts: int = 2):
    """A real MuseAdapter for ``model`` behind the shared budget cap."""
    base = _base_config()
    cfg = MuseConfig(api_key=base.api_key, model=model, base_url=base.base_url,
                     timeout_s=timeout_s, max_attempts=max_attempts, reasoning_effort=effort)
    reg = registry if registry is not None else TaskRegistry()

    def sink(record):
        row = {"agent": agent, **{k: record.get(k) for k in (
            "model", "task", "promptVersion", "outcome", "attempts", "latencyMs",
            "inputTokens", "outputTokens", "reasoningTokens", "estCostUsd")}}
        row["requestedModel"] = model
        row["effort"] = effort
        with _lock, LEDGER.open("a") as fh:
            fh.write(json.dumps(row) + "\n")

    adapter = build_muse_adapter(reg, cfg, telemetry=sink)
    return _CappedPort(agent, adapter, cap_usd), reg
