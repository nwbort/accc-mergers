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

    def test_public_benefit_stage_closes_the_inferred_phase_2_issue(self, tmp_path, monkeypatch):
        out = tmp_path / 'inferred.json'
        monkeypatch.setattr(extract_mergers, 'INFERRED_PHASE_2_PATH', str(out))

        extract_mergers.detect_inferred_phase_2([_public_benefit_applied()])

        payload = json.loads(out.read_text())
        assert payload == {'open': [], 'confirmed': ['MN-65005']}


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
