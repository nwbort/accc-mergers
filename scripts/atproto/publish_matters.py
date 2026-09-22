"""Publish every ACCC matter as a ``fyi.mergers.matter`` record.

One record per matter, keyed by the ACCC's own identifier, so a matter is
addressable as ``at://<did>/fyi.mergers.matter/MN-01016`` without a lookup -
the same trick the site plays with its URLs, and the reason anything else in
the ATmosphere can reference a specific Australian merger review at all.

Runs are incremental. ``data/processed/atproto_records.json`` holds the
content digest of each record as last written, so a pipeline run several times
a day rewrites only the handful of matters that actually moved. Matters that
leave the dataset are deleted from the collection, which keeps this in step
with the self-pruning generated data directories.

The state file is an optimisation and nothing more: ``putRecord`` is an
upsert, so losing it costs one full republish and no correctness.

Usage:
    python -m scripts.atproto.publish_matters [--dry-run] [--limit N]
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from scripts.atproto import config
from scripts.atproto.client import XrpcError
from scripts.atproto.connect import open_client
from scripts.atproto.records import (
    load_matters,
    matter_record,
    matter_rkey,
    record_digest,
)

STATE_VERSION = 1


def load_state(path: Path | None = None) -> dict:
    """Read the digest state, tolerating its absence and a version bump."""
    path = Path(path) if path else config.RECORD_STATE_PATH
    if not path.exists():
        return {"version": STATE_VERSION, "records": {}}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("version") != STATE_VERSION:
        # A format change means the digests can't be trusted; republishing
        # everything is cheap and correct, so don't try to migrate.
        return {"version": STATE_VERSION, "records": {}}
    payload.setdefault("records", {})
    return payload


def save_state(state: dict, path: Path | None = None) -> None:
    path = Path(path) if path else config.RECORD_STATE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    state["version"] = STATE_VERSION
    state["collection"] = config.MATTER_COLLECTION
    path.write_text(
        json.dumps(state, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def plan(matters: list[dict], state: dict, *, now: str) -> tuple[list[tuple[str, dict]], list[str]]:
    """Work out what to write and what to delete.

    Returns ``(writes, deletions)`` where each write is ``(rkey, record)``. A
    record whose digest is unchanged keeps the ``indexedAt`` it was first
    written with, which is what makes that field a real last-changed signal
    rather than a record of when the pipeline last ran.
    """
    known = state.get("records", {})
    writes: list[tuple[str, dict]] = []
    seen: set[str] = set()

    for matter in matters:
        rkey = matter_rkey(matter["merger_id"])
        seen.add(rkey)

        previous = known.get(rkey) or {}
        record = matter_record(matter, indexed_at=now)
        digest = record_digest(record)
        if previous.get("digest") == digest:
            continue
        writes.append((rkey, record))

    deletions = sorted(set(known) - seen)
    return writes, deletions


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Report the plan, write nothing.")
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Cap the records written this run (0 = no cap). Deletions are not capped.",
    )
    parser.add_argument(
        "--pause",
        type=float,
        default=0.2,
        help="Seconds between writes, to stay clear of the PDS rate limit.",
    )
    args = parser.parse_args(argv)

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    matters = load_matters()
    state = load_state()
    writes, deletions = plan(matters, state, now=now)

    if not state["records"] and matters:
        print(f"No publish state - this is a full first publish of {len(matters)} matters.")

    print(
        f"{len(matters)} matters: {len(writes)} to write, "
        f"{len(deletions)} to delete, {len(matters) - len(writes)} unchanged."
    )

    if args.limit and len(writes) > args.limit:
        print(f"Limiting to {args.limit} write(s) this run; the rest follow next run.")
        writes = writes[: args.limit]

    if args.dry_run:
        for rkey, _ in writes[:20]:
            print(f"  would write   {rkey}")
        for rkey in deletions[:20]:
            print(f"  would delete  {rkey}")
        return 0

    if not writes and not deletions:
        return 0

    opened = open_client(pause=args.pause)
    if opened is None:
        return 0
    client, _ = opened

    failures = 0
    try:
        for rkey, record in writes:
            try:
                result = client.put_record(config.MATTER_COLLECTION, rkey, record)
            except XrpcError as exc:
                print(f"  FAILED  {rkey}: {exc}", file=sys.stderr)
                failures += 1
                continue
            state["records"][rkey] = {
                "digest": record_digest(record),
                "indexedAt": record["indexedAt"],
                "cid": result.get("cid", ""),
            }

        for rkey in deletions:
            try:
                client.delete_record(config.MATTER_COLLECTION, rkey)
            except XrpcError as exc:
                print(f"  FAILED  delete {rkey}: {exc}", file=sys.stderr)
                failures += 1
                continue
            state["records"].pop(rkey, None)
    finally:
        # Always save: a run that dies halfway through several hundred writes
        # should resume, not start over.
        save_state(state)

    print(f"Wrote {len(writes) - failures} record(s), deleted {len(deletions)}.")
    if failures:
        print(f"{failures} write(s) failed.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
