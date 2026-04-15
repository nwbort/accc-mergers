#!/usr/bin/env python3
"""
Generate sitemap.xml for mergers.fyi.

Lists every merger detail page plus the static SPA routes, for search
engine crawlers.

Sitemap policy: unlike the weekly digest and RSS feed — which exclude
waivers and suspended assessments via
:func:`merger_filters.filter_public` — this generator does NOT apply that
filter. The detail page ``/mergers/<id>`` is publicly served for every
merger (including waivers), and removing those URLs from the sitemap
would hurt discoverability without affecting what the site actually
renders.

Output: merger-tracker/frontend/public/sitemap.xml
"""

from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape

from merger_filters import load_mergers


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
    raw = merger.get("page_modified_datetime", "")
    if not raw:
        return TODAY
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        return raw[:10] if len(raw) >= 10 else TODAY


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

    lines.append("  <!-- Individual Merger Detail Pages -->")
    for merger in mergers:
        merger_id = merger.get("merger_id")
        if not merger_id:
            continue
        lines.append(url_entry(
            loc=escape(f"{BASE_URL}/mergers/{merger_id}"),
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
    print(f"Wrote sitemap with {len(STATIC_PAGES)} static pages and {len(mergers)} merger pages -> {SITEMAP_OUT}")


if __name__ == "__main__":
    main()
