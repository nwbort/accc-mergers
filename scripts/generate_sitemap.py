#!/usr/bin/env python3
"""
Generate sitemap.xml for mergers.fyi.

Reads merger data from the frontend public data directory and writes
a sitemap covering all static pages and individual merger detail pages.

Output: merger-tracker/frontend/public/sitemap.xml
"""

import json
from datetime import datetime, timezone
from pathlib import Path


BASE_URL = "https://mergers.fyi"
REPO_ROOT = Path(__file__).parent.parent
MERGERS_JSON = REPO_ROOT / "merger-tracker" / "frontend" / "public" / "data" / "mergers.json"
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
]

STATIC_COMMENTS = {
    "/":            "Homepage / Dashboard",
    "/mergers":     "All Mergers Page",
    "/timeline":    "Timeline Page",
    "/industries":  "Industries Page",
    "/commentary":  "Commentary Page",
    "/digest":      "Digest Page",
    "/nick-twort":  "About / Author Page",
}


def load_mergers():
    with open(MERGERS_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data["mergers"] if isinstance(data, dict) else data


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
            loc=f"{BASE_URL}{page['path']}",
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
            loc=f"{BASE_URL}/mergers/{merger_id}",
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
