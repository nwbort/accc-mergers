"""HTTP requests to accc.gov.au."""

from __future__ import annotations

from curl_cffi import requests as _cffi

# Catch this before any IOError handler: it subclasses OSError.
RequestException = _cffi.exceptions.RequestException


def get(url: str, **kwargs) -> _cffi.Response:
    """GET ``url``. Accepts the usual requests-style kwargs."""
    return _cffi.get(url, impersonate='chrome', **kwargs)


def head(url: str, **kwargs) -> _cffi.Response:
    """Status and headers for ``url``, via a streamed GET closed before the body."""
    response = get(url, stream=True, **kwargs)
    response.close()
    return response
