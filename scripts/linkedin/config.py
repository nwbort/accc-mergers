"""Configuration and on-disk state for LinkedIn posting.

Posts reach LinkedIn through a Make.com scenario (``scripts.linkedin.webhook``),
which holds the LinkedIn connection, so the only credentials here are the
webhook's URL and API key. Both come from the environment, and a missing URL
is a *skip*, not an error, as for ntfy and ATProto.
"""

from __future__ import annotations

import os

from scripts.paths import REPO_ROOT

#: Milestones already sent to LinkedIn. Its own file rather than a second
#: key in ``atproto_posts.json``: the two accounts were switched on at
#: different times, so each seeds, and is caught up, independently.
POST_STATE_PATH = REPO_ROOT / "data" / "processed" / "linkedin_posts.json"


def webhook_url() -> str:
    """Where ``scripts.linkedin.webhook`` hands each milestone, or ``""``.

    A Make.com custom webhook whose scenario posts to the company page. The
    URL is the only credential - anyone holding it can post as the page - so
    it is a secret and is never printed.
    """
    return _env("LINKEDIN_WEBHOOK_URL")


def webhook_api_key() -> str:
    """The key a Make webhook with API key authentication expects, or ``""``.

    Sent as the ``x-make-apikey`` header. A secret like the URL, never printed.
    """
    return _env("LINKEDIN_WEBHOOK_API_KEY")


def _env(name: str) -> str:
    return os.environ.get(name, "").strip()
