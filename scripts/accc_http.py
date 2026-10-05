"""HTTP access to accc.gov.au that its Akamai edge will answer.

From 2026-10-05 the ACCC's CDN answers anything that doesn't look like a web
browser with a 403 "Access Denied" page. A probe of the register from GitHub
runners (see the history of scripts/scrape/probe_access.py) found it checks
three things, all of which have to pass:

- the User-Agent must be a plain browser one: a bot or self-identifying UA
  (the old ``mergers-fyi/1.0``, Googlebot, curl's default) is refused even with
  every other header right, as is a browser UA with anything appended;
- at least one ``Sec-Fetch-*`` header must be sent, as every modern browser
  does on a navigation;
- the TLS handshake must look like a browser's: python-requests is refused
  even with a complete set of Chrome headers, while curl and curl_cffi pass.

curl_cffi's ``impersonate="chrome"`` satisfies all three (it sends Chrome's
headers and reproduces Chrome's TLS fingerprint), so every Python request to
the ACCC goes through here. ``scripts/scrape/scrape.sh`` does the same for its
curl calls via ``accc_curl``.
"""

from __future__ import annotations

from curl_cffi import requests as _cffi

IMPERSONATE = 'chrome'

# curl_cffi's base exception subclasses OSError, not requests'. Catch this
# explicitly *before* any IOError handler, or a refused download reads as a
# failure to write the file.
RequestException = _cffi.exceptions.RequestException


def get(url: str, **kwargs) -> _cffi.Response:
    """GET ``url`` as Chrome would. Accepts the usual requests-style kwargs."""
    return _cffi.get(url, impersonate=IMPERSONATE, **kwargs)


def head(url: str, **kwargs) -> _cffi.Response:
    """Status and headers for ``url``, without its body.

    Not a real HEAD: the ACCC's CDN refuses curl_cffi's HEAD requests (403)
    while answering the same request as a GET, so this opens a streamed GET and
    closes it once the headers are in. Safe to call from several threads at
    once, unlike a shared curl_cffi Session.
    """
    response = _cffi.get(url, impersonate=IMPERSONATE, stream=True, **kwargs)
    response.close()
    return response
