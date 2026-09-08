"""Filing-time estimate of a merger's phase-1 review duration.

When a merger is filed we predict how long its phase-1 review will take, in
business days, from the history of *completed* phase-1 reviews. The estimate is
computed once, frozen in a persisted store keyed by merger_id
(``data/processed/phase1_estimates.json``) and attached to every enriched
merger as ``phase_1_estimate`` so it flows into the individual
``mergers/{id}.json`` files and the master ``data/output/mergers.json``.

Method (v2): pool on questionnaire size
---------------------------------------
The ACCC publishes a consultation questionnaire for essentially every
notification, and it lands almost immediately — a median of **1 business day**
after the notification date, and within 3 for every matter on the register. How
many questions it asks turns out to be the strongest filing-time signal of how
long the review will run (Spearman rho = +0.45 against phase-1 business days),
because it reveals the ACCC's own opening read on the matter's complexity.

Matters are therefore pooled by **question count** into four buckets (see
``QUESTION_BUCKETS``) and the estimate is the median of the peers in the
target's bucket, with a whole-of-market median as the fallback when a bucket is
thin. The band is the pool's p25-p75.

Why not ANZSIC (the v1 method)
------------------------------
v1 pooled on industry, with hierarchical backoff through the ANZSIC tree. A
forward-chained backtest over the register showed that method performing
*worse* than a plain global median (MAE 4.80 vs 4.42 business days): phase-1
duration is driven by the statutory clock and by case complexity, not by
sector, so industry pooling was adding variance rather than signal. Pooling on
questionnaire size scores 4.22 — an improvement over v1 of 0.58 business days
(95% CI [+0.30, +0.88], paired bootstrap), and it also tightens the published
band: p25-p75 built on a questionnaire bucket contains the eventual actual
71.9% of the time at a median width of 4 business days, against 54.3% at 5 days
for the industry pools. Industry adds nothing further on top of questionnaire
size, so it is gone from the estimator entirely.

Trimming the pool was tested and deliberately not adopted: the point estimate
is a median, which is already outlier-robust, so dropping the top 1-3 or the
top 5-10% of each pool moves MAE by less than the noise floor (3.86-3.92
against 3.88 untrimmed). Trimming also worsens an existing bias — durations are
right-skewed (median 18, mean 20.2, max 59) so every median-based estimate
already under-predicts by ~3 business days on average, and trimming pushes it
further down.

Forward-chaining discipline
---------------------------
An estimate may only be built from reviews that had already *concluded* when
the target was filed. :func:`compute_estimate` enforces this by filtering the
pool on ``phase_1_end < notification date`` rather than merely excluding the
target itself, so the value is reproducible, is honest about what was knowable
at filing time, and means a historical recompute (e.g. this v1 -> v2 migration)
cannot quietly train on the future. The cutoff is recorded on each estimate as
``as_of``.

The cost is that the earliest matters on the register have too little history
behind them to support any estimate and get ``None``. That is invisible on the
site — ``MergerTimeline`` renders the forecast only while a matter is still
open — and is the correct answer for a matter nobody could have forecast.

Only notification (non-waiver) mergers get an estimate: waivers run on a
different track with no phase-1 clock. Durations are measured exactly as the
rest of the site measures them (notification -> phase-1 end, with referred
matters measured to the referral date) via
:func:`static_data.durations.phase_1_end_date`.
"""

import json
from datetime import date
from statistics import median, quantiles

from scripts.cutoff import is_waiver_merger
from scripts.paths import REPO_ROOT

from .business_days import calculate_business_days
from .durations import phase_1_end_date

# Inclusive upper bounds on question count, finest -> coarsest, each paired with
# its published label. A count above the last bound falls into OVERFLOW_BUCKET.
# Cut points chosen by leave-one-out backtest: 3|5|9 beat 3, 3|6, 3|4|6|9 and a
# nearest-neighbour pool on the raw count. Three questions is the ACCC's
# boilerplate questionnaire and covers ~69% of matters.
QUESTION_BUCKETS = ((3, "3 or fewer"), (5, "4-5"), (9, "6-9"))
OVERFLOW_BUCKET = "10 or more"

# Minimum number of completed reviews a pool must contain before its median is
# trusted. Applies both to a question bucket (below it, the estimate backs off
# to the whole-of-market median) and to the whole-of-market pool itself (below
# it, there is not yet enough history to forecast anything and the estimate is
# withheld).
MIN_SUPPORT = 8

# Bump when the estimate algorithm changes. Entries in the store carrying an
# older version are recomputed on the next run; because compute_estimate is
# forward-chained, that recompute reproduces the filing-time value rather than
# leaking hindsight into the history.
METHOD_VERSION = 2

ESTIMATES_STORE_PATH = REPO_ROOT / "data" / "processed" / "phase1_estimates.json"

_STORE_COMMENT = (
    "Filing-time phase-1 duration estimates, frozen per merger_id when the "
    "merger is first seen with a notification date. Maintained by "
    "static_data.phase1_estimate via generate_static_data.py; do not hand-edit. "
    "Clear an entry (or the whole file) to force recomputation."
)


def question_bucket(count: int | None) -> str | None:
    """Label the question-count bucket ``count`` falls in, or ``None`` if unknown."""
    if count is None:
        return None
    for upper, label in QUESTION_BUCKETS:
        if count <= upper:
            return label
    return OVERFLOW_BUCKET


def question_counts_from(questionnaire_data: dict | None) -> dict[str, int]:
    """Map merger_id -> number of questions in its consultation questionnaire.

    Mergers whose questionnaire has no parsed questions are omitted rather than
    recorded as zero: an unparsed questionnaire is missing data, not a matter
    the ACCC asked nothing about.
    """
    counts: dict[str, int] = {}
    for merger_id, record in (questionnaire_data or {}).items():
        if merger_id.startswith("_") or not isinstance(record, dict):
            continue
        questions = record.get("questions")
        if questions:
            counts[merger_id] = len(questions)
    return counts


def _notification_date(merger: dict) -> str | None:
    """The merger's notification date as a plain ISO date, or ``None``."""
    stamp = merger.get("effective_notification_datetime")
    return stamp[:10] if stamp else None


def build_completed_pool(mergers: list, question_counts: dict | None = None) -> list[dict]:
    """Return completed phase-1 notification reviews as prediction training rows.

    Each row is ``{"merger_id", "bucket", "business_days", "phase_1_end"}``.
    Waivers (no phase-1 clock) and still-open reviews are excluded.
    ``phase_1_end`` is what :func:`compute_estimate` filters on to keep each
    estimate to history that had already concluded at the target's filing.
    """
    question_counts = question_counts or {}
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
        merger_id = m.get("merger_id")
        pool.append(
            {
                "merger_id": merger_id,
                "bucket": question_bucket(question_counts.get(merger_id)),
                "business_days": bd,
                "phase_1_end": end[:10],
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


def compute_estimate(
    merger: dict,
    pool: list[dict],
    estimated_at: str,
    question_counts: dict | None = None,
) -> dict | None:
    """Compute the frozen phase-1 estimate for ``merger`` from ``pool``.

    Only pool rows whose phase 1 concluded strictly before ``merger`` was filed
    are eligible, so the estimate uses nothing that was unknowable at filing.

    Returns ``None`` for waivers, mergers without a notification date, and
    mergers filed before ``MIN_SUPPORT`` reviews had concluded.
    """
    if is_waiver_merger(merger):
        return None
    as_of = _notification_date(merger)
    if not as_of:
        return None

    merger_id = merger.get("merger_id")
    eligible = [
        r for r in pool
        if r["merger_id"] != merger_id and r["phase_1_end"] < as_of
    ]
    all_durations = [r["business_days"] for r in eligible]
    if len(all_durations) < MIN_SUPPORT:
        return None

    question_counts = question_counts or {}
    count = question_counts.get(merger_id)
    bucket = question_bucket(count)

    matched = [r["business_days"] for r in eligible if bucket and r["bucket"] == bucket]
    if len(matched) >= MIN_SUPPORT:
        durations, basis = matched, "questionnaire"
    else:
        durations, basis = all_durations, "global"

    return {
        "expected_business_days": round(median(durations)),
        "range_business_days": _band(durations),
        "basis": basis,
        "question_bucket": bucket if basis == "questionnaire" else None,
        "question_count": count,
        "sample_size": len(durations),
        "as_of": as_of,
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
    enriched: list,
    questionnaire_data: dict | None = None,
    store: dict | None = None,
    estimated_at: str | None = None,
) -> tuple[int, int]:
    """Freeze + attach ``phase_1_estimate`` on each enriched merger in-place.

    New notification mergers (those not already in ``store``) get an estimate
    computed from the review history that had concluded by their filing date,
    frozen into the store. Mergers already in the store keep their frozen value
    so it reflects the filing-time prediction rather than drifting as data
    grows — unless that value predates ``METHOD_VERSION``, in which case it is
    recomputed under the current method. The recompute is safe precisely
    because :func:`compute_estimate` is forward-chained: it rebuilds what the
    current method *would* have said at filing, not what hindsight knows.

    Loads and saves ``data/processed/phase1_estimates.json`` when ``store`` is
    not supplied (the production path). Returns ``(newly_computed, attached)``.
    """
    manage_store = store is None
    if manage_store:
        store = load_store()
    estimated_at = estimated_at or date.today().isoformat()

    question_counts = question_counts_from(questionnaire_data)
    pool = build_completed_pool(enriched, question_counts)

    newly_computed = 0
    attached = 0
    for merger in enriched:
        merger_id = merger.get("merger_id")
        if not merger_id:
            continue
        estimate = store.get(merger_id)
        if estimate is None or estimate.get("method_version") != METHOD_VERSION:
            estimate = compute_estimate(merger, pool, estimated_at, question_counts)
            if estimate is None:
                # Waiver, undated, or filed before there was history to learn
                # from. Drop any superseded entry rather than leave a stale one.
                store.pop(merger_id, None)
                continue
            store[merger_id] = estimate
            newly_computed += 1
        merger["phase_1_estimate"] = estimate
        attached += 1

    if manage_store:
        save_store(store)
    return newly_computed, attached
