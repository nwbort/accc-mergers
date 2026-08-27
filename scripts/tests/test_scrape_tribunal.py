"""Tests for scripts/scrape/scrape_tribunal.py's parsing and download helpers.

The browser-driving half (nodriver → Chrome, Cloudflare challenge) can only be
exercised end-to-end from CI against the live site; these cover the pure logic
that turns a fetched matter page into document records and mirrors the linked
files: parse_matter_page (including the multiple-table / section handling) and
download_document's url_gh derivation, and the in-page fetch that
download_document_via_browser decodes into a mirrored file — including how a
fetch Cloudflare refuses is retried, and the visit that clears a challenge a
fetch cannot.
"""

import asyncio
import base64
import types

import pytest

from scripts.scrape import scrape_tribunal


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


async def _async_value(value):
    """Wrap a plain value so it can be awaited, standing in for an async API."""
    return value


class FakeTab:
    """Stands in for a nodriver Tab: records the JS it was asked to evaluate
    and replays a canned result (or raises).

    ``results`` takes a list to answer successive calls with — the last entry
    stands for every call after it — so a retry that recovers can be set up.
    """

    def __init__(self, result=None, error=None, results=None):
        self.results = list(results) if results is not None else [result]
        self.error = error
        self.expressions = []

    async def evaluate(self, expression, await_promise=False):
        self.expressions.append(expression)
        if self.error is not None:
            raise self.error
        index = min(len(self.expressions), len(self.results)) - 1
        return self.results[index]


class NotAString:
    """What nodriver hands back when evaluate() can't return a plain value —
    e.g. a RemoteObject or a CDP ExceptionDetails."""


class TestDownloadDocumentViaBrowser:
    @pytest.fixture(autouse=True)
    def _no_retry_delay(self, monkeypatch):
        """Keep the retry backoff out of the suite's runtime."""
        monkeypatch.setattr(scrape_tribunal, 'BROWSER_FETCH_RETRY_SECONDS', 0)

    def test_base64_payload_is_written_to_disk(self, tmp_path, monkeypatch):
        monkeypatch.setattr(scrape_tribunal, 'MATTERS_DIR', tmp_path)
        tab = FakeTab('ok:' + base64.b64encode(b'%PDF-1.7 body').decode())

        url_gh = asyncio.run(scrape_tribunal.download_document_via_browser(
            tab,
            'MN-0001',
            'https://www.competitiontribunal.gov.au/x/Application.pdf',
        ))

        assert url_gh == '/mergers/MN-0001/Application.pdf'
        assert (tmp_path / 'MN-0001' / 'Application.pdf').read_bytes() == b'%PDF-1.7 body'
        # The URL must reach the page as a JSON string literal, not interpolated raw.
        assert '"https://www.competitiontribunal.gov.au/x/Application.pdf"' in tab.expressions[0]

    def test_http_error_returns_none_so_caller_can_fall_back(self, tmp_path, monkeypatch):
        monkeypatch.setattr(scrape_tribunal, 'MATTERS_DIR', tmp_path)
        tab = FakeTab('error:HTTP 403')

        url_gh = asyncio.run(scrape_tribunal.download_document_via_browser(
            tab,
            'MN-0001',
            'https://www.competitiontribunal.gov.au/x/Application.pdf',
        ))

        assert url_gh is None
        assert not (tmp_path / 'MN-0001' / 'Application.pdf').exists()
        # Every attempt was spent before giving up.
        assert len(tab.expressions) == scrape_tribunal.BROWSER_FETCH_ATTEMPTS

    def test_a_challenged_fetch_is_retried_and_recovers(self, tmp_path, monkeypatch):
        # Cloudflare refuses a fetch it wanted to challenge with a 403, but the
        # verdict is per request: the next one is usually served. This is the
        # case that left a document recorded without a local mirror.
        monkeypatch.setattr(scrape_tribunal, 'MATTERS_DIR', tmp_path)
        tab = FakeTab(results=[
            'error:HTTP 403 (cf-mitigated: challenge)',
            'ok:' + base64.b64encode(b'%PDF-1.7 body').decode(),
        ])

        url_gh = asyncio.run(scrape_tribunal.download_document_via_browser(
            tab,
            'MN-0001',
            'https://www.competitiontribunal.gov.au/x/Application.pdf',
        ))

        assert url_gh == '/mergers/MN-0001/Application.pdf'
        assert (tmp_path / 'MN-0001' / 'Application.pdf').read_bytes() == b'%PDF-1.7 body'
        assert len(tab.expressions) == 2

    def test_missing_document_is_not_retried(self, tmp_path, monkeypatch):
        # A 404 will still be a 404 in five seconds; don't spend the attempts.
        monkeypatch.setattr(scrape_tribunal, 'MATTERS_DIR', tmp_path)
        tab = FakeTab('error:HTTP 404')

        url_gh = asyncio.run(scrape_tribunal.download_document_via_browser(
            tab,
            'MN-0001',
            'https://www.competitiontribunal.gov.au/x/Application.pdf',
        ))

        assert url_gh is None
        assert len(tab.expressions) == 1

    def test_challenge_html_is_not_saved_under_the_document_name(self, tmp_path, monkeypatch):
        monkeypatch.setattr(scrape_tribunal, 'MATTERS_DIR', tmp_path)
        challenge = b'<html><title>Just a moment...</title><body>checking</body></html>'
        tab = FakeTab('ok:' + base64.b64encode(challenge).decode())

        url_gh = asyncio.run(scrape_tribunal.download_document_via_browser(
            tab,
            'MN-0001',
            'https://www.competitiontribunal.gov.au/x/Application.pdf',
        ))

        assert url_gh is None
        assert not (tmp_path / 'MN-0001' / 'Application.pdf').exists()

    def test_off_domain_url_is_not_fetched(self, tmp_path, monkeypatch):
        monkeypatch.setattr(scrape_tribunal, 'MATTERS_DIR', tmp_path)
        tab = FakeTab('ok:' + base64.b64encode(b'x').decode())

        url_gh = asyncio.run(scrape_tribunal.download_document_via_browser(
            tab, 'MN-0001', 'https://example.com/doc.pdf'
        ))

        assert url_gh is None
        assert tab.expressions == []

    def test_existing_file_is_not_refetched(self, tmp_path, monkeypatch):
        monkeypatch.setattr(scrape_tribunal, 'MATTERS_DIR', tmp_path)
        matter_dir = tmp_path / 'MN-0001'
        matter_dir.mkdir(parents=True)
        (matter_dir / 'Application.pdf').write_bytes(b'original')
        tab = FakeTab('ok:' + base64.b64encode(b'replacement').decode())

        url_gh = asyncio.run(scrape_tribunal.download_document_via_browser(
            tab,
            'MN-0001',
            'https://www.competitiontribunal.gov.au/x/Application.pdf',
        ))

        assert url_gh == '/mergers/MN-0001/Application.pdf'
        assert tab.expressions == []
        assert (matter_dir / 'Application.pdf').read_bytes() == b'original'

    def test_non_string_result_returns_none(self, tmp_path, monkeypatch):
        # The JS deliberately returns a string, not an object: nodriver asks CDP
        # for deep serialization, which overrides returnByValue, so an object
        # would arrive as a RemoteObject tree and silently never download.
        monkeypatch.setattr(scrape_tribunal, 'MATTERS_DIR', tmp_path)
        tab = FakeTab(NotAString())

        url_gh = asyncio.run(scrape_tribunal.download_document_via_browser(
            tab,
            'MN-0001',
            'https://www.competitiontribunal.gov.au/x/Application.pdf',
        ))

        assert url_gh is None
        assert not (tmp_path / 'MN-0001' / 'Application.pdf').exists()

    def test_evaluate_raising_returns_none(self, tmp_path, monkeypatch):
        monkeypatch.setattr(scrape_tribunal, 'MATTERS_DIR', tmp_path)
        tab = FakeTab(error=RuntimeError('devtools connection lost'))

        url_gh = asyncio.run(scrape_tribunal.download_document_via_browser(
            tab,
            'MN-0001',
            'https://www.competitiontribunal.gov.au/x/Application.pdf',
        ))

        assert url_gh is None


class TestSummariseUrls:
    def test_uses_filenames_not_full_urls(self):
        summary = scrape_tribunal.summarise_urls([
            'https://www.competitiontribunal.gov.au/__data/assets/pdf_file/0008/601001/Documentary-Index.pdf',
        ])
        assert summary == 'Documentary-Index.pdf'

    def test_percent_encoding_is_decoded(self):
        summary = scrape_tribunal.summarise_urls([
            'https://www.competitiontribunal.gov.au/x/Notice%20of%20address.pdf',
        ])
        assert summary == 'Notice of address.pdf'

    def test_long_lists_are_truncated(self):
        urls = [f'https://www.competitiontribunal.gov.au/x/doc{i}.pdf' for i in range(8)]
        summary = scrape_tribunal.summarise_urls(urls, limit=3)
        assert summary == 'doc0.pdf, doc1.pdf, doc2.pdf, and 5 more'


class FakeBrowser:
    def stop(self):
        pass


class FakeProc:
    def terminate(self):
        pass


class TestScrapeMattersUnmirroredReporting:
    """The download loop must tell a failed mirror apart from an off-domain link
    that is never meant to be mirrored."""

    MATTER_HTML = """
    <main>
      <table class="table-bordered">
        <tr><th>Date</th><th>Document</th></tr>
        <tr><td>1 July 2026</td>
            <td><a href="https://www.competitiontribunal.gov.au/x/Good.pdf">Good</a></td></tr>
        <tr><td>2 July 2026</td>
            <td><a href="https://www.competitiontribunal.gov.au/x/Blocked.pdf">Blocked</a></td></tr>
        <tr><td>3 July 2026</td>
            <td><a href="https://example.com/Elsewhere.pdf">Elsewhere</a></td></tr>
      </table>
    </main>
    """

    def _run(self, monkeypatch, warnings):
        monkeypatch.setattr(scrape_tribunal, 'uc', types.SimpleNamespace(
            start=lambda **kwargs: _async_value(FakeBrowser()),
        ))
        monkeypatch.setattr(scrape_tribunal, 'find_chrome', lambda: '/usr/bin/chrome')
        monkeypatch.setattr(scrape_tribunal, 'free_port', lambda: 9999)
        monkeypatch.setattr(scrape_tribunal, 'launch_chrome', lambda *a, **k: FakeProc())
        monkeypatch.setattr(scrape_tribunal, 'wait_for_devtools', lambda port: True)

        async def _fetch_page(browser, url):
            return FakeTab(), self.MATTER_HTML

        monkeypatch.setattr(scrape_tribunal, 'fetch_page', _fetch_page)

        async def _via_browser(tab, mid, url):
            # Only the first tribunal document mirrors successfully.
            if url.endswith('Good.pdf'):
                return f'/mergers/{mid}/Good.pdf'
            return None

        monkeypatch.setattr(scrape_tribunal, 'download_document_via_browser', _via_browser)
        # The requests fallback fails too (that is the 403 case).
        monkeypatch.setattr(scrape_tribunal, 'download_document', lambda *a, **k: None)
        monkeypatch.setattr(scrape_tribunal, 'gha_warning', warnings.append)

        records = {'MN-0001': {'tribunal_url': 'https://www.competitiontribunal.gov.au/m/1'}}
        return asyncio.run(
            scrape_tribunal.scrape_matters(['MN-0001'], records, do_download=True)
        )

    def test_only_tribunal_hosted_failures_are_reported(self, monkeypatch):
        warnings = []
        scraped_by_id, failed, unmirrored = self._run(monkeypatch, warnings)

        assert failed == []
        # The off-domain link is not a mirror failure — it is never mirrored.
        assert unmirrored == [
            ('MN-0001', 'https://www.competitiontribunal.gov.au/x/Blocked.pdf')
        ]

        docs = {d['description']: d for d in scraped_by_id['MN-0001']}
        assert docs['Good']['url_gh'] == '/mergers/MN-0001/Good.pdf'
        assert 'url_gh' not in docs['Blocked']
        assert 'url_gh' not in docs['Elsewhere']

    def test_a_warning_annotation_is_raised(self, monkeypatch):
        warnings = []
        self._run(monkeypatch, warnings)

        assert len(warnings) == 1
        assert 'MN-0001' in warnings[0]
        assert 'Blocked.pdf' in warnings[0]
        # The off-domain document must not be named in the warning.
        assert 'Elsewhere.pdf' not in warnings[0]

    def test_no_warning_when_downloads_are_skipped(self, monkeypatch):
        warnings = []
        monkeypatch.setattr(scrape_tribunal, 'uc', types.SimpleNamespace(
            start=lambda **kwargs: _async_value(FakeBrowser()),
        ))
        monkeypatch.setattr(scrape_tribunal, 'find_chrome', lambda: '/usr/bin/chrome')
        monkeypatch.setattr(scrape_tribunal, 'free_port', lambda: 9999)
        monkeypatch.setattr(scrape_tribunal, 'launch_chrome', lambda *a, **k: FakeProc())
        monkeypatch.setattr(scrape_tribunal, 'wait_for_devtools', lambda port: True)

        async def _fetch_page(browser, url):
            return FakeTab(), self.MATTER_HTML

        monkeypatch.setattr(scrape_tribunal, 'fetch_page', _fetch_page)
        monkeypatch.setattr(scrape_tribunal, 'gha_warning', warnings.append)

        records = {'MN-0001': {'tribunal_url': 'https://www.competitiontribunal.gov.au/m/1'}}
        _, failed, unmirrored = asyncio.run(
            scrape_tribunal.scrape_matters(['MN-0001'], records, do_download=False)
        )

        # --no-download / --dry-run skipped them deliberately; not a failure.
        assert failed == []
        assert unmirrored == []
        assert warnings == []


class TestClearChallengeByVisiting:
    """A fetch() can't display Cloudflare's challenge; a navigation can."""

    MATTER_URL = 'https://www.competitiontribunal.gov.au/m/1'
    DOC_URL = 'https://www.competitiontribunal.gov.au/x/Blocked.pdf'

    def _patch_fetch_page(self, monkeypatch, matter_html):
        visited = []

        async def _fetch_page(browser, url):
            visited.append(url)
            if url == self.MATTER_URL:
                return FakeTab(), matter_html
            # A PDF navigation lands on Chrome's viewer, not a challenge.
            return FakeTab(), '<html><body></body></html>'

        monkeypatch.setattr(scrape_tribunal, 'fetch_page', _fetch_page)
        return visited

    def test_visits_the_document_then_returns_to_the_matter_page(self, monkeypatch):
        visited = self._patch_fetch_page(monkeypatch, '<main></main>')

        tab = asyncio.run(scrape_tribunal.clear_challenge_by_visiting(
            FakeBrowser(), self.DOC_URL, self.MATTER_URL
        ))

        assert visited == [self.DOC_URL, self.MATTER_URL]
        assert tab is not None

    def test_returns_none_when_the_matter_page_cannot_be_reloaded(self, monkeypatch):
        # html None means the challenge never cleared; the caller keeps its tab.
        self._patch_fetch_page(monkeypatch, None)

        tab = asyncio.run(scrape_tribunal.clear_challenge_by_visiting(
            FakeBrowser(), self.DOC_URL, self.MATTER_URL
        ))

        assert tab is None


class TestScrapeMattersChallengeRecovery:
    """A document refused once is retried after the challenge is cleared, and
    only counts as unmirrored if that fails too."""

    MATTER_URL = 'https://www.competitiontribunal.gov.au/m/1'
    MATTER_HTML = """
    <main>
      <table class="table-bordered">
        <tr><th>Date</th><th>Document</th></tr>
        <tr><td>1 July 2026</td>
            <td><a href="https://www.competitiontribunal.gov.au/x/Blocked.pdf">Blocked</a></td></tr>
      </table>
    </main>
    """

    def test_the_document_is_mirrored_after_a_visit_clears_the_challenge(
        self, monkeypatch
    ):
        warnings = []
        visited = []
        monkeypatch.setattr(scrape_tribunal, 'uc', types.SimpleNamespace(
            start=lambda **kwargs: _async_value(FakeBrowser()),
        ))
        monkeypatch.setattr(scrape_tribunal, 'find_chrome', lambda: '/usr/bin/chrome')
        monkeypatch.setattr(scrape_tribunal, 'free_port', lambda: 9999)
        monkeypatch.setattr(scrape_tribunal, 'launch_chrome', lambda *a, **k: FakeProc())
        monkeypatch.setattr(scrape_tribunal, 'wait_for_devtools', lambda port: True)

        async def _fetch_page(browser, url):
            visited.append(url)
            if url == self.MATTER_URL:
                return FakeTab(), self.MATTER_HTML
            return FakeTab(), '<html><body></body></html>'

        monkeypatch.setattr(scrape_tribunal, 'fetch_page', _fetch_page)

        attempts = []

        async def _via_browser(tab, mid, url):
            attempts.append(url)
            # Refused the first time, served once the challenge has been cleared.
            return None if len(attempts) == 1 else f'/mergers/{mid}/Blocked.pdf'

        monkeypatch.setattr(scrape_tribunal, 'download_document_via_browser', _via_browser)
        monkeypatch.setattr(scrape_tribunal, 'download_document', lambda *a, **k: None)
        monkeypatch.setattr(scrape_tribunal, 'gha_warning', warnings.append)

        records = {'MN-0001': {'tribunal_url': self.MATTER_URL}}
        scraped_by_id, failed, unmirrored = asyncio.run(
            scrape_tribunal.scrape_matters(['MN-0001'], records, do_download=True)
        )

        assert failed == []
        assert unmirrored == []
        assert warnings == []
        assert scraped_by_id['MN-0001'][0]['url_gh'] == '/mergers/MN-0001/Blocked.pdf'
        # The document itself was visited, then the matter page re-loaded.
        assert visited == [
            self.MATTER_URL,
            'https://www.competitiontribunal.gov.au/x/Blocked.pdf',
            self.MATTER_URL,
        ]
