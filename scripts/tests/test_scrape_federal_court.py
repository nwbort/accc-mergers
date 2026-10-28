"""Tests for the Federal Court scraper (scripts/scrape/scrape_federal_court.py)
and the Commonwealth Courts Portal parser it uses (comcourts_portal.py).

The portal pages under fixtures/comcourts/ are the real pages for
NSD1310/2026 (Coles' judicial review of MN-01068), saved as fetched, so the
parser is checked against the portal's actual markup. fetch_file is driven
from them through a fake session; the judgments site, which needs Chrome, is
stubbed at download_judgment_page.
"""

import asyncio
import json
from pathlib import Path

import pytest

from scripts.scrape import comcourts_portal as portal
from scripts.scrape import scrape_federal_court as fc

FIXTURES = Path(__file__).resolve().parent / 'fixtures' / 'comcourts'
BASE = 'https://www.comcourts.gov.au/file/Federal/P/NSD1310/2026'


def _fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding='utf-8')


class FakeSession:
    """Answers the portal's URLs from the saved pages, and records requests."""

    def __init__(self, files: dict[str, bytes] | None = None):
        self.requested: list[str] = []
        self.files = files or {}

    def get_html(self, url: str) -> str:
        self.requested.append(url)
        path = url.split('?')[0]
        for suffix, name in (
            ('/actions', 'actions.html'),
            ('/events_and_orders', 'events_and_orders.html'),
            ('/documents_filed', 'documents_filed.html'),
            ('/parties', 'parties.html'),
            ('/outcomes', 'outcomes.html'),
        ):
            if path.endswith(suffix):
                return _fixture(name)
        if '/party_contact/' in path:
            return _fixture('party_contact.html')
        raise portal.FetchError(f'unexpected URL {url}')

    def get(self, url: str):
        self.requested.append(url)
        if url in self.files:
            return self.files[url], {
                'Content-Disposition': f'attachment; filename="P_NSD1310_2026_{url.rsplit("/", 1)[-1]}.pdf"'
            }
        raise portal.FetchError(f'unexpected download {url}')


def _fetch(previous=None, session=None):
    return portal.fetch_file(session or FakeSession(), portal.parse_file_ref('NSD1310/2026'), previous)


# --- Portal parsing ----------------------------------------------------------


class TestParseFileRef:
    def test_number(self):
        assert portal.parse_file_ref('NSD1310/2026') == {
            'court': 'Federal', 'kind': 'P', 'number': 'NSD1310', 'year': '2026',
        }

    def test_portal_url_lower_case(self):
        ref = portal.parse_file_ref('https://www.comcourts.gov.au/file/Federal/P/nsd1310/2026/actions')
        assert ref['number'] == 'NSD1310'
        assert portal.file_base_url(ref) == BASE

    def test_rejects_other_text(self):
        with pytest.raises(ValueError):
            portal.parse_file_ref('not a file')


class TestJudgmentLink:
    def test_single_judge(self):
        assert portal.judgment_link('2026', 'FCA', '1000') == {
            'citation': '[2026] FCA 1000',
            'url': 'https://www.judgments.fedcourt.gov.au/judgments/Judgments/fca/single/2026/2026fca1000',
        }

    def test_full_court_pads_number(self):
        assert portal.judgment_link('2026', 'FCAFC', '7')['url'].endswith('/fca/full/2026/2026fcafc0007')

    def test_unknown_court_has_no_url(self):
        assert portal.judgment_link('2026', 'HCA', '1') == {'citation': '[2026] HCA 1'}


class TestParsePages:
    def test_file_details(self):
        details = portal.parse_file_details(_fixture('actions.html'))
        assert details['number'] == 'NSD1310/2026'
        assert details['filing_date'] == '2026-07-17'
        assert details['finalised_date'] == '2026-08-27'
        assert details['court'].startswith('Federal Court of Australia')

    def test_applications(self):
        apps = portal.parse_applications(_fixture('actions.html'), f'{BASE}/actions')
        assert len(apps) == 1
        app = apps[0]
        assert app['id'] == '4066335'
        assert app['type'] == 'Judicial Review'
        assert app['status'] == 'Closed'
        assert set(app['_urls']) == {'events-and-orders', 'documents-filed', 'parties'}

    def test_events_with_orders_and_judgment(self):
        events = portal.parse_events(_fixture('events_and_orders.html'), f'{BASE}/4066335/events_and_orders')
        assert [e['date'] for e in events] == [
            '2026-08-27', '2026-08-07', '2026-07-28', '2026-07-24', '2026-07-21',
        ]
        judgment = events[2]
        assert judgment['reason'] == 'Judgment'
        assert judgment['orders'] == [{
            'title': 'View orders',
            'url': f'{BASE}/4066335/event/33021628/document/2835642',
        }]
        assert judgment['judgments'][0]['citation'] == '[2026] FCA 1000'
        # Listings of one court event share its id; only the first expands to
        # its outcomes.
        assert events[0]['event_id'] == events[1]['event_id'] == '33079582'
        assert '_outcomes_url' in events[0] and '_outcomes_url' not in events[1]
        assert events[0]['outcome'] == 'Finalised - Discontinued/Withdrawn'

    def test_documents_filed(self):
        docs = portal.parse_documents_filed(_fixture('documents_filed.html'))
        assert docs[0] == {
            'date': '2026-08-25', 'time': '11:27',
            'title': 'Notice of Discontinuance',
            'filed_by': 'Coles Supermarkets Australia Pty Limited',
        }
        assert len(docs) == 5

    def test_parties_and_contact(self):
        parties = portal.parse_parties(_fixture('parties.html'), f'{BASE}/4066335/parties')
        roles = {p['role'] for p in parties}
        assert {'Applicant', 'Respondent', 'Docket'} <= roles
        assert any('_contact_url' in p for p in parties)
        contact = portal.parse_contact(_fixture('party_contact.html'))
        assert contact == {
            'address': 'Level 33 300 George St, BRISBANE 4000',
            'business_fax': '07 3360 5799',
            'business_phone': '07 3360 5600',
        }


class TestFetchFile:
    def test_whole_file(self):
        data = _fetch()
        assert data['file']['url'] == f'{BASE}/actions'
        app = data['applications'][0]
        assert '_urls' not in app
        assert len(app['events']) == 5 and len(app['documents']) == 5
        assert all('_outcomes_url' not in e for e in app['events'])
        assert app['events'][0]['outcomes'][0]['order_type'] == 'Directions Orders'
        # Party contact details are fetched (they are kept, not published).
        lawyers = [p for p in app['parties'] if p['role'].startswith('Legal Representative')]
        assert lawyers and all(p.get('contact') for p in lawyers)

    def test_reuses_outcomes_and_contacts(self):
        previous = _fetch()
        session = FakeSession()
        _fetch(previous, session)
        assert not any(u.endswith('/outcomes') or '/party_contact/' in u for u in session.requested)


# --- Merging -----------------------------------------------------------------


class TestMergeFiledDocuments:
    def test_dropped_document_is_kept_in_place(self):
        previous = _fetch()
        data = _fetch()
        gone = data['applications'][0]['documents'].pop(1)
        dropped = fc.merge_filed_documents(previous, data)
        assert [doc for _, doc in dropped] == [gone]
        assert data['applications'][0]['documents'] == previous['applications'][0]['documents']

    def test_new_document_first(self):
        previous = _fetch()
        previous['applications'][0]['documents'].pop(0)
        data = _fetch()
        assert fc.merge_filed_documents(previous, data) == []
        assert data['applications'][0]['documents'][0]['title'] == 'Notice of Discontinuance'

    def test_no_previous(self):
        data = _fetch()
        assert fc.merge_filed_documents(None, data) == []
        assert len(data['applications'][0]['documents']) == 5


# --- Downloads ---------------------------------------------------------------


@pytest.fixture
def matters_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(fc, 'MATTERS_DIR', tmp_path)
    monkeypatch.setattr(fc.tribunal, 'MATTERS_DIR', tmp_path)
    return tmp_path


ORDER_A = f'{BASE}/4066335/event/33021628/document/2835642'
ORDER_B = f'{BASE}/4066335/event/33006778/document/2829036'


class TestOrderFilename:
    def test_content_disposition(self):
        headers = {'Content-Disposition': 'attachment; filename="P_NSD1310_2026_2835642.pdf"'}
        assert fc.order_filename(ORDER_A, headers, b'%PDF-1.7') == 'P_NSD1310_2026_2835642.pdf'

    def test_falls_back_to_document_id(self):
        assert fc.order_filename(ORDER_A, {}, b'%PDF-1.7') == '2835642.pdf'

    def test_page_is_not_a_document(self):
        assert fc.order_filename(ORDER_A, {}, b'<html>login</html>') is None

    def test_unsafe_name_is_sanitised(self):
        headers = {'Content-Disposition': 'attachment; filename="../../etc/x.pdf"'}
        assert fc.order_filename(ORDER_A, headers, b'%PDF') == 'x.pdf'


class TestDownloadOrders:
    def test_downloads_and_records_url_gh(self, matters_dir):
        data = _fetch()
        session = FakeSession({ORDER_A: b'%PDF-a', ORDER_B: b'%PDF-b'})
        assert fc.download_orders(session, 'MN-01068', data, None) == []
        orders = [o for e in data['applications'][0]['events'] for o in e.get('orders', [])]
        assert [o['url_gh'] for o in orders] == [
            '/mergers/MN-01068/P_NSD1310_2026_2835642.pdf',
            '/mergers/MN-01068/P_NSD1310_2026_2829036.pdf',
        ]
        assert (matters_dir / 'MN-01068' / 'P_NSD1310_2026_2835642.pdf').read_bytes() == b'%PDF-a'

    def test_saved_order_is_not_refetched(self, matters_dir):
        previous = _fetch()
        fc.download_orders(FakeSession({ORDER_A: b'%PDF-a', ORDER_B: b'%PDF-b'}), 'MN-01068', previous, None)
        data = _fetch()
        session = FakeSession()
        assert fc.download_orders(session, 'MN-01068', data, previous) == []
        assert session.requested == []

    def test_failed_download_is_reported(self, matters_dir):
        data = _fetch()
        missing = fc.download_orders(FakeSession({ORDER_A: b'%PDF-a'}), 'MN-01068', data, None)
        assert missing == [ORDER_B]

    def test_off_portal_link_is_not_fetched(self, matters_dir):
        data = _fetch()
        data['applications'][0]['events'][2]['orders'][0]['url'] = 'https://example.com/x.pdf'
        session = FakeSession({ORDER_B: b'%PDF-b'})
        fc.download_orders(session, 'MN-01068', data, None)
        assert 'https://example.com/x.pdf' not in session.requested


class FakeBrowser:
    def __init__(self):
        self.started = 0

    async def get(self):
        self.started += 1
        return object()


JUDGMENT = 'https://www.judgments.fedcourt.gov.au/judgments/Judgments/fca/single/2026/2026fca1000'


class TestDownloadJudgments:
    def test_fetches_unsaved_judgment(self, matters_dir, monkeypatch):
        calls = []

        async def fake_download(browser, merger_id, url):
            calls.append(url)
            return f'/mergers/{merger_id}/2026FCA1000.pdf'

        monkeypatch.setattr(fc.tribunal, 'download_judgment_page', fake_download)
        data = _fetch()
        browser = FakeBrowser()
        missing = asyncio.run(fc.download_judgments(browser, 'MN-01068', data, None, {}))
        assert missing == [] and calls == [JUDGMENT]
        assert data['applications'][0]['events'][2]['judgments'][0]['url_gh'] == '/mergers/MN-01068/2026FCA1000.pdf'

    def test_mirrored_judgment_never_starts_chrome(self, matters_dir, monkeypatch):
        (matters_dir / 'MN-01068').mkdir()
        (matters_dir / 'MN-01068' / '2026FCA1000.docx').write_bytes(b'PK')
        previous = _fetch()
        previous['applications'][0]['events'][2]['judgments'][0]['url_gh'] = '/mergers/MN-01068/2026FCA1000.pdf'
        browser = FakeBrowser()
        data = _fetch()
        assert asyncio.run(fc.download_judgments(browser, 'MN-01068', data, previous, {})) == []
        assert browser.started == 0
        assert data['applications'][0]['events'][2]['judgments'][0]['url_gh'] == '/mergers/MN-01068/2026FCA1000.pdf'

    def test_unpublished_judgment_is_retried_later(self, matters_dir, monkeypatch):
        async def not_yet(browser, merger_id, url):
            return None

        monkeypatch.setattr(fc.tribunal, 'download_judgment_page', not_yet)
        data = _fetch()
        assert asyncio.run(fc.download_judgments(FakeBrowser(), 'MN-01068', data, None, {})) == [JUDGMENT]
        assert 'url_gh' not in data['applications'][0]['events'][2]['judgments'][0]


# --- A whole run -------------------------------------------------------------


@pytest.fixture
def reviews_file(tmp_path, monkeypatch, matters_dir):
    path = tmp_path / 'judicial_reviews.json'
    path.write_text(json.dumps({
        '_comment': 'x',
        'MN-01068': [{
            'applicant': 'Coles',
            'filed_date': '2026-07-17',
            'case_number': 'NSD1310/2026',
            'case_url': 'https://www.comcourts.gov.au/file/Federal/P/nsd1310/2026/actions',
        }],
    }))
    monkeypatch.setattr(fc, 'JUDICIAL_REVIEWS_JSON', path)
    monkeypatch.setattr(fc.portal, 'Session', FakeSession)
    return path


class TestScrape:
    def test_writes_portal_block(self, reviews_file):
        assert fc.scrape(None, dry_run=False, download=False) == 0
        record = json.loads(reviews_file.read_text())['MN-01068'][0]
        assert record['applicant'] == 'Coles'
        assert record['portal']['file']['finalised_date'] == '2026-08-27'
        assert json.loads(reviews_file.read_text())['_comment'] == 'x'

    def test_dry_run_writes_nothing(self, reviews_file):
        before = reviews_file.read_text()
        assert fc.scrape(None, dry_run=True) == 0
        assert reviews_file.read_text() == before

    def test_failed_fetch_leaves_record_untouched(self, reviews_file, monkeypatch):
        def broken(*args, **kwargs):
            raise portal.FetchError('portal down')

        monkeypatch.setattr(fc.portal, 'fetch_file', broken)
        before = reviews_file.read_text()
        assert fc.scrape(None, dry_run=False, download=False) == 2
        assert reviews_file.read_text() == before

    def test_empty_applications_leave_record_untouched(self, reviews_file, monkeypatch):
        fc.scrape(None, dry_run=False, download=False)
        before = reviews_file.read_text()
        monkeypatch.setattr(
            fc.portal, 'fetch_file',
            lambda *a, **k: {'file': {'number': 'NSD1310/2026'}, 'applications': []},
        )
        assert fc.scrape(None, dry_run=False, download=False) == 2
        assert reviews_file.read_text() == before

    def test_unknown_merger_id(self, reviews_file):
        assert fc.scrape(['MN-9999'], dry_run=False) == 0

    def test_no_download_keeps_existing_mirrors(self, reviews_file):
        raw = json.loads(reviews_file.read_text())
        previous = _fetch()
        previous['applications'][0]['events'][2]['orders'][0]['url_gh'] = '/mergers/MN-01068/P.pdf'
        raw['MN-01068'][0]['portal'] = previous
        reviews_file.write_text(json.dumps(raw))
        fc.scrape(None, dry_run=False, download=False)
        record = json.loads(reviews_file.read_text())['MN-01068'][0]
        assert record['portal']['applications'][0]['events'][2]['orders'][0]['url_gh'] == '/mergers/MN-01068/P.pdf'
