"""Covers the CLI SQLite build's derived columns.

``build_database`` writes ``under_appeal``, ``has_judicial_review``,
``under_judicial_review``, ``has_conditions``, ``phase_1_estimate_days`` and the
site's reading of the outcome (``determination``) as real columns (rather than leaving them buried in
``raw_json``) so accc-mergers-cli can filter and sort on them. These tests pin
that derivation, because getting it wrong is silent — the database still
builds, it just serves the wrong filter results.
"""

import json
import sqlite3

import pytest

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

    def test_judicial_reviews_list_and_live_flag(self, tmp_path):
        # A record carrying only the newer per-file list still counts as
        # having a review; under_judicial_review tracks the live flag alone.
        bundle = {
            "mergers": [
                _merger(
                    "MN-1",
                    judicial_reviews=[{"case_number": "NSD1/2026", "status": "current"}],
                    under_judicial_review=True,
                ),
                _merger(
                    "MN-2",
                    judicial_reviews=[{"case_number": "NSD2/2026", "status": "concluded"}],
                ),
            ]
        }
        rows = _rows(tmp_path, bundle, "has_judicial_review, under_judicial_review")
        assert rows["MN-1"] == (1, 1)
        assert rows["MN-2"] == (1, 0)

    def test_schema_version_bumped_for_new_columns(self):
        assert SCHEMA_VERSION == 3


def _rows(tmp_path, bundle, columns):
    db_path = tmp_path / "cli.sqlite"
    build_database(db_path, bundle)
    conn = sqlite3.connect(db_path)
    try:
        return {
            r[0]: r[1:]
            for r in conn.execute(f"SELECT merger_id, {columns} FROM mergers")
        }
    finally:
        conn.close()


class TestDetermination:
    """``determination`` matches the outcome the site's header states."""

    @pytest.mark.parametrize(
        "overrides, expected",
        [
            (
                {"status": "Assessment completed", "accc_determination": "Approved"},
                "Approved",
            ),
            (
                {
                    "status": "Assessment completed",
                    "accc_determination": "Approved",
                    "has_conditions": True,
                },
                "Approved with conditions",
            ),
            # A stale conditions flag on another outcome stays hidden.
            (
                {
                    "status": "Assessment completed",
                    "accc_determination": "Not approved",
                    "has_conditions": True,
                },
                "Not approved",
            ),
            # Ceased in phase 2 after a referral: ceased, not "pending".
            (
                {
                    "status": "Assessment ceased",
                    "stage": "Phase 2 - detailed assessment",
                    "phase_1_determination": "Referred to phase 2",
                },
                "Assessment ceased",
            ),
            (
                {"status": "Assessment ceased", "stage": "Phase 1 - initial assessment"},
                "Assessment ceased",
            ),
            # The public benefit phase makes the matter live again.
            (
                {
                    "status": "Under assessment",
                    "stage": "Public benefit phase",
                    "public_benefit_in_progress": True,
                    "phase_2_determination": "Not approved",
                },
                None,
            ),
            # A concluded appeal's effective determination stands.
            (
                {
                    "status": "Assessment completed",
                    "accc_determination": "Not approved",
                    "appeal": {
                        "status": "concluded",
                        "outcome": "set_aside",
                        "effective_determination": "Approved",
                    },
                },
                "Approved",
            ),
            # A current one leaves the ACCC's determination alone.
            (
                {
                    "status": "Assessment completed",
                    "accc_determination": "Not approved",
                    "under_appeal": True,
                    "appeal": {"status": "current", "effective_determination": None},
                },
                "Not approved",
            ),
            (
                {
                    "status": "Under assessment",
                    "stage": "Phase 2 - detailed assessment",
                    "phase_1_determination": "Referred to phase 2",
                },
                None,
            ),
        ],
    )
    def test_outcome(self, tmp_path, overrides, expected):
        rows = _rows(tmp_path, {"mergers": [_merger("MN-1", **overrides)]}, "determination")
        assert rows["MN-1"] == (expected,)

    def test_has_conditions_column(self, tmp_path):
        bundle = {"mergers": [_merger("MN-1", has_conditions=True), _merger("MN-2")]}
        rows = _rows(tmp_path, bundle, "has_conditions")
        assert rows == {"MN-1": (1,), "MN-2": (0,)}


class TestPreNotificationSummary:
    def test_summary_added_to_raw_json(self, tmp_path):
        estimate = {
            "estimated_days": 23,
            "min_days": 8,
            "max_days": 20,
            "id_issued_estimated": "2026-02-08",
            "basis": "bracketed",
        }
        bundle = {
            "mergers": [
                _merger(
                    "MN-1",
                    effective_notification_datetime="2026-03-03T12:00:00Z",
                    pre_notification=estimate,
                ),
                _merger("MN-2"),
            ]
        }
        rows = _rows(tmp_path, bundle, "raw_json")
        raw = json.loads(rows["MN-1"][0])
        assert raw["pre_notification_summary"] == {
            "kind": "around",
            "start_date": "2026-02-08",
            "confidence": "high",
        }
        # The raw estimate is kept alongside it.
        assert raw["pre_notification"] == estimate
        assert "pre_notification_summary" not in json.loads(rows["MN-2"][0])
