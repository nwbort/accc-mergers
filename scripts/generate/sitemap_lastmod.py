"""Pinned sitemap ``lastmod`` dates for hand-edited static pages.

Most static routes are views over data the pipeline regenerates every run, so
``generate_sitemap.py`` stamps them with today's date. A handful are not: the
commentary, author, privacy and copyright pages only change when someone edits
them, and re-dating them on every run tells crawlers they changed when they
didn't. Those pages keep a pinned date in ``sitemap_lastmod.json``, alongside
the files whose edits count as a change to the page.

The date moves via the git pre-commit hook (``.githooks/pre-commit``), which
runs this module with ``--staged``: when a commit touches one of a page's
source files, the page's date becomes today, ``sitemap.xml`` is patched to
match, and both files are added to the commit.
"""

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone

from scripts.paths import REPO_ROOT

LASTMOD_JSON = REPO_ROOT / "scripts" / "generate" / "sitemap_lastmod.json"
SITEMAP_XML = REPO_ROOT / "frontend" / "public" / "sitemap.xml"
BASE_URL = "https://mergers.fyi"


def load_pinned() -> dict:
    """Return ``{path: {"sources": [...], "lastmod": "YYYY-MM-DD"}}``."""
    return json.loads(LASTMOD_JSON.read_text(encoding="utf-8"))


def pinned_lastmods() -> dict[str, str]:
    """Return ``{path: lastmod}`` for every pinned page."""
    return {path: page["lastmod"] for path, page in load_pinned().items()}


def touched_pages(pinned: dict, changed_files: set[str]) -> list[str]:
    """Return the pinned page paths with a source file in ``changed_files``."""
    return [
        path for path, page in pinned.items()
        if changed_files.intersection(page["sources"])
    ]


def patch_sitemap(xml: str, lastmods: dict[str, str]) -> str:
    """Rewrite the ``<lastmod>`` of each given page in a sitemap document."""
    for path, lastmod in lastmods.items():
        loc = re.escape(f"<loc>{BASE_URL}{path}</loc>")
        xml = re.sub(
            rf"({loc}\s*<lastmod>)[^<]*(</lastmod>)",
            rf"\g<1>{lastmod}\g<2>",
            xml,
        )
    return xml


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=REPO_ROOT, check=True,
        capture_output=True, text=True,
    ).stdout


def update_staged() -> list[str]:
    """Bump the pinned date of every page whose sources are staged.

    Returns the bumped page paths. ``sitemap.xml`` is only patched when it has
    no unstaged edits of its own, so the hook never stages work it didn't
    write; the pipeline regenerates it from the JSON either way.
    """
    staged = set(_git("diff", "--cached", "--name-only").split("\n")) - {""}
    pinned = load_pinned()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    bumped = [
        path for path in touched_pages(pinned, staged)
        if pinned[path]["lastmod"] != today
    ]
    if not bumped:
        return []

    for path in bumped:
        pinned[path]["lastmod"] = today
    LASTMOD_JSON.write_text(json.dumps(pinned, indent=2) + "\n", encoding="utf-8")
    to_add = [str(LASTMOD_JSON.relative_to(REPO_ROOT))]

    sitemap_rel = str(SITEMAP_XML.relative_to(REPO_ROOT))
    if SITEMAP_XML.exists() and not _git("diff", "--name-only", "--", sitemap_rel).strip():
        xml = SITEMAP_XML.read_text(encoding="utf-8")
        SITEMAP_XML.write_text(
            patch_sitemap(xml, {path: today for path in bumped}), encoding="utf-8",
        )
        to_add.append(sitemap_rel)

    _git("add", "--", *to_add)
    return bumped


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--staged", action="store_true",
        help="bump pages whose source files are staged (the pre-commit hook)",
    )
    args = parser.parse_args()
    if not args.staged:
        parser.error("nothing to do without --staged")
    for path in update_staged():
        print(f"sitemap: {path} lastmod set to today", file=sys.stderr)


if __name__ == "__main__":
    main()
