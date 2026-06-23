#!/usr/bin/env python3
"""
Generate sitemap.xml for mergers.fyi.

Lists every merger detail page plus the static SPA routes, for search
engine crawlers.

Sitemap policy: unlike the weekly digest and RSS feed — which exclude
suspended assessments via :func:`merger_filters.filter_active` — this
generator does NOT apply any filter. The detail page ``/mergers/<id>``
is publicly served for every merger, including waivers *and* suspended
mergers, and removing those URLs from the sitemap would hurt
discoverability without affecting what the site actually renders.

Output: merger-tracker/frontend/public/sitemap.xml
"""

from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape

from merger_filters import load_mergers
from slug import merger_path
from static_data import anzsic


BASE_URL = "https://mergers.fyi"
REPO_ROOT = Path(__file__).parent.parent
SITEMAP_OUT = REPO_ROOT / "merger-tracker" / "frontend" / "public" / "sitemap.xml"

TODAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")

STATIC_PAGES = [
    {"path": "/",            "changefreq": "daily",   "priority": "1.0"},
    {"path": "/mergers",     "changefreq": "daily",   "priority": "0.9"},
    {"path": "/timeline",    "changefreq": "daily",   "priority": "0.8"},
    {"path": "/industries",  "changefreq": "weekly",  "priority": "0.8"},
    {"path": "/commentary",  "changefreq": "weekly",  "priority": "0.7"},
    {"path": "/digest",      "changefreq": "weekly",  "priority": "0.7"},
    {"path": "/nick-twort",  "changefreq": "monthly", "priority": "0.8"},
    {"path": "/privacy",     "changefreq": "monthly", "priority": "0.8"},
]

STATIC_COMMENTS = {
    "/":            "Homepage / Dashboard",
    "/mergers":     "All Mergers Page",
    "/timeline":    "Timeline Page",
    "/industries":  "Industries Page",
    "/commentary":  "Commentary Page",
    "/digest":      "Digest Page",
    "/nick-twort":  "About / Author Page",
    "/privacy":     "Privacy Policy",
}


def lastmod_for(merger):
    return _format_lastmod(merger.get("page_modified_datetime", ""))


def _format_lastmod(raw):
    if not raw:
        return TODAY
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        return raw[:10] if len(raw) >= 10 else TODAY


def industry_lastmods(mergers):
    """Return ``{anzsic_code: latest_page_modified_datetime}`` for every node.

    A page exists for every ANZSIC node (division → class). A merger's modified
    time rolls up to its node *and* that node's ancestors, so a parent page's
    lastmod reflects the most recent activity anywhere in its subtree. Nodes
    with no merger activity are omitted here and fall back to ``TODAY``.
    """
    latest = {}

    def bump(code, raw):
        if raw and (code not in latest or raw > latest[code]):
            latest[code] = raw

    for merger in mergers:
        raw = merger.get("page_modified_datetime", "")
        for entry in merger.get("anzsic_codes", []) or []:
            code = entry.get("code")
            if not code:
                continue
            bump(code, raw)
            for ancestor in anzsic.ancestors(code):
                bump(ancestor.code, raw)
    return latest


def url_entry(loc, lastmod, changefreq, priority):
    return (
        f"  <url>\n"
        f"    <loc>{loc}</loc>\n"
        f"    <lastmod>{lastmod}</lastmod>\n"
        f"    <changefreq>{changefreq}</changefreq>\n"
        f"    <priority>{priority}</priority>\n"
        f"  </url>"
    )


def generate_sitemap(mergers):
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]

    for page in STATIC_PAGES:
        comment = STATIC_COMMENTS.get(page["path"])
        if comment:
            lines.append(f"  <!-- {comment} -->")
        lines.append(url_entry(
            loc=escape(f"{BASE_URL}{page['path']}"),
            lastmod=TODAY,
            changefreq=page["changefreq"],
            priority=page["priority"],
        ))
        lines.append("")

    lines.append("  <!-- Individual Industry Detail Pages (full ANZSIC tree) -->")
    industry_latest = industry_lastmods(mergers)
    # One URL per ANZSIC node, plus any tagged codes outside the tree.
    all_codes = set(anzsic.hierarchy()) | set(industry_latest)
    for code in sorted(all_codes):
        raw = industry_latest.get(code)
        lines.append(url_entry(
            loc=escape(f"{BASE_URL}/industries/{code}"),
            lastmod=_format_lastmod(raw) if raw else TODAY,
            changefreq="weekly",
            priority="0.5",
        ))
    lines.append("")

    lines.append("  <!-- Individual Merger Detail Pages -->")
    for merger in mergers:
        merger_id = merger.get("merger_id")
        if not merger_id:
            continue
        path = merger_path(merger_id, merger.get("merger_name", ""))
        lines.append(url_entry(
            loc=escape(f"{BASE_URL}{path}"),
            lastmod=lastmod_for(merger),
            changefreq="weekly",
            priority="0.6",
        ))

    lines.append("</urlset>")
    return "\n".join(lines) + "\n"


def main():
    mergers = load_mergers()
    sitemap = generate_sitemap(mergers)
    SITEMAP_OUT.write_text(sitemap, encoding="utf-8")
    industry_count = len(set(anzsic.hierarchy()) | set(industry_lastmods(mergers)))
    print(
        f"Wrote sitemap with {len(STATIC_PAGES)} static pages, "
        f"{industry_count} industry pages and {len(mergers)} merger pages "
        f"-> {SITEMAP_OUT}"
    )


if __name__ == "__main__":
    main()
