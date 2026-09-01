"""Covers the CLI SQLite build's derived columns.

``build_database`` writes ``under_appeal``, ``has_judicial_review`` and
``phase_1_estimate_days`` as real columns (rather than leaving them buried in
``raw_json``) so accc-mergers-cli can filter and sort on them. These tests pin
that derivation, because getting it wrong is silent — the database still
builds, it just serves the wrong filter results.
"""

import sqlite3

from scripts.generate.build_cli_sqlite import SCHEMA_VERSION, build_database


def _merger(merger_id, **overrides):
    base = {
        "merger_id": merger_id,
        "merger_name": f"Merger {merger_id}",
        "status": "Determined",
        "stage": "Phase 1",
        "is_waiver": False,
        "acquirers": [],
        "targets": [],
        "anzsic_codes": [],
        "events": [],
    }
    base.update(overrides)
    return base


class TestDerivedColumns:
    def test_under_appeal_and_judicial_review_flags(self, tmp_path):
        bundle = {
            "mergers": [
                _merger(
                    "MN-1",
                    under_appeal=True,
                    appeal={"tribunal_number": "ACT 1 of 2026"},
                ),
                _merger("MN-2", judicial_review={"applicant": "Someone"}),
                _merger("MN-3"),
            ]
        }
        db_path = tmp_path / "cli.sqlite"
        build_database(db_path, bundle)

        conn = sqlite3.connect(db_path)
        try:
            rows = {
                r[0]: r[1:]
                for r in conn.execute(
                    "SELECT merger_id, under_appeal, has_judicial_review "
                    "FROM mergers ORDER BY merger_id"
                )
            }
        finally:
            conn.close()

        assert rows["MN-1"] == (1, 0)
        assert rows["MN-2"] == (0, 1)
        assert rows["MN-3"] == (0, 0)

    def test_under_appeal_false_keeps_appeal_record(self, tmp_path):
        # A concluded/withdrawn appeal leaves the `appeal` record in place but
        # is no longer "current" -- under_appeal should track that, not just
        # whether an appeal record exists at all.
        bundle = {
            "mergers": [
                _merger(
                    "MN-1",
                    under_appeal=False,
                    appeal={"tribunal_number": "ACT 1 of 2025", "status": "concluded"},
                ),
            ]
        }
        db_path = tmp_path / "cli.sqlite"
        build_database(db_path, bundle)

        conn = sqlite3.connect(db_path)
        try:
            row = conn.execute(
                "SELECT under_appeal, raw_json FROM mergers WHERE merger_id = 'MN-1'"
            ).fetchone()
        finally:
            conn.close()

        assert row[0] == 0
        assert "ACT 1 of 2025" in row[1]

    def test_phase_1_estimate_days_extracted_and_absent_is_null(self, tmp_path):
        bundle = {
            "mergers": [
                _merger(
                    "MN-1",
                    phase_1_estimate={
                        "expected_business_days": 18,
                        "range_business_days": [15, 22],
                        "basis": "industry",
                    },
                ),
                _merger("WA-1", is_waiver=True),
            ]
        }
        db_path = tmp_path / "cli.sqlite"
        build_database(db_path, bundle)

        conn = sqlite3.connect(db_path)
        try:
            rows = dict(
                conn.execute(
                    "SELECT merger_id, phase_1_estimate_days FROM mergers"
                )
            )
        finally:
            conn.close()

        assert rows["MN-1"] == 18
        assert rows["WA-1"] is None

    def test_schema_version_bumped_for_new_columns(self):
        assert SCHEMA_VERSION == 2
