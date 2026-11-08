"""Write ``data/manifest.json``: a fingerprint of every merger and industry file.

The Android app's background check follows a handful of mergers and used to
ask for each one's detail file every couple of hours, plus ``mergers/list.json``
(~115 KB gzipped, changed by any edit anywhere on the register) just to spot
new filings. This one file answers both questions in a single conditional
request:

* ``mergers`` maps each merger id to a short hash of its detail file's bytes,
  so a client holding a copy can tell whether it is current without asking.
  A new id is a new filing.
* ``industries`` does the same for each ``industries/{division}.json`` file
  (keyed by its stem, ``G`` or ``_orphans``), for followed industries.
* ``phase2_current`` lists the matters currently in Phase 2, so the app's
  "follow every Phase 2 matter" option doesn't need ``phase2.json``.

When nothing on the site has changed, the manifest's ETag answers with an
empty 304 and the check stops there.

Run by ``scripts/build.sh`` against the built ``frontend/dist/data`` — so the
hashes describe exactly the bytes being deployed — and never committed: it
would change on every pipeline run for no reader of the repo. It costs one
file of the Pages deployment's 20,000.

The hash is the first ``HASH_LENGTH`` hex digits of the SHA-256 of the file's
bytes. The app recomputes it from its cached copy (``data/Manifest.kt`` in
nwbort/accc-mergers-app), so the two must agree: change both or neither.

    python -m scripts.generate.data_manifest frontend/dist/data
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

# Bump when the shape changes in a way an older app can't read.
FORMAT = 1

# 48 bits: collisions between two versions of one file are not a concern.
HASH_LENGTH = 12

MANIFEST_NAME = "manifest.json"

_DETAIL_FILE_RE = re.compile(r"^(MN|WA)-\d+\.json$", re.IGNORECASE)


def file_hash(data: bytes) -> str:
    """The short content hash the app compares its cached copy against."""
    return hashlib.sha256(data).hexdigest()[:HASH_LENGTH]


def build_manifest(data_dir: Path) -> dict:
    """The manifest for the data files under *data_dir*."""
    mergers_dir = data_dir / "mergers"
    mergers = {
        path.stem: file_hash(path.read_bytes())
        for path in sorted(mergers_dir.glob("*.json"))
        if _DETAIL_FILE_RE.match(path.name)
    }

    industries = {
        path.stem: file_hash(path.read_bytes())
        for path in sorted((data_dir / "industries").glob("*.json"))
    }

    phase2 = json.loads((data_dir / "phase2.json").read_text(encoding="utf-8"))
    phase2_current = [
        m["merger_id"] for m in phase2.get("current", []) if m.get("merger_id")
    ]

    return {
        "format": FORMAT,
        "mergers": mergers,
        "industries": industries,
        "phase2_current": phase2_current,
    }


def write_manifest(data_dir: Path) -> Path:
    """Write the manifest into *data_dir* and return its path."""
    manifest = build_manifest(data_dir)
    if not manifest["mergers"]:
        # An empty manifest would read to the app as every merger having gone.
        raise SystemExit(f"No merger detail files under {data_dir / 'mergers'}")
    out = data_dir / MANIFEST_NAME
    out.write_text(json.dumps(manifest, separators=(",", ":")), encoding="utf-8")
    return out


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("data_dir", type=Path, help="the built data directory, e.g. frontend/dist/data")
    args = parser.parse_args(argv)
    out = write_manifest(args.data_dir)
    print(f"Wrote {out} ({out.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
