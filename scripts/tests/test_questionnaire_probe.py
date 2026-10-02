"""Tests for the guessed-questionnaire-URL probe and its use by the detector."""

import json

from scripts import extract_mergers
from scripts import questionnaire_probe as qp
from scripts.extract_mergers import detect_missing_questionnaires

BASE = qp.BASE_URL


class TestCandidateUrls:
    def test_covers_the_filename_shapes_recent_matters_used(self):
        urls = set(qp.candidate_urls({
            'merger_id': 'MN-70039', 'merger_name': 'Architectus – SBA'}))
        assert BASE + 'Architectus%20-%20SBA%20-%20third-party%20questionnaire.docx' in urls
        assert BASE + 'Questionnaire%20-%20Architectus%20-%20SBA.docx' in urls
        assert BASE + 'Architectus%20-%20SBA%20-%20Questionnaire_0.docx' in urls
        assert BASE + 'Architectus%20-%20SBA%20-%20Questionnaire.pdf' in urls
        assert BASE + 'MN-70039%20-%20Architectus%20-%20SBA%20-%20questionnaire_1.docx' in urls

    def test_dated_consultation_title_uses_the_notification_day(self):
        urls = set(qp.candidate_urls({
            'merger_id': 'MN-85042', 'merger_name': 'Vets Central - Vital Vet',
            'effective_notification_datetime': '2026-09-28T12:00:00Z'}))
        assert BASE + (
            'Vets%20Central%20-%20Vital%20Vet%20-%20Third-party%20questionnaire'
            '%20-%20Phase%201%20consultation%20-%2028%20September%202026.docx') in urls

    def test_drops_a_trailing_parenthetical_the_acc_omits(self):
        urls = set(qp.candidate_urls({
            'merger_id': 'MN-20039',
            'merger_name': 'Calvary – Southern Cross Care (Tasmania)'}))
        assert BASE + 'Calvary%20-%20Southern%20Cross%20Care%20-%20Questionnaire.docx' in urls

    def test_no_repeats_and_nothing_without_a_name(self):
        urls = qp.candidate_urls({'merger_id': 'MN-1', 'merger_name': 'A - B'})
        assert len(urls) == len(set(urls))
        assert qp.candidate_urls({'merger_id': 'MN-1'}) == []


class _Response:
    def __init__(self, status, content_type):
        self.status_code = status
        self.headers = {'content-type': content_type}


class _Session:
    """Serves a document at ``live`` and the ACCC's HTML 404 everywhere else."""

    def __init__(self, live):
        self.live = live

    def head(self, url, **_):
        if url == self.live:
            return _Response(200, 'application/vnd.openxmlformats-officedocument.wordprocessingml.document')
        return _Response(404, 'text/html; charset=UTF-8')


class TestProbeQuestionnaire:
    merger = {'merger_id': 'MN-70039', 'merger_name': 'Architectus – SBA'}

    def test_returns_the_url_that_exists(self):
        live = BASE + 'Questionnaire%20-%20Architectus%20-%20SBA.docx'
        assert qp.probe_questionnaire(self.merger, _Session(live)) == live

    def test_none_when_nothing_exists(self):
        assert qp.probe_questionnaire(self.merger, _Session(None)) is None

    def test_a_200_html_page_is_not_a_document(self):
        class Soft(_Session):
            def head(self, url, **_):
                return _Response(200, 'text/html')
        assert qp.probe_questionnaire(self.merger, Soft(None)) is None

    def test_network_errors_read_as_not_found(self):
        class Down(_Session):
            def head(self, url, **_):
                raise OSError('boom')
        assert qp.probe_questionnaire(self.merger, Down(None)) is None


class TestDetectorUsesProbe:
    def _run(self, mergers, tmp_path, monkeypatch, probe):
        out = tmp_path / 'missing_questionnaires.json'
        monkeypatch.setattr(extract_mergers, 'MISSING_QUESTIONNAIRES_PATH', str(out))
        detect_missing_questionnaires(mergers, probe=probe)
        return json.loads(out.read_text())

    def _recent(self):
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).strftime('%Y-%m-%dT12:00:00Z')

    def test_a_hit_is_reported_but_the_matter_stays_open(self, tmp_path, monkeypatch):
        mergers = [{'merger_id': 'MN-1', 'merger_name': 'A - B', 'events': [],
                    'effective_notification_datetime': self._recent()}]
        result = self._run(mergers, tmp_path, monkeypatch, lambda m: 'https://x/q.docx')
        assert [i['merger_id'] for i in result['open']] == ['MN-1']
        assert result['open'][0]['probed_url'] == 'https://x/q.docx'
        assert 'https://x/q.docx' in result['open'][0]['body']

    def test_no_probe_by_default_and_none_for_stale_matters(self, tmp_path, monkeypatch):
        calls = []
        stale = [{'merger_id': 'MN-2', 'merger_name': 'C - D', 'events': [],
                  'effective_notification_datetime': '2020-01-01T12:00:00Z'}]
        result = self._run(stale, tmp_path, monkeypatch, lambda m: calls.append(m))
        assert calls == [] and result['open'][0]['probed_url'] is None
        result = self._run(stale, tmp_path, monkeypatch, None)
        assert result['open'][0]['probed_url'] is None

    def test_probe_not_called_when_questionnaire_present(self, tmp_path, monkeypatch):
        calls = []
        mergers = [{'merger_id': 'MN-3', 'events': [{'title': 'Questionnaire'}]}]
        self._run(mergers, tmp_path, monkeypatch, lambda m: calls.append(m))
        assert calls == []
