"""The public benefit phase, end to end through the pipeline.

A public benefit application follows a Phase 2 determination (MN-65005 was the
first expected), and moves the register's stage on to "Public benefit phase".
Every stage-driven computation used to read the phase of a determination off
the *current* stage, so the move would have lost the Phase 2 determination,
pulled the stage back to Phase 2 via the referral inference, and dropped the
matter off the Phase 2 tracker. These pin the handling that replaced that.
"""

import copy
import json
import sys
import unittest.mock
from datetime import datetime

import pytest
from bs4 import BeautifulSoup

# Mock heavy transitive imports of extract_mergers, as test_pipeline does.
for _module in ('pdfplumber', 'markdownify', 'requests'):
    sys.modules.setdefault(_module, unittest.mock.MagicMock())

from scripts import extract_mergers, stage_determinations  # noqa: E402
from scripts.atproto.post_bluesky import milestones  # noqa: E402
from scripts.atproto.records import matter_record  # noqa: E402
from scripts.constants import merger_status  # noqa: E402
from scripts.cutoff import get_cutoff_date  # noqa: E402
from scripts.generate import generate_weekly_digest as gwd  # noqa: E402
from scripts.generate.static_data.enrichment import enrich_merger, slim_for_site  # noqa: E402
from scripts.generate.static_data.outputs import list as list_output  # noqa: E402
from scripts.generate.static_data.outputs import phase2, stats, upcoming_events  # noqa: E402
from scripts.generate.static_data.outputs.industries import classify_phase  # noqa: E402

PHASE_2_DATE = '2026-09-22T12:00:00Z'
APPLICATION_DATE = '2026-10-06T12:00:00Z'


def _phase_2_decided():
    """MN-65005 as the register had it the day its Phase 2 determination landed."""
    return {
        'merger_id': 'MN-65005',
        'merger_name': 'Insurance Australia Group – RAC Insurance',
        'status': merger_status.ASSESSMENT_COMPLETED,
        'stage': merger_status.PHASE_2_STAGE,
        'accc_determination': merger_status.NOT_APPROVED,
        'determination_publication_date': PHASE_2_DATE,
        'effective_notification_datetime': '2026-03-03T12:00:00Z',
        # The register's Phase 2 deadline — the day after the determination.
        'end_of_determination_period': '2026-09-23T12:00:00Z',
        'events': [
            {'date': '2026-03-03T12:00:00Z', 'title': 'Merger notified to ACCC'},
            {'date': '2026-04-16T12:00:00Z', 'title': 'Decision to Proceed to a Phase 2 review',
             'url': 'https://www.accc.gov.au/phase2.pdf'},
            {'date': '2026-05-25T12:00:00Z', 'title': 'Summary of Notice of Competition Concerns'},
            {'date': PHASE_2_DATE, 'title': 'IAG-RACI - Phase 2 determination',
             'display_title': 'Phase 2 - detailed assessment determination: Not approved',
             'url': 'https://www.accc.gov.au/determination.pdf', 'is_determination_event': True},
        ],
    }


def _public_benefit_applied(keep_headline=True):
    """The same matter once the application is on the register.

    ``keep_headline`` is whether the register leaves the Phase 2 outcome in its
    determination fields — unknown until the first such page appears, so both
    are covered.
    """
    merger = _phase_2_decided()
    merger['stage'] = merger_status.PUBLIC_BENEFIT_STAGE
    merger['status'] = merger_status.UNDER_ASSESSMENT
    if not keep_headline:
        del merger['accc_determination']
        del merger['determination_publication_date']
    merger['events'].append(
        {'date': APPLICATION_DATE, 'title': 'Public benefit application - IAG - RACI'}
    )
    return merger


def _stored(merger, previous):
    """What extract_mergers writes to mergers.json for ``merger``."""
    stored = copy.deepcopy(merger)
    records = stage_determinations.resolve(stored, previous)
    persisted = stage_determinations.to_persist(stored, records)
    if persisted:
        stored[stage_determinations.FIELD] = persisted
    return stored


def _enriched(keep_headline=True):
    return enrich_merger(_stored(_public_benefit_applied(keep_headline), _phase_2_decided()))


# --- stage labels -------------------------------------------------------------

@pytest.mark.parametrize('stage, phase', [
    ('Phase 1 - initial assessment', merger_status.PHASE_1),
    ('Phase 2 - detailed assessment', merger_status.PHASE_2),
    ('Public benefit phase', merger_status.PUBLIC_BENEFITS),
    ('Waiver application', merger_status.WAIVER),
    ('', None),
    (None, None),
])
def test_stage_phase_reads_every_register_label(stage, phase):
    assert merger_status.stage_phase(stage) == phase


def test_public_benefit_event_naming_phase_2_is_a_public_benefit_event():
    from scripts.generate.static_data.enrichment import extract_phase_from_event
    title = 'Application for a public benefit determination following Phase 2 determination'
    assert extract_phase_from_event(title) == merger_status.PUBLIC_BENEFITS


# --- the per-phase determination record ---------------------------------------

class TestStageDeterminations:
    def test_ordinary_matter_persists_nothing(self):
        merger = _phase_2_decided()
        records = stage_determinations.resolve(merger)
        assert records == {merger_status.PHASE_2: {
            'determination': merger_status.NOT_APPROVED,
            'date': PHASE_2_DATE,
            'stage': merger_status.PHASE_2_STAGE,
        }}
        assert stage_determinations.to_persist(merger, records) is None

    @pytest.mark.parametrize('keep_headline', [True, False])
    def test_phase_2_determination_survives_the_stage_change(self, keep_headline):
        current = _public_benefit_applied(keep_headline)
        records = stage_determinations.resolve(current, _phase_2_decided())

        assert set(records) == {merger_status.PHASE_2}
        assert records[merger_status.PHASE_2]['determination'] == merger_status.NOT_APPROVED
        assert stage_determinations.to_persist(current, records) == records

    def test_headline_still_showing_phase_2_is_not_a_public_benefit_determination(self):
        current = _public_benefit_applied(keep_headline=True)
        records = stage_determinations.resolve(current, _phase_2_decided())
        assert stage_determinations.headline_phase(current, records) == merger_status.PHASE_2

    def test_a_later_determination_is_the_public_benefit_one(self):
        current = _public_benefit_applied()
        current['accc_determination'] = merger_status.APPROVED
        current['determination_publication_date'] = '2026-12-14T12:00:00Z'
        previous = _stored(_public_benefit_applied(), _phase_2_decided())

        records = stage_determinations.resolve(current, previous)

        assert records[merger_status.PHASE_2]['determination'] == merger_status.NOT_APPROVED
        assert records[merger_status.PUBLIC_BENEFITS]['determination'] == merger_status.APPROVED
        assert stage_determinations.headline_phase(current, records) == merger_status.PUBLIC_BENEFITS


# --- extraction ---------------------------------------------------------------

class TestExtraction:
    def test_phase_2_determination_event_keeps_its_phase_2_title(self):
        current = _public_benefit_applied(keep_headline=True)
        records = stage_determinations.resolve(current, _phase_2_decided())

        extract_mergers._add_synthetic_events(current, records)

        det_events = [e for e in current['events'] if e.get('is_determination_event')]
        assert [e['display_title'] for e in det_events] == [
            'Phase 2 - detailed assessment determination: Not approved'
        ]

    def test_public_benefit_determination_leaves_the_phase_2_flag_alone(self):
        current = _public_benefit_applied()
        current['accc_determination'] = merger_status.APPROVED
        current['determination_publication_date'] = '2026-12-14T12:00:00Z'
        current['events'].append({
            'date': '2026-12-14T12:00:00Z', 'title': 'IAG-RACI - Public benefit determination',
            'url': 'https://www.accc.gov.au/public-benefit-determination.pdf',
        })
        previous = _stored(_public_benefit_applied(), _phase_2_decided())
        records = stage_determinations.resolve(current, previous)

        extract_mergers._add_synthetic_events(current, records)

        flagged = {e['date'][:10]: e['display_title'] for e in current['events']
                   if e.get('is_determination_event')}
        assert flagged == {
            '2026-09-22': 'Phase 2 - detailed assessment determination: Not approved',
            '2026-12-14': 'Public benefit phase determination: Approved',
        }

    def test_cleared_headline_still_flags_the_phase_2_determination(self):
        # While the application runs the register clears its headline, so only
        # the recorded Phase 2 determination can say which event holds it —
        # even when the stored event had lost its flag and title (MN-65005).
        current = _public_benefit_applied(keep_headline=False)
        det = next(e for e in current['events'] if e.get('is_determination_event'))
        del det['is_determination_event']
        det['display_title'] = det['title']
        current['events'].append({
            'date': PHASE_2_DATE, 'title': 'IAG-RACI - Phase 2 determination - Summary of reasons',
            'url': 'https://www.accc.gov.au/summary.pdf',
        })
        records = stage_determinations.resolve(current, _phase_2_decided())

        extract_mergers._add_synthetic_events(current, records)

        flagged = [(e['url'], e['display_title'], e['phase'])
                   for e in current['events'] if e.get('is_determination_event')]
        assert flagged == [(
            'https://www.accc.gov.au/determination.pdf',
            'Phase 2 - detailed assessment determination: Not approved',
            merger_status.PHASE_2,
        )]

    def test_recorded_determination_is_flagged_once_across_runs(self):
        current = _public_benefit_applied(keep_headline=False)
        records = stage_determinations.resolve(current, _phase_2_decided())
        extract_mergers._add_synthetic_events(current, records)
        once = copy.deepcopy(current['events'])

        extract_mergers._add_synthetic_events(current, records)

        assert current['events'] == once

    def test_application_date_is_scraped_and_kept(self):
        html = """
        <div class="field field--name-field-acccgov-pub-benefit-date">
          <h3 class="field__label">Public benefit application date</h3>
          <div class="field__item"><time datetime="2026-10-13T12:00:00Z">13 Oct 2026</time></div>
        </div>"""
        soup = BeautifulSoup(html, 'lxml')
        data = extract_mergers._extract_dates_and_status(soup, 'MN-65005', None)
        assert data['public_benefit_application_date'] == '2026-10-13T12:00:00Z'

        later = extract_mergers._extract_dates_and_status(
            BeautifulSoup('<div></div>', 'lxml'), 'MN-65005', data
        )
        assert later['public_benefit_application_date'] == '2026-10-13T12:00:00Z'

    def test_public_benefit_stage_closes_the_inferred_phase_2_issue(self, tmp_path, monkeypatch):
        out = tmp_path / 'inferred.json'
        monkeypatch.setattr(extract_mergers, 'INFERRED_PHASE_2_PATH', str(out))

        extract_mergers.detect_inferred_phase_2([_public_benefit_applied()])

        payload = json.loads(out.read_text())
        assert payload == {'open': [], 'confirmed': ['MN-65005']}


class TestRecordedDeterminationEvents:
    """_add_synthetic_events flags each phase's recorded determination, not
    only the register's headline, so the Phase 2 determination stays the
    determination event however the headline reads (MN-65005)."""

    DET_URL = 'https://www.accc.gov.au/determination.pdf'
    PB_URL = 'https://www.accc.gov.au/public-benefit-determination.pdf'
    PB_DATE = '2026-12-14T12:00:00Z'
    PHASE_2_TITLE = 'Phase 2 - detailed assessment determination: Not approved'

    @staticmethod
    def _flagged(merger):
        return sorted(
            (e['date'][:10], e.get('url'), e['display_title'])
            for e in merger['events'] if e.get('is_determination_event')
        )

    def _run(self, current, previous=None):
        records = stage_determinations.resolve(current, previous or _phase_2_decided())
        extract_mergers._add_synthetic_events(current, records)
        return records

    def _strip_flags(self, merger):
        for e in merger['events']:
            if e.pop('is_determination_event', None):
                e['display_title'] = e['title']

    @pytest.mark.parametrize('keep_headline', [True, False])
    def test_phase_2_determination_is_flagged_either_way(self, keep_headline):
        current = _public_benefit_applied(keep_headline)
        self._strip_flags(current)
        self._run(current)
        assert self._flagged(current) == [
            ('2026-09-22', self.DET_URL, self.PHASE_2_TITLE)]

    def test_reasons_documents_on_the_same_day_are_not_flagged(self):
        current = _public_benefit_applied(keep_headline=False)
        self._strip_flags(current)
        # Listed ahead of the instrument, so a first-match pick would take them.
        current['events'][:0] = [
            {'date': PHASE_2_DATE, 'title': 'IAG-RACI - Phase 2 determination - Summary of reasons',
             'url': 'https://www.accc.gov.au/summary.pdf'},
            {'date': PHASE_2_DATE, 'title': 'IAG-RACI - Phase 2 determination - Statement of reasons',
             'url': 'https://www.accc.gov.au/statement.pdf'},
        ]
        self._run(current)
        assert self._flagged(current) == [
            ('2026-09-22', self.DET_URL, self.PHASE_2_TITLE)]

    def test_a_stale_flag_on_a_reasons_document_moves_to_the_instrument(self):
        current = _public_benefit_applied(keep_headline=False)
        self._strip_flags(current)
        current['events'].append({
            'date': PHASE_2_DATE, 'title': 'IAG-RACI - Phase 2 determination - Summary of reasons',
            'display_title': self.PHASE_2_TITLE,
            'url': 'https://www.accc.gov.au/summary.pdf', 'is_determination_event': True,
        })
        self._run(current)
        assert self._flagged(current) == [
            ('2026-09-22', self.DET_URL, self.PHASE_2_TITLE)]
        summary = next(e for e in current['events'] if e.get('url', '').endswith('summary.pdf'))
        assert summary['display_title'] == summary['title']

    def test_a_document_dated_days_before_the_record_is_found(self):
        # The register's publication date can trail the PDF's row by a few
        # days (MN-30008), and the record keeps the register's date.
        previous = _phase_2_decided()
        previous['determination_publication_date'] = '2026-09-25T12:00:00Z'
        current = _public_benefit_applied(keep_headline=False)
        self._strip_flags(current)
        self._run(current, previous)
        assert self._flagged(current) == [
            ('2026-09-22', self.DET_URL, self.PHASE_2_TITLE)]

    def test_without_a_document_a_synthetic_event_stands_in_once(self):
        current = _public_benefit_applied(keep_headline=False)
        current['events'] = [e for e in current['events'] if e.get('url') != self.DET_URL]
        records = self._run(current)
        extract_mergers._add_synthetic_events(current, records)
        assert self._flagged(current) == [
            ('2026-09-22', None, self.PHASE_2_TITLE)]

    def test_a_late_document_replaces_the_synthetic_event(self):
        # Determined before the instrument was uploaded: the stand-in event is
        # stored, then the PDF appears once the application is under way.
        current = _public_benefit_applied(keep_headline=False)
        det = next(e for e in current['events'] if e.get('url') == self.DET_URL)
        current['events'].remove(det)
        records = self._run(current)
        del det['is_determination_event']
        det['display_title'] = det['title']
        current['events'].append(det)

        extract_mergers._add_synthetic_events(current, records)

        assert self._flagged(current) == [
            ('2026-09-22', self.DET_URL, self.PHASE_2_TITLE)]
        assert not any(e['title'] == self.PHASE_2_TITLE for e in current['events'])

    @pytest.mark.parametrize('keep_headline', [True, False])
    def test_the_public_benefit_determination_joins_the_phase_2_one(self, keep_headline):
        previous = _stored(_public_benefit_applied(keep_headline), _phase_2_decided())
        current = _public_benefit_applied(keep_headline)
        self._strip_flags(current)
        current['accc_determination'] = merger_status.APPROVED
        current['determination_publication_date'] = self.PB_DATE
        current['events'].append({
            'date': self.PB_DATE, 'title': 'IAG-RACI - Public benefit determination',
            'url': self.PB_URL,
        })
        self._run(current, previous)
        assert self._flagged(current) == [
            ('2026-09-22', self.DET_URL, self.PHASE_2_TITLE),
            ('2026-12-14', self.PB_URL, 'Public benefit phase determination: Approved'),
        ]

    def test_phase_1_conditional_clearance_then_public_benefit(self):
        url = 'https://www.accc.gov.au/phase1-determination.pdf'
        decided = {
            'merger_id': 'MN-99999',
            'stage': 'Phase 1 - initial assessment',
            'status': merger_status.ASSESSMENT_COMPLETED,
            'accc_determination': merger_status.APPROVED_WITH_CONDITIONS,
            'determination_publication_date': '2026-08-03T12:00:00Z',
            'events': [{'date': '2026-08-03T12:00:00Z', 'title': 'Phase 1 determination',
                        'url': url}],
        }
        current = copy.deepcopy(decided)
        current['stage'] = merger_status.PUBLIC_BENEFIT_STAGE
        current['status'] = merger_status.UNDER_ASSESSMENT
        del current['accc_determination'], current['determination_publication_date']

        records = stage_determinations.resolve(current, decided)
        extract_mergers._add_synthetic_events(current, records)

        assert set(records) == {merger_status.PHASE_1}
        assert self._flagged(current) == [(
            '2026-08-03', url,
            'Phase 1 - initial assessment determination: Approved with conditions')]
        assert current['events'][0]['phase'] == merger_status.PHASE_1

    @pytest.mark.parametrize('record', [
        {'determination': 'Not approved', 'date': PHASE_2_DATE},  # no stage
        {'determination': 'Not approved', 'stage': merger_status.PHASE_2_STAGE},  # no date
        {'date': PHASE_2_DATE, 'stage': merger_status.PHASE_2_STAGE},  # no outcome
    ])
    def test_an_incomplete_record_is_skipped(self, record):
        current = _public_benefit_applied(keep_headline=False)
        self._strip_flags(current)
        before = copy.deepcopy(current['events'])
        extract_mergers._add_synthetic_events(current, {merger_status.PHASE_2: record})
        assert current['events'] == before

    def test_no_records_and_no_headline_flags_nothing(self):
        current = _public_benefit_applied(keep_headline=False)
        self._strip_flags(current)
        before = copy.deepcopy(current['events'])
        extract_mergers._add_synthetic_events(current, {})
        extract_mergers._add_synthetic_events(current)
        assert current['events'] == before


class TestParseMergerFileEndToEnd:
    """The run that broke MN-65005 (14 Oct 2026), through parse_merger_file:
    the page in the public benefit phase with its headline cleared, the
    Phase 2 determination's documents at the URLs already stored. Whether or
    not the stored event still carries the flag, the run must leave it on the
    instrument, with the Phase 2 title."""

    DET_URL = 'https://www.accc.gov.au/system/files/IAG_RACI%20-%20Phase%202%20determination_1.pdf'
    SUMMARY_URL = 'https://www.accc.gov.au/system/files/Summary%20of%20Reasons_10.pdf'
    PHASE_2_TITLE = 'Phase 2 - detailed assessment determination: Not approved'

    PAGE = f"""<html><body>
    <h1 class="page-title">Insurance Australia Group – RAC Insurance</h1>
    <div class="field--name-dynamic-token-fieldnode-acccgov-merger-id">
      <div class="field__item">MN-65005</div></div>
    <div class="field--name-field-acccgov-merger-status">
      <div class="field__item">Under assessment</div></div>
    <div class="field--name-field-acquisition-stage">Stage Public benefit phase</div>
    <div class="field--name-field-acccgov-pub-reg-date">
      <time datetime="2026-03-03T12:00:00Z">3 March 2026</time></div>
    <div class="field--name-field-acccgov-pub-benefit-date">
      <time datetime="2026-10-13T12:00:00Z">13 October 2026</time></div>
    <div class="table-responsive"><table>
      <tr><td class="acccgov-timeline__date"><time datetime="{PHASE_2_DATE}">22 Sep 2026</time></td>
          <td>Phase 2 determination</td>
          <td class="acccgov-timeline__file-link"><a href="{DET_URL}">PDF</a></td></tr>
      <tr><td class="acccgov-timeline__date"><time datetime="{PHASE_2_DATE}">22 Sep 2026</time></td>
          <td>Phase 2 determination - Summary of reasons</td>
          <td class="acccgov-timeline__file-link"><a href="{SUMMARY_URL}">PDF</a></td></tr>
    </table></div>
    </body></html>"""

    def _stored(self, flagged):
        det = {'date': PHASE_2_DATE, 'title': 'Phase 2 determination',
               'display_title': self.PHASE_2_TITLE if flagged else 'Phase 2 determination',
               'url': self.DET_URL, 'status': 'live'}
        if flagged:
            det['is_determination_event'] = True
        return {
            'merger_id': 'MN-65005',
            'stage': merger_status.PUBLIC_BENEFIT_STAGE,
            'status': merger_status.UNDER_ASSESSMENT,
            'stage_determinations': {merger_status.PHASE_2: {
                'determination': merger_status.NOT_APPROVED,
                'date': '2026-09-23T12:00:00Z',
                'stage': merger_status.PHASE_2_STAGE,
            }},
            'events': [
                det,
                {'date': PHASE_2_DATE, 'title': 'Phase 2 determination - Summary of reasons',
                 'display_title': 'Phase 2 determination - Summary of reasons',
                 'url': self.SUMMARY_URL, 'status': 'live'},
            ],
        }

    def _parse(self, tmp_path, monkeypatch, existing):
        monkeypatch.setattr(extract_mergers, 'download_attachment', lambda *a, **k: None)
        page = tmp_path / 'MN-65005.html'
        page.write_text(self.PAGE, encoding='utf-8')
        return extract_mergers.parse_merger_file(str(page), existing, set(), {})

    @pytest.mark.parametrize('flagged', [True, False])
    def test_the_phase_2_determination_stays_flagged(self, tmp_path, monkeypatch, flagged):
        result = self._parse(tmp_path, monkeypatch, self._stored(flagged))

        assert result['stage'] == merger_status.PUBLIC_BENEFIT_STAGE
        assert not result.get('determination_publication_date')
        assert result['stage_determinations'] == self._stored(flagged)['stage_determinations']
        assert [(e['url'], e['display_title'], e['phase'])
                for e in result['events'] if e.get('is_determination_event')] == [
            (self.DET_URL, self.PHASE_2_TITLE, merger_status.PHASE_2)]

    def test_a_second_run_changes_nothing(self, tmp_path, monkeypatch):
        once = self._parse(tmp_path, monkeypatch, self._stored(False))
        twice = self._parse(tmp_path, monkeypatch, copy.deepcopy(once))
        assert twice == once


# --- enrichment ---------------------------------------------------------------

class TestEnrichment:
    @pytest.mark.parametrize('keep_headline', [True, False])
    def test_matter_is_live_again_with_its_phase_2_outcome_kept(self, keep_headline):
        m = _enriched(keep_headline)

        assert m['stage'] == merger_status.PUBLIC_BENEFIT_STAGE
        assert not m.get('phase_2_inferred')
        assert m['public_benefit_in_progress'] is True
        assert m['status'] == merger_status.UNDER_ASSESSMENT
        assert m['accc_determination'] is None
        assert m['determination_publication_date'] is None
        assert m['phase_1_determination'] == merger_status.REFERRED_TO_PHASE_2
        assert m['phase_2_determination'] == merger_status.NOT_APPROVED
        assert m['phase_2_determination_date'] == PHASE_2_DATE
        assert m['public_benefits_determination'] is None

    def test_stale_phase_2_deadline_is_replaced_with_the_public_benefit_one(self):
        m = _enriched()

        # BD 1 is the day the application appeared; BD 50 falls on 14 Dec.
        assert m['public_benefit_application_date'] == APPLICATION_DATE
        assert m['end_of_determination_period'] == '2026-12-14T12:00:00Z'
        assert m['end_of_determination_period_derived'] is True
        assert m['public_benefit_assessment_date'] == '2026-11-02T12:00:00Z'  # BD 20
        assert m['public_benefit_response_date'] == '2026-11-23T12:00:00Z'  # BD 35

    def test_register_application_date_wins_over_the_first_event(self):
        merger = _public_benefit_applied()
        # The register's field gives the day the application was made, the
        # day before its documents were published (MN-65005: 13 and 14 Oct).
        merger['public_benefit_application_date'] = '2026-10-05T12:00:00Z'
        m = enrich_merger(_stored(merger, _phase_2_decided()))

        assert m['public_benefit_application_date'] == '2026-10-05T12:00:00Z'
        # BD 1 is still the day after the application, so the derived
        # timetable is the one the first event gives.
        assert m['end_of_determination_period'] == '2026-12-14T12:00:00Z'
        assert m['public_benefit_assessment_date'] == '2026-11-02T12:00:00Z'
        assert m['public_benefit_response_date'] == '2026-11-23T12:00:00Z'

    def test_register_deadline_wins_once_published(self):
        merger = _public_benefit_applied()
        merger['end_of_determination_period'] = '2026-12-21T12:00:00Z'  # extended
        m = enrich_merger(_stored(merger, _phase_2_decided()))

        assert m['end_of_determination_period'] == '2026-12-21T12:00:00Z'
        assert not m.get('end_of_determination_period_derived')

    def test_stale_deadline_is_dropped_before_the_application_appears(self):
        merger = _public_benefit_applied()
        merger['events'] = merger['events'][:-1]
        m = enrich_merger(_stored(merger, _phase_2_decided()))

        assert m['end_of_determination_period'] is None
        assert 'public_benefit_assessment_date' not in m

    def test_published_assessment_drops_its_forecast(self):
        merger = _public_benefit_applied()
        merger['events'].append(
            {'date': '2026-10-30T12:00:00Z', 'title': 'Public benefit assessment - IAG - RACI'}
        )
        m = enrich_merger(_stored(merger, _phase_2_decided()))

        assert 'public_benefit_assessment_date' not in m
        assert m['public_benefit_response_date'] == '2026-11-23T12:00:00Z'

    def test_public_benefit_determination(self):
        merger = _public_benefit_applied()
        merger['status'] = merger_status.ASSESSMENT_COMPLETED
        merger['accc_determination'] = merger_status.APPROVED
        merger['determination_publication_date'] = '2026-12-14T12:00:00Z'
        previous = _stored(_public_benefit_applied(), _phase_2_decided())
        m = enrich_merger(_stored(merger, previous))

        assert not m.get('public_benefit_in_progress')
        assert m['accc_determination'] == merger_status.APPROVED
        assert m['status'] == merger_status.ASSESSMENT_COMPLETED
        assert m['phase_2_determination'] == merger_status.NOT_APPROVED
        assert m['public_benefits_determination'] == merger_status.APPROVED
        assert m['public_benefits_determination_date'] == '2026-12-14T12:00:00Z'


# --- outputs ------------------------------------------------------------------

class TestOutputs:
    def test_stays_on_the_phase_2_tracker_as_completed(self):
        payload = phase2.generate([_enriched()])

        assert payload['current'] == []
        [entry] = payload['completed']
        assert entry['determination'] == merger_status.NOT_APPROVED
        assert entry['determination_date'] == PHASE_2_DATE
        assert entry['public_benefit_in_progress'] is True

    def test_counts_as_a_phase_2_matter(self):
        m = _enriched()
        assert classify_phase(m) == merger_status.PHASE_2
        assert list_output._lightweight(m)['reached_phase_2'] is True

    def test_ordinary_list_entry_carries_no_extra_field(self):
        assert 'reached_phase_2' not in list_output._lightweight(enrich_merger(_phase_2_decided()))

    def test_stats_keep_the_phase_2_outcome_and_its_date(self):
        payload = stats.generate([_enriched()])

        assert payload['by_phase_2_determination'] == {merger_status.NOT_APPROVED: 1}
        recent = [(d['determination'], d['determination_date'])
                  for d in payload['recent_determinations']]
        assert (merger_status.NOT_APPROVED, PHASE_2_DATE) in recent

    def test_upcoming_public_benefit_milestones(self, monkeypatch):
        class _Now(datetime):
            @classmethod
            def now(cls, tz=None):
                return datetime(2026, 10, 7, tzinfo=tz)
        monkeypatch.setattr(upcoming_events, 'datetime', _Now)

        payload = upcoming_events.generate([_enriched()], days_ahead=90)

        assert [(e['type'], e['date'][:10], e['event_type_display']) for e in payload['events']] == [
            ('public_benefit_assessment', '2026-11-02', 'Public benefit assessment'),
            ('public_benefit_response_due', '2026-11-23', 'Public benefit responses due'),
            ('determination_due', '2026-12-14', 'Public benefit determination due'),
        ]


# --- digest -------------------------------------------------------------------

def test_digest_lists_the_decline_and_the_ongoing_public_benefit_phase(monkeypatch):
    stored = _stored(_public_benefit_applied(), _phase_2_decided())
    monkeypatch.setattr(gwd, 'load_mergers', lambda: [stored])
    monkeypatch.setattr(gwd, 'filter_active', lambda ms: ms)
    monkeypatch.setattr(gwd, 'get_last_week_range', lambda: (
        datetime.fromisoformat('2026-09-28T00:00:00+10:00'),
        datetime.fromisoformat('2026-10-04T23:59:59+10:00'),
    ))
    monkeypatch.setattr(gwd, 'load_tribunal_appeals', lambda: {})
    monkeypatch.setattr(gwd, 'link_tribunal_appeals', lambda ms, appeals: 0)

    digest = gwd.generate_weekly_digest(previous_digest={})

    assert [m['merger_id'] for m in digest['deals_declined']] == ['MN-65005']
    assert [m['merger_id'] for m in digest['ongoing_public_benefit']] == ['MN-65005']
    assert digest['ongoing_phase_2'] == []


# --- ATmosphere ---------------------------------------------------------------

class TestAtproto:
    def test_posts_the_application_without_reposting_the_phase_2_decline(self):
        found = {m.key: m.headline for m in milestones(slim_for_site(_enriched()))}

        assert found['MN-65005:determined:2026-09-22'] == 'Not approved by the ACCC'
        assert found['MN-65005:public-benefit:2026-10-06'] == 'Public benefit determination sought'

    def test_posts_the_public_benefit_determination(self):
        merger = _public_benefit_applied()
        merger['status'] = merger_status.ASSESSMENT_COMPLETED
        merger['accc_determination'] = merger_status.NOT_APPROVED
        merger['determination_publication_date'] = '2026-12-14T12:00:00Z'
        previous = _stored(_public_benefit_applied(), _phase_2_decided())
        m = enrich_merger(_stored(merger, previous))

        found = {m.key: m.headline for m in milestones(slim_for_site(m))}

        assert found['MN-65005:determined:2026-09-22'] == 'Not approved by the ACCC'
        assert found['MN-65005:public-benefit-determined:2026-12-14'] == (
            'Not approved by the ACCC after public benefit review'
        )

    def test_record_carries_the_phase_2_determination_while_the_application_runs(self):
        record = matter_record(slim_for_site(_enriched()), indexed_at='2026-10-07T00:00:00.000Z')

        assert record['phase'] == merger_status.PUBLIC_BENEFIT_STAGE
        assert [(d['outcome'], d['phase']) for d in record['determinations']] == [
            (merger_status.REFERRED_TO_PHASE_2, 'Phase 1 - initial assessment'),
            (merger_status.NOT_APPROVED, merger_status.PHASE_2_STAGE),
        ]


# --- scraping cutoff ----------------------------------------------------------

def test_conditional_clearance_is_scraped_past_the_application_window():
    merger = {
        'merger_id': 'MN-1',
        'stage': merger_status.PHASE_2_STAGE,
        'accc_determination': merger_status.APPROVED,
        'determination_publication_date': '2026-09-01T12:00:00Z',
        'events': [{'title': 'ACCC accepted s87B undertaking', 'date': '2026-09-01T12:00:00Z'}],
    }
    unconditional = {**merger, 'events': []}

    assert (get_cutoff_date(merger) - get_cutoff_date(unconditional)).days == 14
