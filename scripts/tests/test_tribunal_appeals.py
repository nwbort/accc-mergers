"""Tests for the Australian Competition Tribunal appeal overlay.

Covers loading tribunal_appeals.json, linking appeals onto enriched mergers
(the ``under_appeal`` flag, the ``appeal`` record and the appeal documents
folded into the event timeline), and propagation of ``under_appeal`` to the
lightweight list, Phase 2 and timeline outputs.
"""

import json
import os
import sys
import unittest.mock
from pathlib import Path

# Add scripts directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Mock heavy transitive imports before importing modules that need them
sys.modules.setdefault('pdfplumber', unittest.mock.MagicMock())
sys.modules.setdefault('markdownify', unittest.mock.MagicMock())
sys.modules.setdefault('requests', unittest.mock.MagicMock())

from constants import tribunal
from static_data import loaders
from static_data.enrichment import enrich_merger, link_tribunal_appeals
from static_data.outputs import list as list_out, phase2, stats, timeline


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


def _appeal(merger_id='MN-0001'):
    return {
        merger_id: {
            'tribunal_number': 'ACT 1 of 2026',
            'tribunal_url': 'https://www.competitiontribunal.gov.au/current-matters/act-1-of-2026',
            'appeal_type': tribunal.PARTY_DENIAL,
            'appellant': 'Coles',
            'filed_date': '2026-07-15',
            'documents': [
                {
                    'date': '2026-07-15',
                    'filed_by': 'Coles',
                    'description': 'Application for Review',
                    'confidentiality': 'Non-confidential',
                    'url': 'https://www.competitiontribunal.gov.au/x/Application-for-Review.pdf',
                    'url_gh': '/mergers/MN-0001/Application-for-Review.pdf',
                },
            ],
        }
    }


def _concluded_appeal(merger_id='MN-0001', outcome=None, effective_determination='Not approved'):
    outcome = outcome or tribunal.OUTCOME_AFFIRMED
    appeal = _appeal(merger_id)
    appeal[merger_id]['status'] = tribunal.APPEAL_STATUS_CONCLUDED
    appeal[merger_id]['outcome'] = outcome
    appeal[merger_id]['effective_determination'] = effective_determination
    appeal[merger_id]['concluded_date'] = '2026-11-01'
    return appeal


class TestLinkTribunalAppeals:
    def test_sets_flag_and_record(self):
        mergers = [enrich_merger(_phase2_not_approved())]
        linked = link_tribunal_appeals(mergers, _appeal())
        assert linked == 1
        m = mergers[0]
        assert m['under_appeal'] is True
        assert m['appeal']['tribunal_number'] == 'ACT 1 of 2026'
        assert m['appeal']['appeal_type'] == tribunal.PARTY_DENIAL
        assert m['appeal']['appellant'] == 'Coles'
        assert m['appeal']['status'] == tribunal.APPEAL_STATUS_CURRENT
        assert len(m['appeal']['documents']) == 1

    def test_hearing_date_propagated(self):
        # An optional scheduled hearing start date is carried through onto the
        # merger's appeal record so it can drive a "Tribunal hearing" event.
        appeal = _appeal()
        appeal['MN-0001']['hearing_date'] = '2026-11-09'
        mergers = [enrich_merger(_phase2_not_approved())]
        link_tribunal_appeals(mergers, appeal)
        assert mergers[0]['appeal']['hearing_date'] == '2026-11-09'

    def test_hearing_date_absent_is_none(self):
        # The fixture has no hearing_date → the key is present but null, never
        # missing, so downstream consumers can read it unconditionally.
        mergers = [enrich_merger(_phase2_not_approved())]
        link_tribunal_appeals(mergers, _appeal())
        assert mergers[0]['appeal']['hearing_date'] is None

    def test_missing_status_defaults_to_current(self):
        # The fixture has no explicit status → treated as a live appeal.
        appeal = _appeal()
        appeal['MN-0001'].pop('status', None)
        mergers = [enrich_merger(_phase2_not_approved())]
        link_tribunal_appeals(mergers, appeal)
        assert mergers[0]['under_appeal'] is True
        assert mergers[0]['appeal']['status'] == tribunal.APPEAL_STATUS_CURRENT

    def test_concluded_appeal_is_not_under_appeal(self):
        mergers = [enrich_merger(_phase2_not_approved())]
        link_tribunal_appeals(mergers, _concluded_appeal())
        m = mergers[0]
        # No longer live → badge suppressed everywhere ...
        assert m['under_appeal'] is False
        # ... but the appeal record + documents remain for the detail page.
        assert m['appeal']['status'] == tribunal.APPEAL_STATUS_CONCLUDED
        assert m['appeal']['outcome'] == tribunal.OUTCOME_AFFIRMED
        assert m['appeal']['concluded_date'] == '2026-11-01'
        assert any(e.get('is_appeal') for e in m['events'])

    def test_effective_determination_carried_through(self):
        # Party wins its refusal appeal → the merger effectively becomes Approved.
        mergers = [enrich_merger(_phase2_not_approved())]
        link_tribunal_appeals(
            mergers,
            _concluded_appeal(outcome=tribunal.OUTCOME_SET_ASIDE, effective_determination='Approved'),
        )
        m = mergers[0]
        assert m['appeal']['effective_determination'] == 'Approved'
        # The ACCC's own determination is never rewritten.
        assert m['accc_determination'] == 'Not approved'

    def test_concluded_flag_not_propagated_to_outputs(self):
        mergers = [enrich_merger(_phase2_not_approved())]
        link_tribunal_appeals(mergers, _concluded_appeal())
        assert list_out._lightweight(mergers[0])['under_appeal'] is False
        assert phase2.generate(mergers)['completed'][0]['under_appeal'] is False

    def test_preserves_accc_outcome(self):
        # The appeal layers on top of — never replaces — the ACCC outcome.
        mergers = [enrich_merger(_phase2_not_approved())]
        link_tribunal_appeals(mergers, _appeal())
        assert mergers[0]['status'] == 'Assessment completed'
        assert mergers[0]['accc_determination'] == 'Not approved'

    def test_appeal_document_folded_into_events(self):
        mergers = [enrich_merger(_phase2_not_approved())]
        link_tribunal_appeals(mergers, _appeal())
        appeal_events = [e for e in mergers[0]['events'] if e.get('is_appeal')]
        assert len(appeal_events) == 1
        ev = appeal_events[0]
        # Bare YYYY-MM-DD is promoted to the event datetime format.
        assert ev['date'] == '2026-07-15T12:00:00Z'
        assert ev['url_gh'] == '/mergers/MN-0001/Application-for-Review.pdf'
        assert ev['appeal_filed_by'] == 'Coles'
        assert ev['appeal_confidentiality'] == 'Non-confidential'
        assert ev['tribunal_number'] == 'ACT 1 of 2026'
        assert 'Application for Review' in ev['display_title']

    def test_blank_filed_by_defaults_to_tribunal(self):
        # A tribunal-issued document (order/direction/reasons) has no filing
        # party; the matter page leaves the column blank or shows a lone dash.
        # Each such value should surface as "Tribunal" in the event timeline.
        for placeholder in (None, '', '  ', '-', '–', '—', ' - '):
            appeal = _appeal()
            appeal['MN-0001']['documents'][0]['filed_by'] = placeholder
            mergers = [enrich_merger(_phase2_not_approved())]
            link_tribunal_appeals(mergers, appeal)
            ev = next(e for e in mergers[0]['events'] if e.get('is_appeal'))
            assert ev['appeal_filed_by'] == 'Tribunal', repr(placeholder)

    def test_real_filed_by_preserved(self):
        appeal = _appeal()
        appeal['MN-0001']['documents'][0]['filed_by'] = '  Coles  '
        mergers = [enrich_merger(_phase2_not_approved())]
        link_tribunal_appeals(mergers, appeal)
        ev = next(e for e in mergers[0]['events'] if e.get('is_appeal'))
        assert ev['appeal_filed_by'] == 'Coles'

    def test_no_appeal_leaves_merger_untouched(self):
        mergers = [enrich_merger(_phase2_not_approved('MN-9999'))]
        original_event_count = len(mergers[0]['events'])
        linked = link_tribunal_appeals(mergers, _appeal('MN-0001'))
        assert linked == 0
        assert 'under_appeal' not in mergers[0]
        assert 'appeal' not in mergers[0]
        assert len(mergers[0]['events']) == original_event_count

    def test_empty_appeals_is_noop(self):
        mergers = [enrich_merger(_phase2_not_approved())]
        assert link_tribunal_appeals(mergers, {}) == 0
        assert 'under_appeal' not in mergers[0]

    def test_output_is_json_serialisable(self):
        mergers = [enrich_merger(_phase2_not_approved())]
        link_tribunal_appeals(mergers, _appeal())
        json.dumps(mergers[0])


class TestUnderAppealPropagation:
    def test_lightweight_list_carries_flag(self):
        mergers = [enrich_merger(_phase2_not_approved())]
        link_tribunal_appeals(mergers, _appeal())
        entry = list_out._lightweight(mergers[0])
        assert entry['under_appeal'] is True

    def test_lightweight_defaults_false(self):
        entry = list_out._lightweight(enrich_merger(_phase2_not_approved()))
        assert entry['under_appeal'] is False
        # No appeal → no appeal summary key at all (keeps list payload lean).
        assert 'appeal' not in entry

    def test_lightweight_carries_appeal_summary(self):
        mergers = [enrich_merger(_phase2_not_approved())]
        link_tribunal_appeals(
            mergers,
            _concluded_appeal(outcome=tribunal.OUTCOME_SET_ASIDE, effective_determination='Approved'),
        )
        entry = list_out._lightweight(mergers[0])
        assert entry['appeal'] == {
            'status': tribunal.APPEAL_STATUS_CONCLUDED,
            'outcome': tribunal.OUTCOME_SET_ASIDE,
            'effective_determination': 'Approved',
        }

    def test_phase2_entry_carries_flag(self):
        mergers = [enrich_merger(_phase2_not_approved())]
        link_tribunal_appeals(mergers, _appeal())
        payload = phase2.generate(mergers)
        completed = payload['completed'][0]
        assert completed['under_appeal'] is True

    def test_timeline_events_carry_flag(self, tmp_path):
        mergers = [enrich_merger(_phase2_not_approved())]
        link_tribunal_appeals(mergers, _appeal())
        timeline.generate(mergers, tmp_path, page_size=100)
        events = json.loads((tmp_path / 'timeline' / 'timeline-page-1.json').read_text())['events']
        assert all(e['under_appeal'] for e in events)
        assert any(e['is_appeal'] for e in events)


class TestDashboardRecentActivity:
    def test_appeal_surfaces_as_recent_card(self):
        mergers = [enrich_merger(_phase2_not_approved())]
        link_tribunal_appeals(mergers, _appeal())
        payload = stats.generate(mergers)
        appeal_cards = [c for c in payload['recent_mergers'] if c.get('is_appeal')]
        assert len(appeal_cards) == 1
        card = appeal_cards[0]
        assert card['merger_id'] == 'MN-0001'
        assert card['under_appeal'] is True
        assert card['tribunal_number'] == 'ACT 1 of 2026'
        # A bare filing date is promoted so it sorts against ISO datetimes.
        assert card['appeal_date'] == '2026-07-15T12:00:00Z'

    def test_appeal_date_stays_the_filing_date(self):
        # Later documents keep the card "recent" (they drive the sort key) but
        # must not shift the "Appeal filed" date shown on the card.
        appeal = _appeal()
        appeal['MN-0001']['documents'].append({
            'date': '2026-07-28',
            'filed_by': 'Australian Competition and Consumer Commission',
            'description': 'Documentary Index',
            'confidentiality': 'Non-confidential',
            'url': 'https://www.competitiontribunal.gov.au/x/Documentary-Index.pdf',
        })
        mergers = [enrich_merger(_phase2_not_approved())]
        link_tribunal_appeals(mergers, appeal)
        card = [c for c in stats.generate(mergers)['recent_mergers'] if c.get('is_appeal')][0]
        assert card['appeal_date'] == '2026-07-15T12:00:00Z'
        assert card['effective_notification_datetime'] == '2026-07-28T12:00:00Z'

    def test_appeal_date_falls_back_to_earliest_document(self):
        # No recorded filing date → the first document stands in for it.
        appeal = _appeal()
        del appeal['MN-0001']['filed_date']
        appeal['MN-0001']['documents'].append({
            'date': '2026-07-28',
            'filed_by': 'Australian Competition and Consumer Commission',
            'description': 'Documentary Index',
            'confidentiality': 'Non-confidential',
            'url': 'https://www.competitiontribunal.gov.au/x/Documentary-Index.pdf',
        })
        mergers = [enrich_merger(_phase2_not_approved())]
        link_tribunal_appeals(mergers, appeal)
        card = [c for c in stats.generate(mergers)['recent_mergers'] if c.get('is_appeal')][0]
        assert card['appeal_date'] == '2026-07-15T12:00:00Z'

    def test_no_appeal_means_no_appeal_card(self):
        mergers = [enrich_merger(_phase2_not_approved())]
        payload = stats.generate(mergers)
        assert not any(c.get('is_appeal') for c in payload['recent_mergers'])

    def test_appeal_card_survives_after_conclusion(self):
        # A concluded appeal is still recent activity worth surfacing.
        mergers = [enrich_merger(_phase2_not_approved())]
        link_tribunal_appeals(mergers, _concluded_appeal())
        payload = stats.generate(mergers)
        appeal_cards = [c for c in payload['recent_mergers'] if c.get('is_appeal')]
        assert len(appeal_cards) == 1
        assert appeal_cards[0]['under_appeal'] is False


class TestLoader:
    def test_strips_metadata_keys(self, tmp_path, monkeypatch):
        path = tmp_path / 'tribunal_appeals.json'
        path.write_text(json.dumps({'_comment': 'x', 'MN-0001': _appeal()['MN-0001']}))
        monkeypatch.setattr(loaders, 'TRIBUNAL_APPEALS_JSON', path)
        data = loaders.load_tribunal_appeals()
        assert set(data.keys()) == {'MN-0001'}

    def test_missing_file_returns_empty(self, tmp_path, monkeypatch):
        monkeypatch.setattr(loaders, 'TRIBUNAL_APPEALS_JSON', tmp_path / 'nope.json')
        assert loaders.load_tribunal_appeals() == {}


class TestRealDataFile:
    def test_committed_file_is_valid(self):
        """The checked-in overlay parses and every appeal_type is recognised."""
        repo_root = Path(__file__).resolve().parent.parent.parent
        path = repo_root / 'data' / 'processed' / 'tribunal_appeals.json'
        data = json.loads(path.read_text())
        appeals = {k: v for k, v in data.items() if not k.startswith('_')}
        assert appeals, 'expected at least one tribunal appeal'
        for merger_id, appeal in appeals.items():
            assert appeal['tribunal_number']
            assert appeal['tribunal_url'].startswith('https://')
            assert appeal['appeal_type'] in tribunal.APPEAL_TYPES
            status = appeal.get('status', tribunal.DEFAULT_APPEAL_STATUS)
            assert status in tribunal.APPEAL_STATUSES
            if status == tribunal.APPEAL_STATUS_CONCLUDED:
                # A concluded appeal must record what the tribunal decided.
                assert appeal.get('outcome') in tribunal.APPEAL_OUTCOMES
                assert appeal.get('effective_determination')
            for doc in appeal.get('documents', []):
                assert doc['date']
                assert doc['description']
