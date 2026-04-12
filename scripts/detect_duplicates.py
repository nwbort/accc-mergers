#!/usr/bin/env python3
"""
Detect duplicate or likely-duplicate events within merger records.

The ACCC website sometimes temporarily publishes documents that later disappear
and are replaced, causing the scraper to accumulate multiple event entries that
represent the same real-world event.  This script reports those cases so they
can be inspected and resolved by hand-editing the processed JSON.

Two categories are reported:

  CERTAIN  – events in the same merger with an identical (date, title) pair.
  LIKELY   – events in the same merger with the same date and a title whose
             normalised form shares ≥ 80 % similarity (catches minor wording
             differences, trailing punctuation, etc.).

Usage
-----
  python scripts/detect_duplicates.py [--input PATH] [--output PATH] [--json]

Options
-------
  --input   Path to mergers JSON (default: data/processed/mergers.json)
  --output  Write a JSON report to this path (default: no file written)
  --json    Print JSON report to stdout instead of human-readable text
"""

import argparse
import json
import re
import sys
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
REPO_ROOT = SCRIPT_DIR.parent
DEFAULT_INPUT = REPO_ROOT / "data" / "processed" / "mergers.json"

SIMILARITY_THRESHOLD = 0.80

_REPO = "nwbort/accc-mergers"
_MERGERS_FYI_BASE = "https://mergers.fyi/mergers"


def normalise_title(title: str) -> str:
    """Strip leading/trailing whitespace and punctuation for fuzzy comparison."""
    return re.sub(r"[\s\W]+$", "", title.strip()).lower()


def title_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, normalise_title(a), normalise_title(b)).ratio()


def parse_date(raw: str):
    """Return a date-only string (YYYY-MM-DD) or None."""
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).strftime("%Y-%m-%d")
    except ValueError:
        return None


def find_duplicates(merger: dict) -> list[dict]:
    """
    Return a list of duplicate groups for one merger.

    Each group is a dict:
      {
        "kind":    "certain" | "likely",
        "indices": [int, ...],
        "date":    "YYYY-MM-DD",
        "titles":  [str, ...],         # may differ for "likely"
        "events":  [event_dict, ...]
      }
    """
    events = merger.get("events", [])
    grouped: list[dict] = []
    used: set[int] = set()

    # --- pass 1: exact (date, title) matches ---
    from collections import defaultdict
    exact: dict[tuple, list[int]] = defaultdict(list)
    for idx, ev in enumerate(events):
        date = parse_date(ev.get("date", ""))
        title = ev.get("title", "")
        if date and title:
            exact[(date, title)].append(idx)

    for (date, title), indices in exact.items():
        if len(indices) > 1:
            grouped.append({
                "kind": "certain",
                "indices": indices,
                "date": date,
                "titles": [title],
                "events": [events[i] for i in indices],
            })
            used.update(indices)

    # --- pass 2: same-date, similar title (not already marked certain) ---
    remaining = [i for i in range(len(events)) if i not in used]
    checked: set[tuple[int, int]] = set()

    for i in remaining:
        ev_i = events[i]
        date_i = parse_date(ev_i.get("date", ""))
        title_i = ev_i.get("title", "")
        if not date_i or not title_i:
            continue
        group_indices = [i]
        for j in remaining:
            if j == i or (min(i, j), max(i, j)) in checked:
                continue
            ev_j = events[j]
            date_j = parse_date(ev_j.get("date", ""))
            title_j = ev_j.get("title", "")
            if not date_j or not title_j:
                continue
            if date_i == date_j and title_similarity(title_i, title_j) >= SIMILARITY_THRESHOLD:
                group_indices.append(j)
                checked.add((min(i, j), max(i, j)))

        if len(group_indices) > 1:
            # Avoid re-reporting subsets of an already-found group
            key = frozenset(group_indices)
            if not any(frozenset(g["indices"]) == key for g in grouped):
                titles = [events[k].get("title", "") for k in group_indices]
                grouped.append({
                    "kind": "likely",
                    "indices": group_indices,
                    "date": date_i,
                    "titles": titles,
                    "events": [events[k] for k in group_indices],
                })
                used.update(group_indices)

    return grouped


def event_summary(ev: dict) -> dict:
    """Return a compact representation of an event for reporting."""
    return {
        "date": ev.get("date", ""),
        "title": ev.get("title", ""),
        "url": ev.get("url", ""),
        "url_gh": ev.get("url_gh", ""),
        "status": ev.get("status", ""),
    }


def build_report(mergers: list[dict]) -> dict:
    """Build the full duplicate report structure."""
    findings: list[dict] = []
    certain_count = 0
    likely_count = 0

    for merger in mergers:
        groups = find_duplicates(merger)
        if not groups:
            continue
        merger_entry = {
            "merger_id": merger.get("merger_id", ""),
            "merger_name": merger.get("merger_name", ""),
            "duplicate_groups": [],
        }
        for g in groups:
            if g["kind"] == "certain":
                certain_count += 1
            else:
                likely_count += 1
            merger_entry["duplicate_groups"].append({
                "kind": g["kind"],
                "date": g["date"],
                "titles": g["titles"],
                "indices": g["indices"],
                "events": [event_summary(e) for e in g["events"]],
            })
        findings.append(merger_entry)

    return {
        "summary": {
            "mergers_with_duplicates": len(findings),
            "certain_duplicate_groups": certain_count,
            "likely_duplicate_groups": likely_count,
        },
        "findings": findings,
    }


def print_human_report(report: dict) -> None:
    s = report["summary"]
    print("=" * 70)
    print("ACCC Merger Duplicate Event Report")
    print("=" * 70)
    print(
        f"Mergers with duplicates : {s['mergers_with_duplicates']}\n"
        f"Certain duplicate groups: {s['certain_duplicate_groups']}\n"
        f"Likely  duplicate groups: {s['likely_duplicate_groups']}"
    )
    print()

    for entry in report["findings"]:
        print(f"{'─' * 70}")
        print(f"  {entry['merger_id']}  {entry['merger_name']}")
        for g in entry["duplicate_groups"]:
            kind_tag = "[CERTAIN]" if g["kind"] == "certain" else "[LIKELY ]"
            print(f"\n  {kind_tag}  date: {g['date']}")
            for idx, ev in zip(g["indices"], g["events"]):
                print(f"    event[{idx}]")
                print(f"      title  : {ev['title']}")
                if ev["url"]:
                    print(f"      url    : {ev['url']}")
                if ev["url_gh"]:
                    print(f"      url_gh : {ev['url_gh']}")
                if ev["status"]:
                    print(f"      status : {ev['status']}")
        print()


# ---------------------------------------------------------------------------
# Helpers for GitHub issue generation
# ---------------------------------------------------------------------------

def mergers_fyi_url(merger_id: str) -> str:
    return f"{_MERGERS_FYI_BASE}/{merger_id}"


def _json_github_url(branch: str, line: int | None = None) -> str:
    base = f"https://github.com/{_REPO}/blob/{branch}/data/processed/mergers.json"
    return f"{base}#L{line}" if line else base


def _find_merger_line(input_path: Path, merger_id: str) -> int | None:
    """Return the first line number where merger_id appears in the JSON file."""
    needle = f'"merger_id": "{merger_id}"'
    with input_path.open() as fh:
        for i, line in enumerate(fh, 1):
            if needle in line:
                return i
    return None


def suggest_deletion(group: dict) -> tuple[int, str]:
    """
    Return (index_to_delete, reason) for the most likely duplicate to remove.

    Priority:
    1. Delete the event with status 'removed' if the other is 'live'.
    2. Delete the event that lacks url_gh when the other has it.
    3. Delete the event with fewer populated fields.
    4. Fall back to deleting the last entry (keep the earlier one).
    """
    indices = group["indices"]
    events = group["events"]

    statuses = [ev.get("status", "") for ev in events]
    if "removed" in statuses and "live" in statuses:
        pos = statuses.index("removed")
        return indices[pos], "has status `removed` (no longer present on the ACCC website)"

    has_gh = [bool(ev.get("url_gh")) for ev in events]
    if any(has_gh) and not all(has_gh):
        pos = has_gh.index(False)
        return indices[pos], "lacks an attachment (`url_gh`) while the other entry has one"

    has_url = [bool(ev.get("url")) for ev in events]
    if any(has_url) and not all(has_url):
        pos = has_url.index(False)
        return indices[pos], "has no ACCC URL while the other entry does"

    scores = [sum(1 for v in ev.values() if v) for ev in events]
    if min(scores) != max(scores):
        pos = scores.index(min(scores))
        return indices[pos], "has fewer populated fields than the other entry"

    return indices[-1], f"appears to be a later duplicate — keeping `event[{indices[0]}]` (the earlier entry)"


def _build_sub_issue_body(entry: dict, input_path: Path, branch: str) -> str:
    """Build the markdown body for a per-merger sub-issue."""
    merger_id = entry["merger_id"]
    line = _find_merger_line(input_path, merger_id)
    fyi_url = mergers_fyi_url(merger_id)
    json_url = _json_github_url(branch, line)
    branch_url = f"https://github.com/{_REPO}/tree/{branch}"

    out = [
        f"**mergers.fyi:** [{merger_id}]({fyi_url})",
        f"**JSON:** [`data/processed/mergers.json`]({json_url})"
        + (f" (line {line})" if line else ""),
        f"**Fix branch:** [`{branch}`]({branch_url})",
        "",
        "---",
        "",
    ]

    for i, g in enumerate(entry["duplicate_groups"], 1):
        kind = "CERTAIN" if g["kind"] == "certain" else "LIKELY"
        out.append(f"### Group {i} — {kind} — {g['date']}")
        out.append("")
        out.append("| Index | Status | Title | ACCC URL |")
        out.append("|-------|--------|-------|----------|")
        for idx, ev in zip(g["indices"], g["events"]):
            status = ev.get("status") or "—"
            title = (ev.get("title") or "—").replace("|", "\\|")
            url = ev.get("url") or ""
            link = f"[link]({url})" if url else "—"
            out.append(f"| `event[{idx}]` | `{status}` | {title} | {link} |")
        out.append("")
        del_idx, reason = suggest_deletion(g)
        out.append(f"**Suggested action:** Remove `event[{del_idx}]` — {reason}")
        out.append("")
        out.append("**To fix:**")
        out.append(f"1. Check out branch `{branch}`")
        out.append(f"2. Open `data/processed/mergers.json` and find merger `{merger_id}`")
        out.append(f"3. In the `events` array, remove the entry at index `{del_idx}`")
        out.append("4. Commit, push, and open a PR")
        out.append("")

    return "\n".join(out)


def _build_main_issue_body(report: dict, branch: str, date: str) -> str:
    """Build the markdown body for the top-level duplicate-events issue."""
    branch_url = f"https://github.com/{_REPO}/tree/{branch}"
    s = report["summary"]

    out = [
        f"Duplicate events were detected on **{date}**.",
        "",
        f"**Fix branch:** [`{branch}`]({branch_url})",
        "",
        "Check out this branch, edit `data/processed/mergers.json` to remove the "
        "duplicates described in each sub-issue below, then open a PR.",
        "",
        "---",
        "",
        "## Affected mergers",
        "",
        "| Merger | Name | Groups |",
        "|--------|------|--------|",
    ]

    for entry in report["findings"]:
        mid = entry["merger_id"]
        name = entry["merger_name"].replace("|", "\\|")
        n = len(entry["duplicate_groups"])
        kinds = " + ".join(sorted({g["kind"] for g in entry["duplicate_groups"]}))
        out.append(f"| [{mid}]({mergers_fyi_url(mid)}) | {name} | {n} ({kinds}) |")

    out.extend([
        "",
        "---",
        f"*{s['mergers_with_duplicates']} merger(s) · "
        f"{s['certain_duplicate_groups']} certain · "
        f"{s['likely_duplicate_groups']} likely group(s)*",
    ])

    return "\n".join(out)


def build_issues_data(report: dict, input_path: Path, branch: str, date: str) -> dict:
    """
    Build structured data for GitHub issue creation:
      { "main_issue": { "title", "body" },
        "sub_issues":  [ { "merger_id", "title", "body" }, ... ] }
    """
    sub_issues = []
    for entry in report["findings"]:
        mid = entry["merger_id"]
        name = entry["merger_name"]
        title = f"Fix duplicates: {mid} — {name}"
        if len(title) > 200:
            title = title[:197] + "..."
        sub_issues.append({
            "merger_id": mid,
            "title": title,
            "body": _build_sub_issue_body(entry, input_path, branch),
        })

    return {
        "main_issue": {
            "title": f"Duplicate merger events detected — {date}",
            "body": _build_main_issue_body(report, branch, date),
        },
        "sub_issues": sub_issues,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Detect duplicate or likely-duplicate events in merger data."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT,
        help="Path to mergers JSON (default: data/processed/mergers.json)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Write JSON report to this file",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print JSON report to stdout instead of human-readable text",
    )
    parser.add_argument(
        "--branch",
        default="main",
        metavar="BRANCH",
        help="Branch name used in GitHub links within issue bodies (default: main)",
    )
    parser.add_argument(
        "--issues-json",
        type=Path,
        default=None,
        metavar="PATH",
        dest="issues_json",
        help="Write structured issue data (main issue + per-merger sub-issues) to this JSON file",
    )
    args = parser.parse_args()

    if not args.input.exists():
        print(f"ERROR: input file not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    with args.input.open() as fh:
        raw = json.load(fh)

    # Support both a bare list and the { "mergers": [...] } wrapper
    mergers: list[dict] = raw if isinstance(raw, list) else raw.get("mergers", [])

    report = build_report(mergers)

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print_human_report(report)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("w") as fh:
            json.dump(report, fh, indent=2)
        print(f"JSON report written to {args.output}")

    if args.issues_json:
        today = datetime.utcnow().strftime("%Y-%m-%d")
        issues_data = build_issues_data(report, args.input, args.branch, today)
        args.issues_json.parent.mkdir(parents=True, exist_ok=True)
        with args.issues_json.open("w") as fh:
            json.dump(issues_data, fh, indent=2)
        print(f"Issue data written to {args.issues_json}", file=sys.stderr)

    # Exit with a non-zero code if any duplicates were found (useful in CI)
    total = (
        report["summary"]["certain_duplicate_groups"]
        + report["summary"]["likely_duplicate_groups"]
    )
    sys.exit(1 if total else 0)


if __name__ == "__main__":
    main()
