"""Canonical merger loading and filtering helpers.

This module is the single source of truth for the predicates and loaders used
by every generator that reads ``data/processed/mergers.json``. Historically
the same filtering logic was reimplemented inline in
``generate_static_data.py``, ``generate_weekly_digest.py``,
``generate_rss_feed.py`` and ``generate_sitemap.py``; each copy drifted
subtly, which is a bug surface. This module centralises it.

Canonical status strings live in :mod:`constants.merger_status` — do not
duplicate them here; always compare against the named constants.

Public API
----------
Loaders:
    :func:`load_mergers`

Predicates (single-merger):
    :func:`is_waiver`
    :func:`is_suspended`
    :func:`is_public_visible`

List filters:
    :func:`filter_public`
    :func:`filter_waivers`
    :func:`filter_notifications`
    :func:`filter_suspended`

The static-data package re-exports these from :mod:`static_data.filters` for
backwards compatibility.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, List, Optional, Union

from constants import merger_status

#: Default location of the processed mergers JSON, relative to the repo root.
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
DEFAULT_MERGERS_JSON = REPO_ROOT / "data" / "processed" / "mergers.json"


def load_mergers(path: Optional[Union[str, Path]] = None) -> List[dict]:
    """Load merger records from the processed JSON file.

    This is the single canonical loader for
    ``data/processed/mergers.json`` (or any equivalent override). All
    generators should call this rather than opening the file themselves.

    Accepts both historical on-disk shapes:

    * a top-level JSON list of merger dicts, or
    * a dict of the form ``{"mergers": [...]}``.

    Args:
        path: Optional path to a mergers JSON file. Defaults to
            ``data/processed/mergers.json`` at the repo root.

    Returns:
        A list of merger dicts in whatever order they appear on disk.

    Raises:
        ValueError: if the file exists but is not in a recognised shape.
        FileNotFoundError / json.JSONDecodeError: propagated unchanged so
            callers can decide how to handle missing / malformed data.
    """
    target = Path(path) if path is not None else DEFAULT_MERGERS_JSON
    with open(target, "r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, list):
        return data
    if isinstance(data, dict) and "mergers" in data:
        return data["mergers"]
    raise ValueError(
        f"Unexpected mergers.json format at {target!s}: "
        "expected a list or a dict with a 'mergers' key"
    )


# ---------------------------------------------------------------------------
# Single-merger predicates
# ---------------------------------------------------------------------------


def is_waiver(merger: dict) -> bool:
    """Return True if the merger is a waiver application.

    Reads the enriched ``is_waiver`` boolean that
    :func:`static_data.enrichment.enrich_merger` writes (itself computed by
    :func:`cutoff.is_waiver_merger`, which looks at the ``WA-`` ID prefix or
    the ``'Waiver'`` stage string — see :data:`constants.merger_status.WAIVER`).

    Safe to call on raw (un-enriched) mergers: the value is also written by
    ``extract_mergers.py`` into ``data/processed/mergers.json``.
    """
    return bool(merger.get("is_waiver", False))


def is_suspended(merger: dict) -> bool:
    """Return True if the merger's assessment has been suspended.

    Matches ``merger['status'] ==``
    :data:`constants.merger_status.ASSESSMENT_SUSPENDED` (``'Assessment
    suspended'``). A suspended assessment is paused (e.g. awaiting
    information from parties) and should not appear in curated public
    activity streams.
    """
    return merger.get("status") == merger_status.ASSESSMENT_SUSPENDED


def is_public_visible(merger: dict) -> bool:
    """Return True if the merger belongs in curated public activity streams.

    "Public" here means *curated* feeds such as the upcoming-events widget
    — not "has a publicly-reachable URL". The detail page
    ``/mergers/<id>`` exists and is served regardless of this predicate;
    the sitemap therefore intentionally does *not* use this filter.

    A merger is publicly visible when it is a genuine notification review
    whose assessment is still active — i.e. not a waiver
    (:func:`is_waiver`) and not suspended (:func:`is_suspended`).

    Note: the weekly digest and RSS feed deliberately use the less
    restrictive :func:`filter_active` instead of this predicate — they
    include waivers as part of substantive ACCC activity. See those
    generators' module docstrings.
    """
    return not is_waiver(merger) and not is_suspended(merger)


# ---------------------------------------------------------------------------
# List filters
# ---------------------------------------------------------------------------


def filter_public(mergers: Iterable[dict]) -> List[dict]:
    """Return only mergers that pass :func:`is_public_visible`.

    Used by the upcoming-events widget, which only surfaces substantive
    non-waiver, non-suspended mergers. The digest and RSS feed use the
    less restrictive :func:`filter_active` (waivers included).

    Preserves input order.
    """
    return [m for m in mergers if is_public_visible(m)]


def filter_active(mergers: Iterable[dict]) -> List[dict]:
    """Return only mergers whose assessment is not suspended.

    "Active" here means the ACCC has not paused the review — this
    includes both :data:`constants.merger_status.UNDER_ASSESSMENT` and
    :data:`constants.merger_status.ASSESSMENT_COMPLETED` records, and it
    includes waivers. It is the filter used by curated *activity* feeds
    (weekly digest, RSS feed) where waiver grants / denials are
    legitimate ACCC activity worth surfacing.

    Preserves input order.
    """
    return [m for m in mergers if not is_suspended(m)]


def filter_waivers(mergers: Iterable[dict]) -> List[dict]:
    """Return only the waiver mergers from ``mergers``."""
    return [m for m in mergers if is_waiver(m)]


def filter_notifications(mergers: Iterable[dict]) -> List[dict]:
    """Return only non-waiver (notification) mergers from ``mergers``.

    Together with :func:`filter_waivers` this partitions the input.
    """
    return [m for m in mergers if not is_waiver(m)]


def filter_suspended(mergers: Iterable[dict]) -> List[dict]:
    """Return only mergers whose assessment has been suspended."""
    return [m for m in mergers if is_suspended(m)]


# Backwards-compatible alias for the name originally used by
# static_data.filters. New code should use filter_public.
exclude_for_public_output = filter_public


__all__ = [
    "DEFAULT_MERGERS_JSON",
    "load_mergers",
    "is_waiver",
    "is_suspended",
    "is_public_visible",
    "filter_public",
    "filter_active",
    "filter_waivers",
    "filter_notifications",
    "filter_suspended",
    "exclude_for_public_output",
]
