"""Puts the repository root on ``sys.path`` for the test run.

The tests import the pipeline as a package (``from scripts.cutoff import
...``), so the directory *above* ``scripts/`` has to be importable. pytest
already prepends it when it walks up past ``scripts/__init__.py``, but doing
it here as well means ``pytest scripts/tests/...`` works from any working
directory, not just the repo root.
"""

import sys
from pathlib import Path

REPO_ROOT = str(Path(__file__).resolve().parents[2])
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)
