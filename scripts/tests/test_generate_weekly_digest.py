"""Tests for generate_weekly_digest.

Focuses on the inclusion criteria used to build digest buckets — in
particular the two-week lookback window combined with dedup against
the previous week's digest. That combination is what surfaces
determinations dated on a Friday but only published on the ACCC's
acquisitions register the following Monday, without re-surfacing
items every time ACCC edits an old page.
"""

import os
import sys
import unittest.mock
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# Add scripts directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Mock heavy transitive imports before importing modules that need them
sys.modules.setdefault('pdfplumber', unittest.mock.MagicMock())
sys.modules.setdefault('markdownify', unittest.mock.MagicMock())
sys.modules.setdefault('requests', unittest.mock.MagicMock())

import generate_weekly_digest as gwd
from constants import merger_status


SYDNEY = ZoneInfo('Australia/Sydney')


def _period(monday_iso: str):
    """Build a (Mon 00:00, Sun 23:59:59.999999) range from a Monday date."""
    monday = datetime.fromisoformat(monday_iso).replace(tzinfo=SYDNEY)
    sunday = monday + timedelta(days=6, hours=23, minutes=59, seconds=59, microseconds=999999)
    return monday, sunday


class TestLoadPreviousDigest:
    def test_returns_empty_dict_when_path_is_none(self):
        assert gwd.load_previous_digest(None) == {}

    def test_returns_empty_dict_when_file_missing(self, tmp_path):
        missing = tmp_path / 'nope.json'
        assert gwd.load_previous_digest(missing) == {}

    def test_returns_empty_dict_on_corrupt_json(self, tmp_path):
        corrupt = tmp_path / 'digest.json'
        corrupt.write_text('{not valid json', encoding='utf-8')
        assert gwd.load_previous_digest(corrupt) == {}

    def test_returns_parsed_digest(self, tmp_path):
        import json
        path = tmp_path / 'digest.json'
        path.write_text(
            json.dumps({'deals_cleared': [{'merger_id': 'MN-1'}]}),
            encoding='utf-8',
        )
        result = gwd.load_previous_digest(path)
        assert result == {'deals_cleared': [{'merger_id': 'MN-1'}]}


class TestResolvePreviousDigestPath:
    def test_prefers_dated_archive_for_last_week(self, tmp_path):
        archive_dir = tmp_path / 'archive'
        archive_dir.mkdir()
        fallback = tmp_path / 'digest.json'
        fallback.write_text('{}', encoding='utf-8')

        this_monday, _ = _period('2025-04-14')
        last_monday_iso = '2025-04-07'
        archived = archive_dir / f'digest-{last_monday_iso}.json'
        archived.write_text('{}', encoding='utf-8')

        resolved = gwd.resolve_previous_digest_path(this_monday, archive_dir, fallback)
        assert resolved == archived

    def test_falls_back_to_live_digest_when_archive_missing(self, tmp_path):
        archive_dir = tmp_path / 'archive'
        archive_dir.mkdir()
        fallback = tmp_path / 'digest.json'
        fallback.write_text('{}', encoding='utf-8')

        this_monday, _ = _period('2025-04-14')
        resolved = gwd.resolve_previous_digest_path(this_monday, archive_dir, fallback)
        assert resolved == fallback

    def test_returns_none_when_neither_exists(self, tmp_path):
        archive_dir = tmp_path / 'archive'
        archive_dir.mkdir()
        fallback = tmp_path / 'digest.json'  # does not exist

        this_monday, _ = _period('2025-04-14')
        resolved = gwd.resolve_previous_digest_path(this_monday, archive_dir, fallback)
        assert resolved is None

    def test_does_not_pick_up_wrong_weeks_archive(self, tmp_path):
        """An archive keyed by a different Monday must be ignored — resolver
        must look for *exactly* last week's archive, not just any archive."""
        archive_dir = tmp_path / 'archive'
        archive_dir.mkdir()
        fallback = tmp_path / 'digest.json'
        fallback.write_text('{}', encoding='utf-8')

        # Archive from three weeks ago, not last week.
        (archive_dir / 'digest-2025-03-24.json').write_text('{}', encoding='utf-8')

        this_monday, _ = _period('2025-04-14')
        resolved = gwd.resolve_previous_digest_path(this_monday, archive_dir, fallback)
        assert resolved == fallback


class TestBucketIds:
    def test_empty_digest_returns_empty_set(self):
        assert gwd.bucket_ids({}, 'deals_cleared') == set()

    def test_bucket_absent_returns_empty_set(self):
        assert gwd.bucket_ids({'other_bucket': []}, 'deals_cleared') == set()

    def test_extracts_merger_ids(self):
        digest = {
            'deals_cleared': [
                {'merger_id': 'MN-1'},
                {'merger_id': 'MN-2'},
            ],
        }
        assert gwd.bucket_ids(digest, 'deals_cleared') == {'MN-1', 'MN-2'}

    def test_ignores_entries_without_merger_id(self):
        digest = {'deals_cleared': [{'merger_id': 'MN-1'}, {}]}
        assert gwd.bucket_ids(digest, 'deals_cleared') == {'MN-1'}


class TestWeeklyDigestBuckets:
    """Drive generate_weekly_digest end-to-end via monkeypatched dependencies."""

    def _run(self, mergers, monkeypatch, previous_digest=None, this_monday='2025-04-14'):
        start, end = _period(this_monday)
        monkeypatch.setattr(gwd, 'load_mergers', lambda: mergers)
        monkeypatch.setattr(gwd, 'filter_active', lambda ms: ms)
        monkeypatch.setattr(gwd, 'get_last_week_range', lambda: (start, end))
        return gwd.generate_weekly_digest(previous_digest=previous_digest or {})

    # -----------------------------------------------------------------
    # Normal (same-week) behaviour
    # -----------------------------------------------------------------

    def test_same_week_clearance_is_included(self, monkeypatch):
        merger = {
            'merger_id': 'MN-1',
            'merger_name': 'Mid-week clearance',
            'status': merger_status.ASSESSMENT_COMPLETED,
            'stage': 'Phase 1 - initial assessment',
            'effective_notification_datetime': '2025-03-20T00:00:00Z',
            'determination_publication_date': '2025-04-16T12:00:00Z',  # Wed in period
            'accc_determination': merger_status.APPROVED,
            'events': [],
        }
        digest = self._run([merger], monkeypatch)
        assert [m['merger_id'] for m in digest['deals_cleared']] == ['MN-1']

    def test_same_week_declined_is_included(self, monkeypatch):
        merger = {
            'merger_id': 'MN-2',
            'merger_name': 'Mid-week decline',
            'status': merger_status.ASSESSMENT_COMPLETED,
            'stage': 'Phase 1 - initial assessment',
            'effective_notification_datetime': '2025-03-20T00:00:00Z',
            'determination_publication_date': '2025-04-16T12:00:00Z',
            'accc_determination': merger_status.NOT_APPROVED,
            'events': [],
        }
        digest = self._run([merger], monkeypatch)
        assert [m['merger_id'] for m in digest['deals_declined']] == ['MN-2']

    def test_same_week_new_notification_is_included(self, monkeypatch):
        merger = {
            'merger_id': 'MN-3',
            'merger_name': 'Mid-week notification',
            'status': merger_status.UNDER_ASSESSMENT,
            'stage': 'Phase 1 - initial assessment',
            'effective_notification_datetime': '2025-04-16T12:00:00Z',
            'events': [],
        }
        digest = self._run([merger], monkeypatch)
        assert [m['merger_id'] for m in digest['new_deals_notified']] == ['MN-3']

    # -----------------------------------------------------------------
    # Late-arrival catch-up
    # -----------------------------------------------------------------

    def test_friday_clearance_caught_in_following_week(self, monkeypatch):
        """A decision dated last Friday that the previous digest missed is
        included here, because it's in the 2-week window and wasn't in last
        week's digest."""
        merger = {
            'merger_id': 'MN-100',
            'merger_name': 'Friday clearance',
            'status': merger_status.ASSESSMENT_COMPLETED,
            'stage': 'Phase 1 - initial assessment',
            'effective_notification_datetime': '2025-03-01T00:00:00Z',
            'determination_publication_date': '2025-04-11T00:00:00Z',  # prior Friday
            'accc_determination': merger_status.APPROVED,
            'events': [],
        }
        previous_digest = {
            'new_deals_notified': [],
            'deals_cleared': [],
            'deals_declined': [],
        }
        digest = self._run([merger], monkeypatch, previous_digest=previous_digest)
        assert [m['merger_id'] for m in digest['deals_cleared']] == ['MN-100']

    def test_friday_decline_caught_in_following_week(self, monkeypatch):
        merger = {
            'merger_id': 'MN-101',
            'merger_name': 'Friday decline',
            'status': merger_status.ASSESSMENT_COMPLETED,
            'stage': 'Phase 1 - initial assessment',
            'effective_notification_datetime': '2025-03-01T00:00:00Z',
            'determination_publication_date': '2025-04-11T00:00:00Z',
            'accc_determination': merger_status.NOT_APPROVED,
            'events': [],
        }
        digest = self._run([merger], monkeypatch, previous_digest={})
        assert [m['merger_id'] for m in digest['deals_declined']] == ['MN-101']

    def test_late_notification_caught_in_following_week(self, monkeypatch):
        merger = {
            'merger_id': 'MN-102',
            'merger_name': 'Late notification',
            'status': merger_status.UNDER_ASSESSMENT,
            'stage': 'Phase 1 - initial assessment',
            'effective_notification_datetime': '2025-04-11T00:00:00Z',  # prior Friday
            'events': [],
        }
        digest = self._run([merger], monkeypatch, previous_digest={})
        assert [m['merger_id'] for m in digest['new_deals_notified']] == ['MN-102']

    # -----------------------------------------------------------------
    # Deduplication against last week's digest
    # -----------------------------------------------------------------

    def test_merger_already_in_previous_cleared_is_not_repeated(self, monkeypatch):
        """If last week's digest already surfaced this determination (even with
        a prior-week determination date), this week's digest must not repeat it,
        regardless of any ACCC page edits since then."""
        merger = {
            'merger_id': 'MN-200',
            'merger_name': 'Already digested',
            'status': merger_status.ASSESSMENT_COMPLETED,
            'stage': 'Phase 1 - initial assessment',
            'effective_notification_datetime': '2025-03-01T00:00:00Z',
            'determination_publication_date': '2025-04-09T00:00:00Z',  # prior Wed
            'accc_determination': merger_status.APPROVED,
            'events': [],
        }
        previous_digest = {
            'deals_cleared': [{'merger_id': 'MN-200'}],
        }
        digest = self._run([merger], monkeypatch, previous_digest=previous_digest)
        assert digest['deals_cleared'] == []

    def test_merger_already_in_previous_notifications_is_not_repeated(self, monkeypatch):
        merger = {
            'merger_id': 'MN-201',
            'merger_name': 'Already notified last week',
            'status': merger_status.UNDER_ASSESSMENT,
            'stage': 'Phase 1 - initial assessment',
            'effective_notification_datetime': '2025-04-09T00:00:00Z',
            'events': [],
        }
        previous_digest = {
            'new_deals_notified': [{'merger_id': 'MN-201'}],
        }
        digest = self._run([merger], monkeypatch, previous_digest=previous_digest)
        assert digest['new_deals_notified'] == []

    def test_merger_already_in_previous_declined_is_not_repeated(self, monkeypatch):
        merger = {
            'merger_id': 'MN-202',
            'merger_name': 'Already declined last week',
            'status': merger_status.ASSESSMENT_COMPLETED,
            'stage': 'Phase 1 - initial assessment',
            'effective_notification_datetime': '2025-03-01T00:00:00Z',
            'determination_publication_date': '2025-04-09T00:00:00Z',
            'accc_determination': merger_status.NOT_APPROVED,
            'events': [],
        }
        previous_digest = {
            'deals_declined': [{'merger_id': 'MN-202'}],
        }
        digest = self._run([merger], monkeypatch, previous_digest=previous_digest)
        assert digest['deals_declined'] == []

    def test_dedup_is_per_bucket(self, monkeypatch):
        """A merger that appeared last week as 'new notification' and has since
        been cleared should still show up in this week's cleared bucket —
        dedup must be per-bucket, not global by merger_id."""
        merger = {
            'merger_id': 'MN-203',
            'merger_name': 'Notified last week, cleared this week',
            'status': merger_status.ASSESSMENT_COMPLETED,
            'stage': 'Phase 1 - initial assessment',
            'effective_notification_datetime': '2025-04-09T00:00:00Z',
            'determination_publication_date': '2025-04-16T12:00:00Z',  # this week
            'accc_determination': merger_status.APPROVED,
            'events': [],
        }
        previous_digest = {
            'new_deals_notified': [{'merger_id': 'MN-203'}],
            'deals_cleared': [],
        }
        digest = self._run([merger], monkeypatch, previous_digest=previous_digest)
        assert [m['merger_id'] for m in digest['deals_cleared']] == ['MN-203']

    # -----------------------------------------------------------------
    # Lookback window boundary
    # -----------------------------------------------------------------

    def test_determination_older_than_two_weeks_is_not_included(self, monkeypatch):
        """Items outside the 2-week lookback window are not surfaced, even if
        they somehow missed every prior digest."""
        merger = {
            'merger_id': 'MN-300',
            'merger_name': 'Old determination',
            'status': merger_status.ASSESSMENT_COMPLETED,
            'stage': 'Phase 1 - initial assessment',
            'effective_notification_datetime': '2025-02-01T00:00:00Z',
            'determination_publication_date': '2025-03-28T00:00:00Z',  # >2 weeks old
            'accc_determination': merger_status.APPROVED,
            'events': [],
        }
        digest = self._run([merger], monkeypatch, previous_digest={})
        assert digest['deals_cleared'] == []

    def test_period_metadata_reflects_single_week_not_lookback(self, monkeypatch):
        """The period_start/period_end labels must continue to describe the
        current Mon-Sun week; the email and UI rely on that label. The
        widened lookback window is an internal implementation detail."""
        start, end = _period('2025-04-14')
        digest = self._run([], monkeypatch)
        assert digest['period_start'] == start.isoformat()
        assert digest['period_end'] == end.isoformat()

    # -----------------------------------------------------------------
    # Ongoing buckets are current snapshots
    # -----------------------------------------------------------------

    def test_ongoing_phase1_not_deduplicated(self, monkeypatch):
        """Ongoing phase 1/2 lists reflect the current state of open reviews
        and should not be affected by what last week's digest listed."""
        merger = {
            'merger_id': 'MN-400',
            'merger_name': 'Still under phase 1',
            'status': merger_status.UNDER_ASSESSMENT,
            'stage': 'Phase 1 - initial assessment',
            'effective_notification_datetime': '2025-03-20T00:00:00Z',
            'events': [],
        }
        previous_digest = {'ongoing_phase_1': [{'merger_id': 'MN-400'}]}
        digest = self._run([merger], monkeypatch, previous_digest=previous_digest)
        assert [m['merger_id'] for m in digest['ongoing_phase_1']] == ['MN-400']


class TestMainWritesArchive:
    """main() should write both the live digest and a dated archive snapshot,
    and subsequent runs should dedup against the archive (not the live file)."""

    def _setup(self, monkeypatch, tmp_path, mergers, this_monday='2025-04-14'):
        start, end = _period(this_monday)
        output = tmp_path / 'digest.json'
        archive_dir = tmp_path / 'digest-archive'
        monkeypatch.setattr(gwd, 'OUTPUT_PATH', output)
        monkeypatch.setattr(gwd, 'DIGEST_ARCHIVE_DIR', archive_dir)
        monkeypatch.setattr(gwd, 'load_mergers', lambda: mergers)
        monkeypatch.setattr(gwd, 'filter_active', lambda ms: ms)
        monkeypatch.setattr(gwd, 'get_last_week_range', lambda: (start, end))
        return output, archive_dir, start

    def test_writes_both_live_and_archived_copies(self, monkeypatch, tmp_path):
        merger = {
            'merger_id': 'MN-500',
            'merger_name': 'Clearance',
            'status': merger_status.ASSESSMENT_COMPLETED,
            'stage': 'Phase 1 - initial assessment',
            'effective_notification_datetime': '2025-03-20T00:00:00Z',
            'determination_publication_date': '2025-04-16T12:00:00Z',
            'accc_determination': merger_status.APPROVED,
            'events': [],
        }
        output, archive_dir, start = self._setup(monkeypatch, tmp_path, [merger])

        gwd.main()

        assert output.exists()
        archived = archive_dir / f'digest-{start.date().isoformat()}.json'
        assert archived.exists()

        import json
        live = json.loads(output.read_text(encoding='utf-8'))
        snapshot = json.loads(archived.read_text(encoding='utf-8'))
        assert [m['merger_id'] for m in live['deals_cleared']] == ['MN-500']
        assert live == snapshot

    def test_next_week_dedups_against_archive_not_live_file(self, monkeypatch, tmp_path):
        """Simulate: week 1 runs, live digest.json is then overwritten by a
        mid-week re-run, but the dated archive from week 1 is preserved.
        When week 2's scheduled run happens, it must use the week-1 archive
        as the dedup baseline, not the (corrupted-from-its-POV) live file."""
        import json

        # Set up: a week-1 archive containing MN-600 in deals_cleared.
        week1_start, _ = _period('2025-04-07')
        archive_dir = tmp_path / 'digest-archive'
        archive_dir.mkdir()
        week1_archive = archive_dir / f'digest-{week1_start.date().isoformat()}.json'
        week1_archive.write_text(
            json.dumps({'deals_cleared': [{'merger_id': 'MN-600'}]}),
            encoding='utf-8',
        )

        # Simulate a corrupted live digest.json (e.g. left over from an
        # unrelated mid-week rerun that produced a different set).
        output = tmp_path / 'digest.json'
        output.write_text(
            json.dumps({'deals_cleared': []}),  # pretend MN-600 isn't in it
            encoding='utf-8',
        )

        # Now set up the week-2 run.
        week2_start, week2_end = _period('2025-04-14')
        monkeypatch.setattr(gwd, 'OUTPUT_PATH', output)
        monkeypatch.setattr(gwd, 'DIGEST_ARCHIVE_DIR', archive_dir)
        monkeypatch.setattr(gwd, 'get_last_week_range', lambda: (week2_start, week2_end))

        # MN-600 had a prior-week determination; without the archive dedup,
        # the 2-week lookback window would pull it back in.
        merger = {
            'merger_id': 'MN-600',
            'merger_name': 'Already emailed last week',
            'status': merger_status.ASSESSMENT_COMPLETED,
            'stage': 'Phase 1 - initial assessment',
            'effective_notification_datetime': '2025-03-01T00:00:00Z',
            'determination_publication_date': '2025-04-11T00:00:00Z',
            'accc_determination': merger_status.APPROVED,
            'events': [],
        }
        monkeypatch.setattr(gwd, 'load_mergers', lambda: [merger])
        monkeypatch.setattr(gwd, 'filter_active', lambda ms: ms)

        gwd.main()

        live = json.loads(output.read_text(encoding='utf-8'))
        assert live['deals_cleared'] == [], (
            "MN-600 was emailed last week (present in the archive) and must not "
            "be re-included this week even though the live digest.json was "
            "clobbered by a mid-week rerun"
        )
