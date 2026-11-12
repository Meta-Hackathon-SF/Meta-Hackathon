"""Make the repository root importable so tests can use `server.*` and `tests.matching.*`."""
import sys
from pathlib import Path

REPO_ROOT = str(Path(__file__).resolve().parents[2])

if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)
