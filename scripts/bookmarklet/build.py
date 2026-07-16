#!/usr/bin/env python3
"""Build the installable tribunal-scrape bookmarklet from its JS source.

``scrape_tribunal_page.js`` is the single source of truth (hand-edited,
readable, commented). This script turns it into the two things a browser
actually needs:

  * ``bookmarklet.txt``  the ``javascript:...`` URI, for pasting straight
    into a new bookmark's URL field; and
  * ``install.html``     a plain HTML page with a draggable link carrying
    that same URI, for the "drag this to your bookmarks bar" install path.

Only full-line ``//`` comments and blank lines are stripped before encoding
(no other minification) — safe here because the source deliberately avoids
trailing end-of-line comments, and it keeps the output easy to eyeball
against the source if something looks wrong.

Run this after editing ``scrape_tribunal_page.js``:

    python scripts/bookmarklet/build.py

and commit the regenerated ``bookmarklet.txt`` / ``install.html`` alongside
the source change.
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import quote

BOOKMARKLET_DIR = Path(__file__).parent
SOURCE_JS = BOOKMARKLET_DIR / "scrape_tribunal_page.js"
BOOKMARKLET_TXT = BOOKMARKLET_DIR / "bookmarklet.txt"
INSTALL_HTML = BOOKMARKLET_DIR / "install.html"

BOOKMARK_NAME = "Scrape tribunal page"

# Matches JS's encodeURIComponent(), which additionally leaves !'()* unescaped
# on top of Python's own always-safe set (letters, digits, "_.-~").
_ENCODE_URI_COMPONENT_SAFE = "!'()*"


def _strip_comments(source: str) -> str:
    lines = [
        line for line in source.splitlines()
        if not line.strip().startswith("//")
        and line.strip() != ""
    ]
    return "\n".join(lines)


def build_bookmarklet_uri() -> str:
    source = SOURCE_JS.read_text(encoding="utf-8")
    minified = _strip_comments(source)
    return "javascript:" + quote(minified, safe=_ENCODE_URI_COMPONENT_SAFE)


def build_install_html(uri: str) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Install: {BOOKMARK_NAME}</title>
<style>
  body {{ font: 16px/1.5 -apple-system, BlinkMacSystemFont, sans-serif; max-width: 40em; margin: 3em auto; padding: 0 1em; }}
  .bookmarklet {{ display: inline-block; padding: 0.6em 1.2em; background: #2d5e2d; color: #fff; text-decoration: none; border-radius: 6px; font-weight: 600; }}
  .bookmarklet:hover {{ background: #244b24; }}
  code {{ background: #f0f0f0; padding: 0.1em 0.4em; border-radius: 3px; }}
</style>
</head>
<body>
<h1>{BOOKMARK_NAME}</h1>
<p>Drag this link to your bookmarks bar (not click it):</p>
<p><a class="bookmarklet" href="{uri}">{BOOKMARK_NAME}</a></p>
<p>Then, on a tribunal matter page (e.g. a page under
<code>competitiontribunal.gov.au/current-matters/...</code>), click the
bookmark. It downloads a JSON snapshot of that page's document table(s).
Feed that file to <code>scripts/ingest_tribunal_snapshot.py</code> — see
<code>scripts/bookmarklet/README.md</code>.</p>
<p>If your browser won't let you drag it (some strip <code>javascript:</code>
links), create a new bookmark by hand and paste the contents of
<code>bookmarklet.txt</code> in this directory as its URL instead.</p>
</body>
</html>
"""


def main() -> int:
    uri = build_bookmarklet_uri()
    BOOKMARKLET_TXT.write_text(uri + "\n", encoding="utf-8")
    INSTALL_HTML.write_text(build_install_html(uri), encoding="utf-8")
    print(f"Wrote {BOOKMARKLET_TXT} ({len(uri)} chars)")
    print(f"Wrote {INSTALL_HTML}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
