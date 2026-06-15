"""Human-readable URL slugs for merger detail pages.

The slug is purely decorative — merger pages are always looked up by their
``merger_id`` (e.g. ``MN-01016``). The slug exists for SEO/readability, so the
algorithm here MUST stay in sync with the JavaScript implementation in
``merger-tracker/frontend/src/utils/slug.js`` (used for rendered links and
canonical tags) and the inline copy in
``functions/mergers/[matter]/[[path]].js`` (used by the social-bot OG handler).
If these diverge, the sitemap, canonical tags and rendered URLs disagree.
"""

import re

MAX_SLUG_LENGTH = 80

_NON_ALNUM = re.compile(r"[^a-z0-9]+")
_TRAILING_HYPHENS = re.compile(r"-+$")


def slugify(name: str) -> str:
    """Convert a merger name into a lowercase, hyphen-separated slug.

    Returns an empty string when no usable characters remain.
    """
    if not name:
        return ""
    slug = _NON_ALNUM.sub("-", str(name).lower())
    slug = slug.strip("-")
    slug = slug[:MAX_SLUG_LENGTH]
    slug = _TRAILING_HYPHENS.sub("", slug)
    return slug


def merger_path(merger_id: str, name: str) -> str:
    """Build the canonical path for a merger detail page.

    Includes the readable slug when one can be derived, otherwise falls back to
    the bare ``/mergers/{id}`` form.
    """
    slug = slugify(name)
    return f"/mergers/{merger_id}/{slug}" if slug else f"/mergers/{merger_id}"
