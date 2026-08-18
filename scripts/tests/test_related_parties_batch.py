"""Tests for scripts/related_parties_batch.py — the batch-review CLI for
manually linking related parties (see also test_related_parties.py for the
party_matching helpers it builds on)."""

import os
import sys
import unittest.mock

import pytest

# Add scripts directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Mock heavy transitive imports before importing modules that need them
sys.modules.setdefault('pdfplumber', unittest.mock.MagicMock())
sys.modules.setdefault('markdownify', unittest.mock.MagicMock())
sys.modules.setdefault('requests', unittest.mock.MagicMock())

from related_parties_batch import (
    annotate_parties,
    build_batch,
    format_batch_text,
    select_batch_by_ids,
    select_batch_by_rank,
)
from party_matching import build_group_lookups


def _merger(mid, name, date, acquirers=None, targets=None, other=None):
    return {
        "merger_id": mid,
        "merger_name": name,
        "effective_notification_datetime": date,
        "stage": "Phase 1 - initial assessment",
        "acquirers": acquirers or [],
        "targets": targets or [],
        "other_parties": other or [],
        "merger_description": f"Description for {mid}.",
    }


def _mergers():
    return [
        _merger("MN-1", "Deal One", "2026-01-01T12:00:00Z",
                acquirers=[{"name": "COLES GROUP LIMITED", "identifier": "11 004 089 936"}]),
        _merger("MN-2", "Deal Two", "2026-03-01T12:00:00Z",
                targets=[{"name": "Unmatched Pty Ltd", "identifier": "99 999 999 999"}]),
        _merger("MN-3", "Deal Three", "2026-02-01T12:00:00Z"),
    ]


def _groups():
    return [{
        "id": "coles",
        "canonical_name": "Coles Group",
        "members": [{"name": "COLES GROUP LIMITED", "identifier": "11 004 089 936"}],
    }]


# ---------------------------------------------------------------------------
# select_batch_by_rank
# ---------------------------------------------------------------------------

class TestSelectBatchByRank:
    def test_orders_newest_first_and_slices(self):
        result = select_batch_by_rank(_mergers(), start=1, count=2)
        assert [m["merger_id"] for m in result] == ["MN-2", "MN-3"]

    def test_start_beyond_range_returns_empty(self):
        assert select_batch_by_rank(_mergers(), start=10, count=5) == []

    def test_count_beyond_range_truncates(self):
        result = select_batch_by_rank(_mergers(), start=2, count=10)
        assert [m["merger_id"] for m in result] == ["MN-3", "MN-1"]

    def test_rejects_non_positive_start(self):
        with pytest.raises(ValueError):
            select_batch_by_rank(_mergers(), start=0, count=1)

    def test_rejects_non_positive_count(self):
        with pytest.raises(ValueError):
            select_batch_by_rank(_mergers(), start=1, count=0)


# ---------------------------------------------------------------------------
# select_batch_by_ids
# ---------------------------------------------------------------------------

class TestSelectBatchByIds:
    def test_returns_in_requested_order_not_storage_order(self):
        result = select_batch_by_ids(_mergers(), ["MN-3", "MN-1"])
        assert [m["merger_id"] for m in result] == ["MN-3", "MN-1"]

    def test_raises_listing_missing_ids(self):
        with pytest.raises(KeyError, match="MN-404"):
            select_batch_by_ids(_mergers(), ["MN-1", "MN-404"])


# ---------------------------------------------------------------------------
# annotate_parties
# ---------------------------------------------------------------------------

class TestAnnotateParties:
    def test_flags_matched_and_unmatched_parties(self):
        by_id, by_name = build_group_lookups(_groups())
        annotated = annotate_parties(_mergers()[0], by_id, by_name)
        assert len(annotated) == 1
        assert annotated[0]["role"] == "acquirers"
        assert annotated[0]["group"] == {"id": "coles", "canonical_name": "Coles Group"}

    def test_unmatched_party_has_none_group(self):
        by_id, by_name = build_group_lookups(_groups())
        annotated = annotate_parties(_mergers()[1], by_id, by_name)
        assert annotated[0]["group"] is None

    def test_no_parties_returns_empty_list(self):
        by_id, by_name = build_group_lookups(_groups())
        assert annotate_parties(_mergers()[2], by_id, by_name) == []


# ---------------------------------------------------------------------------
# build_batch / format_batch_text
# ---------------------------------------------------------------------------

class TestBuildBatch:
    def test_assigns_sequential_ranks_from_start_rank(self):
        mergers = _mergers()
        selected = select_batch_by_rank(mergers, start=1, count=3)
        batch = build_batch(mergers, _groups(), start_rank=1, selected=selected)
        assert [entry["rank"] for entry in batch] == [1, 2, 3]

    def test_includes_description_and_annotated_parties(self):
        mergers = _mergers()
        batch = build_batch(mergers, _groups(), start_rank=1, selected=[mergers[0]])
        assert batch[0]["merger_description"] == "Description for MN-1."
        assert batch[0]["parties"][0]["group"]["id"] == "coles"


class TestFormatBatchText:
    def test_renders_matched_and_unmatched_markers(self):
        mergers = _mergers()
        batch = build_batch(mergers, _groups(), start_rank=1, selected=mergers[:2])
        text = format_batch_text(batch)
        assert "MATCHED -> Coles Group (coles)" in text
        assert "UNMATCHED" in text
        assert "#1 MN-1 - Deal One" in text
        assert "#2 MN-2 - Deal Two" in text
