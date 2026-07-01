"""Tests for event-level duplicate detection (``detect_duplicates``).

Focus on the LIKELY pass's ±1 day tolerance, which catches the case where the
ACCC re-publishes a document under a new version and a slightly shifted date
(e.g. MN-01019's Phase 2 review notice appearing on both 20 and 21 Jan).
"""

import os
import sys

# Add scripts directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from detect_duplicates import dates_within_one_day, find_duplicates


def _kinds(groups):
    return {g["kind"] for g in groups}


def test_dates_within_one_day_tolerance():
    assert dates_within_one_day("2026-01-20", "2026-01-20") is True
    assert dates_within_one_day("2026-01-20", "2026-01-21") is True
    assert dates_within_one_day("2026-01-21", "2026-01-20") is True
    assert dates_within_one_day("2026-01-20", "2026-01-22") is False
    assert dates_within_one_day("2026-01-20", "") is False
    # Month boundary
    assert dates_within_one_day("2026-01-31", "2026-02-01") is True


def test_phase2_referral_reupload_one_day_apart_is_likely_duplicate():
    """The Ampol case: same title, dates one day apart after a re-upload."""
    merger = {
        "merger_id": "MN-01019",
        "events": [
            {
                "date": "2026-01-20T12:00:00Z",
                "title": "ACCC decided notification is subject to Phase 2 review",
                "url": "https://accc.gov.au/.../Phase 2 Notice - Redacted_4.pdf",
                "status": "removed",
            },
            {
                "date": "2026-01-21T12:00:00Z",
                "title": "ACCC decided notification is subject to Phase 2 review",
                "url": "https://accc.gov.au/.../Phase 2 Notice - Redacted_7.pdf",
                "status": "live",
            },
        ],
    }
    groups = find_duplicates(merger)
    assert len(groups) == 1
    assert groups[0]["kind"] == "likely"
    assert set(groups[0]["indices"]) == {0, 1}


def test_exact_duplicate_still_certain():
    """Identical (date, title) pairs are still reported as CERTAIN, not LIKELY."""
    merger = {
        "merger_id": "MN-1",
        "events": [
            {"date": "2026-01-20T12:00:00Z", "title": "Statement of Issues"},
            {"date": "2026-01-20T12:00:00Z", "title": "Statement of Issues"},
        ],
    }
    groups = find_duplicates(merger)
    assert len(groups) == 1
    assert groups[0]["kind"] == "certain"


def test_different_event_types_one_day_apart_not_grouped():
    """The tolerance must not group genuinely distinct documents."""
    merger = {
        "merger_id": "MN-2",
        "events": [
            {"date": "2026-01-20T12:00:00Z", "title": "Questionnaire - Acme - Beta"},
            {"date": "2026-01-21T12:00:00Z", "title": "Remedy offer - Acme - Beta"},
        ],
    }
    assert find_duplicates(merger) == []


def test_two_days_apart_not_grouped():
    """Beyond the ±1 day window, same-title events are left alone."""
    merger = {
        "merger_id": "MN-3",
        "events": [
            {"date": "2026-01-20T12:00:00Z", "title": "ACCC decided notification is subject to Phase 2 review"},
            {"date": "2026-01-22T12:00:00Z", "title": "ACCC decided notification is subject to Phase 2 review"},
        ],
    }
    assert find_duplicates(merger) == []


def test_type_label_suffix_not_grouped():
    """Titles with the document-type label at the end, not the start, must
    still be told apart. MN-50009 had 'MAAS - Remedy offer' and
    'MAAS - Questionnaire - Remedy offer' on the same day: the leading
    segments match and the segment counts differ, so the type-prefix and
    equal-length segment checks both miss the inserted 'Questionnaire'
    segment. These are genuinely different documents and must not be
    reported as duplicates.
    """
    merger = {
        "merger_id": "MN-50009",
        "events": [
            {
                "date": "2026-06-29T12:00:00Z",
                "title": "Heidelberg Materials Australia - Construction materials business of MAAS - Remedy offer",
            },
            {
                "date": "2026-06-29T12:00:00Z",
                "title": "Heidelberg Materials Australia - Construction materials business of MAAS - Questionnaire - Remedy offer",
            },
        ],
    }
    assert find_duplicates(merger) == []


def test_three_consecutive_days_no_overlapping_groups():
    """Non-transitive tolerance must not emit overlapping groups that share an index."""
    merger = {
        "merger_id": "MN-4",
        "events": [
            {"date": "2026-01-20T12:00:00Z", "title": "ACCC decided notification is subject to Phase 2 review"},
            {"date": "2026-01-21T12:00:00Z", "title": "ACCC decided notification is subject to Phase 2 review"},
            {"date": "2026-01-22T12:00:00Z", "title": "ACCC decided notification is subject to Phase 2 review"},
        ],
    }
    groups = find_duplicates(merger)
    # 20-21 group, leaving 22 ungrouped (22 is >1 day from the anchor 20).
    all_indices = [i for g in groups for i in g["indices"]]
    assert len(all_indices) == len(set(all_indices)), "events appear in more than one group"
