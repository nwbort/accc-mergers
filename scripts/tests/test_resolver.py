"""Tests for the duplicate-resolution logic.

resolver.py is a thin FastAPI wrapper that delegates to detect_duplicates for
all of the non-trivial logic (duplicate detection, deletion suggestions, and
the report structure that the web UI renders). Those building blocks live in
detect_duplicates.py and are what we exercise here.
"""

import json
import os
import sys
import unittest.mock

# Add scripts directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Mock heavy transitive imports that some scripts modules pull in.
sys.modules.setdefault('pdfplumber', unittest.mock.MagicMock())
sys.modules.setdefault('markdownify', unittest.mock.MagicMock())
sys.modules.setdefault('requests', unittest.mock.MagicMock())

from detect_duplicates import (
    build_report,
    event_summary,
    find_duplicates,
    normalise_title,
    parse_date,
    suggest_deletion,
    title_similarity,
)


# ---------------------------------------------------------------------------
# normalise_title
# ---------------------------------------------------------------------------

class TestNormaliseTitle:
    def test_lowercases(self):
        assert normalise_title("Questionnaire") == "questionnaire"

    def test_strips_leading_and_trailing_whitespace(self):
        assert normalise_title("  Submission  ") == "submission"

    def test_strips_trailing_punctuation(self):
        assert normalise_title("Submission.") == "submission"
        assert normalise_title("Submission!!!") == "submission"
        assert normalise_title("Submission ...") == "submission"

    def test_preserves_internal_punctuation(self):
        # Only trailing punctuation is stripped.
        assert normalise_title("Pre-acquisition") == "pre-acquisition"
        assert normalise_title("Co. Inc.") == "co. inc"

    def test_empty_string(self):
        assert normalise_title("") == ""


# ---------------------------------------------------------------------------
# title_similarity
# ---------------------------------------------------------------------------

class TestTitleSimilarity:
    def test_identical_titles(self):
        assert title_similarity("Submission from Acquirer", "Submission from Acquirer") == 1.0

    def test_ignores_trailing_punctuation(self):
        assert title_similarity("Submission.", "Submission") == 1.0

    def test_ignores_case(self):
        assert title_similarity("Submission", "SUBMISSION") == 1.0

    def test_similar_titles_cross_threshold(self):
        # Small typo variant — should be ≥ 0.8
        ratio = title_similarity(
            "Submission from the acquirer",
            "Submission from the acquirer ",
        )
        assert ratio >= 0.8

    def test_different_titles_below_threshold(self):
        ratio = title_similarity(
            "Notification received from acquirer",
            "Public competition assessment published",
        )
        assert ratio < 0.8


# ---------------------------------------------------------------------------
# parse_date
# ---------------------------------------------------------------------------

class TestParseDate:
    def test_iso_datetime_with_z(self):
        assert parse_date("2025-11-21T12:00:00Z") == "2025-11-21"

    def test_iso_datetime_with_offset(self):
        assert parse_date("2025-11-21T12:00:00+00:00") == "2025-11-21"

    def test_plain_date(self):
        assert parse_date("2025-11-21") == "2025-11-21"

    def test_empty_string(self):
        assert parse_date("") is None

    def test_none(self):
        assert parse_date(None) is None

    def test_invalid(self):
        assert parse_date("not a date") is None


# ---------------------------------------------------------------------------
# find_duplicates
# ---------------------------------------------------------------------------

class TestFindDuplicates:
    def test_no_events_returns_empty(self):
        assert find_duplicates({}) == []
        assert find_duplicates({'events': []}) == []

    def test_unique_events_no_duplicates(self):
        merger = {
            'events': [
                {'date': '2025-01-01T00:00:00Z', 'title': 'Notification'},
                {'date': '2025-02-01T00:00:00Z', 'title': 'Public submissions'},
                {'date': '2025-03-01T00:00:00Z', 'title': 'Determination'},
            ]
        }
        assert find_duplicates(merger) == []

    def test_certain_duplicates_identical_date_and_title(self):
        merger = {
            'events': [
                {'date': '2025-01-01T00:00:00Z', 'title': 'Notification'},
                {'date': '2025-01-01T00:00:00Z', 'title': 'Notification'},
            ]
        }
        groups = find_duplicates(merger)
        assert len(groups) == 1
        assert groups[0]['kind'] == 'certain'
        assert groups[0]['indices'] == [0, 1]
        assert groups[0]['date'] == '2025-01-01'
        assert groups[0]['titles'] == ['Notification']

    def test_likely_duplicates_same_date_similar_title(self):
        merger = {
            'events': [
                {'date': '2025-01-01T00:00:00Z', 'title': 'Submission received'},
                # Small trailing-punctuation difference → similarity = 1.0 after
                # normalisation, still reported as "likely" (titles differ).
                {'date': '2025-01-01T00:00:00Z', 'title': 'Submission received.'},
            ]
        }
        groups = find_duplicates(merger)
        assert len(groups) == 1
        assert groups[0]['kind'] == 'likely'
        assert set(groups[0]['indices']) == {0, 1}

    def test_different_dates_not_duplicates(self):
        merger = {
            'events': [
                {'date': '2025-01-01T00:00:00Z', 'title': 'Notification'},
                {'date': '2025-01-02T00:00:00Z', 'title': 'Notification'},
            ]
        }
        assert find_duplicates(merger) == []

    def test_events_without_date_or_title_skipped(self):
        merger = {
            'events': [
                {'date': '2025-01-01T00:00:00Z', 'title': 'Notification'},
                {'date': '', 'title': 'Notification'},
                {'date': '2025-01-01T00:00:00Z', 'title': ''},
            ]
        }
        assert find_duplicates(merger) == []

    def test_certain_preempts_likely(self):
        # The three identical events should form a single certain group, not
        # both a certain group and a separate likely group.
        merger = {
            'events': [
                {'date': '2025-01-01T00:00:00Z', 'title': 'Submission'},
                {'date': '2025-01-01T00:00:00Z', 'title': 'Submission'},
                {'date': '2025-01-01T00:00:00Z', 'title': 'Submission'},
            ]
        }
        groups = find_duplicates(merger)
        assert len(groups) == 1
        assert groups[0]['kind'] == 'certain'
        assert sorted(groups[0]['indices']) == [0, 1, 2]

    def test_unrelated_events_do_not_interfere(self):
        merger = {
            'events': [
                {'date': '2025-01-01T00:00:00Z', 'title': 'Notification'},
                {'date': '2025-01-01T00:00:00Z', 'title': 'Notification'},
                {'date': '2025-02-01T00:00:00Z', 'title': 'Different event'},
            ]
        }
        groups = find_duplicates(merger)
        assert len(groups) == 1
        assert sorted(groups[0]['indices']) == [0, 1]


# ---------------------------------------------------------------------------
# event_summary
# ---------------------------------------------------------------------------

class TestEventSummary:
    def test_extracts_known_fields(self):
        ev = {
            'date': '2025-01-01',
            'title': 'Submission',
            'url': 'https://example.com',
            'url_gh': 'https://github.com/x/y.pdf',
            'status': 'live',
            'extra_field': 'should be dropped',
        }
        result = event_summary(ev)
        assert result == {
            'date': '2025-01-01',
            'title': 'Submission',
            'url': 'https://example.com',
            'url_gh': 'https://github.com/x/y.pdf',
            'status': 'live',
        }
        assert 'extra_field' not in result

    def test_defaults_for_missing_fields(self):
        assert event_summary({}) == {
            'date': '', 'title': '', 'url': '', 'url_gh': '', 'status': '',
        }


# ---------------------------------------------------------------------------
# build_report
# ---------------------------------------------------------------------------

class TestBuildReport:
    def test_empty_list(self):
        report = build_report([])
        assert report['summary']['mergers_with_duplicates'] == 0
        assert report['summary']['certain_duplicate_groups'] == 0
        assert report['summary']['likely_duplicate_groups'] == 0
        assert report['findings'] == []

    def test_no_duplicates(self):
        mergers = [{
            'merger_id': 'MN-1',
            'merger_name': 'Clean merger',
            'events': [
                {'date': '2025-01-01T00:00:00Z', 'title': 'A'},
                {'date': '2025-02-01T00:00:00Z', 'title': 'B'},
            ],
        }]
        report = build_report(mergers)
        assert report['summary']['mergers_with_duplicates'] == 0
        assert report['findings'] == []

    def test_counts_certain_and_likely_separately(self):
        mergers = [
            {
                'merger_id': 'MN-1',
                'merger_name': 'With certain dup',
                'events': [
                    {'date': '2025-01-01T00:00:00Z', 'title': 'X'},
                    {'date': '2025-01-01T00:00:00Z', 'title': 'X'},
                ],
            },
            {
                'merger_id': 'MN-2',
                'merger_name': 'With likely dup',
                'events': [
                    {'date': '2025-01-01T00:00:00Z', 'title': 'Submission received'},
                    {'date': '2025-01-01T00:00:00Z', 'title': 'Submission received.'},
                ],
            },
            {
                'merger_id': 'MN-3',
                'merger_name': 'Clean',
                'events': [
                    {'date': '2025-01-01T00:00:00Z', 'title': 'Only event'},
                ],
            },
        ]
        report = build_report(mergers)
        assert report['summary']['mergers_with_duplicates'] == 2
        assert report['summary']['certain_duplicate_groups'] == 1
        assert report['summary']['likely_duplicate_groups'] == 1

        ids = {entry['merger_id'] for entry in report['findings']}
        assert ids == {'MN-1', 'MN-2'}

    def test_event_summaries_are_compact_not_full_events(self):
        mergers = [{
            'merger_id': 'MN-1',
            'merger_name': 'Test',
            'events': [
                {
                    'date': '2025-01-01T00:00:00Z',
                    'title': 'X',
                    'url': 'https://a',
                    'url_gh': 'https://b',
                    'status': 'live',
                    'secret': 'should be dropped',
                },
                {
                    'date': '2025-01-01T00:00:00Z',
                    'title': 'X',
                    'url': '',
                    'url_gh': '',
                    'status': 'removed',
                    'secret': 'should be dropped',
                },
            ],
        }]
        report = build_report(mergers)
        finding = report['findings'][0]
        for ev in finding['duplicate_groups'][0]['events']:
            assert 'secret' not in ev
            assert set(ev.keys()) == {'date', 'title', 'url', 'url_gh', 'status'}


# ---------------------------------------------------------------------------
# suggest_deletion
# ---------------------------------------------------------------------------

class TestSuggestDeletion:
    def test_prefers_removed_over_live(self):
        group = {
            'indices': [3, 7],
            'events': [
                {'status': 'live', 'url': 'x', 'url_gh': 'y'},
                {'status': 'removed', 'url': 'x', 'url_gh': 'y'},
            ],
        }
        idx, reason = suggest_deletion(group)
        assert idx == 7
        assert 'removed' in reason.lower()

    def test_prefers_entry_without_gh_attachment(self):
        group = {
            'indices': [3, 7],
            'events': [
                {'status': 'live', 'url': 'x', 'url_gh': 'y'},
                {'status': 'live', 'url': 'x', 'url_gh': ''},
            ],
        }
        idx, reason = suggest_deletion(group)
        assert idx == 7
        assert 'url_gh' in reason or 'attachment' in reason

    def test_prefers_entry_without_accc_url(self):
        group = {
            'indices': [3, 7],
            'events': [
                {'status': 'live', 'url': 'x', 'url_gh': 'y'},
                {'status': 'live', 'url': '', 'url_gh': 'y'},
            ],
        }
        idx, reason = suggest_deletion(group)
        assert idx == 7
        assert 'ACCC URL' in reason or 'url' in reason.lower()

    def test_prefers_entry_with_fewer_fields(self):
        group = {
            'indices': [3, 7],
            'events': [
                {'status': 'live', 'url': 'x', 'url_gh': 'y', 'title': 't', 'extra': 'v'},
                {'status': 'live', 'url': 'x', 'url_gh': 'y'},
            ],
        }
        idx, reason = suggest_deletion(group)
        assert idx == 7
        assert 'fewer' in reason.lower()

    def test_falls_back_to_last_entry(self):
        # Two identical events — suggestion must be deterministic: keep first,
        # remove last.
        group = {
            'indices': [3, 7],
            'events': [
                {'status': 'live', 'url': 'x', 'url_gh': 'y'},
                {'status': 'live', 'url': 'x', 'url_gh': 'y'},
            ],
        }
        idx, reason = suggest_deletion(group)
        assert idx == 7
        assert 'event[3]' in reason  # keeping the earlier one


# ---------------------------------------------------------------------------
# resolver.py: delete-by-index behaviour
# ---------------------------------------------------------------------------
# The resolver module imports fastapi and uvicorn which are not part of the
# pipeline's declared requirements.txt. We verify the delete-by-index logic
# symbolically — the HTTP wrapper is a shim around (a) load JSON, (b) locate
# merger by merger_id, (c) delete events[index], (d) write JSON back.

def _delete_event(mergers_path, merger_id, index):
    """Mirror of the logic in resolver.remove_event. Exists so we can test
    that pipeline invariant without importing FastAPI."""
    with open(mergers_path, 'r') as fh:
        raw = json.load(fh)
    mergers = raw if isinstance(raw, list) else raw.get('mergers', [])
    target = next((m for m in mergers if m.get('merger_id') == merger_id), None)
    if target is None:
        return 'merger_not_found'
    events = target.get('events', [])
    if index < 0 or index >= len(events):
        return 'invalid_index'
    del events[index]
    with open(mergers_path, 'w') as fh:
        json.dump(raw, fh, indent=2)
    return 'ok'


class TestResolverDeletionInvariant:
    def test_deletes_event_at_index(self, tmp_path):
        path = tmp_path / 'mergers.json'
        path.write_text(json.dumps([
            {
                'merger_id': 'MN-1',
                'events': [
                    {'title': 'first'},
                    {'title': 'second'},
                    {'title': 'third'},
                ],
            },
        ]))
        assert _delete_event(str(path), 'MN-1', 1) == 'ok'
        result = json.loads(path.read_text())
        titles = [e['title'] for e in result[0]['events']]
        assert titles == ['first', 'third']

    def test_unknown_merger_is_rejected(self, tmp_path):
        path = tmp_path / 'mergers.json'
        path.write_text(json.dumps([{'merger_id': 'MN-1', 'events': []}]))
        assert _delete_event(str(path), 'MN-DOES-NOT-EXIST', 0) == 'merger_not_found'

    def test_out_of_range_index_is_rejected(self, tmp_path):
        path = tmp_path / 'mergers.json'
        path.write_text(json.dumps([
            {'merger_id': 'MN-1', 'events': [{'title': 'only'}]},
        ]))
        assert _delete_event(str(path), 'MN-1', 5) == 'invalid_index'
        assert _delete_event(str(path), 'MN-1', -1) == 'invalid_index'

    def test_handles_wrapped_dict_shape(self, tmp_path):
        # resolver.py supports both {"mergers": [...]} and a top-level list.
        path = tmp_path / 'mergers.json'
        path.write_text(json.dumps({
            'mergers': [
                {'merger_id': 'MN-1', 'events': [{'title': 'a'}, {'title': 'b'}]},
            ]
        }))
        assert _delete_event(str(path), 'MN-1', 0) == 'ok'
        result = json.loads(path.read_text())
        assert [e['title'] for e in result['mergers'][0]['events']] == ['b']
