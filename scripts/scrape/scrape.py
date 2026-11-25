"""Scrape the ACCC acquisitions register into ``data/raw/``.

Fetches the register listing (every page of it), works out which matter pages
to fetch (``scrape_targets.select_targets``), fetches those in parallel into
``data/raw/matters/{MATTER_NUMBER}.html``, strips the per-request churn out
of each page (:func:`clean_html_bytes`) and drops the ACCC site chrome around
the matter (:func:`trim_chrome`), so an unchanged matter is an unchanged file.

Usage (from the repo root)::

    python -m scripts.scrape.scrape [--all]
    python -m scripts.scrape.scrape --clean-file PATH
    python -m scripts.scrape.scrape --clean-stored

Options:
    --all               Scrape all mergers, ignoring cutoff dates (by default,
                        mergers are skipped 3 weeks after an approved
                        notification or waiver decision), then re-clean every
                        saved HTML file.
    --clean-file PATH   Clean (and trim, if a matter page) one file in place
                        and exit. Used by pipeline.yml to re-clean files after
                        a git rebase.
    --clean-stored      Clean and trim every saved HTML file in place, without
                        scraping. Run after changing either, so the stored
                        pages follow.

Environment:
    SCRAPE_REPORT_DIR   If set, write a report of the run into this directory:
                        targets.json (what was selected, skipped and recovered)
                        and fetched.tsv (status, merger ID and path per fetch).
                        scripts/scrape/scrape_summary.py renders these for the
                        run's GitHub step summary.
    SCRAPE_EXPECT_IDS   Matter IDs the triggering ACCC email named (comma or
                        space separated). The listing is re-crawled, up to
                        EXPECT_RECRAWLS (default 3) more times, EXPECT_RECRAWL_DELAY
                        (default 10) seconds apart, until each is either
                        already in mergers.json or on a listing page. See
                        scripts/scrape/expected_matters.py. They are also
                        fetched even if past cutoff, since the email says they
                        changed.

This replaced ``scrape.sh`` (bash, curl, pup and a perl one-liner). The
cleaner's substitutions are the perl ones, in the same order, run over bytes as
perl's slurp mode did. Most of them now only match inside chrome that
trim_chrome() removes; they stay because the register listing page is cleaned
but never trimmed, and because a matter page that can't be trimmed safely is
stored whole.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable, Iterable, Optional

from bs4 import BeautifulSoup
from lxml import etree, html as lxml_html

from scripts import accc_http
from scripts.cutoff import parse_matter_ids
from scripts.merger_filters import load_mergers_or_empty
from scripts.paths import REPO_ROOT
from scripts.scrape.expected_matters import missing_ids
from scripts.scrape.scrape_targets import print_selection_report, select_targets

BASE_URL = 'https://www.accc.gov.au'
REGISTER_URL = (
    f'{BASE_URL}/public-registers/acquisitions-and-mergers-registers/'
    'acquisitions-register?init=1&items_per_page=50'
)
RAW_DIR = REPO_ROOT / 'data' / 'raw'
MAIN_PAGE_FILE = RAW_DIR / 'acquisitions-register.html'
MATTERS_DIR = RAW_DIR / 'matters'
MERGERS_JSON = REPO_ROOT / 'data' / 'processed' / 'mergers.json'
PARALLEL_JOBS = 24

# curl_cffi's Chrome impersonation supplies the browser's own User-Agent,
# Accept and Sec-Fetch-* headers (matching its TLS fingerprint, which a
# hand-written User-Agent would contradict); only the locale is added.
HEADERS = {'Accept-Language': 'en-AU,en;q=0.9'}

# The HTTP statuses curl's --retry treats as transient.
TRANSIENT_STATUSES = frozenset({408, 429, 500, 502, 503, 504})



def _has_class(name: str) -> str:
    """XPath test for an element carrying CSS class ``name``."""
    return f"contains(concat(' ', normalize-space(@class), ' '), ' {name} ')"


# The CSS selectors scrape.sh gave pup, as XPath over lxml. lxml is the parser
# BeautifulSoup used underneath, without its Python-side tree: it parses a
# matter page ten times faster, and releases the GIL while it does, so the 24
# fetch threads aren't queued behind each other's parsing.
#   .field--name-dynamic-token-fieldnode-acccgov-merger-id p
MATTER_NUMBER_XPATH = etree.XPath(
    f"//*[{_has_class('field--name-dynamic-token-fieldnode-acccgov-merger-id')}]//p")
#   .accc-collapsed-card__header a[href]
LISTING_LINK_XPATH = etree.XPath(f"//*[{_has_class('accc-collapsed-card__header')}]//a[@href]")
#   a[title="Go to last page"][href]
LAST_PAGE_XPATH = etree.XPath('//a[@title="Go to last page"][@href]')

# A matter number becomes a filename, so it is whitelisted to prevent path
# traversal if the upstream site ever returns unexpected content. Expected
# values look like "MN-12345" or "WA-12345".
SAFE_MATTER_NUMBER = re.compile(r'[A-Za-z0-9_-]+')
# What a fallback filename (from the link) may keep.
UNSAFE_FALLBACK_CHARS = re.compile(r'[^A-Za-z0-9_.-]')
# POSIX [:space:] in the C locale, which is what `tr -d '[:space:]'` removed.
ASCII_SPACE = re.compile(r'[ \t\n\r\f\v]')

Sleep = Callable[[float], None]


# --- Cleaning ---------------------------------------------------------------

# (pattern, replacement, count) — count 1 where the perl had no /g. Run over
# the whole file as bytes, in this order, exactly as `perl -0777 -pe` did:
# `.` stops at \n unless the pattern has re.S (perl's /s), and the line-scoped
# negated classes exclude \n so they can't span lines in a slurped file. The
# order matters: the `?t` rule runs over what the icons.svg rule left.
_CLEAN_RULES: list[tuple[re.Pattern[bytes], bytes, int]] = [
    # Collapse the entire Drupal settings JSON blob to a static placeholder.
    # It is machine config full of per-request churn (session/build tokens
    # such as libraries, permissionsHash, css_js_query_string, view_dom_id,
    # ct, _bhlid, brid, ...) that nothing in the pipeline consumes. Replacing
    # it wholesale beats stripping each field individually, so new tokens the
    # upstream site adds inside it never produce diff noise again.
    (re.compile(rb'(<script type="application/json" data-drupal-selector="drupal-settings-json">)'
                rb'.*?(</script>)', re.S),
     rb'\g<1>STATIC_DRUPAL_SETTINGS\g<2>', 1),
    (re.compile(rb'js-view-dom-id-[a-f0-9]{64}'), b'js-view-dom-id-STATIC', 0),
    (re.compile(rb'(id="edit-submit-accc-search-site--)[^"\n]+"'), rb'\g<1>STATIC"', 0),
    (re.compile(rb'(id="edit-actions)--[0-9]+"'), rb'\g<1>"', 0),
    (re.compile(rb'(data-drupal-selector="form-)[^"\n]+(" type="hidden" name="form_build_id")'),
     rb'\g<1>STATIC\g<2>', 0),
    (re.compile(rb'(name="form_build_id" value="form-)[^"\n]+"'), rb'\g<1>STATIC"', 0),
    (re.compile(rb'(css/css_)[^.\n]+\.css'), rb'\g<1>STATIC.css', 0),
    (re.compile(rb'(js/js_)[^.\n]+\.js'), rb'\g<1>STATIC.js', 0),
    (re.compile(rb'include=[^"&>\n]+'), b'include=STATIC', 0),
    (re.compile(rb'href="https://app\.readspeaker\.com/[^"\n]+"'),
     b'href="STATIC_READSPEAKER_URL"', 0),
    (re.compile(rb'(icons\.svg\?t)[^#\n]+#'), rb'\g<1>STATIC#', 0),
    (re.compile(rb'(\?t)[^">\n]+'), rb'\g<1>STATIC', 0),
    # Akamai mPulse's inline BOOMR loader, injected per request before </head>.
    (re.compile(rb'[ \t]*\n[ \t]*<script>!function\(e\)\{var n="https://s\.go-mpulse\.net/boomerang/"'
                rb'.*?\(window\);</script></head>', re.S),
     b'\n  </head>', 1),
    # The upstream site emits these two pairs in either order from one
    # request to the next; fix the order.
    (re.compile(rb'(<meta name="dcterms\.modified"[^\n]*/>\n)(<meta name="dcterms\.created"[^\n]*/>\n)'),
     rb'\g<2>\g<1>', 0),
    (re.compile(rb'(<link rel="canonical"[^\n]*/>\n)(<link rel="shortlink"[^\n]*/>\n)'),
     rb'\g<2>\g<1>', 0),
    (re.compile(rb'(<nav class="accc-entity-hierarchy-megamenu"[^>]*>).*?</nav>', re.S),
     rb'\g<1>STATIC_MEGAMENU</nav>', 1),
    (re.compile(rb'\n{3,}'), b'\n\n', 0),
]


def clean_html_bytes(content: bytes) -> bytes:
    """Strip the per-request dynamic content out of one saved ACCC page."""
    for pattern, replacement, count in _CLEAN_RULES:
        content = pattern.sub(replacement, content, count=count)
    return content


# --- Trimming the site chrome ----------------------------------------------
#
# Most of a register page is the ACCC site around the matter: skip links, the
# header and megamenu, the breadcrumb and ReadSpeaker button, the footer,
# scripts, stylesheets and the "subscribe to this acquisition" modal. None of
# it is about the matter, and it is what churns. trim_chrome() drops exactly
# those parts and keeps everything else, so the stored page is the matter
# itself plus every <meta>, <link> and <title> in <head>.
#
# It is a denylist on purpose. An allowlist ("keep <main>") would silently
# drop anything the ACCC adds outside it: a new section of the page, a
# Tribunal or court notice in the hero, a structured-data block. A denylist
# can only lose what it names, and every name below is site furniture.

# Removed wherever they appear. The element's tail text is kept.
_CHROME_XPATH = etree.XPath(' | '.join([
    # Every <script> but structured data (JSON-LD), which describes the page.
    "//script[not(@type) or translate(@type, 'LDJSON', 'ldjson') != 'application/ld+json']",
    '//noscript',
    '//style',
    "//head/link[translate(@rel, 'STYLESHET', 'stylesheet') = 'stylesheet']",
    "//body//*[@id='skip-links']",
    f"//body//*[{_has_class('region-site-notification-bar')}]",
    f"//body//*[{_has_class('nav-container')}]",
    f"//body//*[{_has_class('breadcrumb-wrapper')}]",
    "//body//footer",
    # The subscribe button and its modal form, inside the article.
    f"//body//*[{_has_class('field--name-dynamic-block-fieldnode-acquisitions-subscribe')}]",
]))

# What a removed region must never contain. If one ever does (the ACCC moves
# a field into the hero's breadcrumb, say), the page is stored whole instead.
_CONTENT_XPATH = etree.XPath(
    "descendant-or-self::*[self::main or self::article or self::h1 or self::table"
    " or self::time or contains(@class, 'field--name-field-')"
    " or contains(@class, 'field--name-dynamic-token-')]")

# Every matter page has these; without them this isn't a page to trim.
_MATTER_PAGE_XPATH = etree.XPath(
    f"//body//*[{_has_class('field--name-dynamic-token-fieldnode-acccgov-merger-id')}]")

_BLANK_LINES = re.compile(rb'\n[ \t]*(?:\n[ \t]*)+\n')


def trim_chrome(content: bytes) -> Optional[bytes]:
    """``content`` without the site chrome, or None if it can't be trimmed safely.

    None means: not a matter page (no merger-ID field), unparseable, or a
    region to remove holds matter content. The caller stores the page whole.
    Whitespace-only lines left where elements were removed are collapsed, so
    trimming an already-trimmed page changes nothing.
    """
    if not content or not content.strip():
        return None
    try:
        document = lxml_html.document_fromstring(
            content, parser=lxml_html.HTMLParser(encoding='utf-8'))
    except (etree.ParserError, ValueError):
        return None
    if not _MATTER_PAGE_XPATH(document):
        return None
    chrome = _CHROME_XPATH(document)
    if any(_CONTENT_XPATH(element) for element in chrome):
        return None
    for element in chrome:
        # A match nested inside another match is already detached.
        if element.getparent() is not None:
            element.drop_tree()
    trimmed = etree.tostring(document.getroottree(), method='html', encoding='utf-8')
    if not trimmed.endswith(b'\n'):
        trimmed += b'\n'
    return _BLANK_LINES.sub(b'\n\n', trimmed)


def prepare_page(content: bytes) -> tuple[bytes, bool]:
    """What is stored for a fetched page, and whether it was trimmed.

    Cleaned, then trimmed if it is a matter page. Cleaning runs first, on the
    markup as the ACCC served it, which is what its rules were written
    against, and again after, so the stored page is a fixed point of both. A
    page trim_chrome() can't trim is stored cleaned but whole.
    """
    cleaned = clean_html_bytes(content)
    trimmed = trim_chrome(cleaned)
    if trimmed is None:
        return cleaned, False
    return clean_html_bytes(trimmed), True


def clean_file(path: Path | str) -> bool:
    """Clean (and trim, if a matter page) one HTML file in place. Returns whether it changed."""
    path = Path(path)
    original = path.read_bytes()
    cleaned, _ = prepare_page(original)
    if cleaned == original:
        return False
    path.write_bytes(cleaned)
    return True


def html_files_to_clean() -> list[Path]:
    """Every saved HTML file ``--all`` re-cleans: the register page and matters."""
    files: list[Path] = []
    for directory in (RAW_DIR, MATTERS_DIR):
        files.extend(sorted(directory.glob('*.html')))
    return files


def clean_all_html() -> None:
    """Re-clean every saved HTML file (``--all``), including earlier runs' pages."""
    files = html_files_to_clean()
    if not files:
        print('No HTML files to clean.')
        return
    print(f'Cleaning dynamic content from {len(files)} HTML file(s)...')
    for path in files:
        clean_file(path)
    print(f'Successfully cleaned {len(files)} HTML file(s)')


# --- HTTP -------------------------------------------------------------------

class FetchError(Exception):
    """A fetch that failed for good. ``status`` is 0 when nothing came back."""

    def __init__(self, url: str, status: int = 0, reason: str = ''):
        self.url = url
        self.status = status
        self.reason = reason
        super().__init__(f'{url} (HTTP {status:03d}){": " + reason if reason else ""}')


_thread_state = threading.local()


def _get(url: str, timeout: float):
    """GET through this thread's session, so each worker reuses its connection.

    A fresh TLS handshake per page was most of a page's fetch time.
    """
    session = getattr(_thread_state, 'session', None)
    if session is None:
        session = _thread_state.session = accc_http.session()
    return session.get(url, headers=HEADERS, timeout=timeout)


def fetch_register_index(url: str = REGISTER_URL, *, attempts: int = 2,
                         retry_delay: float = 30, timeout: float = 30,
                         sleep: Sleep = time.sleep) -> tuple[int, bytes]:
    """Fetch the register's first page, as ``(status, body)``.

    A transport error or a transient status (curl's --retry set) is retried.
    Any other status is returned rather than raised, deliberately: a block
    page (Akamai "Access Denied", a Cloudflare challenge) still arrives as an
    HTML body, and keeping it lets the zero-links diagnostics show what the
    ACCC actually served. Raises FetchError only if no response ever came.
    """
    response = None
    error = ''
    for attempt in range(attempts):
        if attempt:
            sleep(retry_delay)
        try:
            response = _get(url, timeout)
        except accc_http.RequestException as exc:
            response, error = None, str(exc)
            continue
        if response.status_code not in TRANSIENT_STATUSES:
            break
    if response is None:
        raise FetchError(url, 0, error)
    return response.status_code, response.content


def fetch_page(url: str, *, attempts: int = 3, retry_delay: float = 5,
               timeout: float = 30, sleep: Sleep = time.sleep) -> bytes:
    """Fetch a matter page, retrying any failure; raise FetchError at the end.

    A run typically lost one or two of ~100 pages, a different few each time,
    and an unfetched page isn't revisited until the next run. Why they fail
    hasn't been seen, so this retries on any error, an HTTP error status
    included, rather than only transient ones, which would skip an Akamai 403:
    no register page is known to fail for good, so a retried 404 costs seconds
    in a run that fetches 24 at a time. ``timeout`` bounds each attempt, so a
    stalled fetch can't hold its worker until the job times out.
    """
    status, reason = 0, ''
    for attempt in range(attempts):
        if attempt:
            sleep(retry_delay)
        try:
            response = _get(url, timeout)
        except accc_http.RequestException as exc:
            status, reason = 0, str(exc)
            continue
        if response.status_code < 400:
            return response.content
        status, reason = response.status_code, ''
    raise FetchError(url, status, reason)


# --- Parsing ----------------------------------------------------------------

def _soup(html: bytes | str) -> BeautifulSoup:
    return BeautifulSoup(html, 'lxml')


def _select(html: bytes | str, xpath: etree.XPath) -> list:
    """The elements ``xpath`` matches in ``html`` (none for an empty body)."""
    if not html or not html.strip():
        return []
    try:
        document = lxml_html.document_fromstring(html)
    except (etree.ParserError, ValueError):
        return []
    return xpath(document)


def listing_links(html: bytes | str) -> list[str]:
    """The matter links on one register listing page, in page order."""
    links = []
    for anchor in _select(html, LISTING_LINK_XPATH):
        href = anchor.get('href').replace('\r', '').strip()
        if href and '#card-' not in href:
            links.append(href)
    return links


def last_page_number(html: bytes | str) -> int:
    """The listing's last page index (0-based) from its "Go to last page" link."""
    numbers = []
    for anchor in _select(html, LAST_PAGE_XPATH):
        numbers.extend(re.findall(r'[?&]page=([0-9]+)', anchor.get('href')))
    return int(numbers[-1]) if numbers else 0


def matter_number(html: bytes | str) -> str:
    """The case number a matter page states, with all whitespace removed."""
    text = ''.join(p.text_content() for p in _select(html, MATTER_NUMBER_XPATH))
    return ASCII_SPACE.sub('', text)


def is_safe_matter_number(value: str) -> bool:
    """Whether ``value`` is safe to use as a filename stem."""
    return bool(SAFE_MATTER_NUMBER.fullmatch(value))


def fallback_filename(link: str) -> str:
    """A filename stem from the link's last segment, scrubbed to a safe set.

    Empty when nothing safe is left, in which case the page isn't saved.
    """
    stripped = link.rstrip('/')
    base = stripped.rsplit('/', 1)[-1] if stripped else ''
    return UNSAFE_FALLBACK_CHARS.sub('', base)


# --- Run report -------------------------------------------------------------

class Manifest:
    """``fetched.tsv``: one ``status<TAB>merger_id<TAB>link`` row per fetch."""

    def __init__(self, path: Optional[Path]):
        self.path = path
        self._lock = threading.Lock()
        if path is not None:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('', encoding='utf-8')

    def record(self, status: str, merger_id: str, link: str) -> None:
        if self.path is None:
            return
        with self._lock, open(self.path, 'a', encoding='utf-8') as f:
            f.write(f'{status}\t{merger_id or "UNKNOWN"}\t{link}\n')


# --- Fetching ---------------------------------------------------------------

def fetch_matter_page(link: str, manifest: Manifest,
                      fetch: Optional[Callable[[str], bytes]] = None,
                      matters_dir: Optional[Path] = None) -> Optional[str]:
    """Fetch one matter page and save it cleaned. Returns an error, or None."""
    fetch = fetch or fetch_page
    matters_dir = matters_dir or MATTERS_DIR
    full_url = f'{BASE_URL}{link}'
    try:
        content = fetch(full_url)
    except FetchError as exc:
        manifest.record('failed', '', link)
        return f'{full_url} (HTTP {exc.status:03d})'

    number = matter_number(content)
    if number and not is_safe_matter_number(number):
        print(f"    Warning: Rejected unsafe matter number '{number}' for {full_url}",
              file=sys.stderr)
        number = ''

    if number:
        stem = number
    else:
        stem = fallback_filename(link)
        if not stem:
            print(f'    Warning: Skipping {full_url} (no safe filename)', file=sys.stderr)
            manifest.record('failed', '', link)
            return f'{full_url} (no safe filename)'
        print(f'    Warning: Could not find matter number for {full_url}. '
              f'Used fallback name: {stem}')

    stored, trimmed = prepare_page(content)
    if not trimmed:
        # Losing a section of the page would be worse than storing chrome.
        print(f'::warning::Stored {stem}.html whole: its site chrome could not be '
              f'trimmed safely (see trim_chrome in scrape.py). {full_url}')
    (matters_dir / f'{stem}.html').write_bytes(stored)
    manifest.record('ok', number, link)
    return None


def fetch_listing_page(page: int) -> bytes:
    """One register listing page's body, whatever its status (b'' if none came)."""
    url = f'{REGISTER_URL}&page={page}'
    try:
        response = _get(url, 30)
    except accc_http.RequestException as exc:
        print(f'    Warning: register page {page} could not be fetched: {exc}',
              file=sys.stderr)
        return b''
    if response.status_code != 200:
        print(f'    Warning: register page {page} returned HTTP {response.status_code}',
              file=sys.stderr)
    return response.content


def crawl_listing(pages: Iterable[int], pool: ThreadPoolExecutor) -> list[bytes]:
    """Fetch the given listing pages in parallel, in page order."""
    return list(pool.map(fetch_listing_page, pages))


# --- Diagnostics ------------------------------------------------------------

_DIAGNOSTIC_SELECTORS = (
    '.accc-collapsed-card__header a', '.accc-collapsed-card',
    'a[href*="/acquisitions-register/"]', 'a[title="Go to last page"]',
    '.views-row', 'table tbody tr',
)
_DIAGNOSTIC_HEADERS = re.compile(
    r'^(server|content-type|content-length|location|x-akamai|akamai|cf-|x-cache'
    r'|x-reference|set-cookie)', re.I)


def print_register_diagnostics(status: int, body: bytes) -> None:
    """Enough of an empty listing to tell a block page from a markup change."""
    soup = _soup(body)
    title = soup.title.get_text() if soup.title else ''
    print(f'::error::No acquisition links found on the register (HTTP {status}). '
          'The fetch was blocked or the website structure changed.')
    print('--- Register page diagnostics ---')
    print(f'URL:    {REGISTER_URL}')
    print(f'Status: HTTP {status}')
    print(f'Size:   {len(body)} bytes')
    print(f'Title:  {" ".join(title.split())[:200]}')
    print('Selector counts:')
    for selector in _DIAGNOSTIC_SELECTORS:
        print(f'  {selector:<45} {len(soup.select(selector))}')
    print('Response headers (fresh HEAD request):')
    try:
        response = accc_http.head(REGISTER_URL, headers=HEADERS, timeout=30)
        print(f'  HTTP {response.status_code}')
        for name, value in response.headers.items():
            if _DIAGNOSTIC_HEADERS.match(name):
                print(f'  {name}: {value}')
    except accc_http.RequestException as exc:
        print(f'  (request failed: {exc})')
    print('First 60 lines of the page body:')
    for line in body.decode('utf-8', errors='replace').splitlines()[:60]:
        print(f'  | {line[:300]}')
    print('--- End register page diagnostics ---')


# --- Main -------------------------------------------------------------------

def _display(path: Path) -> str:
    """``path`` relative to the repo root where it can be, for log lines."""
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _merge_recrawl(relative_links: list[str], pages: list[bytes]) -> list[str]:
    """Links a re-crawl served that the earlier crawls didn't, sorted.

    Only these are added, so the run summary's listing and duplicate counts
    still describe one crawl rather than counting every re-crawled row as a
    duplicate.
    """
    seen = set(relative_links)
    served = {link for page in pages for link in listing_links(page)}
    return sorted(served - seen)


def scrape(*, scrape_all: bool = False, expect_ids: str = '',
           report_dir: Optional[Path] = None, recrawls: int = 3,
           recrawl_delay: float = 10, sleep: Sleep = time.sleep) -> int:
    """Run one scrape. Returns the process exit status."""
    manifest = Manifest(report_dir / 'fetched.tsv' if report_dir else None)

    # 1. The first page of the register.
    print(f'Downloading main register page from {REGISTER_URL}...')
    try:
        main_status, main_body = fetch_register_index(sleep=sleep)
    except FetchError:
        print('Failed to download main page after retries (HTTP none)')
        return 1
    MAIN_PAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
    MAIN_PAGE_FILE.write_bytes(main_body)
    print(f"Saved main page to '{_display(MAIN_PAGE_FILE)}' "
          f'(HTTP {main_status}, {len(main_body)} bytes)')
    clean_file(MAIN_PAGE_FILE)
    main_page = MAIN_PAGE_FILE.read_bytes()

    MATTERS_DIR.mkdir(parents=True, exist_ok=True)

    with ThreadPoolExecutor(max_workers=PARALLEL_JOBS) as pool:
        # 2. Every listing page, for its matter links. Every page any crawl
        #    fetched is kept, so the expected-matters check can read the case
        #    numbers off the cards of every crawl, not just the links.
        print('Extracting links from register pages...')
        listing_pages = [main_page]
        relative_links = listing_links(main_page)
        last_page = last_page_number(main_page)
        if last_page > 0:
            print(f'Register has {last_page + 1} pages. Fetching additional pages in parallel...')
            pages = crawl_listing(range(1, last_page + 1), pool)
            listing_pages.extend(pages)
            for page in pages:
                relative_links.extend(listing_links(page))

        # 3. Make sure the listing served every matter the triggering email
        #    named. The listing's unstable sort can drop any row. A matter we
        #    already know is recovered by select_targets from its stored URL,
        #    but a brand-new matter has nothing to recover from: if the crawl
        #    drops it, an email-triggered run misses the very matter it was
        #    triggered for. So crawl again, up to `recrawls` more times, until
        #    every emailed ID is either known or on a listing page. A matter
        #    still missing after that (the email can arrive before the
        #    register shows it) is a warning, not a failure: the next run
        #    will pick it up.
        if expect_ids and relative_links:
            expected = parse_matter_ids(expect_ids)
            known = {m.get('merger_id') for m in load_mergers_or_empty(MERGERS_JSON)}
            crawl = 0
            while True:
                pages_text = [p.decode('utf-8', errors='replace') for p in listing_pages]
                missing = missing_ids(expected, pages_text, known)
                if not missing:
                    if crawl:
                        print(f'    Every emailed matter found after {crawl} extra listing crawl(s).')
                    break
                if crawl >= recrawls:
                    print('::warning::Emailed matter(s) not on the register listing after '
                          f'{crawl + 1} crawl(s): {" ".join(missing)}')
                    break
                crawl += 1
                print(f'    Emailed matter(s) missing from the listing: {" ".join(missing)}. '
                      f'Crawling it again ({crawl}/{recrawls})...')
                sleep(recrawl_delay)
                pages = crawl_listing(range(0, last_page + 1), pool)
                listing_pages.extend(pages)
                new_links = _merge_recrawl(relative_links, pages)
                if new_links:
                    print(f'    Crawl {crawl} served {len(new_links)} matter(s) '
                          'the earlier crawl(s) missed.')
                    relative_links.extend(new_links)

        # The register always lists matters, so an empty listing means the
        # fetch was blocked or the markup changed. Either way the run has
        # scraped nothing, and exiting 0 here once let three runs in a row
        # pass green while doing no work.
        if not relative_links:
            print_register_diagnostics(main_status, main_page)
            return 1

        # 4. Which matters to fetch. select_targets drops matters past cutoff
        #    (unless --all), de-duplicates the listing, and adds back any
        #    matter we already know about that this crawl's listing failed to
        #    mention; see scrape_targets.py.
        if scrape_all:
            print('Scraping all mergers (--all flag specified)')
        links_to_fetch, stats = select_targets(
            relative_links,
            load_mergers_or_empty(MERGERS_JSON),
            scrape_all=scrape_all,
            # Emailed matters are fetched even past cutoff: the email says
            # they changed.
            include_ids=parse_matter_ids(expect_ids),
        )
        if report_dir:
            with open(report_dir / 'targets.json', 'w', encoding='utf-8') as f:
                json.dump(stats, f, indent=2)
        print_selection_report(stats)

        if not links_to_fetch:
            print('No mergers to fetch (all are past cutoff).')
            print('Scraping process completed successfully.')
            return 0

        # 5. The matter pages themselves.
        print(f'Fetching {len(links_to_fetch)} merger page(s)...')
        errors = [e for e in pool.map(lambda link: fetch_matter_page(link, manifest),
                                      links_to_fetch) if e]

    print(f'Successfully fetched {len(links_to_fetch) - len(errors)} merger page(s)')
    if errors:
        print(f'{len(errors)} merger page(s) unsuccessful:')
        for error in errors:
            print(f'- {error}')

    # 6. A full pass when scraping everything, so files saved by earlier runs
    #    are cleaned by the current rules too.
    if scrape_all:
        clean_all_html()

    print('Scraping process completed successfully.')
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description='Scrape the ACCC acquisitions register.')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--all', action='store_true',
                       help='Ignore cutoff dates and fetch every known matter')
    group.add_argument('--clean-file', metavar='PATH',
                       help='Clean (and trim, if a matter page) one HTML file in place and exit')
    group.add_argument('--clean-stored', action='store_true',
                       help='Clean and trim every stored HTML file in place, without scraping')
    args = parser.parse_args(argv)

    # Progress lines interleave with stderr warnings in the Actions log.
    sys.stdout.reconfigure(line_buffering=True)

    if args.clean_file:
        try:
            clean_file(args.clean_file)
        except OSError as exc:
            print(f'Error: could not clean {args.clean_file}: {exc}', file=sys.stderr)
            return 1
        return 0

    if args.clean_stored:
        clean_all_html()
        return 0

    report_dir = os.environ.get('SCRAPE_REPORT_DIR') or None
    return scrape(
        scrape_all=args.all,
        expect_ids=os.environ.get('SCRAPE_EXPECT_IDS', ''),
        report_dir=Path(report_dir) if report_dir else None,
        recrawls=int(os.environ.get('EXPECT_RECRAWLS') or 3),
        recrawl_delay=float(os.environ.get('EXPECT_RECRAWL_DELAY') or 10),
    )


if __name__ == '__main__':
    sys.exit(main())
