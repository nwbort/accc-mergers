"""Filing-time estimate of a merger's phase-1 review duration.

When a merger is filed we predict how long its phase-1 review will take, in
business days, from the history of *completed* phase-1 reviews in the same
industries. The estimate is computed once, frozen in a persisted store keyed by
merger_id (``data/processed/phase1_estimates.json``) and attached to every
enriched merger as ``phase_1_estimate`` so it flows into the individual
``mergers/{id}.json`` files and the master ``data/output/mergers.json``.

Method (see the backtest that justifies it in the PR/commit history)
--------------------------------------------------------------------
Phase-1 duration is dominated by the statutory process — most reviews land in a
tight 15-20 business-day band regardless of sector — so a raw class-level
median built on one or two observations is noisier than the whole-of-market
median. The estimate therefore uses **pooled medians with hierarchical
backoff**:

* A merger is usually tagged with several ANZSIC codes at several levels. Each
  tag is resolved up to every hierarchy level (class -> group -> subdivision ->
  division).
* Walking finest -> coarsest, we pool the durations of every completed
  notification merger that shares *any* of the target's industries at that
  level, and take the first level whose pool reaches ``MIN_SUPPORT``
  observations. Union-pooling across the target's industries handles the
  multi-industry case (weighting by data volume) instead of arbitrarily picking
  one code.
* If no level has enough data we fall back to the global median of all
  completed phase-1 reviews (``basis == "global"``).

Only notification (non-waiver) mergers get an estimate: waivers run on a
different track with no phase-1 clock. Durations are measured exactly as the
rest of the site measures them (notification -> phase-1 end, with referred
matters measured to the referral date) via
:func:`static_data.durations.phase_1_end_date`.
"""

import json
from datetime import date
from pathlib import Path
from statistics import median, quantiles

from cutoff import is_waiver_merger

from . import anzsic
from .business_days import calculate_business_days
from .durations import phase_1_end_date

# Finest -> coarsest. The estimate uses the finest level with enough support.
LEVELS = ("class", "group", "subdivision", "division")

# Minimum number of completed reviews a pool must contain before its median is
# trusted over the whole-of-market median. Chosen by leave-one-out backtest:
# lower thresholds overfit sparse industries and raise error; higher thresholds
# just collapse back to the global median. 8 minimised MAE on the current data.
MIN_SUPPORT = 8

# Bump when the estimate algorithm changes so stale frozen values are
# recognisable (and could be recomputed by clearing the store).
METHOD_VERSION = 1

SCRIPT_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = SCRIPT_DIR.parent
ESTIMATES_STORE_PATH = REPO_ROOT / "data" / "processed" / "phase1_estimates.json"

_STORE_COMMENT = (
    "Filing-time phase-1 duration estimates, frozen per merger_id when the "
    "merger is first seen with a notification date. Maintained by "
    "static_data.phase1_estimate via generate_static_data.py; do not hand-edit. "
    "Clear an entry (or the whole file) to force recomputation."
)


def resolve_level_codes(raw_codes: list[str]) -> dict[str, set[str]]:
    """Map a merger's tagged ANZSIC codes up to a set of codes at each level.

    A tag coarser than a given level (e.g. a subdivision tag has no class) can't
    be drilled down, so it contributes nothing at the finer level.
    """
    resolved: dict[str, set[str]] = {lvl: set() for lvl in LEVELS}
    for code in raw_codes:
        node = anzsic.get(code)
        if node is None:
            continue
        if node.level in resolved:
            resolved[node.level].add(node.code)
        for ancestor in anzsic.ancestors(code):
            if ancestor.level in resolved:
                resolved[ancestor.level].add(ancestor.code)
    return resolved


def _merger_codes(merger: dict) -> list[str]:
    return [c.get("code", "") for c in (merger.get("anzsic_codes") or []) if c.get("code")]


def build_completed_pool(mergers: list) -> list[dict]:
    """Return completed phase-1 notification reviews as prediction training rows.

    Each row is ``{"merger_id", "levels": {level: {codes}}, "business_days"}``.
    Waivers (no phase-1 clock) and still-open reviews are excluded.
    """
    pool = []
    for m in mergers:
        if is_waiver_merger(m):
            continue
        start = m.get("effective_notification_datetime")
        end = phase_1_end_date(m)
        if not (start and end):
            continue
        bd = calculate_business_days(start, end)
        if bd is None:
            continue
        pool.append(
            {
                "merger_id": m.get("merger_id"),
                "levels": resolve_level_codes(_merger_codes(m)),
                "business_days": bd,
            }
        )
    return pool


def _band(values: list[int]) -> list[int]:
    """A rough low-high band (p25-p75) for a pool of durations.

    Falls back to (min, max) when there are too few points for quartiles.
    """
    if len(values) < 2:
        return [min(values), max(values)]
    try:
        q = quantiles(values, n=4)  # [p25, p50, p75]
        return [round(q[0]), round(q[2])]
    except Exception:
        return [min(values), max(values)]


def compute_estimate(merger: dict, pool: list[dict], estimated_at: str) -> dict | None:
    """Compute the frozen phase-1 estimate for ``merger`` from ``pool``.

    Returns ``None`` for waivers, mergers without a notification date, or when
    there is no completed history at all to learn from. The merger itself is
    excluded from the pool so a backfilled (already-completed) merger never
    predicts from its own outcome.
    """
    if is_waiver_merger(merger):
        return None
    if not merger.get("effective_notification_datetime"):
        return None

    merger_id = merger.get("merger_id")
    others = [r for r in pool if r["merger_id"] != merger_id]
    all_durations = [r["business_days"] for r in others]
    if not all_durations:
        return None

    target_levels = resolve_level_codes(_merger_codes(merger))

    for level in LEVELS:
        target_codes = target_levels[level]
        if not target_codes:
            continue
        matched = [
            r["business_days"] for r in others if target_codes & r["levels"][level]
        ]
        if len(matched) >= MIN_SUPPORT:
            return {
                "expected_business_days": round(median(matched)),
                "range_business_days": _band(matched),
                "basis": "industry",
                "anzsic_level": level,
                "anzsic_codes": sorted(target_codes),
                "sample_size": len(matched),
                "estimated_at": estimated_at,
                "method_version": METHOD_VERSION,
            }

    # No level had enough industry history: fall back to the whole-of-market median.
    return {
        "expected_business_days": round(median(all_durations)),
        "range_business_days": _band(all_durations),
        "basis": "global",
        "anzsic_level": None,
        "anzsic_codes": [],
        "sample_size": len(all_durations),
        "estimated_at": estimated_at,
        "method_version": METHOD_VERSION,
    }


def load_store() -> dict:
    """Load the frozen estimates store, or an empty dict if absent/unreadable."""
    try:
        with open(ESTIMATES_STORE_PATH, encoding="utf-8") as f:
            data = json.load(f)
        return {k: v for k, v in data.items() if not k.startswith("_")}
    except FileNotFoundError:
        return {}
    except (json.JSONDecodeError, OSError) as e:
        print(f"Warning: could not load {ESTIMATES_STORE_PATH}: {e}")
        return {}


def save_store(store: dict) -> None:
    """Persist the frozen estimates store (sorted by merger_id, with a comment)."""
    ESTIMATES_STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {"_comment": _STORE_COMMENT}
    for merger_id in sorted(store):
        payload[merger_id] = store[merger_id]
    with open(ESTIMATES_STORE_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def attach_phase_1_estimates(
    enriched: list, store: dict | None = None, estimated_at: str | None = None
) -> tuple[int, int]:
    """Freeze + attach ``phase_1_estimate`` on each enriched merger in-place.

    New notification mergers (those not already in ``store``) get an estimate
    computed from the current completed-review history and frozen into the
    store; mergers already in the store keep their original frozen value so it
    reflects the filing-time prediction rather than drifting as data grows.

    Loads and saves ``data/processed/phase1_estimates.json`` when ``store`` is
    not supplied (the production path). Returns ``(newly_computed, attached)``.
    """
    manage_store = store is None
    if manage_store:
        store = load_store()
    estimated_at = estimated_at or date.today().isoformat()

    pool = build_completed_pool(enriched)

    newly_computed = 0
    attached = 0
    for merger in enriched:
        merger_id = merger.get("merger_id")
        if not merger_id:
            continue
        estimate = store.get(merger_id)
        if estimate is None:
            estimate = compute_estimate(merger, pool, estimated_at)
            if estimate is None:
                continue  # waiver / no notification date / no history yet
            store[merger_id] = estimate
            newly_computed += 1
        merger["phase_1_estimate"] = estimate
        attached += 1

    if manage_store:
        save_store(store)
    return newly_computed, attached
