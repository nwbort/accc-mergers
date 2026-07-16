"""Tests for scripts/scrape_tribunal.py's document-saving helpers.

Focused on save_document_content, the bookmarklet-snapshot counterpart to
download_document: it writes bytes already fetched client-side (past
Cloudflare) rather than making its own HTTP request.
"""

import base64
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import scrape_tribunal


class TestSaveDocumentContent:
    def test_writes_file_and_returns_url_gh(self, tmp_path, monkeypatch):
        monkeypatch.setattr(scrape_tribunal, 'MATTERS_DIR', tmp_path)
        content = b'%PDF-1.4 fake pdf bytes'

        url_gh = scrape_tribunal.save_document_content(
            'MN-0001',
            'https://www.competitiontribunal.gov.au/x/Application.pdf',
            base64.b64encode(content).decode('ascii'),
        )

        assert url_gh == '/mergers/MN-0001/Application.pdf'
        written = tmp_path / 'MN-0001' / 'Application.pdf'
        assert written.read_bytes() == content

    def test_off_domain_url_is_rejected(self, tmp_path, monkeypatch):
        monkeypatch.setattr(scrape_tribunal, 'MATTERS_DIR', tmp_path)

        url_gh = scrape_tribunal.save_document_content(
            'MN-0001', 'https://example.com/doc.pdf', base64.b64encode(b'x').decode('ascii'),
        )

        assert url_gh is None
        assert not (tmp_path / 'MN-0001').exists()

    def test_existing_file_is_not_overwritten(self, tmp_path, monkeypatch):
        monkeypatch.setattr(scrape_tribunal, 'MATTERS_DIR', tmp_path)
        matter_dir = tmp_path / 'MN-0001'
        matter_dir.mkdir(parents=True)
        (matter_dir / 'Application.pdf').write_bytes(b'original')

        url_gh = scrape_tribunal.save_document_content(
            'MN-0001',
            'https://www.competitiontribunal.gov.au/x/Application.pdf',
            base64.b64encode(b'new-content').decode('ascii'),
        )

        assert url_gh == '/mergers/MN-0001/Application.pdf'
        assert (matter_dir / 'Application.pdf').read_bytes() == b'original'

    def test_invalid_base64_returns_none(self, tmp_path, monkeypatch):
        monkeypatch.setattr(scrape_tribunal, 'MATTERS_DIR', tmp_path)

        url_gh = scrape_tribunal.save_document_content(
            'MN-0001', 'https://www.competitiontribunal.gov.au/x/Application.pdf', 'not-valid-base64!!!',
        )

        assert url_gh is None

    def test_docx_served_as_pdf_same_as_download_document(self, tmp_path, monkeypatch):
        monkeypatch.setattr(scrape_tribunal, 'MATTERS_DIR', tmp_path)

        url_gh = scrape_tribunal.save_document_content(
            'MN-0001',
            'https://www.competitiontribunal.gov.au/x/Submission.docx',
            base64.b64encode(b'docx-bytes').decode('ascii'),
        )

        assert url_gh == '/mergers/MN-0001/Submission.pdf'
        assert (tmp_path / 'MN-0001' / 'Submission.docx').exists()
