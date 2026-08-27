"""Tests for scrape_summary.py — the scrape run's step-summary Markdown.

The summary exists for spot checking: when an ACCC register email says a
matter changed, the run's summary has to show whether that merger ID was
fetched at all, and whether its page actually changed.
"""

import json
import sys
import unittest.mock

sys.modules.setdefault('pdfplumber', unittest.mock.MagicMock())
sys.modules.setdefault('markdownify', unittest.mock.MagicMock())
sys.modules.setdefault('requests', unittest.mock.MagicMock())

from scripts.scrape.scrape_summary import (INLINE_LIMIT, load_changed_ids, load_fetched,
                            load_stats, render)


def _report(tmp_path, fetched_rows=None, stats=None):
    if fetched_rows is not None:
        (tmp_path / 'fetched.tsv').write_text(
            ''.join(f'{s}\t{m}\t{p}\n' for s, m, p in fetched_rows)
        )
    if stats is not None:
        (tmp_path / 'targets.json').write_text(json.dumps(stats))
    return str(tmp_path)


class TestLoadFetched:
    def test_splits_ok_from_failed(self, tmp_path):
        report = _report(tmp_path, [('ok', 'MN-1', '/a'), ('failed', 'UNKNOWN', '/b')])

        ok, failed = load_fetched(report)

        assert [e['merger_id'] for e in ok] == ['MN-1']
        assert [e['path'] for e in failed] == ['/b']

    def test_missing_file(self, tmp_path):
        assert load_fetched(str(tmp_path)) == ([], [])

    def test_malformed_rows_are_ignored(self, tmp_path):
        report = _report(tmp_path, None)
        (tmp_path / 'fetched.tsv').write_text('ok\tMN-1\n\nok\tMN-2\t/b\n')

        ok, failed = load_fetched(report)

        assert [e['merger_id'] for e in ok] == ['MN-2']
        assert failed == []


class TestLoadStats:
    def test_missing_file(self, tmp_path):
        assert load_stats(str(tmp_path)) == {}

    def test_malformed_json(self, tmp_path):
        (tmp_path / 'targets.json').write_text('{not json')
        assert load_stats(str(tmp_path)) == {}

    def test_reads_stats(self, tmp_path):
        report = _report(tmp_path, stats={'listing': 7})
        assert load_stats(report)['listing'] == 7


class TestLoadChangedIds:
    def test_keys_off_the_matter_filename(self, tmp_path):
        path = tmp_path / 'changed.txt'
        path.write_text('data/raw/matters/MN-100123.html\n'
                        'data/raw/matters/WA-100456.html\n')

        assert load_changed_ids(str(path)) == {'MN-100123', 'WA-100456'}

    def test_ignores_attachments_and_other_files(self, tmp_path):
        path = tmp_path / 'changed.txt'
        path.write_text('data/raw/matters/MN-1/questionnaire.pdf\n'
                        'data/raw/acquisitions-register.html\n'
                        'data/processed/mergers.json\n')

        assert load_changed_ids(str(path)) == set()

    def test_strips_quoting_git_adds_to_unusual_paths(self, tmp_path):
        path = tmp_path / 'changed.txt'
        path.write_text('"data/raw/matters/MN-100123.html"\n')

        assert load_changed_ids(str(path)) == {'MN-100123'}

    def test_no_file_given(self):
        assert load_changed_ids(None) == set()


class TestRender:
    def test_lists_every_scraped_merger_id(self):
        out = render({}, [{'merger_id': 'MN-2', 'path': '/b'},
                          {'merger_id': 'MN-1', 'path': '/a'}], [], set())

        assert '**Merger IDs scraped (2):** `MN-1`, `MN-2`' in out

    def test_flags_which_pages_changed(self):
        fetched = [{'merger_id': 'MN-1', 'path': '/a'},
                   {'merger_id': 'MN-2', 'path': '/b'}]

        out = render({}, fetched, [], {'MN-2'})

        assert '**Changed this run (1):** `MN-2`' in out
        assert '| Pages changed | 1 |' in out

    def test_ignores_changed_pages_the_run_did_not_fetch(self):
        # A page left dirty by an earlier run is not this run's doing.
        out = render({}, [{'merger_id': 'MN-1', 'path': '/a'}], [], {'MN-9'})

        assert '| Pages changed | 0 |' in out
        assert 'MN-9' not in out

    def test_names_matters_skipped_past_cutoff(self):
        stats = {'skipped': 1,
                 'skipped_mergers': [{'merger_id': 'MN-5', 'path': '/e'}]}

        out = render(stats, [], [], set())

        assert '| Skipped (past cutoff) | 1 |' in out
        assert '`MN-5`' in out

    def test_names_matters_recovered_from_outside_the_listing(self):
        stats = {'recovered': 1,
                 'recovered_mergers': [{'merger_id': 'MN-6', 'path': '/f'}]}

        out = render(stats, [], [], set())

        assert 'Recovered from outside the listing (1):** `MN-6`' in out

    def test_reports_fetch_failures(self):
        out = render({}, [], [{'merger_id': 'UNKNOWN', 'path': '/broken'}], set())

        assert '| Fetch failures | 1 |' in out
        assert '`/broken`' in out

    def test_long_lists_are_collapsed(self):
        fetched = [{'merger_id': f'MN-{i}', 'path': f'/{i}'}
                   for i in range(INLINE_LIMIT + 1)]

        out = render({}, fetched, [], set())

        assert '<details>' in out
        assert f'<summary>Merger IDs scraped ({INLINE_LIMIT + 1})</summary>' in out

    def test_empty_run_says_so(self):
        out = render({'listing': 0}, [], [], set())

        assert 'No matter pages were fetched.' in out
        assert 'No matter pages changed in this run.' in out

    def test_no_report_at_all(self):
        out = render({}, [], [], set())

        assert 'No scrape report was produced' in out
