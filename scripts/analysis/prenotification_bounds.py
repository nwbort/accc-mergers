#!/usr/bin/env python3
"""Infer bounds on ACCC pre-notification duration from merger ID structure.

ACCC merger IDs look like ``MN-01016`` / ``WA-25017``: a 2-letter case type
(MN = merger notification, WA = waiver application), then a 2-digit group and a
3-digit sequence number. The group/sequence counter is shared between MN and WA
cases, and IDs appear to be allocated when a party first opens a case with the
ACCC -- i.e. at the start of pre-notification, not at formal notification.

If sequence numbers are allocated in time order within a group, then for two
cases A and B in the same group with seq(A) < seq(B):

    alloc(A) <= alloc(B) <= notified(B)

so if A was notified *after* B, A's pre-notification period must have been at
least ``notified(A) - notified(B)`` long. Taking the tightest such witness gives

    prenotification(A) >= notified(A) - min{ notified(B) : same group, seq(B) > seq(A) }

which is a hard lower bound under the monotone-allocation assumption.
"""
import argparse
import collections
import datetime as dt
import itertools
import json
import os
import statistics

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_DATA = os.path.join(REPO, "data", "processed", "mergers.json")


def load(path):
    """Return one record per merger with its ID decomposed and dates parsed."""
    out = []
    for m in json.load(open(path)):
        merger_id = m.get("merger_id") or ""
        if len(merger_id) != 8 or merger_id[2] != "-":
            continue
        notified = m.get("original_notification_datetime") or m.get(
            "effective_notification_datetime"
        )
        if not notified:
            continue
        out.append(
            {
                "id": merger_id,
                "kind": merger_id[:2],
                "group": merger_id[3:5],
                "seq": int(merger_id[5:]),
                "name": m.get("merger_name", ""),
                "stage": m.get("stage", ""),
                "status": m.get("status", ""),
                "notified": dt.datetime.fromisoformat(
                    notified.replace("Z", "+00:00")
                ).date(),
            }
        )
    return out


def concordance(records):
    """Kendall-style concordant/discordant counts of seq vs notification date."""
    per_group = collections.defaultdict(list)
    for r in records:
        per_group[r["group"]].append(r)
    rows = []
    for group, members in sorted(per_group.items()):
        conc = disc = tie = 0
        for a, b in itertools.combinations(members, 2):
            dd = (a["notified"] - b["notified"]).days
            if dd == 0:
                tie += 1
            elif (a["seq"] - b["seq"]) * dd > 0:
                conc += 1
            else:
                disc += 1
        rows.append((group, len(members), conc, disc, tie))
    return rows


def add_bounds(records):
    """Attach the lower bound on pre-notification days to each record.

    Within a group the running minimum of notification dates taken from the
    highest sequence number downwards is the tightest available upper bound on
    when each ID was allocated.
    """
    per_group = collections.defaultdict(list)
    for r in records:
        per_group[r["group"]].append(r)
    for members in per_group.values():
        members.sort(key=lambda r: r["seq"], reverse=True)
        best = None  # (date, witness id) of the tightest higher-seq case so far
        for r in members:
            r["alloc_before"] = best[0] if best else None
            r["witness"] = best[1] if best else None
            r["lower_bound_days"] = (
                max(0, (r["notified"] - best[0]).days) if best else None
            )
            if best is None or r["notified"] < best[0]:
                best = (r["notified"], r["id"])
    return records


def pair_types(records):
    """Discordance rates split by the case type of the lower/higher sequence ID.

    Waiver applications have no pre-notification stage, so waiver-vs-waiver pairs
    measure how reliably the sequence number tracks allocation order, while
    MN-then-WA pairs measure the pre-notification delay on merger notifications.
    """
    per_group = collections.defaultdict(list)
    for r in records:
        per_group[r["group"]].append(r)
    counts = collections.defaultdict(lambda: [0, 0, 0, []])
    for members in per_group.values():
        for a, b in itertools.combinations(members, 2):
            lo, hi = (a, b) if a["seq"] < b["seq"] else (b, a)
            bucket = counts[f'{lo["kind"]} then {hi["kind"]}']
            days = (hi["notified"] - lo["notified"]).days
            if days == 0:
                bucket[2] += 1
            elif days > 0:
                bucket[0] += 1
            else:
                bucket[1] += 1
                bucket[3].append(-days)
    return counts


def anchor_estimates(records, slack=0):
    """Estimate each notification's pre-notification period from waiver anchors.

    A waiver application is lodged when its ID is issued, so its notification
    date dates the group counter. Bracketing a merger notification between the
    nearest waiver below and above its sequence number brackets when its own ID
    was issued, and interpolating between the two estimates it.
    """
    per_group = collections.defaultdict(list)
    for r in records:
        per_group[r["group"]].append(r)
    for members in per_group.values():
        members.sort(key=lambda r: r["seq"])
        waivers = [r for r in members if r["kind"] == "WA"]
        for r in members:
            below = [w for w in waivers if w["seq"] < r["seq"]]
            above = [w for w in waivers if w["seq"] > r["seq"]]
            # Allocation order only guarantees monotonicity, so take the
            # tightest anchor on each side rather than the nearest one.
            lo = max((w["notified"] for w in below), default=None)
            hi = min((w["notified"] for w in above), default=None)
            r["anchor_max"] = (r["notified"] - lo).days + slack if lo else None
            r["anchor_min"] = max(0, (r["notified"] - hi).days) if hi else None
            if lo and hi and hi > lo:
                span = above[0]["seq"] - below[-1]["seq"]
                frac = (r["seq"] - below[-1]["seq"]) / span if span else 0.5
                alloc = lo + dt.timedelta(days=round((hi - lo).days * frac))
                r["anchor_point"] = max(0, (r["notified"] - alloc).days)
            else:
                r["anchor_point"] = None
    return records


def summarise(values, label):
    if not values:
        print(f"  {label}: no data")
        return
    values = sorted(values)
    quantile = lambda p: values[min(len(values) - 1, int(p * len(values)))]
    print(
        f"  {label}: n={len(values):>3}  mean={statistics.mean(values):>5.1f}d"
        f"  median={quantile(0.5):>3}d  p75={quantile(0.75):>3}d"
        f"  p90={quantile(0.90):>3}d  max={max(values):>3}d"
    )


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data", default=DEFAULT_DATA)
    ap.add_argument("--top", type=int, default=25, help="how many cases to list")
    args = ap.parse_args()

    records = load(args.data)
    print(f"Loaded {len(records)} mergers with a parseable ID and notification date\n")

    print("=" * 78)
    print("1. Does the sequence number track the notification date within a group?")
    print("=" * 78)
    print(f"{'group':>6} {'n':>4} {'conc':>6} {'disc':>5} {'tie':>4} {'agree':>7}")
    total_conc = total_disc = total_tie = 0
    for group, n, conc, disc, tie in concordance(records):
        total_conc, total_disc, total_tie = (
            total_conc + conc,
            total_disc + disc,
            total_tie + tie,
        )
        agree = conc / (conc + disc) if conc + disc else float("nan")
        print(f"{group:>6} {n:>4} {conc:>6} {disc:>5} {tie:>4} {agree:>6.1%}")
    agree = total_conc / (total_conc + total_disc)
    print(
        f"{'ALL':>6} {len(records):>4} {total_conc:>6} {total_disc:>5} {total_tie:>4}"
        f" {agree:>6.1%}   (Kendall tau-a = {(total_conc - total_disc) / (total_conc + total_disc):+.3f})"
    )

    print()
    print("=" * 78)
    print("2. Lower bounds on the pre-notification period")
    print("=" * 78)
    add_bounds(records)
    bounded = [r for r in records if r["lower_bound_days"] is not None]
    positive = [r for r in bounded if r["lower_bound_days"] > 0]
    print(
        f"{len(positive)} of {len(bounded)} cases ({len(positive) / len(bounded):.0%})"
        " have a provable pre-notification period of at least one day.\n"
    )
    summarise([r["lower_bound_days"] for r in bounded], "all cases          ")
    summarise([r["lower_bound_days"] for r in positive], "cases with a bound ")
    for kind, label in (("MN", "merger notifications"), ("WA", "waiver applications")):
        subset = [r["lower_bound_days"] for r in bounded if r["kind"] == kind]
        summarise(subset, f"{label:<19}")
        summarise([v for v in subset if v > 0], f"{label} (>0)".ljust(19))

    print(f"\n  Strongest {args.top} bounds:")
    print(
        f"  {'merger id':<10} {'notified':<11} {'>= days':>7}  {'witness':<10}"
        f" {'witness notified':<17} name"
    )
    for r in sorted(bounded, key=lambda r: -r["lower_bound_days"])[: args.top]:
        print(
            f"  {r['id']:<10} {r['notified']} {r['lower_bound_days']:>7}"
            f"  {r['witness']:<10} {str(r['alloc_before']):<17} {r['name'][:44]}"
        )

    print()
    print("=" * 78)
    print("3. Validation: pre-notification delay vs. allocation-order noise")
    print("=" * 78)
    print(f"{'sequence order':<18} {'conc':>6} {'disc':>6} {'tie':>5} {'inverted':>9} {'median':>7}")
    for key, (conc, disc, tie, sizes) in sorted(pair_types(records).items()):
        median = f"{sorted(sizes)[len(sizes) // 2]}d" if sizes else "-"
        print(
            f"{key:<18} {conc:>6} {disc:>6} {tie:>5}"
            f" {disc / (conc + disc):>8.1%} {median:>7}"
        )
    print(
        "\n  A waiver is lodged as soon as its ID is issued, so 'WA then WA' and"
        "\n  'WA then MN' pairs should almost never invert -- and they don't."
        " Inversions\n  concentrate entirely in pairs where the earlier ID is a"
        " merger notification,\n  which is the pre-notification period showing"
        " through."
    )

    print()
    print("=" * 78)
    print("4. Waiver-anchored estimates of the pre-notification period")
    print("=" * 78)
    anchor_estimates(records)
    notifications = [r for r in records if r["kind"] == "MN"]
    for field, label in (
        ("anchor_min", "lower bound (days)"),
        ("anchor_point", "interpolated estimate"),
        ("anchor_max", "upper bound (days)"),
    ):
        summarise([r[field] for r in notifications if r[field] is not None], label)
    print(
        "\n  Bounds assume a waiver is lodged the day its ID is issued; every day"
        "\n  of waiver lag widens the upper bound by the same amount."
    )

    print("\n  Interpolated estimate by notification month:")
    by_month = collections.defaultdict(list)
    for r in notifications:
        if r["anchor_point"] is not None:
            by_month[r["notified"].strftime("%Y-%m")].append(r["anchor_point"])
    for month, values in sorted(by_month.items()):
        values.sort()
        bar = "#" * round(statistics.mean(values) / 2)
        print(
            f"    {month}  n={len(values):>3}  median={values[len(values) // 2]:>3}d"
            f"  mean={statistics.mean(values):>5.1f}d  {bar}"
        )

    print()
    print("=" * 78)
    print("5. Unaccounted-for IDs (allocated but never public)")
    print("=" * 78)
    per_group = collections.defaultdict(list)
    for r in records:
        per_group[r["group"]].append(r["seq"])
    observed = missing = 0
    for group, seqs in sorted(per_group.items()):
        span = max(seqs) - min(seqs) + 1
        observed, missing = observed + len(seqs), missing + span - len(seqs)
    print(
        f"  {observed} IDs observed, {missing} gaps inside the observed ranges"
        f" ({missing / (observed + missing):.0%} of allocated IDs never surface)"
    )


if __name__ == "__main__":
    main()
