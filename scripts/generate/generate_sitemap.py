#!/usr/bin/env python3
"""
Generate sitemap.xml for mergers.fyi.

Lists every merger detail page plus the static SPA routes, for search
engine crawlers.

Sitemap policy — mergers: unlike the weekly digest and RSS feed — which
exclude suspended assessments via :func:`merger_filters.filter_active` —
this generator does NOT apply any filter to merger pages. The detail page
``/mergers/<id>`` is publicly served for every merger, including waivers
*and* suspended mergers, and removing those URLs from the sitemap would
hurt discoverability without affecting what the site actually renders.

Sitemap policy — parties and industries: these ARE filtered, because the
pipeline generates a page for every party appearance and every ANZSIC node
whether or not there is anything on it. Listing all of them spends crawl
budget on ~1,800 single-merger shelf companies and ~290 empty ANZSIC nodes
at the expense of the merger pages that matter. Included are:

* every hand-declared canonical party group in ``related_parties.json``
  (curated, so notable by definition, even at one merger); plus
* every synthesised party with two or more mergers — repeat acquirers that
  simply have not been grouped by hand yet, and the exact candidates
  ``detect_related_parties.py`` surfaces for grouping; plus
* every ANZSIC node with at least one merger somewhere in its subtree.

Excluded pages are still built, prerendered with their own title/canonical
by ``frontend/prerender.js``, linked from merger detail
pages and served normally — they are simply not advertised for crawling.
They are deliberately NOT ``noindex``: each is a factually distinct record
and can still answer a long-tail "was <company> acquired" query.

Output: frontend/public/sitemap.xml
"""

from datetime import datetime, timezone
from xml.sax.saxutils import escape

from scripts.merger_filters import load_mergers
from scripts.slug import industry_path, merger_path, party_path
from scripts.generate.static_data import anzsic
from scripts.generate.static_data.loaders import load_related_parties
from scripts.generate.static_data.outputs.parties import build_party_pages
from scripts.paths import REPO_ROOT


BASE_URL = "https://mergers.fyi"
SITEMAP_OUT = REPO_ROOT / "frontend" / "public" / "sitemap.xml"

TODAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")

STATIC_PAGES = [
    {"path": "/",            "changefreq": "daily",   "priority": "1.0"},
    {"path": "/mergers",     "changefreq": "daily",   "priority": "0.9"},
    {"path": "/timeline",    "changefreq": "daily",   "priority": "0.8"},
    {"path": "/industries",  "changefreq": "weekly",  "priority": "0.8"},
    {"path": "/parties",     "changefreq": "weekly",  "priority": "0.8"},
    {"path": "/analysis",    "changefreq": "weekly",  "priority": "0.7"},
    {"path": "/phase-2",     "changefreq": "daily",   "priority": "0.7"},
    {"path": "/refiled-notifications", "changefreq": "daily", "priority": "0.6"},
    {"path": "/extensions",  "changefreq": "daily",   "priority": "0.6"},
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
    "/parties":     "Parties Page",
    "/analysis":    "Analysis Page",
    "/phase-2":     "Phase 2 Tracker Page",
    "/refiled-notifications": "Refiled Notifications Page",
    "/extensions":  "Phase 1 Extensions Page",
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


def industry_codes_with_mergers(mergers):
    """Return the set of ANZSIC codes with at least one merger in their subtree.

    A merger counts towards every code it is tagged with *and* all of that
    code's ancestors, so a division is included whenever anything beneath it
    has activity. Deliberately independent of ``page_modified_datetime`` (which
    :func:`industry_lastmods` keys on) so an industry with mergers but no
    timestamps is still listed.
    """
    codes = set()
    for merger in mergers:
        for entry in merger.get("anzsic_codes", []) or []:
            code = entry.get("code")
            if not code:
                continue
            codes.add(code)
            codes.update(ancestor.code for ancestor in anzsic.ancestors(code))
    return codes


def group_merger_count(group):
    """Distinct mergers on a party page, counted across all three roles."""
    return len({
        merger_id
        for role_mergers in group["mergers_by_role"].values()
        for merger_id in role_mergers
    })


def sitemap_party_groups(party_groups, related_parties):
    """Filter party pages down to the ones worth advertising for crawling.

    Keeps hand-declared canonical groups plus any synthesised group with two
    or more mergers — see the module docstring for the reasoning.
    """
    canonical_ids = {g.get("id") for g in related_parties if g.get("id")}
    return [
        g for g in party_groups
        if g["id"] in canonical_ids or group_merger_count(g) >= 2
    ]


def party_lastmods(party_groups):
    """Return ``{party_id: latest_page_modified_datetime}`` across each group's mergers."""
    latest = {}
    for group in party_groups:
        raw_values = [
            m.get("page_modified_datetime", "")
            for role_mergers in group["mergers_by_role"].values()
            for m in role_mergers.values()
        ]
        raw_values = [r for r in raw_values if r]
        if raw_values:
            latest[group["id"]] = max(raw_values)
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


def generate_sitemap(mergers, party_groups, related_parties):
    listed_party_groups = sitemap_party_groups(party_groups, related_parties)
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

    lines.append("  <!-- Industry Detail Pages (ANZSIC nodes with merger activity) -->")
    industry_latest = industry_lastmods(mergers)
    # Only nodes with mergers in their subtree; empty nodes are built and
    # served, just not advertised. Tagged codes outside the known tree are
    # included by the same rule.
    all_codes = industry_codes_with_mergers(mergers)
    for code in sorted(all_codes):
        raw = industry_latest.get(code)
        # Append the readable slug derived from the ANZSIC name, matching what
        # the SPA renders and links to. Codes tagged outside the known tree have
        # no node (and so no name) and fall back to the bare /industries/{code}.
        node = anzsic.get(code)
        path = industry_path(code, node.name if node else "")
        lines.append(url_entry(
            loc=escape(f"{BASE_URL}{path}"),
            lastmod=_format_lastmod(raw) if raw else TODAY,
            changefreq="weekly",
            priority="0.5",
        ))
    lines.append("")

    lines.append("  <!-- Party Pages (canonical groups + repeat parties) -->")
    party_latest = party_lastmods(party_groups)
    for group in sorted(listed_party_groups, key=lambda g: g["id"]):
        path = party_path(group["id"], group["canonical_name"])
        raw = party_latest.get(group["id"])
        lines.append(url_entry(
            loc=escape(f"{BASE_URL}{path}"),
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
    related_parties = load_related_parties()
    party_groups = build_party_pages(mergers, related_parties)
    sitemap = generate_sitemap(mergers, party_groups, related_parties)
    SITEMAP_OUT.write_text(sitemap, encoding="utf-8")
    industry_count = len(industry_codes_with_mergers(mergers))
    listed_parties = len(sitemap_party_groups(party_groups, related_parties))
    print(
        f"Wrote sitemap with {len(STATIC_PAGES)} static pages, "
        f"{industry_count} industry pages, "
        f"{listed_parties} of {len(party_groups)} party pages "
        f"and {len(mergers)} merger pages -> {SITEMAP_OUT}"
    )


if __name__ == "__main__":
    main()
