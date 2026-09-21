"""Tests for scripts/compress_pdfs.py — the preset-selection policy and the
validation that decides whether a compressed file is safe to keep.

Ghostscript isn't invoked here: compress_file() takes the compressor as a
parameter, so these tests substitute a fake that writes a file of whatever size
the scenario needs.
"""

import shutil
import sys
import unittest.mock
from pathlib import Path

import pytest

sys.modules.setdefault('pdfplumber', unittest.mock.MagicMock())

from scripts.compress_pdfs import (  # noqa: E402
    PAGES_ASSET_LIMIT,
    QUALITY_PRESETS,
    TEMP_SUFFIX,
    compress_file,
    ghostscript_compress,
    iter_oversized,
    main,
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


class TestGhostscriptFailureIsNotSilent:
    """A ghostscript that never runs must not be reported as a tidy warning.

    This is the shape of the Ubuntu 26.04 breakage: ghostscript 10.06 refused
    every -sOutputFile ending in .tmp, so compress_file() rejected all four
    presets, main() exited 0 anyway, and the pipeline step went green having
    compressed nothing — while build.sh then dropped the still-oversized files
    out of the deployment.
    """

    def test_compress_file_reports_an_error_when_no_preset_produced_output(
        self, tmp_path, stats
    ):
        src = write_pdf(tmp_path / "big.pdf", 30 * MIB)

        result = compress_file(
            src, target=20 * MIB,
            runner=fake_compressor({}),  # every preset fails outright
        )

        assert result.status == "error"
        assert "ghostscript" in result.detail

    def test_a_document_that_merely_stayed_too_big_is_still_a_warning(
        self, tmp_path, stats
    ):
        # Ghostscript ran fine; the document just wouldn't shrink past the hard
        # limit. That degrades gracefully and must not fail the pipeline.
        src = write_pdf(tmp_path / "big.pdf", 30 * MIB)

        result = compress_file(
            src, target=20 * MIB, limit=25 * MIB,
            runner=fake_compressor({p: 28 * MIB for p in QUALITY_PRESETS}),
        )

        assert result.status == "failed"

    def test_main_exits_non_zero_when_ghostscript_never_runs(
        self, tmp_path, stats, monkeypatch
    ):
        write_pdf(tmp_path / "big.pdf", 30 * MIB)
        monkeypatch.setattr('scripts.compress_pdfs.shutil.which', lambda name: '/usr/bin/gs')
        monkeypatch.setattr(
            'scripts.compress_pdfs.ghostscript_compress',
            lambda src, dst, preset: False,
        )

        assert main(["--root", str(tmp_path)]) == 1

    def test_main_exits_zero_when_a_document_just_would_not_shrink(
        self, tmp_path, stats, monkeypatch
    ):
        write_pdf(tmp_path / "big.pdf", 30 * MIB)
        monkeypatch.setattr('scripts.compress_pdfs.shutil.which', lambda name: '/usr/bin/gs')
        monkeypatch.setattr(
            'scripts.compress_pdfs.ghostscript_compress',
            fake_compressor({p: 28 * MIB for p in QUALITY_PRESETS}),
        )

        assert main(["--root", str(tmp_path)]) == 0


class TestTempFileNaming:
    """The candidate ghostscript writes has to be named something ghostscript
    will open, and something nothing else mistakes for a deployable document."""

    def test_temp_suffix_is_a_pdf_extension(self):
        # ghostscript 10.06 (Ubuntu 26.04) fails with "Unable to open the
        # initial device" on any -sOutputFile ending in .tmp. The extension is
        # the only thing that matters — not the leading dot, not -dSAFER.
        assert TEMP_SUFFIX.endswith(".pdf")

    def test_candidates_are_written_next_to_the_original_with_that_suffix(
        self, tmp_path, stats
    ):
        src = write_pdf(tmp_path / "big.pdf", 30 * MIB)
        seen = []

        def spy(source, dst, preset):
            seen.append(Path(dst))
            write_pdf(dst, 14 * MIB)
            return True

        compress_file(src, target=20 * MIB, runner=spy)

        assert seen, "the runner was never called"
        for dst in seen:
            assert dst.name.endswith(TEMP_SUFFIX), dst.name
            assert dst.parent == src.parent

    def test_a_leftover_candidate_is_not_treated_as_a_deployable_pdf(self, tmp_path):
        # Every path in compress_file unlinks its candidate in a finally, so one
        # only survives an outright kill — but *.pdf globs match dotfiles, so
        # iter_oversized would otherwise try to compress the debris.
        write_pdf(tmp_path / f".big.pdf.prepress{TEMP_SUFFIX}", 30 * MIB)
        write_pdf(tmp_path / f".big.pdf.best{TEMP_SUFFIX}", 30 * MIB)
        write_pdf(tmp_path / "big.pdf", 30 * MIB)

        assert [p.name for p in iter_oversized(tmp_path, PAGES_ASSET_LIMIT)] == ["big.pdf"]


def minimal_pdf_bytes():
    """A valid one-page PDF, built with real xref offsets so gs won't complain."""
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length 44 >>\nstream\nBT /F1 12 Tf 20 100 Td (compressible) Tj ET\nendstream",
    ]

    out = bytearray(b"%PDF-1.7\n")
    offsets = []
    for i, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % i + body + b"\nendobj\n"

    xref_at = len(out)
    out += b"xref\n0 %d\n" % (len(objects) + 1)
    out += b"0000000000 65535 f \n"
    for off in offsets:
        out += b"%010d 00000 n \n" % off
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
        len(objects) + 1, xref_at,
    )
    return bytes(out)


@pytest.mark.skipif(shutil.which("gs") is None, reason="ghostscript not installed")
class TestAgainstRealGhostscript:
    """The one check the fakes above cannot make: that the filename we hand
    ghostscript is one it will actually open.

    Ghostscript 10.06 rejects an -sOutputFile ending in .tmp outright, which is
    invisible to a dependency-injected runner and was invisible in CI too — the
    run went green having compressed nothing. This drives the real binary on
    whatever image the suite happens to run on, so a future version rejecting
    the naming scheme fails here instead of silently in the pipeline.
    """

    def test_ghostscript_accepts_the_temp_filename_compress_file_uses(self, tmp_path):
        src = tmp_path / "doc.pdf"
        src.write_bytes(minimal_pdf_bytes())
        dst = tmp_path / f".{src.name}.prepress{TEMP_SUFFIX}"

        assert ghostscript_compress(src, dst, "prepress") is True
        assert dst.exists() and dst.stat().st_size > 0
        assert dst.read_bytes().startswith(b"%PDF")

    def test_every_name_compress_file_generates_is_one_ghostscript_opens(
        self, tmp_path, stats
    ):
        # The test above pins one hand-written name; this one lets compress_file
        # choose the names itself and then hands each to the real binary, so the
        # two halves can't drift apart. The injected runners used everywhere else
        # accept any name at all — which is precisely why .tmp survived in here.
        src = tmp_path / "doc.pdf"
        src.write_bytes(minimal_pdf_bytes())

        names = []

        def capture(source, dst, preset):
            names.append(Path(dst))
            return False  # fail every preset; we only want the filenames

        compress_file(src, target=20 * MIB, runner=capture)

        assert len(names) == len(QUALITY_PRESETS)
        for dst in names:
            assert ghostscript_compress(src, dst, "prepress") is True, dst.name
