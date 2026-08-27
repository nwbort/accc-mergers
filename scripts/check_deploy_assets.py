#!/usr/bin/env python3
"""Report files that are too big for Cloudflare Pages to deploy.

This is the safety net behind scripts/compress_pdfs.py. Compression runs in the
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
limit and doesn't exist until build time, so it isn't checked here.)

Usage:
    python -m scripts.check_deploy_assets             # report; exit 0
    python -m scripts.check_deploy_assets --fail      # exit 1 if anything is over
    python -m scripts.check_deploy_assets --json out.json   # payload for CI
"""

import argparse
import json
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
        "--json", type=Path, metavar="PATH",
        help="write the findings and a ready-to-post issue body to PATH",
    )
    parser.add_argument(
        "--fail", action="store_true",
        help="exit non-zero when a file is over the limit",
    )
    args = parser.parse_args(argv)

    oversized = find_oversized(args.root, args.limit)

    if args.json:
        payload = {
            "count": len(oversized),
            "files": [{"path": p, "size": s} for p, s in oversized],
            "title": ISSUE_TITLE,
            "body": build_issue_body(oversized, args.limit) if oversized else "",
        }
        args.json.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    if not oversized:
        print(f"No deployable files over {format_size(args.limit)}")
        return 0

    print(
        f"{len(oversized)} file(s) over {format_size(args.limit)} — these will be "
        f"left out of the deployment:",
        file=sys.stderr,
    )
    for path, size in oversized:
        print(f"  {path} ({format_size(size)})", file=sys.stderr)
    print("Run `python -m scripts.compress_pdfs` to try to shrink them.", file=sys.stderr)

    return 1 if args.fail else 0


if __name__ == "__main__":
    sys.exit(main())
