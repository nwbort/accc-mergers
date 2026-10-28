#!/usr/bin/env python3
"""Scrape Federal Court judicial review files into judicial_reviews.json.

Background
----------
An ACCC merger decision can be taken to the Federal Court by judicial review
as well as to the Tribunal. ``data/processed/judicial_reviews.json`` holds,
per merger (keyed by ACCC merger_id), a list of records, one per Federal Court
file, each with a few hand-maintained fields (``applicant``, ``filed_date``,
``case_number``, ``case_url``) and a ``portal`` block this script fills in
from the file's pages on the Commonwealth Courts Portal (comcourts.gov.au):
the file details, and for each application its court listings (with any
orders and judgments), its documents filed and its parties. See
:mod:`scripts.scrape.comcourts_portal` for the page formats.

As with the tribunal, the "list of files to scrape" is simply every record
that carries a ``case_url`` (or a ``case_number``); add a record by hand to
start tracking a new file.

Ported from nwbort/scrape-fed, with the downloads moved into this repo's own
tree:

  * each "View orders" PDF is downloaded into ``data/raw/matters/{merger_id}/``
    under the name the portal gives it (``P_NSD1310_2026_2835642.pdf``) and
    served as ``/mergers/{merger_id}/{file}``, like any ACCC attachment. The
    portal is plain server-rendered HTML with no Cloudflare in front of it, so
    this is ordinary HTTP;
  * each "View judgment" is fetched from judgments.fedcourt.gov.au, which *is*
    behind Cloudflare's managed challenge, by the tribunal scraper's own
    judgment downloader
    (:func:`scripts.scrape.scrape_tribunal.download_judgment_page`), which
    drives a real Chrome via nodriver. Chrome is only started when there is a
    judgment that hasn't been saved yet, so most runs never launch it, and
    without nodriver installed everything but the judgments still works. The
    Word document it saves is converted to PDF by the pipeline's DOCX step.

A download that fails is left without ``url_gh`` and retried on the next run.

Merging
-------
The portal's own tables are authoritative and are rewritten on each run, with
one exception: an application's documents filed are merged **additively**, as
the tribunal's are (:func:`scripts.scrape.scrape_tribunal.merge_documents`),
because each one is a merger timeline event and a row the portal stops
showing would otherwise silently disappear from the site. A dropped document
is kept and reported; delete it by hand to drop it for good.

If any of a file's pages fails to load, or the file suddenly has no
applications, that record is left untouched and the run exits non-zero.

Usage
-----
Normally this runs from CI on the "Scrape Tribunal" workflow's schedule, after
the tribunal scraper::

  pip install -r scripts/requirements-tribunal.txt
  xvfb-run -a python -m scripts.scrape.scrape_federal_court             # every file
  python -m scripts.scrape.scrape_federal_court MN-01068               # just these merger_ids
  python -m scripts.scrape.scrape_federal_court --no-download          # record metadata only
  python -m scripts.scrape.scrape_federal_court --dry-run              # parse and report, write nothing
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import tempfile
from email.message import Message
from pathlib import Path
from urllib.parse import urlparse

from scripts.constants.judicial_review import review_records
from scripts.paths import REPO_ROOT
from scripts.scrape import comcourts_portal as portal
from scripts.scrape import scrape_tribunal as tribunal

JUDICIAL_REVIEWS_JSON = REPO_ROOT / "data" / "processed" / "judicial_reviews.json"
MATTERS_DIR = tribunal.MATTERS_DIR

PORTAL_HOST = "www.comcourts.gov.au"


# --- Records -----------------------------------------------------------------


def load_reviews(path: Path | None = None) -> dict:
    with open(path or JUDICIAL_REVIEWS_JSON, encoding="utf-8") as f:
        return json.load(f)


def write_reviews(raw: dict, path: Path | None = None) -> None:
    with open(path or JUDICIAL_REVIEWS_JSON, "w", encoding="utf-8") as f:
        json.dump(raw, f, indent=2, ensure_ascii=False)
        f.write("\n")


def file_ref(record: dict) -> dict | None:
    """The portal file a record names, by its case URL or else its number."""
    for value in (record.get("case_url"), record.get("case_number")):
        if value:
            try:
                return portal.parse_file_ref(value)
            except ValueError:
                continue
    return None


def review_label(merger_id: str, record: dict) -> str:
    """``MN-01068 (NSD1310/2026)``: a merger can have more than one file."""
    number = record.get("case_number")
    return f"{merger_id} ({number})" if number else merger_id


def filed_document_key(doc: dict) -> tuple:
    """Identity of a document filed: the portal gives it no id or link, so it
    is the row's own fields."""
    return (doc.get("date"), doc.get("time"), doc.get("title"), doc.get("filed_by"))


def merge_filed_documents(previous: dict | None, data: dict) -> list[tuple[str, dict]]:
    """Fold each application's previous documents filed into ``data`` in
    place (see the module docstring). Returns ``(application title, doc)``
    for each document kept although the portal no longer lists it."""
    dropped = []
    old_apps = {a.get("id"): a for a in (previous or {}).get("applications") or []}
    for app in data.get("applications") or []:
        old_docs = (old_apps.get(app.get("id")) or {}).get("documents") or []
        scraped = app.get("documents") or []
        dropped.extend(
            (app.get("title") or app.get("id"), doc)
            for doc in tribunal.dropped_documents(old_docs, scraped, key=filed_document_key)
        )
        app["documents"] = tribunal.merge_documents(old_docs, scraped, key=filed_document_key)
    return dropped


# --- Orders ------------------------------------------------------------------


def previous_url_gh(previous: dict | None, kind: str) -> dict[str, str]:
    """url -> url_gh for every order or judgment (``kind``) saved earlier."""
    out = {}
    for app in (previous or {}).get("applications") or []:
        for event in app.get("events") or []:
            for item in event.get(kind) or []:
                if item.get("url") and item.get("url_gh"):
                    out[item["url"]] = item["url_gh"]
    return out


def is_portal_url(url: str) -> bool:
    """Only download from the portal itself (SSRF guard)."""
    parsed = urlparse(url)
    return parsed.scheme == "https" and parsed.hostname == PORTAL_HOST


def order_filename(url: str, headers: dict, data: bytes) -> str | None:
    """The name the portal gives the file (``P_NSD1310_2026_2835642.pdf``),
    else the document id from the URL with an extension sniffed from the
    bytes. None if neither gives a safe filename."""
    msg = Message()
    disposition = next(
        (v for k, v in headers.items() if k.lower() == "content-disposition"), ""
    )
    msg["content-disposition"] = disposition
    name = os.path.basename(msg.get_filename() or "").strip()
    if not name or not os.path.splitext(name)[1]:
        stem = name or urlparse(url).path.rstrip("/").rsplit("/", 1)[-1]
        ext = tribunal.sniff_extension(data)
        if not ext:
            return None
        name = stem + ext
    return name if tribunal.is_safe_filename(name) else tribunal.sanitize_filename(name)


def download_orders(
    session: portal.Session, merger_id: str, data: dict, previous: dict | None
) -> list[str]:
    """Fill in ``url_gh`` for each order, downloading the ones not saved yet.
    Returns the URLs that couldn't be downloaded."""
    saved = previous_url_gh(previous, "orders")
    missing = []
    for app in data.get("applications") or []:
        for event in app.get("events") or []:
            for order in event.get("orders") or []:
                url = order.get("url")
                if not url:
                    continue
                url_gh = tribunal.existing_mirror(merger_id, saved.get(url))
                if url_gh:
                    order["url_gh"] = url_gh
                    continue
                if not is_portal_url(url):
                    print(f"    Warning: not downloading off-portal order {url}", file=sys.stderr)
                    continue
                try:
                    body, headers = session.get(url)
                except Exception as e:
                    print(f"    Warning: could not download {url}: {e}", file=sys.stderr)
                    missing.append(url)
                    continue
                filename = order_filename(url, headers, body)
                if filename is None:
                    print(f"    Warning: {url} is not a document", file=sys.stderr)
                    missing.append(url)
                    continue
                local_path = MATTERS_DIR / merger_id / filename
                if not local_path.exists():
                    local_path.parent.mkdir(parents=True, exist_ok=True)
                    local_path.write_bytes(body)
                    print(f"    Downloaded {filename} ({len(body)} bytes)", flush=True)
                order["url_gh"] = f"/mergers/{merger_id}/{tribunal.get_serve_filename(filename)}"
    return missing


# --- Judgments ---------------------------------------------------------------


class LazyBrowser:
    """A Chrome started on first use and stopped by :meth:`close`.

    Launched the way the tribunal scraper launches its own (ourselves, then
    attach once DevTools answers), but only when a judgment needs fetching.
    """

    def __init__(self):
        self._proc = None
        self._browser = None

    async def get(self):
        if self._browser is not None:
            return self._browser
        if tribunal.uc is None:
            raise RuntimeError(
                "nodriver is not installed; run "
                "`pip install -r scripts/requirements-tribunal.txt`"
            )
        chrome_path = tribunal.find_chrome()
        port = tribunal.free_port()
        self._proc = tribunal.launch_chrome(
            chrome_path, port, tempfile.mkdtemp(prefix="cf-fedcourt-")
        )
        if not tribunal.wait_for_devtools(port):
            self.close()
            raise RuntimeError("Chrome DevTools endpoint never became ready")
        self._browser = await tribunal._with_timeout(
            tribunal.uc.start(host="127.0.0.1", port=port, browser_executable_path=chrome_path),
            "uc.start",
        )
        return self._browser

    def close(self):
        if self._browser is not None:
            try:
                self._browser.stop()
            except Exception:
                pass
            self._browser = None
        if self._proc is not None:
            try:
                self._proc.terminate()
            except Exception:
                pass
            self._proc = None


async def download_judgments(
    browser: LazyBrowser,
    merger_id: str,
    data: dict,
    previous: dict | None,
    cache: dict[tuple[str, str], str | None],
) -> list[str]:
    """Fill in ``url_gh`` for each judgment, fetching the ones not saved yet.

    ``cache`` holds this run's results by (merger_id, URL), so a judgment
    linked from two listings is only fetched once. Returns the URLs that
    couldn't be fetched (often a judgment not published yet)."""
    saved = previous_url_gh(previous, "judgments")
    missing = []
    for app in data.get("applications") or []:
        for event in app.get("events") or []:
            for judgment in event.get("judgments") or []:
                url = judgment.get("url")
                if not url:
                    continue
                url_gh = tribunal.existing_mirror(merger_id, saved.get(url))
                if url_gh is None:
                    key = (merger_id, url)
                    if key not in cache:
                        try:
                            b = await browser.get()
                        except Exception as e:
                            print(f"    Warning: no browser for {url}: {e}", file=sys.stderr)
                            cache[key] = None
                        else:
                            print(f"    Following judgment {url}", flush=True)
                            cache[key] = await tribunal.download_judgment_page(b, merger_id, url)
                    url_gh = cache[key]
                if url_gh:
                    judgment["url_gh"] = url_gh
                else:
                    missing.append(url)
    return missing


# --- Run ---------------------------------------------------------------------


def _summary(data: dict) -> str:
    apps = data.get("applications") or []
    listings = sum(len(a.get("events") or []) for a in apps)
    documents = sum(len(a.get("documents") or []) for a in apps)
    parties = sum(len(a.get("parties") or []) for a in apps)
    return (
        f"{len(apps)} application(s), {listings} listing(s), "
        f"{documents} document(s) filed, {parties} part(y/ies)"
    )


async def scrape_reviews(
    targets: list[tuple[str, dict]], download: bool
) -> tuple[dict[int, dict], list[str], list[tuple[str, str]], list[tuple[str, str, dict]]]:
    """Fetch every target file. Returns ``(scraped, failed, unmirrored,
    dropped)``: ``scraped`` maps ``id(record)`` to its new ``portal`` block,
    ``failed`` labels the files that couldn't be fetched, ``unmirrored`` holds
    ``(label, url)`` for each order or judgment without a local copy, and
    ``dropped`` holds ``(label, application, doc)`` for each document kept
    although the portal no longer lists it."""
    session = portal.Session()
    browser = LazyBrowser()
    judgment_cache: dict[tuple[str, str], str | None] = {}
    scraped: dict[int, dict] = {}
    failed: list[str] = []
    unmirrored: list[tuple[str, str]] = []
    dropped: list[tuple[str, str, dict]] = []
    try:
        for mid, record in targets:
            label = review_label(mid, record)
            ref = file_ref(record)
            previous = record.get("portal")
            print(f"Scraping {label}: {portal.file_base_url(ref)}/actions", flush=True)
            try:
                data = portal.fetch_file(session, ref, previous)
            except Exception as e:
                print(f"  FAILED: {label}: {e!r}", file=sys.stderr)
                tribunal.gha_warning(f"scrape_federal_court: could not fetch {label}: {e}")
                failed.append(label)
                continue
            if (previous or {}).get("applications") and not data["applications"]:
                print(
                    f"  FAILED: {label} now has no applications; assuming a bad "
                    f"page and leaving the record untouched",
                    file=sys.stderr,
                )
                failed.append(label)
                continue
            print(f"  {_summary(data)}", flush=True)

            dropped.extend((label, app, doc) for app, doc in merge_filed_documents(previous, data))
            if download:
                missing = download_orders(session, mid, data, previous)
                missing += await download_judgments(browser, mid, data, previous, judgment_cache)
                if missing:
                    unmirrored.extend((label, url) for url in missing)
                    tribunal.gha_warning(
                        f"scrape_federal_court: {len(missing)} order(s)/judgment(s) "
                        f"for {label} were recorded without a local mirror: "
                        f"{tribunal.summarise_urls(missing)}"
                    )
            else:
                # Keep the mirrors already on file even when not downloading.
                for kind in ("orders", "judgments"):
                    saved = previous_url_gh(previous, kind)
                    for app in data["applications"]:
                        for event in app.get("events") or []:
                            for item in event.get(kind) or []:
                                if item.get("url") in saved:
                                    item["url_gh"] = saved[item["url"]]
            scraped[id(record)] = data
    finally:
        browser.close()
    return scraped, failed, unmirrored, dropped


def scrape(merger_ids: list[str] | None, dry_run: bool, download: bool = True) -> int:
    raw = load_reviews()
    records = {mid: v for mid, v in raw.items() if not mid.startswith("_")}

    if merger_ids:
        for mid in merger_ids:
            if mid not in records:
                print(f"Warning: {mid} is not in judicial_reviews.json", file=sys.stderr)
        selected = [mid for mid in merger_ids if mid in records]
    else:
        selected = list(records)

    # review_records doesn't copy, so updating a record updates ``raw``.
    targets = []
    for mid in selected:
        for record in review_records(records[mid]):
            if file_ref(record) is None:
                print(f"Skipping {review_label(mid, record)}: no case_url or case_number")
                continue
            targets.append((mid, record))
    if not targets:
        print("No Federal Court files to scrape.")
        return 0

    # nodriver wants its own loop, as in the tribunal scraper; without it
    # (no judgments can be fetched anyway) a plain one does.
    loop = tribunal.uc.loop() if tribunal.uc is not None else asyncio.new_event_loop()
    scraped, failed, unmirrored, dropped = loop.run_until_complete(
        scrape_reviews(targets, download=download and not dry_run)
    )

    changed = 0
    for _, record in targets:
        data = scraped.get(id(record))
        if data is not None and data != record.get("portal"):
            record["portal"] = data
            changed += 1

    if dry_run:
        print(f"\nDry run: {changed} file(s) would change; nothing written.")
    elif changed:
        write_reviews(raw)
        print(f"\nUpdated {changed} file(s) in {JUDICIAL_REVIEWS_JSON}")
    else:
        print("\nNo changes.")

    if dropped:
        print(
            f"\n{len(dropped)} document(s) filed are no longer listed on the "
            f"portal and were kept on file:",
            file=sys.stderr,
        )
        for label, app, doc in dropped:
            print(f"  {label} [{app}]: {doc.get('date') or '?'} — {doc.get('title')}", file=sys.stderr)
    if unmirrored:
        print(
            f"\n{len(unmirrored)} order(s)/judgment(s) recorded without a local "
            f"mirror (will be retried next run):",
            file=sys.stderr,
        )
        for label, url in unmirrored:
            print(f"  {label}: {url}", file=sys.stderr)
    if failed:
        print(
            f"\n{len(failed)} of {len(targets)} file(s) failed to fetch: {', '.join(failed)}",
            file=sys.stderr,
        )
        return 2
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "merger_ids",
        nargs="*",
        help="Optional merger_ids whose files to scrape (default: every file with a case_url or case_number).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch and report changes without writing the JSON or downloading files.",
    )
    parser.add_argument(
        "--no-download",
        action="store_true",
        help="Record the portal's tables only; do not download orders or judgments.",
    )
    args = parser.parse_args()
    return scrape(args.merger_ids or None, args.dry_run, download=not args.no_download)


if __name__ == "__main__":
    raise SystemExit(main())
