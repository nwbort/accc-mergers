"""Predicates and list filters for segmenting enriched mergers.

These replace the inline list comprehensions that used to live in
``generate_stats_json`` and ``generate_analysis_json`` (the notification/waiver
split) and in ``generate_upcoming_events_json`` (exclude waivers + suspended).

All filters expect *enriched* mergers — specifically, ``is_waiver`` must have
been set by :func:`static_data.enrichment.enrich_merger`.
"""

from constants import merger_status


def is_waiver(merger: dict) -> bool:
    """Return True if the merger has been tagged as a waiver application."""
    return bool(merger.get('is_waiver', False))


def is_suspended(merger: dict) -> bool:
    """Return True if the merger's assessment has been suspended."""
    return merger.get('status') == merger_status.ASSESSMENT_SUSPENDED


def filter_waivers(mergers: list) -> list:
    """Return only the waiver mergers from ``mergers``."""
    return [m for m in mergers if is_waiver(m)]


def filter_notifications(mergers: list) -> list:
    """Return only non-waiver (notification) mergers from ``mergers``."""
    return [m for m in mergers if not is_waiver(m)]


def filter_suspended(mergers: list) -> list:
    """Return only mergers whose assessment has been suspended."""
    return [m for m in mergers if is_suspended(m)]


def exclude_for_public_output(mergers: list) -> list:
    """Exclude waivers and suspended mergers.

    This is the combined predicate used by generators that should only show
    "live" notification mergers to the public (e.g. the upcoming-events feed).
    """
    return [m for m in mergers if not is_waiver(m) and not is_suspended(m)]
