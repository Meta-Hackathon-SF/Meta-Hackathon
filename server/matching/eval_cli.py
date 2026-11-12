"""CLI for the offline matching evaluation.

    python -m server.matching.eval_cli --seed 7 --pools 50

Runs ONLY with the scripted FakeMusePort, so the output proves harness mechanics and
constraint safety, not Muse ranking quality. The label says so.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from typing import Optional, Sequence

from server.matching.evaluation import evaluate, generate_synthetic_pools

FIXTURE_LABEL = "fixture (fake Muse, not a quality result)"
DEFAULT_SEED = 7
DEFAULT_POOLS = 50


def build_port():
    """Hook for a live Muse port (Adam's adapter will implement it).

    Must return an object satisfying MusePortLike. Live results should be labeled
    separately from fixture runs. Not implemented here: no network or paid calls.
    """
    raise NotImplementedError("live Muse port is not wired yet")


def _parse(argv: Optional[Sequence[str]]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Offline Group Quests matching evaluation")
    p.add_argument("--seed", type=int, default=DEFAULT_SEED)
    p.add_argument("--pools", type=int, default=DEFAULT_POOLS)
    p.add_argument("--live", action="store_true", help="use build_port() (not implemented)")
    return p.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parse(argv)
    if args.live:
        try:
            build_port()
        except NotImplementedError as exc:
            print(f"--live unavailable: {exc}", file=sys.stderr)
            return 2
    from tests.matching.fixtures import FakeMusePort  # fixture-only dependency
    pools = generate_synthetic_pools(args.seed, args.pools)
    report = asyncio.run(evaluate(pools, FakeMusePort(), label=FIXTURE_LABEL))
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
