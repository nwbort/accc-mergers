"""Tests for scripts/scrape_tribunal.py's parsing and download helpers.

The browser-driving half (nodriver → Chrome, Cloudflare challenge) can only be
exercised end-to-end from CI against the live site; these cover the pure logic
that turns a fetched matter page into document records and mirrors the linked
files: parse_matter_page (including the multiple-table / section handling) and
download_document's url_gh derivation.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import scrape_tribunal


BASE_URL = 'https://www.competitiontribunal.gov.au/current-matters/act-1-of-2026'


class TestParseMatterPageSingleTable:
    def test_columns_matched_by_header(self):
        html = """
        <main>
          <table class="table-bordered">
            <thead><tr>
              <th>Date filed</th><th>Filed by</th>
              <th>Document</th><th>Confidentiality</th>
            </tr></thead>
            <tbody>
              <tr>
                <td>15 July 2026</td>
                <td>Coles Supermarkets</td>
                <td><a href="/x/Application-for-Review.pdf">Application for review (PDF, 537.8 KB)</a></td>
                <td>Non-confidential</td>
              </tr>
            </tbody>
          </table>
        </main>
        """
        docs = scrape_tribunal.parse_matter_page(html, BASE_URL)
        assert len(docs) == 1
        doc = docs[0]
        assert doc['date'] == '2026-07-15'
        assert doc['filed_by'] == 'Coles Supermarkets'
        # The trailing "(PDF, 537.8 KB)" annotation is stripped from the title.
        assert doc['description'] == 'Application for review'
        assert doc['confidentiality'] == 'Non-confidential'
        # Relative hrefs are resolved against the page URL.
        assert doc['url'] == (
            'https://www.competitiontribunal.gov.au/x/Application-for-Review.pdf'
        )
        # The first (main) table's documents carry no section.
        assert 'section' not in doc

    def test_header_row_inside_tbody_is_not_parsed_as_document(self):
        # The live tribunal table has no <thead>: its header row sits inside
        # <tbody> as the first <tr>. That row must drive column mapping without
        # also being returned as a bogus "Date filed / Description" document.
        html = """
        <main>
          <table class="table-bordered">
            <tbody>
              <tr>
                <th>Date filed</th><th>Filed by</th>
                <th>Document</th><th>Confidentiality</th>
              </tr>
              <tr>
                <td>21 July 2026</td><td>-</td>
                <td><a href="/x/Directions.pdf">Directions</a></td>
                <td>Non-confidential</td>
              </tr>
            </tbody>
          </table>
        </main>
        """
        docs = scrape_tribunal.parse_matter_page(html, BASE_URL)
        assert len(docs) == 1
        assert docs[0]['description'] == 'Directions'
        assert docs[0]['date'] == '2026-07-21'

    def test_reordered_columns_still_matched(self):
        # Column order varies across matter pages; matching is by header text.
        html = """
        <table class="table-bordered">
          <tr><th>Document</th><th>Confidentiality</th><th>Date</th></tr>
          <tr>
            <td><a href="/x/Directions.pdf">Directions</a></td>
            <td>Confidential</td>
            <td>21/07/2026</td>
          </tr>
        </table>
        """
        docs = scrape_tribunal.parse_matter_page(html, BASE_URL)
        assert len(docs) == 1
        assert docs[0]['description'] == 'Directions'
        assert docs[0]['confidentiality'] == 'Confidential'
        assert docs[0]['date'] == '2026-07-21'


class TestParseMatterPageMultipleTables:
    def test_second_table_documents_carry_section_from_h3(self):
        html = """
        <main>
          <table class="table-bordered">
            <thead><tr><th>Date</th><th>Document</th></tr></thead>
            <tbody>
              <tr><td>15 July 2026</td>
                  <td><a href="/x/Application.pdf">Application for review</a></td></tr>
            </tbody>
          </table>
          <h3>Submissions by interested party</h3>
          <table class="table-bordered">
            <thead><tr><th>Date</th><th>Document</th></tr></thead>
            <tbody>
              <tr><td>20 July 2026</td>
                  <td><a href="/x/Intervene.pdf">Application for Leave to Intervene</a></td></tr>
            </tbody>
          </table>
        </main>
        """
        docs = scrape_tribunal.parse_matter_page(html, BASE_URL)
        assert len(docs) == 2

        main_doc = docs[0]
        assert main_doc['description'] == 'Application for review'
        # First table → no section.
        assert 'section' not in main_doc

        grouped_doc = docs[1]
        assert grouped_doc['description'] == 'Application for Leave to Intervene'
        # Later table → tagged with the nearest preceding <h3>.
        assert grouped_doc['section'] == 'Submissions by interested party'

    def test_each_later_table_gets_its_own_preceding_heading(self):
        html = """
        <main>
          <table class="table-bordered">
            <tr><th>Date</th><th>Document</th></tr>
            <tr><td>1 July 2026</td><td><a href="/a.pdf">Main doc</a></td></tr>
          </table>
          <h3>Group A</h3>
          <table class="table-bordered">
            <tr><th>Date</th><th>Document</th></tr>
            <tr><td>2 July 2026</td><td><a href="/b.pdf">Doc B</a></td></tr>
          </table>
          <h3>Group B</h3>
          <table class="table-bordered">
            <tr><th>Date</th><th>Document</th></tr>
            <tr><td>3 July 2026</td><td><a href="/c.pdf">Doc C</a></td></tr>
          </table>
        </main>
        """
        docs = scrape_tribunal.parse_matter_page(html, BASE_URL)
        sections = [d.get('section') for d in docs]
        assert sections == [None, 'Group A', 'Group B']

    def test_non_document_tables_are_skipped(self):
        # A layout/table with no recognisable document headers is ignored, and
        # it does not consume the "first table" slot for section tagging.
        html = """
        <main>
          <table class="table-bordered">
            <tr><th>Foo</th><th>Bar</th></tr>
            <tr><td>nope</td><td>nothing here</td></tr>
          </table>
          <table class="table-bordered">
            <tr><th>Date</th><th>Document</th></tr>
            <tr><td>15 July 2026</td><td><a href="/x/App.pdf">Application</a></td></tr>
          </table>
        </main>
        """
        docs = scrape_tribunal.parse_matter_page(html, BASE_URL)
        assert len(docs) == 1
        assert docs[0]['description'] == 'Application'


class TestDownloadDocument:
    def test_off_domain_url_is_not_mirrored(self, tmp_path, monkeypatch):
        monkeypatch.setattr(scrape_tribunal, 'MATTERS_DIR', tmp_path)
        url_gh = scrape_tribunal.download_document(
            'MN-0001', 'https://example.com/doc.pdf'
        )
        assert url_gh is None
        assert not (tmp_path / 'MN-0001').exists()

    def test_existing_file_returns_url_gh_without_redownloading(self, tmp_path, monkeypatch):
        monkeypatch.setattr(scrape_tribunal, 'MATTERS_DIR', tmp_path)
        matter_dir = tmp_path / 'MN-0001'
        matter_dir.mkdir(parents=True)
        (matter_dir / 'Application.pdf').write_bytes(b'original')

        def _fail(*args, **kwargs):  # requests.get must not be called
            raise AssertionError('should not re-download an existing file')

        monkeypatch.setattr(scrape_tribunal.requests, 'get', _fail)

        url_gh = scrape_tribunal.download_document(
            'MN-0001',
            'https://www.competitiontribunal.gov.au/x/Application.pdf',
        )
        assert url_gh == '/mergers/MN-0001/Application.pdf'
        assert (matter_dir / 'Application.pdf').read_bytes() == b'original'

    def test_docx_served_as_pdf(self, tmp_path, monkeypatch):
        monkeypatch.setattr(scrape_tribunal, 'MATTERS_DIR', tmp_path)
        matter_dir = tmp_path / 'MN-0001'
        matter_dir.mkdir(parents=True)
        # Pretend it's already mirrored so we exercise only the url_gh mapping.
        (matter_dir / 'Submission.docx').write_bytes(b'docx-bytes')

        url_gh = scrape_tribunal.download_document(
            'MN-0001',
            'https://www.competitiontribunal.gov.au/x/Submission.docx',
        )
        # DOCX is served as the PDF the convert workflow produces.
        assert url_gh == '/mergers/MN-0001/Submission.pdf'
