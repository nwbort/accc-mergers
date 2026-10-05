"""Temporary probe: which request shapes can still reach accc.gov.au from CI?

The ACCC's Akamai edge began answering the pipeline's scraper with a 403
"Access Denied" on 2026-10-05. This tries a matrix of clients, User-Agents,
header sets, referers, HTTP versions and IP families against the register (and
a few other URLs) and prints a table, so we can tell an IP block from a
fingerprint/header block. Not part of the pipeline; delete once diagnosed.

Run: python -m scripts.scrape.probe_access  (browser probes need xvfb-run)
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import subprocess
import time
from dataclasses import dataclass

REGISTER = ("https://www.accc.gov.au/public-registers/acquisitions-and-mergers-registers/"
            "acquisitions-register?init=1&items_per_page=50")
OTHER_URLS = {
    "home": "https://www.accc.gov.au/",
    "home-apex": "https://accc.gov.au/",
    "robots": "https://www.accc.gov.au/robots.txt",
    "matter": ("https://www.accc.gov.au/public-registers/acquisitions-and-mergers-registers/"
               "acquisitions-register/asahi-%E2%80%93-warehouse-site-on-tilburn-rd-deer-park-vic"),
    "pdf": ("https://www.accc.gov.au/system/files/public-merger-register/documents/"
            "Asahi%20warehouse%20lease%20-%20Determination%20-%20September%205.pdf"),
    "register-bare": ("https://www.accc.gov.au/public-registers/acquisitions-and-mergers-registers/"
                      "acquisitions-register"),
}

UAS = {
    "current": "Mozilla/5.0 (compatible; mergers-fyi/1.0; +https://mergers.fyi)",
    "chrome-win": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"),
    "chrome-mac": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"),
    "firefox": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:143.0) Gecko/20100101 Firefox/143.0",
    "safari": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
               "(KHTML, like Gecko) Version/18.6 Safari/605.1.15"),
    "iphone": ("Mozilla/5.0 (iPhone; CPU iPhone OS 18_6 like Mac OS X) AppleWebKit/605.1.15 "
               "(KHTML, like Gecko) Version/18.6 Mobile/15E148 Safari/604.1"),
    "googlebot": "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
    "bingbot": "Mozilla/5.0 (compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm)",
    "curl": None,  # curl's own default UA
    "empty": "",
}

BROWSER_HEADERS = [
    "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language: en-AU,en;q=0.9",
    "Upgrade-Insecure-Requests: 1",
    "Sec-Fetch-Dest: document",
    "Sec-Fetch-Mode: navigate",
    "Sec-Fetch-Site: none",
    "Sec-Fetch-User: ?1",
]
CHROME_CH = [
    'sec-ch-ua: "Chromium";v="140", "Not=A?Brand";v="24", "Google Chrome";v="140"',
    "sec-ch-ua-mobile: ?0",
    'sec-ch-ua-platform: "Windows"',
]
REFERERS = {
    "google": "https://www.google.com/",
    "accc-home": "https://www.accc.gov.au/",
    "accc-registers": "https://www.accc.gov.au/public-registers/acquisitions-and-mergers-registers",
    "bing": "https://www.bing.com/",
}


@dataclass
class Result:
    label: str
    status: str
    size: int
    title: str
    cards: int


def summarise(body: str) -> tuple[str, int]:
    m = re.search(r"<title[^>]*>(.*?)</title>", body, re.I | re.S)
    title = re.sub(r"\s+", " ", m.group(1)).strip()[:60] if m else ""
    return title, body.count("accc-collapsed-card__header")


def curl(label: str, url: str, ua: str | None, headers: list[str] = (),
         extra: list[str] = ()) -> Result:
    cmd = ["curl", "-s", "-L", "--compressed", "--max-time", "25",
           "-o", "/tmp/probe_body", "-w", "%{http_code} %{http_version} %{remote_ip}"]
    if ua is not None:
        cmd += ["-A", ua]
    for h in headers:
        cmd += ["-H", h]
    cmd += list(extra) + [url]
    out = subprocess.run(cmd, capture_output=True, text=True).stdout.strip()
    try:
        body = open("/tmp/probe_body", encoding="utf-8", errors="replace").read()
    except FileNotFoundError:
        body = ""
    title, cards = summarise(body)
    return Result(label, out or "ERR", len(body), title, cards)


def curl_cffi_probe(label: str, url: str, impersonate: str, referer: str | None = None) -> Result:
    try:
        from curl_cffi import requests as cr
        headers = {"Referer": referer} if referer else {}
        r = cr.get(url, impersonate=impersonate, timeout=25, headers=headers)
        title, cards = summarise(r.text)
        return Result(label, f"{r.status_code} {r.http_version}", len(r.text), title, cards)
    except Exception as e:  # noqa: BLE001 - a probe; report and carry on
        return Result(label, f"ERR {type(e).__name__}", 0, str(e)[:60], 0)


def requests_probe(label: str, url: str) -> Result:
    try:
        import requests
        h = dict(x.split(": ", 1) for x in BROWSER_HEADERS + CHROME_CH)
        h["User-Agent"] = UAS["chrome-win"]
        r = requests.get(url, headers=h, timeout=25)
        title, cards = summarise(r.text)
        return Result(label, str(r.status_code), len(r.text), title, cards)
    except Exception as e:  # noqa: BLE001
        return Result(label, f"ERR {type(e).__name__}", 0, str(e)[:60], 0)


async def browser_probes(results: list[Result]) -> None:
    try:
        import nodriver as uc
    except ImportError as e:
        results.append(Result("nodriver", f"ERR {e}", 0, "", 0))
        return
    chrome = os.environ.get("CHROME_PATH") or None
    for headless in (False, True):
        tag = "headless" if headless else "headful"
        try:
            browser = await uc.start(headless=headless, browser_executable_path=chrome,
                                     sandbox=False)
            # Warm up on the homepage first, as a person would arrive.
            for name, url in (("home", OTHER_URLS["home"]), ("register", REGISTER),
                              ("matter", OTHER_URLS["matter"])):
                tab = await browser.get(url)
                await asyncio.sleep(8)  # let any JS challenge (Akamai sensor) run
                body = await asyncio.wait_for(tab.get_content(), 30)
                title, cards = summarise(body)
                results.append(Result(f"nodriver {tag} {name}", "-", len(body), title, cards))
            browser.stop()
        except Exception as e:  # noqa: BLE001
            results.append(Result(f"nodriver {tag}", f"ERR {type(e).__name__}", 0,
                                  str(e)[:60], 0))


def main() -> None:
    print("== Egress ==")
    for svc in ("https://ipinfo.io/json", "https://api64.ipify.org?format=json"):
        r = subprocess.run(["curl", "-s", "--max-time", "10", svc], capture_output=True, text=True)
        print(svc, "->", r.stdout.strip().replace("\n", " ")[:400])
    print()

    results: list[Result] = []
    full = BROWSER_HEADERS + CHROME_CH

    def add(r: Result) -> None:
        results.append(r)
        print(f"{r.label:55} {r.status:22} {r.size:>8} cards={r.cards:<3} {r.title}", flush=True)
        time.sleep(0.7)  # be gentle; a rate limit would muddy the results

    # 1. Every UA, bare and with full browser headers.
    for name, ua in UAS.items():
        add(curl(f"curl ua={name}", REGISTER, ua))
        add(curl(f"curl ua={name} +browser-headers", REGISTER, ua, full))
    # 1b. Narrowed in a local bisect: a browser UA plus a single Sec-Fetch-*
    # header passed, while any bot/self-identifying UA failed even with them.
    sfm = ["Sec-Fetch-Mode: navigate"]
    add(curl("curl chrome +Sec-Fetch-Mode only", REGISTER, UAS["chrome-win"], sfm))
    add(curl("curl chrome +Sec-Fetch-Dest only", REGISTER, UAS["chrome-win"],
             ["Sec-Fetch-Dest: document"]))
    add(curl("curl chrome (no extra headers)", REGISTER, UAS["chrome-win"]))
    add(curl("curl current +Sec-Fetch-Mode", REGISTER, UAS["current"], sfm))
    add(curl("curl chrome+mergers-fyi suffix +Sec-Fetch-Mode", REGISTER,
             UAS["chrome-win"] + " mergers-fyi/1.0 (+https://mergers.fyi)", sfm))
    add(curl("curl empty UA +sec-ch-ua +Sec-Fetch-Mode", REGISTER, "", CHROME_CH + sfm))
    add(curl("curl chrome +Sec-Fetch-Mode url=matter-real", OTHER_URLS["matter"],
             UAS["chrome-win"], sfm))
    # 2. Referers on a browser-looking request.
    for name, ref in REFERERS.items():
        add(curl(f"curl chrome +headers referer={name}", REGISTER, UAS["chrome-win"],
                 full + [f"Referer: {ref}", "Sec-Fetch-Site: cross-site"]))
        add(curl(f"curl current referer={name}", REGISTER, UAS["current"], [f"Referer: {ref}"]))
    # 3. Transport variations.
    for name, extra in {"http1.1": ["--http1.1"], "http2": ["--http2"], "ipv4": ["-4"],
                        "ipv6": ["-6"], "tls1.3": ["--tlsv1.3"]}.items():
        add(curl(f"curl chrome +headers {name}", REGISTER, UAS["chrome-win"], full, extra))
    # 4. Other URLs (is it the whole site, or just the register?).
    for name, url in OTHER_URLS.items():
        add(curl(f"curl current url={name}", url, UAS["current"]))
        add(curl(f"curl chrome +headers url={name}", url, UAS["chrome-win"], full))
    add(curl("curl current http:// (no TLS)", REGISTER.replace("https://", "http://"),
             UAS["current"], extra=["--max-redirs", "0"]))
    # 5. Other clients.
    add(requests_probe("python-requests chrome +headers", REGISTER))
    for imp in ("chrome", "chrome131", "chrome136", "edge101", "safari", "safari_ios",
                "firefox", "firefox135"):
        add(curl_cffi_probe(f"curl_cffi impersonate={imp}", REGISTER, imp))
    add(curl_cffi_probe("curl_cffi chrome referer=google", REGISTER, "chrome", REFERERS["google"]))
    add(curl_cffi_probe("curl_cffi chrome url=home", OTHER_URLS["home"], "chrome"))

    browser_results: list[Result] = []
    asyncio.run(browser_probes(browser_results))
    for r in browser_results:
        add(r)

    # Markdown table for the step summary.
    lines = ["## accc.gov.au access probe", "",
             "| Probe | Status | Bytes | Cards | Title |", "|---|---|---:|---:|---|"]
    for r in results:
        ok = " ✅" if r.cards else ""
        lines.append(f"| {r.label}{ok} | {r.status} | {r.size} | {r.cards} | "
                     f"{r.title.replace('|', '/')} |")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a") as f:
            f.write("\n".join(lines) + "\n")
    with open("probe-results.json", "w") as f:
        json.dump([r.__dict__ for r in results], f, indent=1)
    winners = [r.label for r in results if r.cards]
    print("\n== Probes that got the register listing ==")
    print("\n".join(winners) or "NONE")


if __name__ == "__main__":
    main()
