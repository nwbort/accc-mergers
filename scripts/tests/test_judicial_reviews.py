"""Tests for the Federal Court judicial review overlay.

Covers the lifecycle read off the portal (constants.judicial_review), loading
judicial_reviews.json, and linking review records onto enriched mergers: the
per-file ``judicial_reviews`` records, the merger-level ``judicial_review``
summary, the ``under_judicial_review`` flag, the timeline events folded in
from the file's documents filed, orders and judgments, and the hearings
surfaced as upcoming events. The scraper that writes the portal block is
covered by test_scrape_federal_court.py.
"""

import json
import sys
import unittest.mock
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Mock heavy transitive imports before importing modules that need them
sys.modules.setdefault('pdfplumber', unittest.mock.MagicMock())
sys.modules.setdefault('markdownify', unittest.mock.MagicMock())
sys.modules.setdefault('requests', unittest.mock.MagicMock())

from scripts.atproto import records as atproto_records
from scripts.constants import judicial_review
from scripts.generate import og_cards
from scripts.generate.static_data import loaders
from scripts.generate.static_data.enrichment import enrich_merger, link_judicial_reviews
from scripts.generate.static_data.outputs import list as list_output
from scripts.generate.static_data.outputs import upcoming_events

CASE_URL = 'https://www.comcourts.gov.au/file/Federal/P/nsd1310/2026/actions'
ORDER_URL = 'https://www.comcourts.gov.au/file/Federal/P/NSD1310/2026/4066335/event/33021628/document/2835642'
JUDGMENT_URL = 'https://www.judgments.fedcourt.gov.au/judgments/Judgments/fca/single/2026/2026fca1000'


def _phase2_not_approved(merger_id='MN-0001'):
    return {
        'merger_id': merger_id,
        'merger_name': f'{merger_id} deal',
        'status': 'Assessment completed',
        'stage': 'Phase 2 - detailed assessment',
        'accc_determination': 'Not approved',
        'determination_publication_date': '2026-07-01T12:00:00Z',
        'end_of_determination_period': '2026-07-02T12:00:00Z',
        'effective_notification_datetime': '2025-11-27T12:00:00Z',
        'events': [
            {'title': 'Merger notified to ACCC', 'date': '2025-11-27T12:00:00Z'},
            {'title': 'ACCC decided notification is subject to Phase 2 review', 'date': '2026-01-29T12:00:00Z'},
        ],
    }


def _portal(finalised=None, listings=None):
    """A portal block shaped like NSD1310/2026's, as the scraper writes it."""
    if listings is None:
        listings = [
            {
                'date': '2026-07-28', 'time': '13:00', 'reason': 'Judgment',
                'presiding': "Justice O'Bryan", 'location': 'Chambers',
                'outcome': 'Adjourned - For review of progress', 'event_id': '2',
                'orders': [{'title': 'View orders', 'url': ORDER_URL,
                            'url_gh': '/mergers/MN-0001/P_NSD1310_2026_2835642.pdf'}],
                'judgments': [{'citation': '[2026] FCA 1000', 'url': JUDGMENT_URL,
                               'url_gh': '/mergers/MN-0001/2026FCA1000.pdf'}],
            },
            {
                'date': '2026-07-21', 'time': '9:30', 'reason': 'First Case Management Hearing',
                'presiding': "Justice O'Bryan", 'location': 'VIC - Remote', 'outcome': '',
                'event_id': '1',
            },
        ]
        if finalised:
            listings.insert(0, {
                'date': finalised, 'time': '8:30', 'reason': 'Administrative Listing',
                'presiding': "Justice O'Bryan", 'location': 'Chambers',
                'outcome': 'Finalised - Discontinued/Withdrawn', 'event_id': '3',
            })
    return {
        'file': {
            'court': 'Federal Court of Australia, New South Wales Registry',
            'number': 'NSD1310/2026',
            'filing_date': '2026-07-17',
            'finalised_date': finalised or '',
            'url': CASE_URL,
        },
        'applications': [{
            'title': 'MISCELLANEOUS', 'type': 'Judicial Review', 'id': '4066335',
            'status': 'Closed' if finalised else 'Open',
            'events': listings,
            'documents': [
                {'date': '2026-07-17', 'time': '14:05',
                 'title': 'Originating Application for Judicial Review',
                 'filed_by': 'Coles Supermarkets Australia Pty Limited'},
            ],
            'parties': [
                {'role': 'Applicant', 'name': 'Coles Supermarkets Australia Pty Limited', 'end_date': ''},
                {'role': 'Legal Representative Applicant', 'name': 'Some Firm', 'end_date': '',
                 'contact': {'business_phone': '03 0000 0000'}},
                {'role': 'Provisional Docket', 'name': 'National Operations Registrar', 'end_date': '2026-07-20'},
                {'role': 'Docket', 'name': "Justice O'Bryan", 'end_date': finalised or ''},
            ],
        }],
    }


def _record(**overrides):
    record = {
        'applicant': 'Coles',
        'filed_date': '2026-07-17',
        'case_number': 'NSD1310/2026',
        'case_url': CASE_URL,
    }
    record.update(overrides)
    return record


def _linked(*records, merger_id='MN-0001'):
    mergers = [enrich_merger(_phase2_not_approved(merger_id))]
    linked = link_judicial_reviews(mergers, {merger_id: list(records)})
    return linked, mergers[0]


# --- Lifecycle ---------------------------------------------------------------


class TestLifecycle:
    def test_unscraped_record_is_current(self):
        assert judicial_review.status(_record()) == 'current'
        assert judicial_review.outcome(_record()) is None

    def test_finalised_file_is_concluded_and_discontinued(self):
        record = _record(portal=_portal(finalised='2026-08-27'))
        assert judicial_review.status(record) == 'concluded'
        assert judicial_review.outcome(record) == 'withdrawn'
        assert judicial_review.concluded_date(record) == '2026-08-27'

    def test_hand_fields_win(self):
        record = _record(portal=_portal(finalised='2026-08-27'),
                         outcome='dismissed', concluded_date='2026-08-28')
        assert judicial_review.outcome(record) == 'dismissed'
        assert judicial_review.concluded_date(record) == '2026-08-28'
        assert judicial_review.status(_record(portal=_portal(), status='concluded')) == 'concluded'

    def test_finalised_wording(self):
        assert judicial_review.outcome_from_listing('Finalised - Discontinued/Withdrawn') == 'withdrawn'
        assert judicial_review.outcome_from_listing('Finalised - Application dismissed') == 'dismissed'
        assert judicial_review.outcome_from_listing('Finalised - Appeal allowed') == 'set_aside'
        assert judicial_review.outcome_from_listing('Finalised - Orders made') is None
        assert judicial_review.outcome_from_listing('Adjourned - For review of progress') is None

    def test_hearings(self):
        assert judicial_review.is_hearing({'reason': 'First Case Management Hearing', 'location': 'VIC - Remote'})
        assert not judicial_review.is_hearing({'reason': 'Administrative Listing', 'location': 'Court 1'})
        assert not judicial_review.is_hearing({'reason': 'Judgment', 'location': 'Chambers'})

    def test_review_records(self):
        assert judicial_review.review_records({'a': 1}) == [{'a': 1}]
        assert judicial_review.review_records([{'a': 1}, {}, None]) == [{'a': 1}]
        assert judicial_review.review_records(None) == []


# --- Linking -----------------------------------------------------------------


class TestLinkJudicialReviews:
    def test_unscraped_record_still_links(self):
        linked, m = _linked(_record())
        assert linked == 1
        assert m['judicial_review']['applicant'] == 'Coles'
        assert m['judicial_review']['case_number'] == 'NSD1310/2026'
        assert m['judicial_review']['case_url'] == CASE_URL
        assert m['judicial_review']['status'] == 'current'
        assert m['under_judicial_review'] is True
        assert m['judicial_reviews'][0]['listings'] == []

    def test_bare_record_reads_as_list_of_one(self):
        mergers = [enrich_merger(_phase2_not_approved())]
        assert link_judicial_reviews(mergers, {'MN-0001': _record()}) == 1
        assert len(mergers[0]['judicial_reviews']) == 1

    def test_concluded_review_is_not_live(self):
        _, m = _linked(_record(portal=_portal(finalised='2026-08-27')))
        assert m['under_judicial_review'] is False
        review = m['judicial_reviews'][0]
        assert review['status'] == 'concluded'
        assert review['outcome'] == 'withdrawn'
        assert review['concluded_date'] == '2026-08-27'
        assert m['judicial_review']['outcome'] == 'withdrawn'

    def test_record_carries_court_and_docket_not_parties(self):
        _, m = _linked(_record(portal=_portal()))
        review = m['judicial_reviews'][0]
        assert review['court'] == 'Federal Court of Australia, New South Wales Registry'
        assert review['docket'] == "Justice O'Bryan"
        assert 'parties' not in json.dumps(review)
        assert 'business_phone' not in json.dumps(m)

    def test_listings_are_flagged_as_hearings(self):
        _, m = _linked(_record(portal=_portal()))
        listings = m['judicial_reviews'][0]['listings']
        assert [(l['date'], l['hearing']) for l in listings] == [
            ('2026-07-28', False), ('2026-07-21', True),
        ]
        assert 'event_id' not in listings[0]
        assert listings[0]['judgments'][0]['url_gh'] == '/mergers/MN-0001/2026FCA1000.pdf'

    def test_timeline_events(self):
        _, m = _linked(_record(portal=_portal()))
        review_events = [e for e in m['events'] if e.get('review_forum') == 'federal_court']
        assert [(e['date'], e['display_title'], e['url_gh']) for e in review_events] == [
            ('2026-07-17T12:00:00Z', 'Federal Court – Originating Application for Judicial Review', None),
            ('2026-07-28T12:00:00Z', 'Federal Court – Orders', '/mergers/MN-0001/P_NSD1310_2026_2835642.pdf'),
            ('2026-07-28T12:00:00Z', 'Federal Court – Judgment [2026] FCA 1000', '/mergers/MN-0001/2026FCA1000.pdf'),
        ]
        assert all(e['is_appeal'] for e in review_events)
        assert review_events[0]['appeal_filed_by'] == 'Coles Supermarkets Australia Pty Limited'
        assert review_events[1]['appeal_filed_by'] == "Justice O'Bryan"
        assert review_events[0]['case_number'] == 'NSD1310/2026'

    def test_orders_named_by_listing(self):
        listings = [{
            'date': '2026-07-21', 'reason': 'First Case Management Hearing', 'presiding': 'J',
            'orders': [{'url': ORDER_URL}],
        }]
        _, m = _linked(_record(portal=_portal(listings=listings)))
        titles = [e['title'] for e in m['events'] if e.get('review_forum')]
        assert 'Orders (First Case Management Hearing)' in titles

    def test_two_files_summarised(self):
        _, m = _linked(
            _record(portal=_portal(finalised='2026-08-27')),
            _record(applicant='Woolworths', case_number='NSD1400/2026', filed_date='2026-08-01',
                    case_url='https://www.comcourts.gov.au/file/Federal/P/nsd1400/2026/actions'),
        )
        assert m['under_judicial_review'] is True
        summary = m['judicial_review']
        assert summary['applicant'] == 'Coles and Woolworths'
        assert summary['case_number'] == 'NSD1310/2026 and NSD1400/2026'
        assert summary['filed_date'] == '2026-07-17'
        assert summary['status'] == 'current'
        assert summary['outcome'] is None

    def test_no_entry_means_no_record(self):
        mergers = [enrich_merger(_phase2_not_approved())]
        assert link_judicial_reviews(mergers, {'MN-9999': [_record()]}) == 0
        assert 'judicial_review' not in mergers[0]
        assert 'under_judicial_review' not in mergers[0]

    def test_empty_dict_is_noop(self):
        mergers = [enrich_merger(_phase2_not_approved())]
        assert link_judicial_reviews(mergers, {}) == 0

    def test_list_entry_carries_flag_only_while_live(self):
        _, live = _linked(_record())
        _, done = _linked(_record(portal=_portal(finalised='2026-08-27')))
        assert list_output._lightweight(live)['under_judicial_review'] is True
        assert 'under_judicial_review' not in list_output._lightweight(done)


class TestUpcomingHearings:
    def _merger_with_listing(self, days_ahead, **listing):
        date = (datetime.now(timezone.utc) + timedelta(days=days_ahead)).strftime('%Y-%m-%d')
        listings = [{'date': date, 'time': '10:15', 'presiding': 'J', 'outcome': '', **listing}]
        _, m = _linked(_record(portal=_portal(listings=listings)))
        return m, date

    def _hearings(self, m):
        return [e for e in upcoming_events.generate([m])['events'] if e['type'] == 'federal_court_hearing']

    def test_future_hearing_is_upcoming(self):
        m, date = self._merger_with_listing(100, reason='Hearing', location='Court 18A')
        hearings = self._hearings(m)
        assert len(hearings) == 1
        assert hearings[0]['date'] == f'{date}T12:00:00Z'
        assert hearings[0]['event_type_display'] == 'Federal Court hearing'
        assert hearings[0]['case_number'] == 'NSD1310/2026'
        assert hearings[0]['hearing_reason'] == 'Hearing'

    def test_chambers_and_past_listings_are_not(self):
        m, _ = self._merger_with_listing(5, reason='Administrative Listing', location='Chambers')
        assert self._hearings(m) == []
        m, _ = self._merger_with_listing(-5, reason='Hearing', location='Court 18A')
        assert self._hearings(m) == []


class TestPublishedElsewhere:
    def test_atproto_entry_per_file_with_status(self):
        _, m = _linked(_record(portal=_portal(finalised='2026-08-27')))
        entries = [a for a in atproto_records._appeals(m) if a['forum'] == 'federal-court-of-australia']
        assert entries == [{
            'forum': 'federal-court-of-australia',
            'caseNumber': 'NSD1310/2026',
            'caseUrl': CASE_URL,
            'applicant': 'Coles',
            'filedOn': '2026-07-17',
            'status': 'concluded',
            'outcome': 'withdrawn',
        }]

    def test_og_card_drops_concluded_review(self):
        _, live = _linked(_record())
        _, done = _linked(_record(portal=_portal(finalised='2026-08-27')))
        assert og_cards.current_card(live) != og_cards.current_card(done)
        assert og_cards.current_card(done) == og_cards.current_card(enrich_merger(_phase2_not_approved()))


class TestLoader:
    def test_strips_metadata_keys(self, tmp_path, monkeypatch):
        path = tmp_path / 'judicial_reviews.json'
        path.write_text(json.dumps({'_comment': 'x', 'MN-0001': [_record()]}))
        monkeypatch.setattr(loaders, 'JUDICIAL_REVIEWS_JSON', path)
        assert loaders.load_judicial_reviews() == {'MN-0001': [_record()]}

    def test_bare_record_loads_as_list(self, tmp_path, monkeypatch):
        path = tmp_path / 'judicial_reviews.json'
        path.write_text(json.dumps({'MN-0001': _record()}))
        monkeypatch.setattr(loaders, 'JUDICIAL_REVIEWS_JSON', path)
        assert loaders.load_judicial_reviews() == {'MN-0001': [_record()]}

    def test_missing_file_returns_empty(self, tmp_path, monkeypatch):
        monkeypatch.setattr(loaders, 'JUDICIAL_REVIEWS_JSON', tmp_path / 'nope.json')
        assert loaders.load_judicial_reviews() == {}


class TestRealDataFile:
    def test_committed_file_is_valid(self):
        """The checked-in overlay parses, is a list per merger, and every
        record has the hand-maintained fields."""
        repo_root = Path(__file__).resolve().parent.parent.parent
        path = repo_root / 'data' / 'processed' / 'judicial_reviews.json'
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        for merger_id, records in data.items():
            if merger_id.startswith('_'):
                continue
            assert isinstance(records, list) and records, merger_id
            for review in records:
                assert review.get('applicant')
                assert review.get('filed_date')
                assert review.get('case_number')
                assert review.get('case_url', '').startswith('https://www.comcourts.gov.au/')
                for key in ('status', 'outcome'):
                    allowed = {'status': {'current', 'concluded'}, 'outcome': judicial_review.OUTCOMES}[key]
                    assert review.get(key) in allowed | {None}, (merger_id, key)

    def test_mirrored_files_exist(self):
        """Every url_gh the scraper recorded names a file on disk (or the DOCX
        the pipeline converts to it)."""
        repo_root = Path(__file__).resolve().parent.parent.parent
        data = json.loads((repo_root / 'data' / 'processed' / 'judicial_reviews.json').read_text())
        for merger_id, records in data.items():
            if merger_id.startswith('_'):
                continue
            for review in records:
                for app in (review.get('portal') or {}).get('applications') or []:
                    for listing in app.get('events') or []:
                        for item in (listing.get('orders') or []) + (listing.get('judgments') or []):
                            if not item.get('url_gh'):
                                continue
                            name = item['url_gh'].rsplit('/', 1)[-1]
                            folder = repo_root / 'data' / 'raw' / 'matters' / merger_id
                            stem = name.rsplit('.', 1)[0]
                            assert any((folder / n).exists() for n in (name, f'{stem}.docx')), item['url_gh']
