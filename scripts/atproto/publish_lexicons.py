"""Publish the ``fyi.mergers.*`` schemas so the records below them resolve.

An NSID's authority is its domain reversed, so ``fyi.mergers.matter`` is
answerable only by whoever controls ``mergers.fyi``. Resolution runs
domain -> DID -> schema: a ``_lexicon.mergers.fyi`` DNS TXT record names the
DID, and the DID's repo carries one ``com.atproto.lexicon.schema`` record per
NSID, keyed by the NSID itself. This writes that second half; the DNS record
is a one-off, and the run prints exactly what it has to say.

Usage:
    python -m scripts.atproto.publish_lexicons [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from scripts.atproto import config
from scripts.atproto.client import XrpcError
from scripts.atproto.connect import open_client


def load_lexicons(directory: Path | None = None) -> list[dict]:
    """Read and check every lexicon file, sorted by NSID."""
    directory = Path(directory) if directory else config.LEXICON_DIR
    lexicons = []
    for path in sorted(directory.glob("*.json")):
        lexicon = json.loads(path.read_text(encoding="utf-8"))
        validate_lexicon(lexicon, path)
        lexicons.append(lexicon)
    return lexicons


def validate_lexicon(lexicon: dict, path: Path) -> None:
    """Fail loudly on the three mistakes that are invisible once published.

    A schema whose ``id`` disagrees with its filename, or sits under an
    authority the site does not control, publishes fine and then resolves to
    nothing (or to somebody else). Catching that here is the difference
    between a failed run and a collection of records nobody can validate.
    """
    nsid = lexicon.get("id")
    if nsid != path.stem:
        raise ValueError(f"{path.name}: lexicon id {nsid!r} does not match the filename")
    if lexicon.get("lexicon") != 1:
        raise ValueError(f"{path.name}: expected \"lexicon\": 1")
    if not nsid.startswith(f"{config.NSID_AUTHORITY}."):
        raise ValueError(
            f"{path.name}: {nsid!r} is outside the {config.NSID_AUTHORITY} authority, "
            "which is the only one mergers.fyi can answer for"
        )
    if not lexicon.get("defs"):
        raise ValueError(f"{path.name}: no defs")


def schema_record(lexicon: dict) -> dict:
    """The ``com.atproto.lexicon.schema`` record carrying one lexicon."""
    return {"$type": config.SCHEMA_COLLECTION, **lexicon}


def dns_instructions(lexicons: list[dict]) -> list[str]:
    """The DNS TXT records the published schemas need to be resolvable.

    One per authority prefix: NSIDs differing only in their final segment
    share an authority and so share a record.
    """
    identity = config.load_identity()
    did = identity.did or "<the DID in atproto/identity.json>"
    authorities = sorted({nsid.rsplit(".", 1)[0] for nsid in (lex["id"] for lex in lexicons)})
    return [
        f'_lexicon.{".".join(reversed(authority.split(".")))}  TXT  "did={did}"'
        for authority in authorities
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate the lexicons and print what would be written.",
    )
    args = parser.parse_args(argv)

    lexicons = load_lexicons()
    if not lexicons:
        print("No lexicons to publish.", file=sys.stderr)
        return 0

    print(f"{len(lexicons)} lexicon(s): {', '.join(lex['id'] for lex in lexicons)}")
    for line in dns_instructions(lexicons):
        print(f"  needs DNS: {line}")

    if args.dry_run:
        return 0

    opened = open_client()
    if opened is None:
        return 0
    client, _ = opened

    written = 0
    for lexicon in lexicons:
        nsid = lexicon["id"]
        record = schema_record(lexicon)
        existing = client.get_record(config.SCHEMA_COLLECTION, nsid)
        if existing and existing.get("value") == record:
            print(f"  unchanged  {nsid}")
            continue
        try:
            client.put_record(config.SCHEMA_COLLECTION, nsid, record)
        except XrpcError as exc:
            print(f"  FAILED     {nsid}: {exc}", file=sys.stderr)
            return 1
        print(f"  published  {nsid}")
        written += 1

    print(f"Published {written} lexicon(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
