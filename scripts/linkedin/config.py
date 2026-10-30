"""Credentials, author and on-disk state for the LinkedIn poster.

Everything comes from the environment. Unlike the ATProto identity there is
nothing public worth committing: the author URN is not secret, but it is only
meaningful next to the token that may post as it, so the two live together.

Two ways to authenticate, depending on which LinkedIn product the app has:

* ``LINKEDIN_ACCESS_TOKEN`` - a member access token, used as is. This is all a
  self-serve "Share on LinkedIn" app gets, and it lasts 60 days, after which
  the secret has to be replaced by hand (the run fails loudly when it expires).
* ``LINKEDIN_REFRESH_TOKEN`` with ``LINKEDIN_CLIENT_ID`` and
  ``LINKEDIN_CLIENT_SECRET`` - an app approved for the Community Management
  API gets programmatic refresh tokens, valid for a year, and each run mints
  its own access token from them. Wins over a plain access token when both
  are set.

A missing token or author is a *skip*, not an error, as for ntfy and ATProto.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from scripts.paths import REPO_ROOT

#: Milestones already posted to LinkedIn. Its own file rather than a second
#: key in ``atproto_posts.json``: the two accounts are switched on at
#: different times, so each seeds, and is caught up, independently.
POST_STATE_PATH = REPO_ROOT / "data" / "processed" / "linkedin_posts.json"

API_BASE = "https://api.linkedin.com/rest"
TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"

#: The ``LinkedIn-Version`` header every versioned call must carry, as YYYYMM.
#: LinkedIn sunsets each version about a year after release, after which calls
#: carrying it are refused - bump this (or set ``LINKEDIN_API_VERSION``) when
#: the run starts failing on it. The Posts and Images calls used here have not
#: changed shape across the versions in support at the time of writing.
DEFAULT_API_VERSION = "202609"


@dataclass(frozen=True)
class Credentials:
    """How to obtain an access token, and whom to post as."""

    author: str
    access_token: str = ""
    refresh_token: str = ""
    client_id: str = ""
    client_secret: str = ""

    @property
    def refreshable(self) -> bool:
        return bool(self.refresh_token and self.client_id and self.client_secret)


def load_credentials() -> Credentials | None:
    """The configured credentials, or ``None`` when posting cannot happen.

    ``LINKEDIN_AUTHOR_URN`` names who posts: ``urn:li:organization:{id}`` for a
    company page, ``urn:li:person:{id}`` for a member's own profile.
    """
    author = _env("LINKEDIN_AUTHOR_URN")
    creds = Credentials(
        author=author,
        access_token=_env("LINKEDIN_ACCESS_TOKEN"),
        refresh_token=_env("LINKEDIN_REFRESH_TOKEN"),
        client_id=_env("LINKEDIN_CLIENT_ID"),
        client_secret=_env("LINKEDIN_CLIENT_SECRET"),
    )
    if not author or not (creds.access_token or creds.refreshable):
        return None
    return creds


def api_version() -> str:
    return _env("LINKEDIN_API_VERSION") or DEFAULT_API_VERSION


def posting_enabled() -> bool:
    """Whether LinkedIn posting is switched on.

    A second switch on top of the credentials, for the same reason as
    ``ATPROTO_POST_ENABLED``: adding the step to a workflow, or setting the
    secret while testing the token, should not be the thing that starts posting.
    """
    return _env("LINKEDIN_POST_ENABLED").lower() in {"1", "true", "yes"}


def webhook_url() -> str:
    """Where ``scripts.linkedin.webhook`` hands each milestone, or ``""``.

    A Make.com (or Zapier, Pipedream, n8n) custom webhook whose scenario posts
    to the company page. The URL is the only credential - anyone holding it
    can post as the page - so it is a secret and is never printed.
    """
    return _env("LINKEDIN_WEBHOOK_URL")


def _env(name: str) -> str:
    return os.environ.get(name, "").strip()
