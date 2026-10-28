"""Fetch and parse a Federal Court file on the Commonwealth Courts Portal.

Ported from nwbort/scrape-fed's ``portal.py``; used by
:mod:`scripts.scrape.scrape_federal_court`, which keeps
``data/processed/judicial_reviews.json`` in step with the portal.

The portal isn't behind Cloudflare: every page is plain server-rendered HTML,
so this uses urllib only. A file's public pages are:

    /file/Federal/P/NSD1310/2026/actions          file details + applications
    /file/Federal/P/NSD1310/2026/<app>/events_and_orders
    /file/Federal/P/NSD1310/2026/<app>/event/<event>/outcomes
    /file/Federal/P/NSD1310/2026/<app>/documents_filed
    /file/Federal/P/NSD1310/2026/<app>/parties
    /file/Federal/P/NSD1310/2026/<app>/party_contact/<id>
    /file/Federal/P/NSD1310/2026/<app>/event/<event>/document/<doc>   (orders PDF)

The actions page lists the file's applications (the originating application
and any interlocutory ones) as expandable rows; the other pages are the HTML
fragments the portal loads into them when a row is expanded.

Judgments are linked as javascript:openFCAJudgment('2026', 'FCA', '1000'),
which opens the judgment on judgments.fedcourt.gov.au; see judgment_link().

Run standalone to print a file as JSON without saving anything::

    python -m scripts.scrape.comcourts_portal NSD1310/2026
    python -m scripts.scrape.comcourts_portal https://www.comcourts.gov.au/file/Federal/P/nsd1310/2026/actions
"""

from __future__ import annotations

import json
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from html import unescape
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

BASE_URL = "https://www.comcourts.gov.au"
USER_AGENT = "Mozilla/5.0 (compatible; mergers-fyi/1.0; +https://mergers.fyi)"
REQUEST_TIMEOUT = 60
# Pause between requests so a file with many applications doesn't hammer the
# portal.
REQUEST_DELAY_SECONDS = 0.5
FETCH_ATTEMPTS = 3
FETCH_RETRY_SECONDS = 5

JUDGMENTS_BASE = "https://www.judgments.fedcourt.gov.au/judgments/Judgments"
# openFCAJudgment()'s court codes and where each one's judgments live.
JUDGMENT_PATHS = {"fca": "fca/single", "fcafc": "fca/full"}

_FILE_RE = re.compile(
    r"(?:/file/)?(?:(?P<court>[A-Za-z]+)/(?P<kind>[A-Za-z]+)/)?"
    r"(?P<number>[A-Za-z]+\d+)/(?P<year>\d{4})",
)


class FetchError(Exception):
    pass


# --- Helpers -----------------------------------------------------------------


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", unescape(text).replace("\xa0", " ")).strip()


def normalize_date(text: str) -> str:
    """'27-Aug-2026' -> '2026-08-27'; leave unrecognised text untouched."""
    text = clean(text)
    for fmt in ("%d-%b-%Y", "%d %B %Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return text


def parse_file_ref(text: str) -> dict:
    """'NSD1310/2026', 'Federal/P/NSD1310/2026' or a portal URL ->
    {'court': 'Federal', 'kind': 'P', 'number': 'NSD1310', 'year': '2026'}."""
    path = urlparse(text).path if "://" in text else text
    m = _FILE_RE.search(path.strip())
    if not m:
        raise ValueError(f"not a file number or portal URL: {text!r}")
    return {
        "court": m.group("court") or "Federal",
        "kind": (m.group("kind") or "P").upper(),
        "number": m.group("number").upper(),
        "year": m.group("year"),
    }


def file_slug(ref: dict) -> str:
    """Directory name for a file: 'nsd1310-2026'."""
    return f"{ref['number']}-{ref['year']}".lower()


def file_base_url(ref: dict) -> str:
    return f"{BASE_URL}/file/{ref['court']}/{ref['kind']}/{ref['number']}/{ref['year']}"


def judgment_link(year: str, court: str, number: str) -> dict:
    """The judgment openFCAJudgment(year, court, number) would open.

    Returns {'citation': '[2026] FCA 1000', 'url': ...}; 'url' is left out
    for a court code the portal's script doesn't know either."""
    court = court.strip()
    out = {"citation": f"[{year}] {court.upper()} {int(number)}"}
    path = JUDGMENT_PATHS.get(court.lower())
    if path:
        out["url"] = f"{JUDGMENTS_BASE}/{path}/{year}/{year}{court.lower()}{int(number):04d}"
    return out


# --- HTTP --------------------------------------------------------------------


class Session:
    """urllib with the portal's session cookie carried between requests."""

    def __init__(self):
        self.cookies: dict[str, str] = {}
        self._last = 0.0

    def get(self, url: str) -> tuple[bytes, dict]:
        """GET url, returning (body, headers). Redirects aren't followed: the
        portal answers anything it won't show the public with a 302 to its
        login page, which is an error here, not content."""
        last_error = None
        for attempt in range(1, FETCH_ATTEMPTS + 1):
            wait = self._last + REQUEST_DELAY_SECONDS - time.time()
            if wait > 0:
                time.sleep(wait)
            try:
                return self._get_once(url)
            except FetchError:
                raise
            except Exception as e:
                last_error = e
                print(f"  GET {url} failed (attempt {attempt}/{FETCH_ATTEMPTS}): {e}", flush=True)
                if attempt < FETCH_ATTEMPTS:
                    time.sleep(FETCH_RETRY_SECONDS)
            finally:
                self._last = time.time()
        raise FetchError(f"GET {url} failed: {last_error}")

    def _get_once(self, url: str) -> tuple[bytes, dict]:
        headers = {"User-Agent": USER_AGENT}
        if self.cookies:
            headers["Cookie"] = "; ".join(f"{k}={v}" for k, v in self.cookies.items())
        req = urllib.request.Request(url, headers=headers)
        opener = urllib.request.build_opener(_NoRedirect)
        try:
            r = opener.open(req, timeout=REQUEST_TIMEOUT)
        except urllib.error.HTTPError as e:
            if e.code in (301, 302, 303, 307, 308):
                raise FetchError(f"{url} redirects to {e.headers.get('Location')}")
            if e.code in (404, 410):
                raise FetchError(f"{url}: HTTP {e.code}")
            raise
        with r:
            for cookie in r.headers.get_all("Set-Cookie") or []:
                name, _, value = cookie.split(";", 1)[0].partition("=")
                self.cookies[name.strip()] = value.strip()
            return r.read(), dict(r.headers)

    def get_html(self, url: str) -> str:
        data, _ = self.get(url)
        return data.decode("utf-8", "replace")


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


# --- HTML tables -------------------------------------------------------------


class _TableParser(HTMLParser):
    """Collect every table row on a page as
    {'class': ..., 'cells': [{'text', 'links', 'onclick', 'header'}]}.

    'links' is [(href, text)] for each link in the cell. Nested tables aren't
    used by any of the fragments, so they aren't handled."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows: list[dict] = []
        self._row: dict | None = None
        self._cell: dict | None = None
        self._text: list[str] = []
        self._link: list | None = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "tr":
            self._row = {"class": attrs.get("class") or "", "onclick": attrs.get("onclick") or "", "cells": []}
        elif tag in ("td", "th") and self._row is not None:
            self._cell = {
                "text": "",
                "links": [],
                "onclick": attrs.get("onclick") or "",
                "header": tag == "th",
            }
            self._text = []
        elif tag == "br" and self._cell is not None:
            self._text.append("\n")
        elif tag == "a" and self._cell is not None:
            self._link = [attrs.get("href") or "", []]

    def handle_endtag(self, tag):
        if tag == "a" and self._link is not None and self._cell is not None:
            self._cell["links"].append((self._link[0], clean("".join(self._link[1]))))
            self._link = None
        elif tag in ("td", "th") and self._cell is not None:
            self._cell["text"] = clean("".join(self._text))
            self._row["cells"].append(self._cell)
            self._cell = None
        elif tag == "tr" and self._row is not None:
            self._row["cells"] and self.rows.append(self._row)
            self._row = None

    def handle_data(self, data):
        if self._cell is not None:
            self._text.append(data)
            if self._link is not None:
                self._link[1].append(data)


def table_rows(html: str) -> list[dict]:
    parser = _TableParser()
    parser.feed(html)
    return parser.rows


def _data_rows(html: str) -> list[list[dict]]:
    """Rows with no header cells, as lists of cells."""
    return [r["cells"] for r in table_rows(html) if not any(c["header"] for c in r["cells"])]


# --- Page parsers ------------------------------------------------------------


def parse_file_details(html: str) -> dict:
    """The 'File details' table: Court, Number, Title, Filing Date, ..."""
    m = re.search(r'<table class="lhs-header-table".*?</table>', html, re.S)
    if not m:
        return {}
    details = {}
    for row in table_rows(m.group(0)):
        cells = row["cells"]
        if len(cells) >= 2 and cells[0]["header"]:
            key = re.sub(r"\W+", "_", cells[0]["text"].rstrip(":").strip().lower()).strip("_")
            value = cells[1]["text"]
            details[key] = normalize_date(value) if key.endswith("date") else value
    return details


def _div_text(block: str, cls: str) -> list[str]:
    return [
        clean(re.sub(r"<[^>]+>", " ", t))
        for t in re.findall(rf'<div class="{cls}[^"]*">(.*?)</div>', block, re.S)
    ]


def parse_applications(html: str, page_url: str = BASE_URL) -> list[dict]:
    """The 'Existing applications' rows on the actions page.

    Each row is a <div id="coa-N"> header (title, type, filed, status,
    finalised) followed by <div id="coa-details-N"> holding the URLs of its
    events, documents and parties fragments."""
    apps = []
    starts = [m for m in re.finditer(r'<div id="coa-(\d+)"([^>]*)>', html)]
    for i, m in enumerate(starts):
        n = m.group(1)
        end = starts[i + 1].start() if i + 1 < len(starts) else len(html)
        block = html[m.start():end]
        header, _, details = block.partition(f'id="coa-details-{n}"')
        level = re.search(r"coa-level(\d+)", m.group(2))
        title = re.search(r"<h3[^>]*>(.*?)</h3>", header, re.S)
        dates = _div_text(header, "col_date")
        app = {
            "title": clean(re.sub(r"<[^>]+>", " ", title.group(1))) if title else "",
            "type": (_div_text(header, "col_type") or [""])[0],
            "filed": normalize_date(dates[0]) if dates else "",
            "status": (_div_text(header, "col_status") or [""])[0],
            "finalised": normalize_date(dates[1]) if len(dates) > 1 else "",
        }
        if level:
            app["level"] = int(level.group(1))
        for kind, url in re.findall(r"showHideDetails\(\s*'?\w+'?\s*,\s*'coa-([\w-]+)'\s*,\s*'([^']+)'", details):
            app.setdefault("_urls", {})[kind] = urljoin(page_url, unescape(url))
        url = app.get("_urls", {}).get("events-and-orders") or next(iter(app.get("_urls", {}).values()), "")
        idm = re.search(r"/(\d+)/[a-z_]+$", url)
        app["id"] = idm.group(1) if idm else n
        apps.append(app)
    return apps


_ONCLICK_URL_RE = re.compile(r"showHideDetails\([^)]*?'(/file/[^']+)'")
_JUDGMENT_JS_RE = re.compile(r"openFCAJudgment\(\s*'(\d{4})'\s*,\s*'(\w+)'\s*,\s*'(\d+)'\s*\)")


def parse_events(html: str, page_url: str = BASE_URL) -> list[dict]:
    """The 'Court Events and Orders' table, one dict per listing.

    Columns: [details] [spinner] Date | Time | Reason | Presiding Officer(s)
    | Location | Outcome | Orders. A court event can span several listings
    (an adjournment and the day judgment is delivered, say); they share an
    event_id, and the event's outcomes (order and decision types) are behind
    the 'Details' expander on its first row."""
    events = []
    for row in table_rows(html):
        cells = row["cells"]
        if len(cells) < 9 or any(c["header"] for c in cells):
            continue
        date = normalize_date(cells[2]["text"])
        if not re.match(r"\d{4}-\d{2}-\d{2}$", date):
            continue
        onclick = next((c["onclick"] for c in cells if c["onclick"]), "")
        outcomes_url = _ONCLICK_URL_RE.search(unescape(onclick))
        event = {
            "date": date,
            "time": cells[3]["text"],
            "reason": cells[4]["text"],
            "presiding": cells[5]["text"],
            "location": cells[6]["text"],
            "outcome": cells[7]["text"],
        }
        if outcomes_url:
            idm = re.search(r"/event/(\d+)/", outcomes_url.group(1))
            if idm:
                event["event_id"] = idm.group(1)
            if "clickable-row" in row["class"]:
                event["_outcomes_url"] = urljoin(page_url, outcomes_url.group(1))
        orders, judgments = [], []
        for href, text in cells[8]["links"]:
            j = _JUDGMENT_JS_RE.search(href)
            if j:
                judgments.append(judgment_link(*j.groups()))
            elif href and not href.startswith(("#", "javascript:")):
                orders.append({"title": text, "url": urljoin(page_url, href)})
        if orders:
            event["orders"] = orders
        if judgments:
            event["judgments"] = judgments
        events.append(event)
    return events


def parse_outcomes(html: str) -> list[dict]:
    """An event's outcomes: Order Type | Decision Type."""
    return [
        {"order_type": cells[0]["text"], "decision_type": cells[1]["text"]}
        for cells in _data_rows(html)
        if len(cells) >= 2
    ]


def parse_documents_filed(html: str, page_url: str = BASE_URL) -> list[dict]:
    """'Documents Filed': Date | Time | Document Title | Filed By | [link].

    The public can't download filed documents, so the last column is
    normally empty; a link there is kept in case that changes."""
    docs = []
    for cells in _data_rows(html):
        if len(cells) < 4:
            continue
        doc = {
            "date": normalize_date(cells[0]["text"]),
            "time": cells[1]["text"],
            "title": cells[2]["text"],
            "filed_by": cells[3]["text"],
        }
        links = [h for c in cells[2:] for h, _ in c["links"] if h and not h.startswith(("#", "javascript:"))]
        if links:
            doc["url"] = urljoin(page_url, links[0])
        docs.append(doc)
    return docs


def parse_parties(html: str, page_url: str = BASE_URL) -> list[dict]:
    """'Parties': [contact] [spinner] Role | Name | End Date. A row whose
    <tr> expands to a contact (lawyers, mostly) carries its URL."""
    parties = []
    for row in table_rows(html):
        cells = row["cells"]
        if len(cells) < 5 or any(c["header"] for c in cells):
            continue
        party = {
            "role": cells[2]["text"],
            "name": cells[3]["text"],
            "end_date": normalize_date(cells[4]["text"]),
        }
        url = _ONCLICK_URL_RE.search(unescape(row["onclick"]))
        if url:
            party["_contact_url"] = urljoin(page_url, url.group(1))
        parties.append(party)
    return parties


def parse_contact(html: str) -> dict:
    """A party contact: Address, Business Phone, ... as a dict."""
    contact = {}
    for row in table_rows(html):
        cells = row["cells"]
        if len(cells) >= 2 and cells[0]["header"]:
            key = re.sub(r"\W+", "_", cells[0]["text"].rstrip(":").strip().lower()).strip("_")
            # Empty address lines still get their comma: "170 North Terrace, , ADELAIDE".
            contact[key] = re.sub(r"(?:\s*,)+\s*", ", ", cells[1]["text"]).strip(", ")
    return contact


# --- A whole file ------------------------------------------------------------


def _pop_urls(obj, key):
    """obj[key], removing it (the fragment URLs are scaffolding, not data)."""
    return obj.pop(key, None)


def _event_signature(events: list[dict], event_id: str) -> tuple:
    """What an event's listings show; while it's unchanged so are its
    outcomes."""
    return tuple(
        (e["date"], e["time"], e["reason"], e["outcome"], tuple(o["url"] for o in e.get("orders", [])))
        for e in events
        if e.get("event_id") == event_id
    )


def _cache(previous: dict | None) -> tuple[dict, dict]:
    """Outcomes and contacts from a previous scrape, keyed so they can be
    reused: outcomes by (application, event, the event's listings) and
    contacts by (application, role, name)."""
    outcomes, contacts = {}, {}
    for app in (previous or {}).get("applications", []):
        for e in app.get("events", []):
            if "outcomes" in e and e.get("event_id"):
                key = (app["id"], e["event_id"], _event_signature(app["events"], e["event_id"]))
                outcomes[key] = e["outcomes"]
        for p in app.get("parties", []):
            if "contact" in p:
                contacts[(app["id"], p["role"], p["name"])] = p["contact"]
    return outcomes, contacts


def fetch_file(session: Session, ref: dict, previous: dict | None = None) -> dict:
    """Everything the portal shows the public about a file.

    An event's outcomes and a party's contact take a request each, which
    adds up on a long-running file, so with previous (the last scrape) they
    are reused while the event's listings, or the party, are unchanged.

    Raises FetchError if the actions page or any fragment can't be loaded, so
    a half-fetched file is never mistaken for one whose rows disappeared."""
    cached_outcomes, cached_contacts = _cache(previous)
    base = file_base_url(ref)
    actions_url = f"{base}/actions"
    html = session.get_html(actions_url)
    details = parse_file_details(html)
    if not details.get("number"):
        raise FetchError(f"no file details on {actions_url}")
    apps = parse_applications(html, actions_url)
    for app in apps:
        urls = _pop_urls(app, "_urls") or {}
        events_url = urls.get("events-and-orders")
        app["events"] = parse_events(session.get_html(events_url), events_url) if events_url else []
        for event in app["events"]:
            url = _pop_urls(event, "_outcomes_url")
            if not url:
                continue
            key = (app["id"], event.get("event_id"), _event_signature(app["events"], event.get("event_id")))
            if key in cached_outcomes:
                event["outcomes"] = cached_outcomes[key]
            else:
                event["outcomes"] = parse_outcomes(session.get_html(url))
        docs_url = urls.get("documents-filed")
        app["documents"] = parse_documents_filed(session.get_html(docs_url), docs_url) if docs_url else []
        parties_url = urls.get("parties")
        app["parties"] = parse_parties(session.get_html(parties_url), parties_url) if parties_url else []
        for party in app["parties"]:
            url = _pop_urls(party, "_contact_url")
            if not url:
                continue
            key = (app["id"], party["role"], party["name"])
            party["contact"] = cached_contacts.get(key) or parse_contact(session.get_html(url))
    return {"file": {**details, "url": actions_url}, "applications": apps}


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python -m scripts.scrape.comcourts_portal FILE_NUMBER_OR_URL", file=sys.stderr)
        return 1
    data = fetch_file(Session(), parse_file_ref(sys.argv[1]))
    print(json.dumps(data, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
