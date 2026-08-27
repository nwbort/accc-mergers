"""Tests for scripts/compress_pdfs.py — the preset-selection policy and the
validation that decides whether a compressed file is safe to keep.

Ghostscript isn't invoked here: compress_file() takes the compressor as a
parameter, so these tests substitute a fake that writes a file of whatever size
the scenario needs.
"""

import sys
import unittest.mock

import pytest

sys.modules.setdefault('pdfplumber', unittest.mock.MagicMock())

from scripts.compress_pdfs import (  # noqa: E402
    PAGES_ASSET_LIMIT,
    QUALITY_PRESETS,
    compress_file,
    iter_oversized,
    rejection_reason,
)

MIB = 1024 * 1024


def write_pdf(path, size):
    """A file of exactly ``size`` bytes at ``path``."""
    path.write_bytes(b"%PDF-1.7\n" + b"\0" * (size - 9))
    return path


def fake_compressor(sizes):
    """A stand-in for ghostscript_compress that writes ``sizes[preset]`` bytes.

    A preset mapped to None fails outright, the way ghostscript does on a
    document it can't process.
    """
    def run(src, dst, preset):
        size = sizes.get(preset)
        if size is None:
            return False
        write_pdf(dst, size)
        return True
    return run


@pytest.fixture
def stats(monkeypatch):
    """Make every PDF look like a valid 10-page document with a text layer, so
    validation passes unless a test says otherwise."""
    monkeypatch.setattr('scripts.compress_pdfs.pdf_stats', lambda path: (10, 5000))


class TestPresetSelection:
    def test_picks_the_highest_quality_preset_that_meets_the_target(self, tmp_path, stats):
        src = write_pdf(tmp_path / "big.pdf", 30 * MIB)
        result = compress_file(
            src,
            target=20 * MIB,
            runner=fake_compressor({
                'prepress': 28 * MIB,   # over target
                'printer': 19 * MIB,    # first to fit — should win
                'ebook': 14 * MIB,      # would fit too, but lower quality
            }),
        )

        assert result.status == "compressed"
        assert result.preset == "printer"
        assert src.stat().st_size == 19 * MIB

    def test_walks_down_the_ladder_until_the_target_is_met(self, tmp_path, stats):
        src = write_pdf(tmp_path / "big.pdf", 60 * MIB)
        result = compress_file(
            src,
            target=15 * MIB,
            runner=fake_compressor({
                'prepress': 55 * MIB,
                'printer': 40 * MIB,
                'ebook': 22 * MIB,
                'screen': 12 * MIB,
            }),
        )

        assert result.preset == "screen"
        assert src.stat().st_size == 12 * MIB

    def test_falls_back_to_the_best_preset_under_the_hard_limit(self, tmp_path, stats):
        # Nothing reaches the target, but /printer clears the limit Pages
        # actually enforces — deploying that beats not deploying at all, and it
        # should be preferred over the lower-quality preset that also clears it.
        src = write_pdf(tmp_path / "big.pdf", 40 * MIB)
        result = compress_file(
            src,
            target=10 * MIB,
            limit=25 * MIB,
            runner=fake_compressor({
                'prepress': 30 * MIB,
                'printer': 24 * MIB,
                'ebook': 22 * MIB,
                'screen': 20 * MIB,
            }),
        )

        assert result.status == "compressed"
        assert result.preset == "printer"
        assert src.stat().st_size == 24 * MIB

    def test_leaves_the_file_alone_when_nothing_gets_under_the_limit(self, tmp_path, stats):
        src = write_pdf(tmp_path / "huge.pdf", 200 * MIB)
        result = compress_file(
            src,
            target=20 * MIB,
            limit=25 * MIB,
            runner=fake_compressor({p: 100 * MIB for p in QUALITY_PRESETS}),
        )

        assert result.status == "failed"
        assert src.stat().st_size == 200 * MIB

    def test_skips_presets_ghostscript_fails_on(self, tmp_path, stats):
        src = write_pdf(tmp_path / "big.pdf", 30 * MIB)
        result = compress_file(
            src,
            target=20 * MIB,
            runner=fake_compressor({'prepress': None, 'printer': None, 'ebook': 14 * MIB}),
        )

        assert result.preset == "ebook"

    def test_dry_run_reports_without_touching_the_file(self, tmp_path, stats):
        src = write_pdf(tmp_path / "big.pdf", 30 * MIB)
        result = compress_file(
            src, target=20 * MIB, dry_run=True,
            runner=fake_compressor({'prepress': 28 * MIB, 'printer': 19 * MIB}),
        )

        assert result.status == "would-compress"
        assert result.preset == "printer"
        assert src.stat().st_size == 30 * MIB

    def test_leaves_no_temp_files_behind(self, tmp_path, stats):
        src = write_pdf(tmp_path / "big.pdf", 40 * MIB)
        compress_file(
            src, target=10 * MIB, limit=25 * MIB,
            runner=fake_compressor({
                'prepress': 30 * MIB, 'printer': 24 * MIB,
                'ebook': 22 * MIB, 'screen': 20 * MIB,
            }),
        )

        assert [p.name for p in tmp_path.iterdir()] == ["big.pdf"]


class TestValidation:
    def test_rejects_a_compressed_file_that_lost_pages(self, tmp_path, monkeypatch):
        src = write_pdf(tmp_path / "big.pdf", 30 * MIB)
        # The original has 10 pages; anything ghostscript writes claims 9.
        monkeypatch.setattr(
            'scripts.compress_pdfs.pdf_stats',
            lambda path: (10, 5000) if path == src else (9, 5000),
        )
        result = compress_file(
            src, target=20 * MIB,
            runner=fake_compressor({p: 14 * MIB for p in QUALITY_PRESETS}),
        )

        assert result.status == "failed"
        assert src.stat().st_size == 30 * MIB

    def test_rejects_a_compressed_file_that_lost_its_text_layer(self, tmp_path, monkeypatch):
        src = write_pdf(tmp_path / "big.pdf", 30 * MIB)
        monkeypatch.setattr(
            'scripts.compress_pdfs.pdf_stats',
            lambda path: (10, 5000) if path == src else (10, 100),
        )
        result = compress_file(
            src, target=20 * MIB,
            runner=fake_compressor({p: 14 * MIB for p in QUALITY_PRESETS}),
        )

        assert result.status == "failed"

    def test_tolerates_a_small_text_difference(self, tmp_path, monkeypatch):
        # Ghostscript's rewrite shifts the extracted text by a character or two;
        # that's normal and must not block compression.
        src = write_pdf(tmp_path / "big.pdf", 30 * MIB)
        monkeypatch.setattr(
            'scripts.compress_pdfs.pdf_stats',
            lambda path: (10, 5000) if path == src else (10, 4999),
        )
        result = compress_file(
            src, target=20 * MIB,
            runner=fake_compressor({p: 14 * MIB for p in QUALITY_PRESETS}),
        )

        assert result.status == "compressed"

    def test_ignores_the_text_check_for_a_scan_with_no_text_layer(self, tmp_path, monkeypatch):
        # A pure image scan has no text to compare, so the check shouldn't
        # veto compressing it.
        src = write_pdf(tmp_path / "scan.pdf", 30 * MIB)
        monkeypatch.setattr('scripts.compress_pdfs.pdf_stats', lambda path: (10, 0))
        result = compress_file(
            src, target=20 * MIB,
            runner=fake_compressor({p: 14 * MIB for p in QUALITY_PRESETS}),
        )

        assert result.status == "compressed"

    def test_rejects_output_that_is_not_smaller(self, tmp_path):
        src = write_pdf(tmp_path / "a.pdf", 30 * MIB)
        candidate = write_pdf(tmp_path / "b.pdf", 30 * MIB)

        assert rejection_reason((10, 5000), candidate, 30 * MIB) == "no smaller than the original"

    def test_rejects_an_empty_output(self, tmp_path):
        candidate = tmp_path / "b.pdf"
        candidate.write_bytes(b"")

        assert rejection_reason((10, 5000), candidate, 30 * MIB) == "produced no output"

    def test_rejects_when_the_original_could_not_be_read(self, tmp_path):
        candidate = write_pdf(tmp_path / "b.pdf", 10 * MIB)

        reason = rejection_reason(None, candidate, 30 * MIB)
        assert reason == "original could not be validated"


class TestFindingOversizedFiles:
    def test_finds_only_files_over_the_limit(self, tmp_path):
        (tmp_path / "MN-1").mkdir()
        (tmp_path / "MN-2").mkdir()
        write_pdf(tmp_path / "MN-1" / "big.pdf", 30 * MIB)
        write_pdf(tmp_path / "MN-1" / "small.pdf", 1 * MIB)
        write_pdf(tmp_path / "MN-2" / "also-big.pdf", 26 * MIB)

        found = [p.name for p in iter_oversized(tmp_path, PAGES_ASSET_LIMIT)]
        assert sorted(found) == ["also-big.pdf", "big.pdf"]

    def test_a_file_exactly_at_the_limit_is_not_oversized(self, tmp_path):
        # Pages allows files "up to 25 MiB", and scripts/build.sh copies them,
        # so this must agree with that boundary.
        write_pdf(tmp_path / "exact.pdf", PAGES_ASSET_LIMIT)

        assert iter_oversized(tmp_path, PAGES_ASSET_LIMIT) == []

    def test_ignores_non_pdf_files(self, tmp_path):
        (tmp_path / "big.docx").write_bytes(b"\0" * (30 * MIB))

        assert iter_oversized(tmp_path, PAGES_ASSET_LIMIT) == []

    def test_missing_directory_is_not_an_error(self, tmp_path):
        assert iter_oversized(tmp_path / "nope", PAGES_ASSET_LIMIT) == []
