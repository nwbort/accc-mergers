"""Anchors for the two directories the pipeline resolves everything against.

Modules used to derive these inline with ``Path(__file__).parent...``, which
meant every module had to know how deep in ``scripts/`` it sat. Importing them
from here instead keeps that knowledge in one place, so moving a module between
sub-packages does not silently repoint its data paths.
"""

from pathlib import Path

#: The ``scripts/`` package directory.
SCRIPTS_DIR = Path(__file__).resolve().parent

#: The repository root — ``data/``, ``frontend/`` etc. hang off this.
REPO_ROOT = SCRIPTS_DIR.parent
