"""Tests for the quarterly report PDFs (generate/quarterly_pdf.py)."""

import sys
import unittest.mock
from datetime import date

sys.modules.setdefault('pdfplumber', unittest.mock.MagicMock())
sys.modules.setdefault('markdownify', unittest.mock.MagicMock())
sys.modules.setdefault('requests', unittest.mock.MagicMock())

from scripts.generate import quarterly_pdf
from scripts.generate.static_data.outputs import quarterly


def _notification(merger_id, filed, decided, outcome='Approved'):
    return {
        'merger_id': merger_id,
        'merger_name': f'{merger_id} – Acquirer & Target',
        'is_waiver': False,
        'status': 'Assessment completed',
        'stage': 'Phase 1 - initial assessment',
        'effective_notification_datetime': f'{filed}T12:00:00Z',
        'phase_1_determination': outcome,
        'phase_1_determination_date': f'{decided}T12:00:00Z',
        'acquirers': [{'name': 'Bidco Inc', 'identifier_type': None, 'identifier': ''}],
        'targets': [],
        'anzsic_codes': [{'code': '6322'}],
        'events': [],
    }


def _payload(commentary=None):
    mergers = [
        _notification('MN-1', '2026-04-01', '2026-04-22'),
        _notification('MN-2', '2026-07-01', '2026-07-22'),
        _notification('MN-3', '2026-07-01', '2026-08-12', 'Referred to phase 2'),
    ]
    mergers[2]['appeals'] = [{
        'tribunal_number': 'ACT 9 of 2026', 'tribunal_url': 'https://tribunal.example/act-9',
        'appellant': 'Acquirer', 'status': 'current', 'filed_date': '2026-09-01',
    }]
    return quarterly.generate(mergers, as_at=date(2026, 10, 22), commentary=commentary)


def test_one_pdf_per_published_quarter(tmp_path):
    names = quarterly_pdf.generate(_payload(), tmp_path)
    assert names == [
        'mergers-fyi-quarterly-merger-report-2026Q1.pdf',
        'mergers-fyi-quarterly-merger-report-2026Q2.pdf',
        'mergers-fyi-quarterly-merger-report-2026Q3.pdf',
    ]
    assert sorted(p.name for p in tmp_path.iterdir()) == names
    for name in names:
        assert (tmp_path / name).read_bytes().startswith(b'%PDF-')


def test_output_is_deterministic(tmp_path):
    first, second = tmp_path / 'a', tmp_path / 'b'
    quarterly_pdf.generate(_payload(), first)
    quarterly_pdf.generate(_payload(), second)
    for path in first.iterdir():
        assert path.read_bytes() == (second / path.name).read_bytes(), path.name


def test_an_unchanged_report_is_not_rewritten(tmp_path):
    quarterly_pdf.generate(_payload(), tmp_path)
    target = tmp_path / 'mergers-fyi-quarterly-merger-report-2026Q3.pdf'
    mtime = target.stat().st_mtime_ns
    quarterly_pdf.generate(_payload(), tmp_path)
    assert target.stat().st_mtime_ns == mtime
    assert not list(tmp_path.glob('.*.tmp'))


def test_stale_reports_are_pruned_and_other_files_kept(tmp_path):
    (tmp_path / 'quarterly-report-2025-Q4.pdf').write_bytes(b'%PDF-old')
    (tmp_path / 'notes.txt').write_text('keep me')
    quarterly_pdf.generate(_payload(), tmp_path)
    assert not (tmp_path / 'quarterly-report-2025-Q4.pdf').exists()
    assert (tmp_path / 'notes.txt').exists()


def test_report_links_each_matter_and_its_own_page(tmp_path):
    # Link annotations are stored uncompressed, so their URIs can be read off
    # the raw bytes without a PDF parser (pdfplumber is mocked in this suite).
    quarterly_pdf.generate(_payload(), tmp_path)
    raw = (tmp_path / 'mergers-fyi-quarterly-merger-report-2026Q3.pdf').read_bytes()
    assert b'https://mergers.fyi/mergers/MN-3/' in raw
    assert b'https://mergers.fyi/quarterly/26Q3' in raw
    # Q3's milestones only: MN-1 was decided in Q2 without going further.
    assert b'/mergers/MN-1/' not in raw


def test_report_links_back_into_the_site(tmp_path):
    quarterly_pdf.generate(_payload(), tmp_path)
    raw = (tmp_path / 'mergers-fyi-quarterly-merger-report-2026Q3.pdf').read_bytes()
    for path in (b'/analysis', b'/current-status', b'/industries/K/', b'/phase-2', b'/mergers'):
        assert b'https://mergers.fyi' + path in raw, path


def test_report_carries_tribunal_reviews(tmp_path):
    quarterly_pdf.generate(_payload(), tmp_path)
    assert b'https://tribunal.example/act-9' in (tmp_path / 'mergers-fyi-quarterly-merger-report-2026Q3.pdf').read_bytes()
    # Lodged in Q3, so not in Q2's report.
    assert b'tribunal.example' not in (tmp_path / 'mergers-fyi-quarterly-merger-report-2026Q2.pdf').read_bytes()


def test_commentary_joins_the_brief_with_its_links(tmp_path):
    commentary = {'26Q3': [{'commentary': 'See the [tracker](https://mergers.fyi/phase-2?from=comment).',
                            'author': 'Nick'}]}
    quarterly_pdf.generate(_payload(commentary), tmp_path)
    assert b'https://mergers.fyi/phase-2?from=comment' in (tmp_path / 'mergers-fyi-quarterly-merger-report-2026Q3.pdf').read_bytes()
    assert b'from=comment' not in (tmp_path / 'mergers-fyi-quarterly-merger-report-2026Q2.pdf').read_bytes()


def test_inline_markdown():
    assert quarterly_pdf.inline_markdown('**Bold** and *italic* and _also_') == (
        '<b>Bold</b> and <i>italic</i> and <i>also</i>'
    )
    assert quarterly_pdf.inline_markdown('[A & B](https://x.example/?a=1&b=2)') == (
        '<link href="https://x.example/?a=1&amp;b=2" color="#335145">A &amp; B</link>'
    )
    # Markup-looking text is escaped, not interpreted; snake_case is left alone.
    assert quarterly_pdf.inline_markdown('a < b, merger_id') == 'a &lt; b, merger_id'
    assert quarterly_pdf.inline_markdown('one\n\ntwo\nthree') == 'one<br/><br/>two three'


def test_files_are_named_for_whoever_downloads_them(tmp_path):
    payload = _payload()
    assert [q['report_pdf'] for q in payload['quarters']] == [
        'mergers-fyi-quarterly-merger-report-2026Q1.pdf',
        'mergers-fyi-quarterly-merger-report-2026Q2.pdf',
        'mergers-fyi-quarterly-merger-report-2026Q3.pdf',
    ]


def test_files_under_an_old_name_are_pruned(tmp_path):
    (tmp_path / 'quarterly-report-2026-Q3.pdf').write_bytes(b'%PDF-old')
    quarterly_pdf.generate(_payload(), tmp_path)
    assert not (tmp_path / 'quarterly-report-2026-Q3.pdf').exists()


def test_footer_links_the_site_and_there_are_no_notes(tmp_path):
    quarterly_pdf.generate(_payload(), tmp_path)
    raw = (tmp_path / 'mergers-fyi-quarterly-merger-report-2026Q3.pdf').read_bytes()
    assert b'/URI (https://mergers.fyi)' in raw
    # The notes' pointer links (e.g. to mergers.fyi/analysis as a sentence) are gone.
    assert b'The interactive version' not in raw
