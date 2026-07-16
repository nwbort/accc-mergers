"""Tests for scripts/ingest_tribunal_snapshot.py.

Covers matching a bookmarklet snapshot to its tribunal_appeals.json entry by
tribunal_url, folding its documents in via scrape_tribunal.merge_documents,
and the CLI-level ingest() loop (dry-run, missing files, unmatched URLs).
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import ingest_tribunal_snapshot as ingest_mod
import scrape_tribunal
from ingest_tribunal_snapshot import find_merger_id, ingest, ingest_snapshot


def _records():
    return {
        'MN-0001': {
            'tribunal_url': 'https://www.competitiontribunal.gov.au/current-matters/act-1-of-2026',
            'documents': [],
        },
        'MN-0002': {
            'tribunal_url': 'https://www.competitiontribunal.gov.au/current-matters/act-2-of-2026/',
            'documents': [],
        },
    }


def _write(path, payload):
    path.write_text(json.dumps(payload), encoding='utf-8')
    return path


class TestFindMergerId:
    def test_matches_exact_url(self):
        assert find_merger_id(_records(), 'https://www.competitiontribunal.gov.au/current-matters/act-1-of-2026') == 'MN-0001'

    def test_matches_ignoring_trailing_slash(self):
        # MN-0002's stored url has a trailing slash; a snapshot captured
        # without one (or vice versa) should still match.
        assert find_merger_id(_records(), 'https://www.competitiontribunal.gov.au/current-matters/act-2-of-2026') == 'MN-0002'

    def test_no_match_returns_none(self):
        assert find_merger_id(_records(), 'https://www.competitiontribunal.gov.au/current-matters/act-99-of-2026') is None

    def test_empty_records(self):
        assert find_merger_id({}, 'https://example.com') is None


class TestIngestSnapshot:
    def test_merges_documents_and_reports_change(self, tmp_path):
        records = _records()
        snapshot = _write(tmp_path / 'snap.json', {
            'tribunal_url': 'https://www.competitiontribunal.gov.au/current-matters/act-1-of-2026',
            'documents': [
                {'date': '2026-07-15', 'filed_by': 'Coles', 'description': 'Application for Review',
                 'confidentiality': 'Non-confidential', 'url': 'https://www.competitiontribunal.gov.au/x/App.pdf'},
            ],
        })

        merger_id, changed = ingest_snapshot(snapshot, records, dry_run=False, download=False)

        assert merger_id == 'MN-0001'
        assert changed is True
        assert records['MN-0001']['documents'][0]['description'] == 'Application for Review'
        # The other record is untouched.
        assert records['MN-0002']['documents'] == []

    def test_dry_run_does_not_mutate_records(self, tmp_path):
        records = _records()
        snapshot = _write(tmp_path / 'snap.json', {
            'tribunal_url': 'https://www.competitiontribunal.gov.au/current-matters/act-1-of-2026',
            'documents': [{'date': '2026-07-15', 'description': 'Doc', 'url': 'https://x/doc.pdf'}],
        })

        merger_id, changed = ingest_snapshot(snapshot, records, dry_run=True, download=False)

        assert merger_id == 'MN-0001'
        assert changed is True  # reported as "would change" ...
        assert records['MN-0001']['documents'] == []  # ... but nothing is mutated

    def test_preserves_existing_url_gh(self, tmp_path):
        # merge_documents carries over a hand-set/previously-downloaded
        # url_gh for a document matched by url, same as a normal scrape.
        records = _records()
        records['MN-0001']['documents'] = [
            {'date': '2026-07-15', 'url': 'https://www.competitiontribunal.gov.au/x/App.pdf',
             'url_gh': '/mergers/MN-0001/App.pdf'},
        ]
        snapshot = _write(tmp_path / 'snap.json', {
            'tribunal_url': 'https://www.competitiontribunal.gov.au/current-matters/act-1-of-2026',
            'documents': [
                {'date': '2026-07-15', 'description': 'Application for Review',
                 'url': 'https://www.competitiontribunal.gov.au/x/App.pdf'},
            ],
        })

        ingest_snapshot(snapshot, records, dry_run=False, download=False)

        assert records['MN-0001']['documents'][0]['url_gh'] == '/mergers/MN-0001/App.pdf'

    def test_unmatched_tribunal_url_leaves_records_untouched(self, tmp_path):
        records = _records()
        snapshot = _write(tmp_path / 'snap.json', {
            'tribunal_url': 'https://www.competitiontribunal.gov.au/current-matters/act-99-of-2026',
            'documents': [{'date': '2026-07-15', 'description': 'Doc', 'url': 'https://x/doc.pdf'}],
        })

        merger_id, changed = ingest_snapshot(snapshot, records, dry_run=False, download=False)

        assert merger_id is None
        assert changed is False
        assert records['MN-0001']['documents'] == []

    def test_missing_documents_key_is_skipped(self, tmp_path):
        records = _records()
        snapshot = _write(tmp_path / 'snap.json', {'tribunal_url': 'https://www.competitiontribunal.gov.au/current-matters/act-1-of-2026'})

        merger_id, changed = ingest_snapshot(snapshot, records, dry_run=False, download=False)

        assert merger_id is None
        assert changed is False

    def test_invalid_json_is_skipped(self, tmp_path):
        records = _records()
        snapshot = tmp_path / 'snap.json'
        snapshot.write_text('not json', encoding='utf-8')

        merger_id, changed = ingest_snapshot(snapshot, records, dry_run=False, download=False)

        assert merger_id is None
        assert changed is False

    def test_download_true_calls_download_document_per_url(self, tmp_path, monkeypatch):
        calls = []

        def fake_download_document(merger_id, url):
            calls.append((merger_id, url))
            return f'/mergers/{merger_id}/mirrored.pdf'

        monkeypatch.setattr(ingest_mod, 'download_document', fake_download_document)

        records = _records()
        snapshot = _write(tmp_path / 'snap.json', {
            'tribunal_url': 'https://www.competitiontribunal.gov.au/current-matters/act-1-of-2026',
            'documents': [{'date': '2026-07-15', 'description': 'Doc', 'url': 'https://x/doc.pdf'}],
        })

        ingest_snapshot(snapshot, records, dry_run=False, download=True)

        assert calls == [('MN-0001', 'https://x/doc.pdf')]
        assert records['MN-0001']['documents'][0]['url_gh'] == '/mergers/MN-0001/mirrored.pdf'

    def test_content_base64_uses_save_document_content_not_download(self, tmp_path, monkeypatch):
        # When the bookmarklet embedded the file bytes, ingest should write
        # them directly rather than falling back to a network fetch.
        save_calls = []
        download_calls = []

        monkeypatch.setattr(
            ingest_mod, 'save_document_content',
            lambda merger_id, url, content_base64: save_calls.append((merger_id, url, content_base64))
            or f'/mergers/{merger_id}/embedded.pdf',
        )
        monkeypatch.setattr(
            ingest_mod, 'download_document',
            lambda merger_id, url: download_calls.append((merger_id, url)) or '/mergers/x/should-not-happen.pdf',
        )

        records = _records()
        snapshot = _write(tmp_path / 'snap.json', {
            'tribunal_url': 'https://www.competitiontribunal.gov.au/current-matters/act-1-of-2026',
            'documents': [{
                'date': '2026-07-15', 'description': 'Doc', 'url': 'https://x/doc.pdf',
                'content_base64': 'ZmFrZS1wZGYtYnl0ZXM=',
            }],
        })

        ingest_snapshot(snapshot, records, dry_run=False, download=True)

        assert save_calls == [('MN-0001', 'https://x/doc.pdf', 'ZmFrZS1wZGYtYnl0ZXM=')]
        assert download_calls == []
        assert records['MN-0001']['documents'][0]['url_gh'] == '/mergers/MN-0001/embedded.pdf'
        # The transient field must never end up persisted in the merged record.
        assert 'content_base64' not in records['MN-0001']['documents'][0]

    def test_content_error_falls_back_to_download_document(self, tmp_path, monkeypatch):
        calls = []
        monkeypatch.setattr(
            ingest_mod, 'download_document',
            lambda merger_id, url: calls.append((merger_id, url)) or f'/mergers/{merger_id}/mirrored.pdf',
        )

        records = _records()
        snapshot = _write(tmp_path / 'snap.json', {
            'tribunal_url': 'https://www.competitiontribunal.gov.au/current-matters/act-1-of-2026',
            'documents': [{
                'date': '2026-07-15', 'description': 'Doc', 'url': 'https://x/doc.pdf',
                'content_error': 'HTTP 403',
            }],
        })

        ingest_snapshot(snapshot, records, dry_run=False, download=True)

        assert calls == [('MN-0001', 'https://x/doc.pdf')]
        assert records['MN-0001']['documents'][0]['url_gh'] == '/mergers/MN-0001/mirrored.pdf'
        assert 'content_error' not in records['MN-0001']['documents'][0]

    def test_content_base64_stripped_even_when_not_downloading(self, tmp_path):
        # --no-download / dry-run must not leave content_base64 sitting in
        # the persisted documents list.
        records = _records()
        snapshot = _write(tmp_path / 'snap.json', {
            'tribunal_url': 'https://www.competitiontribunal.gov.au/current-matters/act-1-of-2026',
            'documents': [{
                'date': '2026-07-15', 'description': 'Doc', 'url': 'https://x/doc.pdf',
                'content_base64': 'ZmFrZS1wZGYtYnl0ZXM=',
            }],
        })

        ingest_snapshot(snapshot, records, dry_run=False, download=False)

        assert 'content_base64' not in records['MN-0001']['documents'][0]


class TestIngestCli:
    def test_writes_updated_json(self, tmp_path, monkeypatch):
        appeals_path = tmp_path / 'tribunal_appeals.json'
        _write(appeals_path, _records())
        monkeypatch.setattr(scrape_tribunal, 'TRIBUNAL_APPEALS_JSON', appeals_path)

        snapshot = _write(tmp_path / 'snap.json', {
            'tribunal_url': 'https://www.competitiontribunal.gov.au/current-matters/act-1-of-2026',
            'documents': [{'date': '2026-07-15', 'description': 'Doc', 'url': 'https://x/doc.pdf'}],
        })

        exit_code = ingest([str(snapshot)], dry_run=False, download=False)

        assert exit_code == 0
        written = json.loads(appeals_path.read_text())
        assert written['MN-0001']['documents'][0]['description'] == 'Doc'

    def test_dry_run_writes_nothing(self, tmp_path, monkeypatch):
        appeals_path = tmp_path / 'tribunal_appeals.json'
        original = _records()
        _write(appeals_path, original)
        monkeypatch.setattr(scrape_tribunal, 'TRIBUNAL_APPEALS_JSON', appeals_path)

        snapshot = _write(tmp_path / 'snap.json', {
            'tribunal_url': 'https://www.competitiontribunal.gov.au/current-matters/act-1-of-2026',
            'documents': [{'date': '2026-07-15', 'description': 'Doc', 'url': 'https://x/doc.pdf'}],
        })

        exit_code = ingest([str(snapshot)], dry_run=True, download=False)

        assert exit_code == 0
        assert json.loads(appeals_path.read_text()) == original

    def test_missing_file_returns_nonzero_exit(self, tmp_path, monkeypatch):
        appeals_path = tmp_path / 'tribunal_appeals.json'
        _write(appeals_path, _records())
        monkeypatch.setattr(scrape_tribunal, 'TRIBUNAL_APPEALS_JSON', appeals_path)

        exit_code = ingest([str(tmp_path / 'nope.json')], dry_run=False, download=False)

        assert exit_code == 2

    def test_multiple_snapshots_update_different_mergers(self, tmp_path, monkeypatch):
        appeals_path = tmp_path / 'tribunal_appeals.json'
        _write(appeals_path, _records())
        monkeypatch.setattr(scrape_tribunal, 'TRIBUNAL_APPEALS_JSON', appeals_path)

        snap1 = _write(tmp_path / 'snap1.json', {
            'tribunal_url': 'https://www.competitiontribunal.gov.au/current-matters/act-1-of-2026',
            'documents': [{'date': '2026-07-15', 'description': 'Doc1', 'url': 'https://x/1.pdf'}],
        })
        snap2 = _write(tmp_path / 'snap2.json', {
            'tribunal_url': 'https://www.competitiontribunal.gov.au/current-matters/act-2-of-2026',
            'documents': [{'date': '2026-07-16', 'description': 'Doc2', 'url': 'https://x/2.pdf'}],
        })

        exit_code = ingest([str(snap1), str(snap2)], dry_run=False, download=False)

        assert exit_code == 0
        written = json.loads(appeals_path.read_text())
        assert written['MN-0001']['documents'][0]['description'] == 'Doc1'
        assert written['MN-0002']['documents'][0]['description'] == 'Doc2'
