#!/usr/bin/env python3
"""Shrink PDFs that are too big for Cloudflare Pages to deploy.

Pages rejects an *entire* deployment if any single asset is over 25 MiB, so one
outsized attachment takes the whole site build down. Scanned exhibits from the
Competition Tribunal are the usual culprit: MN-01068's 30.8 MB affidavit is 69
page scans stored as lossless Flate RGB bitmaps, which is a very expensive way
to hold what is really a fax-quality scan of a typed document.

Ghostscript re-encodes those page images as JPEG. At the presets used here it
leaves the page count, the text layer and the image pixel dimensions alone — the
30.8 MB affidavit comes out at 20.6 MB with no visible difference at reading
zoom — so this is a storage-format change, not a resampling of the document.

The file is rewritten in place under data/raw/matters. Both scrapers skip a
document whose local path already exists (see ``download_attachment`` in
extract_mergers.py and ``_resolve_download_target`` in scrape_tribunal.py), so a
compressed file stays compressed rather than being re-fetched at full size on
the next run. The originals remain in git history.

Compression is best-effort: anything that can't be brought under the limit, or
that fails validation, is left exactly as it was. scripts/build.sh still leaves
oversized files out of the deployment, and the Pages Function still redirects
those to the document's source URL, so a failure here degrades rather than
breaks.

Usage:
    python scripts/compress_pdfs.py                  # all of data/raw/matters
    python scripts/compress_pdfs.py path/to/file.pdf # specific files
    python scripts/compress_pdfs.py --dry-run        # report, change nothing
"""

import argparse
import os
import shutil
import subprocess
import sys
from collections import namedtuple
from pathlib import Path

MATTERS_DIR = Path("data/raw/matters")

# The hard limit Cloudflare Pages enforces per asset. Must stay in sync with
# MAX_ASSET_SIZE in scripts/build.sh.
PAGES_ASSET_LIMIT = 25 * 1024 * 1024

# What we actually aim for. Sitting just under the hard limit is a bad place to
# be — it leaves no room for a document to be re-scanned slightly larger — and
# the reader downloads whatever we deploy, so the headroom is worth having.
DEFAULT_TARGET_SIZE = 20 * 1024 * 1024

# Ghostscript presets, best quality first. The first one that gets the file
# under the target wins, so a document only loses as much fidelity as it has to.
# None of these upsample, and none downsample images already below their dpi
# threshold, which covers every scan we've seen (144 ppi).
QUALITY_PRESETS = ("prepress", "printer", "ebook", "screen")

# A compressed file has to keep every page and effectively all of its text layer
# — Ghostscript preserves both, so a shortfall means the rewrite went wrong and
# the original should be kept.
MIN_TEXT_RATIO = 0.95
TEXT_CHECK_THRESHOLD = 200  # chars; below this the text layer is too small to judge

Result = namedtuple("Result", "path original_size new_size preset status detail")


def iter_oversized(root, limit=PAGES_ASSET_LIMIT):
    """PDFs under ``root`` that exceed ``limit``, in a stable order."""
    root = Path(root)
    if not root.exists():
        return []
    oversized = [
        p for p in root.rglob("*.pdf")
        if p.is_file() and p.stat().st_size > limit
    ]
    return sorted(oversized)


def pdf_stats(path):
    """``(page_count, text_length)`` for a PDF, or None if it can't be read.

    A file we can't parse is one we can't validate, so callers treat None as a
    reason to leave the original alone.
    """
    try:
        import pdfplumber
    except ImportError:  # pragma: no cover - pdfplumber is in requirements.txt
        print("Warning: pdfplumber not installed, skipping validation", file=sys.stderr)
        return None

    try:
        with pdfplumber.open(str(path)) as pdf:
            pages = len(pdf.pages)
            text = "".join(page.extract_text() or "" for page in pdf.pages)
        return pages, len(text)
    except Exception as e:
        print(f"Warning: could not read {path}: {e}", file=sys.stderr)
        return None


def ghostscript_compress(src, dst, preset):
    """Re-encode ``src`` into ``dst`` at ``preset``. True if Ghostscript succeeded."""
    cmd = [
        "gs",
        "-sDEVICE=pdfwrite",
        "-dCompatibilityLevel=1.7",
        f"-dPDFSETTINGS=/{preset}",
        # Scanned filings repeat the same letterhead and watermark on every
        # page; storing those once is free size on documents that have them.
        "-dDetectDuplicateImages=true",
        "-dCompressFonts=true",
        "-dNOPAUSE",
        "-dBATCH",
        "-dQUIET",
        "-dSAFER",
        f"-sOutputFile={dst}",
        str(src),
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
    except FileNotFoundError:
        print("Error: ghostscript (gs) is not installed", file=sys.stderr)
        return False
    except subprocess.TimeoutExpired:
        print(f"Warning: ghostscript timed out on {src}", file=sys.stderr)
        return False

    if proc.returncode != 0:
        detail = (proc.stderr or "").strip().splitlines()
        tail = detail[-1] if detail else f"exit {proc.returncode}"
        print(f"Warning: ghostscript failed on {src}: {tail}", file=sys.stderr)
        return False
    return True


def rejection_reason(original_stats, candidate, original_size):
    """Why ``candidate`` shouldn't replace the original, or None if it's good."""
    if not candidate.exists() or candidate.stat().st_size == 0:
        return "produced no output"

    if candidate.stat().st_size >= original_size:
        return "no smaller than the original"

    if original_stats is None:
        # We couldn't read the original, so there's nothing to compare against.
        return "original could not be validated"

    candidate_stats = pdf_stats(candidate)
    if candidate_stats is None:
        return "compressed file could not be read back"

    original_pages, original_text = original_stats
    new_pages, new_text = candidate_stats

    if new_pages != original_pages:
        return f"page count changed ({original_pages} -> {new_pages})"

    if original_text >= TEXT_CHECK_THRESHOLD and new_text < original_text * MIN_TEXT_RATIO:
        return f"text layer shrank ({original_text} -> {new_text} chars)"

    return None


def compress_file(
    path,
    target=DEFAULT_TARGET_SIZE,
    limit=PAGES_ASSET_LIMIT,
    presets=QUALITY_PRESETS,
    dry_run=False,
    runner=ghostscript_compress,
):
    """Rewrite ``path`` at the highest-quality preset that gets it under ``target``.

    Falls back to accepting anything under the hard ``limit`` if no preset
    reaches the target — deploying a barely-small-enough file still beats not
    deploying it at all.
    """
    path = Path(path)
    original_size = path.stat().st_size
    original_stats = pdf_stats(path)

    tmp_dir = path.parent
    # Highest-quality candidate that cleared the hard limit but missed the
    # target, kept in case no preset reaches the target. Presets run best-first,
    # so the first one to fit is the one worth holding.
    held = None
    held_size = None
    held_preset = None

    try:
        for preset in presets:
            tmp = tmp_dir / f".{path.name}.{preset}.tmp"
            try:
                if not runner(path, tmp, preset):
                    continue

                reason = rejection_reason(original_stats, tmp, original_size)
                if reason is not None:
                    print(f"  {preset}: rejected — {reason}", file=sys.stderr)
                    continue

                size = tmp.stat().st_size
                if size <= target:
                    if dry_run:
                        return Result(path, original_size, size, preset, "would-compress", None)
                    os.replace(tmp, path)
                    tmp = None  # consumed by the replace
                    return Result(path, original_size, size, preset, "compressed", None)

                if size <= limit and held is None:
                    held = tmp_dir / f".{path.name}.best.tmp"
                    os.replace(tmp, held)
                    tmp = None
                    held_size, held_preset = size, preset
            finally:
                if tmp is not None:
                    tmp.unlink(missing_ok=True)

        if held is not None:
            if dry_run:
                return Result(
                    path, original_size, held_size, held_preset, "would-compress", None
                )
            os.replace(held, path)
            held = None  # consumed by the replace
            return Result(
                path, original_size, held_size, held_preset, "compressed", None
            )

        return Result(
            path, original_size, original_size, None, "failed",
            f"no preset got it under {limit} bytes",
        )
    finally:
        if held is not None:
            held.unlink(missing_ok=True)


def format_size(n):
    return f"{n / (1024 * 1024):.1f} MiB"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "paths", nargs="*", type=Path,
        help="specific PDFs to compress (default: every oversized PDF under --root)",
    )
    parser.add_argument("--root", type=Path, default=MATTERS_DIR)
    parser.add_argument(
        "--limit", type=int, default=PAGES_ASSET_LIMIT,
        help="hard per-asset size limit in bytes (default: Cloudflare Pages' 25 MiB)",
    )
    parser.add_argument(
        "--target", type=int, default=DEFAULT_TARGET_SIZE,
        help="size to aim for in bytes; lower means more aggressive compression",
    )
    parser.add_argument("--dry-run", action="store_true", help="report without rewriting")
    args = parser.parse_args(argv)

    if args.paths:
        targets = [p for p in args.paths if p.is_file()]
        missing = [p for p in args.paths if not p.is_file()]
        for p in missing:
            print(f"Warning: not a file: {p}", file=sys.stderr)
    else:
        targets = iter_oversized(args.root, args.limit)

    if not targets:
        print(f"No PDFs over {format_size(args.limit)} under {args.root}")
        return 0

    if shutil.which("gs") is None:
        print("Error: ghostscript (gs) is not installed", file=sys.stderr)
        return 1

    failures = 0
    for path in targets:
        print(f"{path} ({format_size(path.stat().st_size)})")
        result = compress_file(
            path, target=args.target, limit=args.limit, dry_run=args.dry_run,
        )
        if result.status == "failed":
            print(f"  could not compress: {result.detail}", file=sys.stderr)
            failures += 1
            continue
        verb = "would compress" if result.status == "would-compress" else "compressed"
        saved = 100 * (1 - result.new_size / result.original_size)
        print(
            f"  {verb} to {format_size(result.new_size)} "
            f"(-{saved:.0f}%, /{result.preset})"
        )

    # Anything still oversized is left for build.sh to skip and the Pages
    # Function to redirect, so this stays a warning rather than a hard failure.
    if failures:
        print(
            f"{failures} file(s) still over the limit — the deployment will skip "
            "them and redirect to the source URL",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
