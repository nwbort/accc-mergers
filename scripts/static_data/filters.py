"""Predicates and list filters for segmenting enriched mergers.

The canonical implementations now live in :mod:`merger_filters` so that
every generator in ``scripts/`` can share a single source of truth. This
module re-exports them unchanged for backwards compatibility with the
static-data package's existing callers.

All filters expect *enriched* mergers — specifically, ``is_waiver`` must have
been set by :func:`static_data.enrichment.enrich_merger` (the raw
``data/processed/mergers.json`` also carries the flag, written by
``extract_mergers.py``).
"""

from merger_filters import (
    exclude_for_public_output,
    filter_notifications,
    filter_public,
    filter_suspended,
    filter_waivers,
    is_public_visible,
    is_suspended,
    is_waiver,
)

__all__ = [
    "is_waiver",
    "is_suspended",
    "is_public_visible",
    "filter_waivers",
    "filter_notifications",
    "filter_suspended",
    "filter_public",
    "exclude_for_public_output",
]
