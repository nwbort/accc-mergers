"""Build the data bundle the accc-mergers-cli companion tool is made from.

Called from :func:`scripts.generate.generate_static_data.main` with what that
run has just built in memory: the enriched merger records, the questionnaire
payloads, the parsed NOCC summaries, and the ``stats.json`` and
``industries.json`` payloads. Writes three files under ``data/output/cli/``:

``cli-manifest.json``
    The version counter and bundle checksum. The only one of the three tracked
    in git: it is how a run knows whether the bundle changed since the last
    one, and what version to stamp next. ``pipeline.yml`` publishes
    ``cli.sqlite`` exactly when a commit changes this file.

``cli-bundle.json``
    Every merger, questionnaire and NOCC summary plus stats and industries, in
    one file. Gitignored: ``build_cli_sqlite.py`` turns it into the
    ``cli.sqlite`` that ships on the orphan ``cli-dist`` branch, in the same job.

``cli-merger-manifest.json``
    ``{merger_id: sha256}`` of every record, for a not-yet-implemented
    per-record sync. Gitignored, and rewritten only when the version is bumped.

The mergers are the *full* enriched records, not the deployed per-merger files:
those carry only what the site renders (``enrichment.slim_for_site``), while
the CLI indexes everything (see ``build_cli_sqlite``'s ``raw_json`` column).
Determination text is cleaned of PDF layout newlines on the way in
(:mod:`scripts.parse.determination_text`), since the CLI has no rendering layer
to do it.

The manifest changes only when the bundle's bytes do. The bundle is serialised
deterministically (records ordered by ``merger_id``, questionnaires and NOCCs
keyed and key-sorted), so an unchanged dataset is a byte-identical bundle and
the version stays put. This replaced ``generate-cli-data.sh`` (bash, jq and
inline Python, reading a 10.8 MB ``data/output/mergers.json`` written moments
earlier by the same run) and reproduces its bundle byte for byte, so the switch
did not bump the version.

Modes (``generate_static_data --cli-bundle``):

``update`` (the default)
    Bump the version and rewrite the manifest when the bundle changed. The
    bundle itself is always written, so a local run leaves one to build from.
``force``
    Bump the version even when nothing changed.
``republish``
    Never touch the manifest; write the bundle for ``build_cli_sqlite`` to
    publish at the version main already records. Used by the manual
    ``publish-cli-sqlite.yml``, which regenerates from a fresh checkout: a
    regeneration on a later day can legitimately differ from the bundle that
    version was stamped on (date-relative fields such as a court listing
    passing), so a mismatch warns rather than fails. Bumping instead would mint
    a version main never records, which the next pipeline run would then
    stamp on different content.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from scripts.parse.determination_text import clean_merger
from scripts.paths import REPO_ROOT

BUNDLE_DIR = REPO_ROOT / "data" / "output" / "cli"
BUNDLE_FILE = "cli-bundle.json"
MANIFEST_FILE = "cli-manifest.json"
MERGER_MANIFEST_FILE = "cli-merger-manifest.json"

MODES = ("update", "force", "republish")


@dataclass
class Result:
    """What :func:`write` did."""

    version: int
    bundle_sha256: str
    changed: bool  # the bundle differs from the one the manifest records
    bumped: bool  # the manifest was rewritten with a new version
    merger_count: int


def nocc_records(nocc_data: dict) -> dict[str, dict]:
    """The NOCC summaries the bundle carries, keyed by merger id.

    Entries without parsed sections (including parse errors, which carry only
    ``error`` and ``file_path``) are skipped. A matter with several distinct
    summaries (a re-issue) also lists them all, latest first, under
    ``all_noccs``.
    """
    records = {}
    for merger_id, data in nocc_data.items():
        if not data.get("sections"):
            continue
        record = _nocc_record(data)
        all_noccs = data.get("all_noccs", [])
        if len(all_noccs) > 1:
            record["all_noccs"] = [_nocc_record(n) for n in all_noccs if n.get("sections")]
        records[merger_id] = record
    return records


def _nocc_record(data: dict) -> dict:
    return {
        "title": data.get("title"),
        "matter_id": data.get("matter_id"),
        "document_type": data.get("document_type"),
        "date": data.get("date"),
        "date_iso": data.get("date_iso"),
        "file_name": data.get("file_name"),
        "file_path": data.get("file_path"),
        "sections": data.get("sections", []),
    }


def _copy(value):
    """A deep, JSON-normalised copy, so cleaning never touches the caller's data."""
    return json.loads(json.dumps(value))


def _keyed(records: dict[str, dict]) -> dict:
    """``records`` with every key, at every depth, in sorted order."""
    return json.loads(json.dumps(records, sort_keys=True))


def build_bundle(
    mergers: list[dict],
    questionnaires: dict[str, dict],
    noccs: dict[str, dict],
    stats,
    industries,
) -> dict:
    """Assemble the bundle. ``mergers`` is left unmodified."""
    records = sorted((_copy(m) for m in mergers), key=lambda m: m.get("merger_id") or "")
    for record in records:
        clean_merger(record)
    return {
        "mergers": records,
        "questionnaires": _keyed(questionnaires),
        "noccs": _keyed(noccs),
        "stats": _copy(stats),
        "industries": _copy(industries),
    }


def serialise(bundle: dict) -> bytes:
    """The bundle's bytes, which its checksum (and so its version) is taken over."""
    return (json.dumps(bundle, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def merger_checksums(mergers: list[dict]) -> dict[str, str]:
    """``{merger_id: sha256}`` of each record serialised on its own.

    Hashed uncleaned, in the form a merger file is written in (``indent=2``),
    so a record's checksum depends only on the record.
    """
    return {
        m["merger_id"]: hashlib.sha256(json.dumps(m, indent=2).encode()).hexdigest()
        for m in mergers
        if m.get("merger_id")
    }


def _read_manifest(path: Path) -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def _write_bytes(path: Path, data: bytes) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


def _write_json(path: Path, payload) -> None:
    _write_bytes(path, (json.dumps(payload, indent=2) + "\n").encode("utf-8"))


def _warn(message: str) -> None:
    prefix = "::warning::" if os.environ.get("GITHUB_ACTIONS") else "WARNING: "
    print(prefix + message)


def write(
    mergers: list[dict],
    questionnaires: dict[str, dict],
    noccs: dict[str, dict],
    stats,
    industries,
    *,
    mode: str = "update",
    out_dir: Path = BUNDLE_DIR,
    now: datetime | None = None,
) -> Result:
    """Write the bundle, and the manifests when ``mode`` says the version moves."""
    if mode not in MODES:
        raise ValueError(f"unknown CLI bundle mode {mode!r}; expected one of {MODES}")
    if not mergers:
        # The shell script refused too: an empty bundle would be published as
        # a new version and wipe every CLI user's database.
        raise ValueError("no merger records to bundle")

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = out_dir / MANIFEST_FILE

    data = serialise(build_bundle(mergers, questionnaires, noccs, stats, industries))
    sha = hashlib.sha256(data).hexdigest()

    previous = _read_manifest(manifest_path)
    prev_sha = previous.get("bundle_sha256") or ""
    prev_version = int(previous.get("version") or 0)
    changed = sha != prev_sha

    if mode == "republish" and not prev_sha:
        raise ValueError(f"republish needs an existing {manifest_path} to publish at")

    _write_bytes(out_dir / BUNDLE_FILE, data)

    if mode == "republish" or (not changed and mode != "force"):
        if mode == "republish" and changed:
            _warn(
                f"the regenerated CLI bundle differs from the one v{prev_version} was "
                f"stamped on (manifest {prev_sha[:12]}, regenerated {sha[:12]}); "
                f"publishing it as v{prev_version}. The next pipeline run will bump it."
            )
        return Result(prev_version, sha, changed, False, len(mergers))

    version = prev_version + 1
    merger_manifest = (json.dumps(merger_checksums(mergers), indent=2, sort_keys=True) + "\n").encode()
    _write_bytes(out_dir / MERGER_MANIFEST_FILE, merger_manifest)
    generated_at = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    _write_json(manifest_path, {
        "version": version,
        "generated_at": generated_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "merger_count": len(mergers),
        "bundle_sha256": sha,
        "merger_manifest_sha256": hashlib.sha256(merger_manifest).hexdigest(),
    })
    return Result(version, sha, changed, True, len(mergers))
