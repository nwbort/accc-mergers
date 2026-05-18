#!/usr/bin/env python3
"""Build the pre-indexed SQLite database the accc-mergers-cli downloads.

Reads ``data/output/cli/cli-bundle.json`` (produced upstream by
``scripts/generate-cli-data.sh``) and writes two files into the chosen
output directory:

* ``cli.sqlite`` -- the indexed database. Schema is defined verbatim by
  ``SCHEMA`` below; the CLI checks the ``schema_version`` row in ``meta``
  and refuses to install a DB whose version it doesn't recognise.
* ``cli-manifest.json`` -- describes the DB (version, timestamp, sha256,
  row count). The CLI fetches this first to decide whether to download
  the database.

Bump ``SCHEMA_VERSION`` (and coordinate with a CLI release) whenever the
schema changes in a way that would break older CLIs reading the new DB.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1


SCHEMA = """
CREATE TABLE mergers (
    merger_id TEXT PRIMARY KEY,
    merger_name TEXT,
    status TEXT,
    stage TEXT,
    is_waiver INTEGER,
    acquirers_text TEXT,
    targets_text TEXT,
    industries_text TEXT,
    determination TEXT,
    phase INTEGER,
    notification_date TEXT,
    determination_date TEXT,
    related_merger_id TEXT,
    related_relationship TEXT,
    related_merger_name TEXT,
    raw_json TEXT
);

CREATE INDEX mergers_related_merger_id_idx ON mergers(related_merger_id);

CREATE VIRTUAL TABLE merger_content USING fts5(
    merger_id UNINDEXED,
    merger_name,
    acquirers_text,
    targets_text,
    industries_text,
    merger_description,
    determination_reasons,
    determination_overlap,
    all_determination_text,
    tokenize = 'porter unicode61'
);

CREATE TABLE questionnaires (
    merger_id TEXT PRIMARY KEY,
    deadline TEXT,
    deadline_iso TEXT,
    file_name TEXT,
    questions_count INTEGER,
    raw_json TEXT,
    all_questionnaires_json TEXT
);

CREATE VIRTUAL TABLE questionnaire_content USING fts5(
    merger_id UNINDEXED,
    question_number UNINDEXED,
    question_text,
    tokenize = 'porter unicode61'
);

CREATE TABLE noccs (
    merger_id TEXT PRIMARY KEY,
    matter_id TEXT,
    date TEXT,
    date_iso TEXT,
    document_type TEXT,
    file_name TEXT,
    file_path TEXT,
    raw_json TEXT
);

CREATE VIRTUAL TABLE nocc_content USING fts5(
    merger_id UNINDEXED,
    section_number UNINDEXED,
    section_title,
    block_number UNINDEXED,
    block_text,
    tokenize = 'porter unicode61'
);

CREATE TABLE meta (
    key TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE stats (
    key TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE industries (
    key TEXT PRIMARY KEY,
    value TEXT
);
"""


def _join_names(items: Any, key: str = "name") -> str:
    if not items:
        return ""
    parts = []
    for it in items:
        if not isinstance(it, dict):
            continue
        name = it.get(key)
        if name:
            parts.append(name)
    return "; ".join(parts)


def _compute_determination(m: dict[str, Any]) -> str | None:
    if m.get("accc_determination"):
        return m["accc_determination"]
    if m.get("phase_2_determination"):
        return m["phase_2_determination"]
    stage = (m.get("stage") or "").lower()
    if "phase 2" in stage:
        return None
    return m.get("phase_1_determination")


def _compute_phase(m: dict[str, Any]) -> int | None:
    stage = (m.get("stage") or "").lower()
    p1 = m.get("phase_1_determination")
    p2 = m.get("phase_2_determination")
    p1_lower = (p1 or "").lower()
    if "phase 2" in stage or p2 or "phase 2" in p1_lower:
        return 2
    if "phase 1" in stage or p1:
        return 1
    return None


def _determination_sections(m: dict[str, Any]) -> list[tuple[str, str]]:
    """Yield (item, details) pairs from every event's determination_table_content."""
    out: list[tuple[str, str]] = []
    for event in m.get("events") or []:
        if not isinstance(event, dict):
            continue
        for entry in event.get("determination_table_content") or []:
            if not isinstance(entry, dict):
                continue
            item = entry.get("item") or ""
            details = entry.get("details") or ""
            out.append((item, details))
    return out


def _section_text(m: dict[str, Any], wanted: str) -> str:
    wanted_norm = wanted.strip().lower()
    parts = [
        details
        for item, details in _determination_sections(m)
        if item.strip().lower() == wanted_norm and details
    ]
    return "\n\n".join(parts)


def _all_determination_text(m: dict[str, Any]) -> str:
    parts = []
    for item, content in _determination_sections(m):
        if not content:
            continue
        parts.append(f"{item}\n{content}")
    return "\n\n".join(parts)


def _insert_merger(conn: sqlite3.Connection, m: dict[str, Any]) -> None:
    acquirers_text = _join_names(m.get("acquirers"))
    targets_text = _join_names(m.get("targets"))
    industries_text = _join_names(m.get("anzsic_codes"))
    related = m.get("related_merger") or {}

    conn.execute(
        """
        INSERT INTO mergers (
            merger_id, merger_name, status, stage, is_waiver,
            acquirers_text, targets_text, industries_text,
            determination, phase, notification_date, determination_date,
            related_merger_id, related_relationship, related_merger_name,
            raw_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            m["merger_id"],
            m.get("merger_name"),
            m.get("status"),
            m.get("stage"),
            1 if m.get("is_waiver") else 0,
            acquirers_text,
            targets_text,
            industries_text,
            _compute_determination(m),
            _compute_phase(m),
            m.get("effective_notification_datetime"),
            m.get("determination_publication_date"),
            related.get("merger_id") if related else None,
            related.get("relationship") if related else None,
            related.get("merger_name") if related else None,
            json.dumps(m),
        ),
    )

    conn.execute(
        """
        INSERT INTO merger_content (
            merger_id, merger_name, acquirers_text, targets_text, industries_text,
            merger_description, determination_reasons, determination_overlap,
            all_determination_text
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            m["merger_id"],
            m.get("merger_name"),
            acquirers_text,
            targets_text,
            industries_text,
            m.get("merger_description"),
            _section_text(m, "Reasons for determination"),
            _section_text(m, "Overlap and relationship between the parties"),
            _all_determination_text(m),
        ),
    )


def _insert_questionnaire(
    conn: sqlite3.Connection, merger_id: str, q: dict[str, Any]
) -> None:
    questions = q.get("questions") or []
    raw_count = q.get("questions_count")
    try:
        questions_count = int(raw_count) if raw_count is not None else len(questions)
    except (TypeError, ValueError):
        questions_count = len(questions)

    all_qs = q.get("all_questionnaires")
    conn.execute(
        """
        INSERT INTO questionnaires
        (merger_id, deadline, deadline_iso, file_name, questions_count,
         raw_json, all_questionnaires_json)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            merger_id,
            q.get("deadline"),
            q.get("deadline_iso"),
            q.get("file_name"),
            questions_count,
            json.dumps(questions),
            json.dumps(all_qs) if all_qs is not None else None,
        ),
    )

    for question in questions:
        if not isinstance(question, dict):
            continue
        number = question.get("number") or question.get("question_number") or ""
        text = (
            question.get("text")
            or question.get("question")
            or question.get("question_text")
            or ""
        )
        conn.execute(
            """
            INSERT INTO questionnaire_content
            (merger_id, question_number, question_text)
            VALUES (?, ?, ?)
            """,
            (merger_id, str(number), text),
        )


def _insert_nocc(
    conn: sqlite3.Connection, merger_id: str, n: dict[str, Any]
) -> None:
    sections = n.get("sections") or []

    normalised_sections = []
    for s in sections:
        if not isinstance(s, dict):
            continue
        blocks = []
        for b in s.get("blocks") or []:
            if not isinstance(b, dict):
                continue
            blocks.append(
                {
                    "number": b.get("number"),
                    "text": b.get("text"),
                    "type": b.get("type"),
                }
            )
        normalised_sections.append(
            {"number": s.get("number"), "title": s.get("title"), "blocks": blocks}
        )

    conn.execute(
        """
        INSERT INTO noccs
        (merger_id, matter_id, date, date_iso, document_type, file_name,
         file_path, raw_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            merger_id,
            n.get("matter_id") or merger_id,
            n.get("date"),
            n.get("date_iso"),
            n.get("document_type"),
            n.get("file_name"),
            n.get("file_path"),
            json.dumps({"sections": normalised_sections}),
        ),
    )

    for section in normalised_sections:
        section_number = str(section["number"] or "")
        section_title = section["title"] or ""
        for block in section["blocks"]:
            text = block.get("text") or ""
            if not text.strip():
                continue
            conn.execute(
                """
                INSERT INTO nocc_content
                (merger_id, section_number, section_title,
                 block_number, block_text)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    merger_id,
                    section_number,
                    section_title,
                    str(block.get("number") or ""),
                    text,
                ),
            )


def build_database(db_path: Path, bundle: dict[str, Any]) -> int:
    """Build the SQLite file at ``db_path``. Returns the inserted merger count."""
    if db_path.exists():
        db_path.unlink()

    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(SCHEMA)
        conn.execute(
            "INSERT INTO meta (key, value) VALUES ('schema_version', ?)",
            (str(SCHEMA_VERSION),),
        )

        merger_count = 0
        for m in bundle.get("mergers") or []:
            if not isinstance(m, dict):
                continue
            if not m.get("merger_id"):
                continue
            _insert_merger(conn, m)
            merger_count += 1

        for mid, q in (bundle.get("questionnaires") or {}).items():
            if not isinstance(q, dict):
                continue
            _insert_questionnaire(conn, mid, q)

        for mid, n in (bundle.get("noccs") or {}).items():
            if not isinstance(n, dict):
                continue
            _insert_nocc(conn, mid, n)

        stats = bundle.get("stats")
        if stats is not None:
            conn.execute(
                "INSERT INTO stats (key, value) VALUES ('stats', ?)",
                (json.dumps(stats),),
            )

        industries = bundle.get("industries")
        if industries is not None:
            conn.execute(
                "INSERT INTO industries (key, value) VALUES ('industries', ?)",
                (json.dumps(industries),),
            )

        conn.commit()
    finally:
        conn.close()

    return merger_count


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _validate(db_path: Path, expected_count: int) -> None:
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            "SELECT value FROM meta WHERE key='schema_version'"
        ).fetchone()
        if not row or row[0] != str(SCHEMA_VERSION):
            raise SystemExit(
                f"schema_version mismatch: got {row!r}, expected '{SCHEMA_VERSION}'"
            )

        (count,) = conn.execute("SELECT COUNT(*) FROM mergers").fetchone()
        if count != expected_count:
            raise SystemExit(
                f"mergers row count {count} does not match expected {expected_count}"
            )

        (integrity,) = conn.execute("PRAGMA integrity_check").fetchone()
        if integrity != "ok":
            raise SystemExit(f"PRAGMA integrity_check returned {integrity!r}")
    finally:
        conn.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--bundle",
        type=Path,
        default=Path("data/output/cli/cli-bundle.json"),
        help="Path to cli-bundle.json (default: %(default)s)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Directory to write cli.sqlite and cli-manifest.json into",
    )
    parser.add_argument(
        "--version",
        type=int,
        help=(
            "Data version to embed in the manifest. Defaults to the 'version' "
            "field of the companion cli-manifest.json sitting next to --bundle."
        ),
    )
    args = parser.parse_args(argv)

    bundle_path: Path = args.bundle
    out_dir: Path = args.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    bundle = json.loads(bundle_path.read_text())

    if args.version is not None:
        version = args.version
    else:
        companion = bundle_path.with_name("cli-manifest.json")
        if not companion.exists():
            raise SystemExit(
                f"--version not given and no companion manifest at {companion}"
            )
        version = int(json.loads(companion.read_text())["version"])

    db_path = out_dir / "cli.sqlite"
    manifest_path = out_dir / "cli-manifest.json"

    merger_count = build_database(db_path, bundle)
    _validate(db_path, merger_count)

    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "version": version,
        "generated_at": generated_at,
        "merger_count": merger_count,
        "sqlite_sha256": _sha256(db_path),
        "sqlite_filename": "cli.sqlite",
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")

    print(
        f"Built {db_path} "
        f"(mergers={merger_count}, version={version}, "
        f"schema_version={SCHEMA_VERSION})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
