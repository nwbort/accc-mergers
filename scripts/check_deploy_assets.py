#!/usr/bin/env python3
"""Report deployments Cloudflare Pages will refuse: oversized files, too many files.

Pages enforces two limits, and they fail in opposite ways.

The *per-asset* limit is 25 MiB, and this is the safety net behind
scripts/compress_pdfs.py. Compression runs in the
scrape workflows before anything is committed and handles the ordinary case (a
scanned exhibit stored as lossless bitmaps), but it can't help every file — a
PDF that's genuinely 200 MB of imagery won't come under the limit at any
quality, and files can reach the repo by routes that never run compression at
all (a manual workflow, a direct commit).

Whatever it can't fix used to surface as a hard Pages build failure. It doesn't
any more: scripts/build.sh leaves oversized files out of the deployment so the
rest of the site still ships, and the Pages Function redirects them to their
source URL. That's the right trade for availability, but it means an oversized
file is now *silent* — the site builds green while quietly not hosting the
document. Hence this check, which runs on every push to main and opens a GitHub
issue so it's visible.

What counts as deployable is whatever ends up in dist/, which is exactly two
source trees: the PDFs scripts/build.sh copies out of data/raw/matters, and
Vite's publicDir, copied verbatim. Keep DEPLOY_SOURCES in step with those.
(Vite's own build output — JS/CSS chunks — is orders of magnitude below the
size limit and doesn't exist until build time, so it isn't weighed here. It
does count toward the file budget below, where it is estimated rather than
measured.)

The *file count* limit is the other one, and it is worse. Pages caps a
deployment at 20,000 files (100,000 on a paid plan). Go over and wrangler
refuses the whole upload — ``Pages only supports up to 20,000 files in a
deployment`` — after the build has otherwise succeeded. Pages then keeps
serving the previous deployment, so the site does not go down; it silently
stops updating. Nothing announces this either: the Pages build runs on
Cloudflare's side in response to the push, so pipeline.yml pushes, exits green,
and every workflow stays passing while the site is frozen at whatever shipped
last.

That limit counts *files*, not bytes, which is why ~2,200 one-kilobyte party
files used to cost as much of the budget as ~2,200 large ones (they are packed
into shard buckets now — see scripts/shard.py). It is also why this check has
to account for the prerendered HTML: ``frontend/prerender.js`` writes one file
per merger, party and industry, which is over half the deployment and does not
exist until build time. Those are derived here from the same data files the
prerenderer reads, so the count can be checked on a push without running a
build.

Usage:
    python -m scripts.check_deploy_assets             # report; exit 0
    python -m scripts.check_deploy_assets --fail      # exit 1 if anything is over
    python -m scripts.check_deploy_assets --json out.json   # payload for CI
"""

import argparse
import json
import re
import sys
from pathlib import Path

from scripts.compress_pdfs import PAGES_ASSET_LIMIT, format_size

# (directory, glob) pairs that feed the deployment. See the module docstring.
DEPLOY_SOURCES = (
    ("data/raw/matters", "*.pdf"),
    ("frontend/public", "*"),
)

ISSUE_LABEL = "oversized-asset"
ISSUE_TITLE = "Files too large to deploy to Cloudflare Pages"

FILE_COUNT_LABEL = "deploy-file-count"
FILE_COUNT_TITLE = "Approaching Cloudflare Pages' file-count limit"

# Cloudflare Pages caps a deployment at this many files on the free plan
# (100,000 on a paid plan, which additionally needs PAGES_WRANGLER_MAJOR_VERSION=4
# set on the build). Exceeding it fails the upload outright.
PAGES_FILE_LIMIT = 20_000

# Report once the deployment passes this share of the limit. The point is lead
# time: at ~90 new matters a month and ~8 files each, 80% leaves well over a
# year to act, which is the difference between choosing a fix and needing one.
FILE_COUNT_WARN_RATIO = 0.8

# Files in the deployment that come from neither source tree and can't be
# counted without building: Vite's hashed JS/CSS chunks. Currently ~46; the
# allowance is rounded up because the exact number moves with code splitting and
# being a few dozen out against a 20,000 budget changes nothing.
VITE_BUILD_FILES = 60

# Prerendered pages that aren't one-per-record: frontend/prerender.js walks
# STATIC_PAGE_META (currently 12 routes, minus the root it skips) and Vite emits
# the root index.html itself. Same tolerance argument as above — this is a
# dozen files, not a thousand, so it is a constant rather than a JS parse.
PRERENDERED_STATIC_PAGES = 13

# Per-merger data files, as frontend/prerender.js matches them (MATTER_FILE_RE).
_MATTER_FILE_RE = re.compile(r"^(MN|WA)-\d+\.json$", re.IGNORECASE)


def find_oversized(root=Path("."), limit=PAGES_ASSET_LIMIT, sources=DEPLOY_SOURCES):
    """Deployable files over ``limit``, as ``(relative_path, size)``, largest first."""
    root = Path(root)
    found = {}
    for directory, pattern in sources:
        base = root / directory
        if not base.exists():
            continue
        for path in base.rglob(pattern):
            if not path.is_file():
                continue
            size = path.stat().st_size
            if size > limit:
                found[str(path.relative_to(root))] = size
    return sorted(found.items(), key=lambda kv: (-kv[1], kv[0]))


def _count_files(base, pattern="*"):
    """Number of files under ``base`` matching ``pattern``. 0 if it's missing."""
    if not base.exists():
        return 0
    return sum(1 for path in base.rglob(pattern) if path.is_file())


def count_deploy_files(root=Path("."), asset_limit=PAGES_ASSET_LIMIT):
    """Files the next deployment will contain, broken down by where they come from.

    dist/ is assembled from four things, and each is counted the way the build
    actually produces it:

    * ``pdfs`` — data/raw/matters, copied in by scripts/build.sh. Files over the
      per-asset limit are excluded, because build.sh leaves them out too.
    * ``public`` — frontend/public, which Vite copies verbatim as publicDir.
    * ``prerendered`` — one HTML file per merger, party and industry, written by
      frontend/prerender.js. Derived from the same data the prerenderer reads
      (per-merger and per-industry files, and the parties.json index, which is
      the list it filters party pages against) so this works without a build.
    * ``build`` — Vite's own hashed chunks, an allowance rather than a count.

    Returns a dict with the breakdown, the ``total``, the ``limit`` and the
    ``warn_at`` threshold.
    """
    root = Path(root)
    data_dir = root / "frontend" / "public" / "data"

    pdfs = sum(
        1
        for path in (root / "data" / "raw" / "matters").rglob("*.pdf")
        if path.is_file() and path.stat().st_size <= asset_limit
    ) if (root / "data" / "raw" / "matters").exists() else 0

    mergers = sum(
        1 for path in (data_dir / "mergers").glob("*.json")
        if _MATTER_FILE_RE.match(path.name)
    ) if (data_dir / "mergers").exists() else 0

    industries = _count_files(data_dir / "industries", "*.json")

    # prerender.js renders the parties listed in parties.json, not every record
    # in the shard buckets — ids folded into a canonical group are skipped.
    parties = 0
    try:
        index = json.loads((data_dir / "parties.json").read_text(encoding="utf-8"))
        parties = len(index.get("parties", index))
    except (OSError, ValueError, AttributeError, TypeError):
        pass

    breakdown = {
        "public": _count_files(root / "frontend" / "public"),
        "prerendered": mergers + parties + industries + PRERENDERED_STATIC_PAGES,
        "pdfs": pdfs,
        "build": VITE_BUILD_FILES,
    }
    return {
        "breakdown": breakdown,
        "prerendered_detail": {
            "mergers": mergers,
            "parties": parties,
            "industries": industries,
            "static": PRERENDERED_STATIC_PAGES,
        },
        "total": sum(breakdown.values()),
        "limit": PAGES_FILE_LIMIT,
        "warn_at": int(PAGES_FILE_LIMIT * FILE_COUNT_WARN_RATIO),
    }


def build_file_count_issue_body(counts):
    """Markdown for the file-count tracking issue."""
    total, limit = counts["total"], counts["limit"]
    over = total > limit
    pct = 100 * total / limit

    lines = [
        f"The next deployment is **{total:,} files** against Cloudflare Pages' "
        f"**{limit:,}** limit ({pct:.0f}%).",
        "",
    ]
    if over:
        lines += [
            "**This is over the limit. Deployments are failing.**",
            "",
            "Pages refuses the whole upload with `Pages only supports up to "
            f"{limit:,} files in a deployment`, after the build has otherwise "
            "succeeded. The previous deployment keeps serving, so the site is "
            "up but **frozen** — it stops picking up new pipeline data, and no "
            "workflow here goes red, because the Pages build runs on "
            "Cloudflare's side.",
        ]
    else:
        lines += [
            "Not a problem yet, and the site is deploying normally. This is "
            "lead time: going over doesn't degrade anything gracefully — Pages "
            "refuses the entire deployment and the site quietly stops updating "
            "while every workflow here stays green.",
        ]

    lines += [
        "",
        "| Source | Files |",
        "| --- | ---: |",
        f"| Prerendered HTML (`frontend/prerender.js`) | {counts['breakdown']['prerendered']:,} |",
        f"| `frontend/public/` (data JSON, icons, fonts) | {counts['breakdown']['public']:,} |",
        f"| Matter PDFs (`data/raw/matters/`) | {counts['breakdown']['pdfs']:,} |",
        f"| Vite build output (estimated) | {counts['breakdown']['build']:,} |",
        f"| **Total** | **{total:,}** |",
        "",
        "Prerendered pages break down as "
        + ", ".join(
            f"{v:,} {k}" for k, v in counts["prerendered_detail"].items()
        )
        + ".",
        "",
        "### Options",
        "",
        "- **Raise the limit.** A paid plan allows 100,000 files, but it needs "
        "`PAGES_WRANGLER_MAJOR_VERSION=4` set on the build — it is not applied "
        "automatically on upgrade, and several people have reported the 20,000 "
        "cap still being enforced without it. Verify it before relying on it.",
        "- **Generate fewer files.** Prerendered HTML is usually the largest "
        "block, at one file per merger, party and industry. Narrowing party "
        "prerendering to the pages `generate_sitemap.py` already considers "
        "worth crawling would cut it substantially — but the pages dropped fall "
        "back to serving the root `index.html`, which is the duplicate-HTML "
        "problem `prerender.js` exists to prevent, so it needs care.",
        "- **Pack small files together.** `parties/` was 2,229 one-kilobyte "
        "files before being sharded into 256 buckets (`scripts/shard.py`); the "
        "same trick applies to any per-item directory.",
        "",
        "This issue closes itself once the count is back under "
        f"{counts['warn_at']:,}.",
    ]
    return "\n".join(lines)


def build_issue_body(oversized, limit=PAGES_ASSET_LIMIT):
    """Markdown for the tracking issue."""
    lines = [
        f"{len(oversized)} file(s) in the deployment sources are over Cloudflare "
        f"Pages' {format_size(limit)} per-asset limit.",
        "",
        "These are **left out of the deployed site** by `scripts/build.sh` — the "
        "build stays green and the rest of the site ships normally, but the "
        "documents themselves aren't hosted. Requests for them are redirected to "
        "their source URL on the ACCC/Tribunal site by the Pages Function, so "
        "links still resolve; the copy under our control is just missing.",
        "",
        "| File | Size |",
        "| --- | ---: |",
    ]
    for path, size in oversized:
        # ACCC filenames are free-form and occasionally carry characters that
        # would break out of a markdown table cell or a code span.
        cell = path.replace("|", "\\|").replace("`", "'")
        lines.append(f"| `{cell}` | {format_size(size)} |")

    lines += [
        "",
        "### What to do",
        "",
        "Try compression first — it fixes most cases, and it's what the scrape "
        "workflows already run automatically:",
        "",
        "```",
        "python -m scripts.compress_pdfs",
        "```",
        "",
        "If that reports it can't get the file under the limit, it's a file "
        "whose content genuinely needs the bytes. Options are to accept the "
        "redirect-to-source behaviour (nothing to do — close this issue), or to "
        "split the document. Lowering `--target` trades quality for size if the "
        "file is close.",
        "",
        "This issue closes itself once nothing is over the limit.",
    ]
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument(
        "--limit", type=int, default=PAGES_ASSET_LIMIT,
        help="per-asset size limit in bytes (default: Cloudflare Pages' 25 MiB)",
    )
    parser.add_argument(
        "--file-limit", type=int, default=PAGES_FILE_LIMIT,
        help="per-deployment file count limit (default: Cloudflare Pages' 20,000)",
    )
    parser.add_argument(
        "--json", type=Path, metavar="PATH",
        help="write the findings and ready-to-post issue bodies to PATH",
    )
    parser.add_argument(
        "--fail", action="store_true",
        help="exit non-zero when a file is over the size limit, or when the "
             "deployment is over the file-count limit",
    )
    args = parser.parse_args(argv)

    oversized = find_oversized(args.root, args.limit)
    counts = count_deploy_files(args.root, args.limit)
    counts["limit"] = args.file_limit
    counts["warn_at"] = int(args.file_limit * FILE_COUNT_WARN_RATIO)

    over_limit = counts["total"] > counts["limit"]
    approaching = counts["total"] >= counts["warn_at"]

    if args.json:
        payload = {
            "count": len(oversized),
            "files": [{"path": p, "size": s} for p, s in oversized],
            "title": ISSUE_TITLE,
            "body": build_issue_body(oversized, args.limit) if oversized else "",
            "file_count": {
                **counts,
                "over_limit": over_limit,
                "approaching": approaching,
                "title": FILE_COUNT_TITLE,
                "body": build_file_count_issue_body(counts) if approaching else "",
            },
        }
        args.json.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    # --- file count ---------------------------------------------------------
    pct = 100 * counts["total"] / counts["limit"]
    summary = (
        f"{counts['total']:,} files in the next deployment "
        f"({pct:.0f}% of the {counts['limit']:,} limit) — "
        + ", ".join(f"{v:,} {k}" for k, v in counts["breakdown"].items())
    )
    if over_limit:
        print(
            f"OVER THE FILE LIMIT: {summary}\n"
            "Pages will refuse the whole deployment and keep serving the "
            "previous one — the site will silently stop updating.",
            file=sys.stderr,
        )
    elif approaching:
        print(
            f"Approaching the file limit: {summary}\n"
            f"Going over means Pages refuses the entire deployment, not just "
            f"the excess. See the tracking issue for options.",
            file=sys.stderr,
        )
    else:
        print(summary)

    # --- oversized files ----------------------------------------------------
    if oversized:
        print(
            f"{len(oversized)} file(s) over {format_size(args.limit)} — these will be "
            f"left out of the deployment:",
            file=sys.stderr,
        )
        for path, size in oversized:
            print(f"  {path} ({format_size(size)})", file=sys.stderr)
        print("Run `python -m scripts.compress_pdfs` to try to shrink them.", file=sys.stderr)
    else:
        print(f"No deployable files over {format_size(args.limit)}")

    # Merely approaching the file limit is a heads-up, not a failure — the site
    # is deploying fine. Being over it is not: deployments are already broken.
    if args.fail and (oversized or over_limit):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
