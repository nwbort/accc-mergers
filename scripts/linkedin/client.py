"""A small client for the four LinkedIn REST calls the poster needs.

Hand-rolled on ``requests`` for the same reason as the XRPC client: mint an
access token, upload an image, create a post and list the author's own posts
are all there is, and there is no official Python SDK worth installing on
every pipeline run for them.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from urllib.parse import quote

import requests

from scripts.linkedin import config

TIMEOUT = 30
MAX_ATTEMPTS = 4
MAX_BACKOFF = 60


class LinkedInError(RuntimeError):
    """A LinkedIn call failed. ``status`` is the HTTP status, where there was one."""

    def __init__(self, message: str, *, status: int | None = None):
        super().__init__(message)
        self.status = status


def mint_access_token(creds: config.Credentials, http: requests.Session | None = None) -> str:
    """An access token: refreshed from the refresh token when there is one,
    else the configured access token as is."""
    if not creds.refreshable:
        return creds.access_token
    http = http or requests.Session()
    try:
        response = http.post(
            config.TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "refresh_token": creds.refresh_token,
                "client_id": creds.client_id,
                "client_secret": creds.client_secret,
            },
            timeout=TIMEOUT,
        )
    except requests.RequestException as exc:
        raise LinkedInError(f"token refresh failed: {exc}") from exc
    if response.status_code != 200:
        raise LinkedInError(
            f"token refresh failed ({response.status_code}): {_message(response)}",
            status=response.status_code,
        )
    return response.json()["access_token"]


@dataclass
class LinkedInClient:
    """Authenticated client posting as one author."""

    access_token: str
    author: str
    version: str = field(default_factory=config.api_version)
    pause: float = 0.0
    http: requests.Session = field(default_factory=requests.Session)

    def upload_image(self, data: bytes) -> str:
        """Upload a PNG and return its ``urn:li:image:`` URN."""
        payload = self._request(
            "POST",
            "/images?action=initializeUpload",
            json={"initializeUploadRequest": {"owner": self.author}},
        ).json()
        value = payload.get("value") or {}
        upload_url, image = value.get("uploadUrl"), value.get("image")
        if not upload_url or not image:
            raise LinkedInError("initializeUpload returned no upload URL")
        try:
            response = self.http.put(
                upload_url,
                data=data,
                headers={
                    "Authorization": f"Bearer {self.access_token}",
                    "Content-Type": "application/octet-stream",
                },
                timeout=TIMEOUT,
            )
        except requests.RequestException as exc:
            raise LinkedInError(f"image upload failed: {exc}") from exc
        if response.status_code >= 300:
            raise LinkedInError(
                f"image upload failed ({response.status_code})", status=response.status_code
            )
        return image

    def create_post(self, post: dict) -> str:
        """Create a post and return its URN (``urn:li:share:...``)."""
        response = self._request("POST", "/posts", json=post)
        if self.pause:
            time.sleep(self.pause)
        return response.headers.get("x-restli-id", "")

    def list_posts(self, count: int = 100) -> list[dict]:
        """The author's own most recent posts, newest first.

        Needs ``r_organization_social`` for a page, or the restricted
        ``r_member_social`` for a person - which a self-serve app does not
        get, so the caller has to cope with a 403 here.
        """
        path = (
            f"/posts?author={quote(self.author, safe='')}&q=author"
            f"&count={count}&sortBy=CREATED"
        )
        response = self._request("GET", path, headers={"X-RestLi-Method": "FINDER"})
        return response.json().get("elements") or []

    def _request(self, method: str, path: str, *, json=None, headers=None) -> requests.Response:
        all_headers = {
            "Authorization": f"Bearer {self.access_token}",
            "LinkedIn-Version": self.version,
            "X-Restli-Protocol-Version": "2.0.0",
        }
        all_headers.update(headers or {})
        url = config.API_BASE + path
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                response = self.http.request(
                    method, url, json=json, headers=all_headers, timeout=TIMEOUT
                )
            except requests.RequestException as exc:
                if attempt == MAX_ATTEMPTS:
                    raise LinkedInError(f"{method} {path} failed: {exc}") from exc
                time.sleep(2**attempt)
                continue
            if response.status_code < 300:
                return response
            retryable = response.status_code == 429 or response.status_code >= 500
            if not retryable or attempt == MAX_ATTEMPTS:
                raise LinkedInError(
                    f"{method} {path} failed ({response.status_code}): {_message(response)}",
                    status=response.status_code,
                )
            time.sleep(min(_retry_after(response, 2**attempt), MAX_BACKOFF))
        raise AssertionError("unreachable")


def _retry_after(response: requests.Response, default: float) -> float:
    try:
        return float(response.headers.get("Retry-After", default))
    except ValueError:
        return default


def _message(response: requests.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        return response.text[:200]
    return str(body.get("message") or body.get("error_description") or body)[:200]
