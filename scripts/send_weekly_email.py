#!/usr/bin/env python3
"""Send the mergers.fyi weekly digest email via Resend.

Reads digest.json, builds an HTML email, creates a Resend broadcast,
and sends it to the configured audience.

Required environment variables:
    RESEND_API_KEY           — Resend API key
    RESEND_AUDIENCE_ID       — Resend audience ID for the production send

Optional environment variables:
    AUDIENCE                 — 'production' (default) or 'test'. When 'test',
                               the broadcast is sent to RESEND_TEST_AUDIENCE_ID
                               and the subject is prefixed with [TEST].
    RESEND_TEST_AUDIENCE_ID  — Resend audience ID for test sends (required
                               when AUDIENCE=test)
    DRY_RUN                  — If set to 'true', prints the HTML and exits without sending
    SEND_FROM                — Sender address (default: mergers.fyi weekly digest <digest@mergers.fyi>)
"""

import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from html import escape as esc
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

from date_utils import parse_iso_datetime

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

SITE_BASE = "https://mergers.fyi"
RESEND_API_BASE = "https://api.resend.com"
SEND_FROM = os.environ.get("SEND_FROM", "Australian Merger Tracker <digest@mergers.fyi>")

# Colour palette matching tailwind.config.js.
# NOTE: colours must be plain 6-digit hex — Outlook's Word renderer does not
# understand 8-digit hex with alpha, rgba(), or CSS variables.
COLORS = {
    "new_merger":       {"border": "#5B3758", "pale": "#F3EBF2", "dark": "#3D2539"},
    "cleared":          {"border": "#10b981", "pale": "#D1FAE5", "dark": "#059669"},
    "phase_2_referral": {"border": "#d97706", "pale": "#fef3c7", "dark": "#b45309"},
    "declined":         {"border": "#f49097", "pale": "#FEE7E9", "dark": "#E8636C"},
    "ceased":           {"border": "#9333ea", "pale": "#faf5ff", "dark": "#7e22ce"},
    "phase_1":          {"border": "#B8935C", "pale": "#FCECC9", "dark": "#8A6B3E"},
    "phase_2":          {"border": "#52489c", "pale": "#E8E5F3", "dark": "#3A3372"},
}

GREEN = "#335145"          # site primary
GREEN_TINT = "#A9C6B6"     # muted wordmark tint on the green header
GREEN_PALE = "#EAF1EC"     # CTA strip background
INK = "#1F2937"            # near-black headings
BODY_TEXT = "#4B5563"
MUTED = "#6B7280"
FAINT = "#9CA3AF"
HAIRLINE = "#E3E8E5"       # outer borders
ROW_LINE = "#F0F2F1"       # row dividers
PAGE_BG = "#EEF1EF"
DUE_SOON = "#B45309"       # amber for imminent determination deadlines

# Outlook falls back to Times New Roman unless font-family is set; the
# embedded <style> block covers modern clients and the MSO conditional
# covers Outlook, so FONT is only stamped on structural elements.
FONT = "'Segoe UI',Arial,Helvetica,sans-serif"

# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_digest() -> dict:
    digest_path = (
        Path(__file__).parent.parent
        / "merger-tracker" / "frontend" / "public" / "data" / "digest.json"
    )
    with open(digest_path, "r", encoding="utf-8") as f:
        return json.load(f)

# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def _is_feedback_week(period_start_iso: str) -> bool:
    """Return True once every 8 weeks, based on weeks elapsed since a fixed Monday."""
    from datetime import date as _date
    _REFERENCE_MONDAY = _date(2024, 1, 1)  # confirmed Monday
    try:
        dt = datetime.fromisoformat(period_start_iso)
        delta_days = (dt.date() - _REFERENCE_MONDAY).days
        return (delta_days // 7) % 8 == 0
    except (ValueError, AttributeError, TypeError):
        return False


def format_date(date_str: str) -> str:
    """Convert an ISO datetime string to a short human-readable date (AEST)."""
    if not date_str:
        return "N/A"
    dt = parse_iso_datetime(date_str)
    if dt is None:
        return date_str
    try:
        dt = dt.astimezone(ZoneInfo("Australia/Sydney"))
        return dt.strftime("%-d %b %Y")
    except (ValueError, AttributeError):
        return date_str


def format_date_range(period_start: str, period_end: str) -> str:
    """Format the week period as e.g. '16–22 February 2026'."""
    try:
        start = datetime.fromisoformat(period_start)
        end = datetime.fromisoformat(period_end)
        start_day = start.day
        end_day = end.day
        start_month = start.strftime("%B")
        end_month = end.strftime("%B")
        year = end.year
        if start_month == end_month:
            return f"{start_day}–{end_day} {end_month} {year}"
        return f"{start_day} {start_month} – {end_day} {end_month} {year}"
    except (ValueError, AttributeError):
        return ""


def strip_markdown(text: str) -> str:
    """Strip common markdown markers so descriptions read cleanly in email."""
    if not text:
        return ""
    # Bold/italic
    text = re.sub(r"\*{1,2}(.*?)\*{1,2}", r"\1", text, flags=re.DOTALL)
    # Inline links [label](url)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    return text.strip()


WORD_BREAK_THRESHOLD = 0.7  # Only break at word boundary if at least 70% through max_chars


def truncate(text: str, max_chars: int = 200) -> str:
    """Strip markdown then truncate to max_chars, breaking on a word boundary."""
    text = strip_markdown(text)
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars]
    last_space = cut.rfind(" ")
    if last_space > int(max_chars * WORD_BREAK_THRESHOLD):
        cut = cut[:last_space]
    return cut + "…"


def pluralise(n: int, singular: str, plural: str | None = None) -> str:
    return singular if n == 1 else (plural or singular + "s")


def join_and(parts: list[str]) -> str:
    if len(parts) <= 1:
        return "".join(parts)
    return ", ".join(parts[:-1]) + " and " + parts[-1]


def _text_table(headers: list[str], rows: list[list[str]]) -> str:
    """Render a simple fixed-width text table."""
    all_rows = [headers] + rows
    widths = [max(len(str(r[i])) for r in all_rows) for i in range(len(headers))]
    header_line = " | ".join(h.ljust(widths[i]) for i, h in enumerate(headers))
    sep_line = "-+-".join("-" * w for w in widths)
    data_lines = [
        " | ".join(str(row[i]).ljust(widths[i]) for i in range(len(row)))
        for row in rows
    ]
    return "\n".join([header_line, sep_line] + data_lines)


def _text_section(title: str, headers: list[str], rows: list[list[str]], empty_msg: str) -> str:
    lines = [title, "-" * len(title)]
    if rows:
        lines.append(_text_table(headers, rows))
    else:
        lines.append(empty_msg)
    return "\n".join(lines)


def build_text_email(digest: dict) -> str:
    """Build a plain-text version of the weekly digest email."""
    date_range = format_date_range(digest["period_start"], digest["period_end"])

    referred = digest.get("deals_referred_to_phase_2") or []
    ceased = digest.get("deals_assessment_ceased") or []

    lines = [
        "Australian Merger Tracker weekly digest",
        f"Week of {date_range}",
        f"{SITE_BASE}/digest",
        "",
        "SUMMARY",
        "-------",
        f"New deals notified   : {len(digest['new_deals_notified'])}",
        f"Cleared              : {len(digest['deals_cleared'])}",
    ]
    if ceased:
        lines.append(f"Assessment ceased    : {len(ceased)}")
    lines += [
        f"Referred to phase 2  : {len(referred)}",
        f"Declined             : {len(digest['deals_declined'])}",
        f"Ongoing phase 1      : {len(digest['ongoing_phase_1'])}",
        f"Ongoing phase 2      : {len(digest['ongoing_phase_2'])}",
        "",
    ]

    new_rows = [
        [m.get("merger_name", m["merger_id"]), format_date(m.get("effective_notification_datetime"))]
        for m in digest["new_deals_notified"]
    ]
    lines.append(_text_section("NEW MERGERS NOTIFIED", ["Merger", "Notified"], new_rows, "No new mergers notified this week."))
    lines.append("")
    lines.append("")

    cleared_mergers = digest["deals_cleared"]
    cleared_title = "MERGERS APPROVED"
    if not cleared_mergers:
        lines.append(_text_section(cleared_title, ["Merger", "Date"], [], "No mergers approved this week."))
    else:
        cleared_groups = _cleared_groups(cleared_mergers)
        cleared_lines = [cleared_title, "-" * len(cleared_title)]
        for label, group_mergers in cleared_groups:
            cleared_lines.append(f"\n{label}")
            group_rows = [
                [m.get("merger_name", m["merger_id"]), format_date(m.get("determination_publication_date"))]
                for m in group_mergers
            ]
            cleared_lines.append(_text_table(["Merger", "Date"], group_rows))
        lines.append("\n".join(cleared_lines))
    lines.append("")
    lines.append("")

    if ceased:
        ceased_rows = [
            [m.get("merger_name", m["merger_id"]), format_date(m.get("ceased_date")), m.get("stage") or "N/A"]
            for m in ceased
        ]
        lines.append(_text_section("ASSESSMENT CEASED", ["Merger", "Date ceased", "Stage"], ceased_rows, ""))
        lines.append("")
        lines.append("")

    referred_rows = [
        [m.get("merger_name", m["merger_id"]), format_date(m.get("phase_1_determination_date"))]
        for m in referred
    ]
    lines.append(_text_section("REFERRED TO PHASE 2", ["Merger", "Referral date"], referred_rows, "No mergers referred to phase 2 this week."))
    lines.append("")
    lines.append("")

    declined_rows = [
        [m.get("merger_name", m["merger_id"]), format_date(m.get("determination_publication_date"))]
        for m in digest["deals_declined"]
    ]
    lines.append(_text_section("MERGERS DECLINED", ["Merger", "Date"], declined_rows, "No mergers declined this week."))
    lines.append("")
    lines.append("")

    phase1_rows = [
        [m.get("merger_name", m["merger_id"]), format_date(m.get("effective_notification_datetime"))]
        for m in digest["ongoing_phase_1"]
    ]
    lines.append(_text_section("ONGOING – PHASE 1 – INITIAL ASSESSMENT", ["Merger", "Notified"], phase1_rows, "No ongoing phase 1 mergers."))
    lines.append("")
    lines.append("")

    phase2_rows = [
        [m.get("merger_name", m["merger_id"]), format_date(m.get("effective_notification_datetime"))]
        for m in digest["ongoing_phase_2"]
    ]
    lines.append(_text_section("ONGOING – PHASE 2 – DETAILED ASSESSMENT", ["Merger", "Notified"], phase2_rows, "No ongoing phase 2 mergers."))
    lines.append("")

    unsub_var = "{{{RESEND_UNSUBSCRIBE_URL}}}"
    footer = [
        "--",
        "You're receiving this because you subscribed at mergers.fyi.",
        f"Unsubscribe: {unsub_var}",
    ]
    if _is_feedback_week(digest.get("period_start", "")):
        footer.insert(0, "Got thoughts, feedback or any market gossip? Just reply to this email - we'd love to hear from you.")
        footer.insert(1, "")
    lines += footer

    return "\n".join(lines)

# ---------------------------------------------------------------------------
# Email HTML building blocks
#
# Layout rules for Outlook (Word rendering engine), which most of the
# audience uses:
#   * tables only — no floats, no flex, no display:inline-block
#   * spacing via td padding; margins only on divs inside tds
#   * no border-radius, text-transform, letter-spacing reliance, or alpha hex
#   * width attributes alongside CSS widths
#   * fonts via embedded <style> (modern clients) + MSO conditional (Outlook)
# ---------------------------------------------------------------------------

def merger_url(merger: dict) -> str:
    return f"{SITE_BASE}/mergers/{esc(merger['merger_id'])}"


def merger_name(merger: dict) -> str:
    return esc(merger.get("merger_name", merger["merger_id"]))


def chip(label: str, pale: str, dark: str) -> str:
    # Outlook honours background-color on spans but not padding, so the
    # nbsp padding keeps the chip readable everywhere.
    return (
        f'<span style="background-color:{pale};color:{dark};font-size:10px;'
        f'font-weight:700;">&nbsp;{label}&nbsp;</span>'
    )


def waiver_chip() -> str:
    return " " + chip("WAIVER", "#EEF0EF", MUTED)


def _counts(digest: dict) -> dict:
    return {
        "new": len(digest["new_deals_notified"]),
        "cleared": len(digest["deals_cleared"]),
        "referred": len(digest.get("deals_referred_to_phase_2") or []),
        "declined": len(digest["deals_declined"]),
        "ceased": len(digest.get("deals_assessment_ceased") or []),
        "p1": len(digest["ongoing_phase_1"]),
        "p2": len(digest["ongoing_phase_2"]),
    }


_NUMBER_WORDS = {
    1: "one", 2: "two", 3: "three", 4: "four", 5: "five",
    6: "six", 7: "seven", 8: "eight", 9: "nine", 10: "ten",
}


def build_lede(c: dict) -> str:
    """A written summary of the week, composed from the digest counts."""
    def b(n: int) -> str:
        return f'<strong style="color:{INK};">{n}</strong>'

    def bw(n: int) -> str:
        # Spelled-out small numbers read better mid-sentence
        return f'<strong style="color:{INK};">{_NUMBER_WORDS.get(n, n)}</strong>'

    sentences = []
    if c["new"] and c["cleared"]:
        sentences.append(
            f"The ACCC was notified of {b(c['new'])} new {pluralise(c['new'], 'deal')} "
            f"this week and cleared {b(c['cleared'])}."
        )
    elif c["new"]:
        sentences.append(
            f"The ACCC was notified of {b(c['new'])} new {pluralise(c['new'], 'deal')} this week, "
            "and cleared none."
        )
    elif c["cleared"]:
        sentences.append(
            f"The ACCC cleared {b(c['cleared'])} {pluralise(c['cleared'], 'deal')} this week, "
            "with no new deals notified."
        )
    else:
        sentences.append(
            "A quiet week at the ACCC – no new deals were notified and no clearances were published."
        )

    mid = []
    if c["referred"]:
        mid.append(
            f"{bw(c['referred'])} {pluralise(c['referred'], 'deal was', 'deals were')} "
            "referred to a phase 2 review"
        )
    if c["declined"]:
        mid.append(f"{bw(c['declined'])} {pluralise(c['declined'], 'was', 'were')} declined")
    if c["ceased"]:
        mid.append(f"{bw(c['ceased'])} {pluralise(c['ceased'], 'assessment')} ceased")
    if mid:
        sentence = join_and(mid)
        # Capitalise the first letter, skipping the <strong …> markup
        sentences.append(re.sub(r">([a-z])", lambda m: ">" + m.group(1).upper(), sentence, count=1) + ".")

    ongoing = c["p1"] + c["p2"]
    if ongoing:
        if c["p1"] and c["p2"]:
            split = f" – {b(c['p1'])} in phase 1 and {b(c['p2'])} in phase 2"
        elif c["p1"]:
            split = ", all in phase 1"
        else:
            split = ", all in phase 2"
        sentences.append(
            f"{b(ongoing)} {pluralise(ongoing, 'assessment remains', 'assessments remain')} "
            f"on foot{split}."
        )

    return " ".join(sentences)


def build_scoreboard(c: dict) -> str:
    """A slim row of linked figures under the lede."""
    cells = [
        (c["new"], "NEW", COLORS["new_merger"], "new-mergers"),
        (c["cleared"], "CLEARED", COLORS["cleared"], "mergers-approved"),
    ]
    if c["ceased"]:
        cells.append((c["ceased"], "CEASED", COLORS["ceased"], "mergers-ceased"))
    cells += [
        (c["referred"], "TO PHASE 2", COLORS["phase_2_referral"], "mergers-referred"),
        (c["declined"], "DECLINED", COLORS["declined"], "mergers-declined"),
        (c["p1"], "PHASE 1", COLORS["phase_1"], "ongoing-phase-1"),
        (c["p2"], "PHASE 2", COLORS["phase_2"], "ongoing-phase-2"),
    ]
    width = str(100 // len(cells)) + "%"
    tds = "".join(
        f'<td width="{width}" align="center" style="padding:10px 2px;">'
        f'<a href="{SITE_BASE}/digest#{anchor}" style="text-decoration:none;">'
        f'<span style="font-size:21px;font-weight:800;color:{color["border"]};">{n}</span><br>'
        f'<span style="font-size:9px;font-weight:700;color:{FAINT};letter-spacing:1px;">{label}</span>'
        "</a></td>"
        for n, label, color, anchor in cells
    )
    return (
        '<table width="100%" cellpadding="0" cellspacing="0" border="0" role="presentation">'
        f"<tr>{tds}</tr></table>"
    )


def section_head(title: str, accent: str, right_text: str = "") -> str:
    right = (
        f'<td align="right" style="padding:28px 0 8px;border-bottom:2px solid {accent};'
        f'font-size:12px;font-weight:700;color:{FAINT};" valign="bottom">{esc(right_text)}</td>'
        if right_text
        else f'<td style="padding:28px 0 8px;border-bottom:2px solid {accent};">&nbsp;</td>'
    )
    return (
        f'<tr><td style="padding:28px 0 8px;border-bottom:2px solid {accent};'
        f'font-size:17px;font-weight:800;color:{INK};" valign="bottom">{esc(title)}</td>{right}</tr>'
    )


def empty_section_row(message: str) -> str:
    return (
        f'<tr><td colspan="2" style="padding:14px 0;font-size:13px;'
        f'color:{FAINT};font-style:italic;">{esc(message)}</td></tr>'
    )


def section_table(rows: str) -> str:
    return (
        '<table width="100%" cellpadding="0" cellspacing="0" border="0" role="presentation">'
        f"{rows}</table>"
    )

# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------

def build_new_deals(mergers: list) -> str:
    c = COLORS["new_merger"]
    rows = section_head("New deals notified", c["border"],
                        f"{len(mergers)} this week" if mergers else "")
    if not mergers:
        rows += empty_section_row("No new deals were notified this week.")
    else:
        for i, m in enumerate(mergers):
            divider = "" if i == len(mergers) - 1 else f"border-bottom:1px solid {ROW_LINE};"
            meta_bits = [
                esc(m.get("merger_id", "")),
                f"Notified {esc(format_date(m.get('effective_notification_datetime')))}",
            ]
            if m.get("end_of_determination_period"):
                meta_bits.append(
                    f"Decision due {esc(format_date(m.get('end_of_determination_period')))}"
                )
            desc = truncate(m.get("merger_description", ""))
            desc_html = (
                f'<div style="font-size:13px;color:{BODY_TEXT};line-height:19px;'
                f'margin-top:5px;">{esc(desc)}</div>'
                if desc else ""
            )
            waiver = waiver_chip() if m.get("is_waiver") else ""
            rows += (
                f'<tr><td colspan="2" style="padding:14px 0 13px;{divider}">'
                f'<a href="{merger_url(m)}" style="color:{c["dark"]};font-size:14px;'
                f'font-weight:700;text-decoration:none;line-height:1.4;">{merger_name(m)}</a>{waiver}'
                f'<div style="font-size:11px;color:{FAINT};margin-top:3px;">{" &middot; ".join(meta_bits)}</div>'
                f"{desc_html}</td></tr>"
            )
    return section_table(rows)


def _cleared_phase(merger: dict) -> str:
    """Return 'phase2', 'phase1', or 'merger' for a cleared deal."""
    if merger.get("phase_2_determination") == "Approved":
        return "phase2"
    if merger.get("phase_1_determination") == "Approved":
        return "phase1"
    return "merger"


def _cleared_groups(mergers: list) -> list[tuple[str, list]]:
    """Return non-empty (label, items) groups sorted phase2→phase1→merger."""
    phase2 = [m for m in mergers if _cleared_phase(m) == "phase2"]
    phase1 = [m for m in mergers if _cleared_phase(m) == "phase1"]
    general = [m for m in mergers if _cleared_phase(m) == "merger"]
    return [
        (label, items)
        for label, items in [
            ("Phase 2 – detailed assessment", phase2),
            ("Phase 1 – initial assessment", phase1),
            ("Waiver", general),
        ]
        if items
    ]


_GENERIC_DETERMINATIONS = {"approved", "not approved", "declined", "referred to phase 2"}


def _decision_entries(digest: dict) -> list[dict]:
    """Flatten the week's outcomes into one list, with phase 2 activity
    (decisions made in phase 2 and referrals to phase 2) at the top."""
    entries = []
    cleared_group_labels = {"Phase 2 – detailed assessment": "Phase 2",
                            "Phase 1 – initial assessment": "Phase 1",
                            "Waiver": "Waiver"}
    for label, group in _cleared_groups(digest["deals_cleared"]):
        for m in group:
            det = (
                m.get("accc_determination")
                or m.get("phase_1_determination")
                or m.get("phase_2_determination")
                or ""
            )
            entries.append({
                "merger": m,
                "chip_label": "CLEARED",
                "color": COLORS["cleared"],
                "context": cleared_group_labels[label],
                "date": m.get("determination_publication_date"),
                "detail": det if det.lower() not in _GENERIC_DETERMINATIONS else "",
                "is_phase2": label == "Phase 2 – detailed assessment",
            })
    for m in digest.get("deals_referred_to_phase_2") or []:
        det = m.get("accc_determination") or m.get("phase_1_determination") or ""
        entries.append({
            "merger": m,
            "chip_label": "TO PHASE 2",
            "color": COLORS["phase_2_referral"],
            "context": "Phase 1 determination",
            "date": m.get("phase_1_determination_date"),
            "detail": det if det.lower() not in _GENERIC_DETERMINATIONS else "",
            "is_phase2": True,
        })
    for m in digest["deals_declined"]:
        det = (
            m.get("accc_determination")
            or m.get("phase_1_determination")
            or m.get("phase_2_determination")
            or ""
        )
        entries.append({
            "merger": m,
            "chip_label": "DECLINED",
            "color": COLORS["declined"],
            "context": "",
            "date": m.get("determination_publication_date"),
            "detail": det if det.lower() not in _GENERIC_DETERMINATIONS else "",
            "is_phase2": bool(m.get("phase_2_determination")),
        })
    for m in digest.get("deals_assessment_ceased") or []:
        entries.append({
            "merger": m,
            "chip_label": "CEASED",
            "color": COLORS["ceased"],
            "context": m.get("stage") or "",
            "date": m.get("ceased_date"),
            "detail": "",
            "is_phase2": "phase 2" in (m.get("stage") or "").lower(),
        })
    # Stable sort: phase 2 activity first, otherwise keep grouped order
    entries.sort(key=lambda e: not e["is_phase2"])
    return entries


def build_decisions(digest: dict) -> str:
    entries = _decision_entries(digest)
    rows = section_head("Decisions", GREEN,
                        f"{len(entries)} this week" if entries else "")
    if not entries:
        rows += empty_section_row("No decisions were published this week.")
    else:
        for i, e in enumerate(entries):
            m = e["merger"]
            divider = "" if i == len(entries) - 1 else f"border-bottom:1px solid {ROW_LINE};"
            meta_bits = [x for x in (
                e["context"],
                esc(format_date(e["date"])),
                esc(m.get("merger_id", "")),
            ) if x]
            waiver = waiver_chip() if m.get("is_waiver") and e["chip_label"] != "CLEARED" else ""
            detail_html = (
                f'<div style="font-size:12px;color:{BODY_TEXT};line-height:18px;'
                f'margin-top:4px;">{esc(e["detail"])}</div>'
                if e["detail"] else ""
            )
            rows += (
                f'<tr><td colspan="2" style="padding:13px 0 12px;{divider}">'
                f'<a href="{merger_url(m)}" style="color:{e["color"]["dark"]};font-size:14px;'
                f'font-weight:700;text-decoration:none;line-height:1.4;">{merger_name(m)}</a>{waiver}'
                f'<div style="margin-top:4px;">{chip(e["chip_label"], e["color"]["pale"], e["color"]["dark"])}'
                f' <span style="font-size:11px;color:{FAINT};">{" &middot; ".join(meta_bits)}</span></div>'
                f"{detail_html}</td></tr>"
            )
    return section_table(rows)


def _phase_group_row(label: str, color: dict, count: int) -> str:
    return (
        f'<tr><td style="padding:16px 0 5px;border-bottom:1px solid {ROW_LINE};'
        f'font-size:10px;font-weight:700;color:{color["dark"]};letter-spacing:1px;" '
        f'valign="bottom">{esc(label.upper())}</td>'
        f'<td align="right" style="padding:16px 0 5px;border-bottom:1px solid {ROW_LINE};'
        f'font-size:10px;font-weight:700;color:{FAINT};" valign="bottom">{count}</td></tr>'
    )


def build_pipeline(digest: dict) -> str:
    """All ongoing assessments as a compact list, grouped by phase (phase 2
    first) and sorted by decision due date within each group. Dates due
    within a fortnight are shown in amber."""
    far_future = datetime(9999, 1, 1, tzinfo=timezone.utc)

    def due_dt(m: dict):
        return parse_iso_datetime(m.get("end_of_determination_period") or "")

    groups = [
        ("Phase 2 – detailed assessment", "phase_2", sorted(digest["ongoing_phase_2"], key=lambda m: due_dt(m) or far_future)),
        ("Phase 1 – initial assessment", "phase_1", sorted(digest["ongoing_phase_1"], key=lambda m: due_dt(m) or far_future)),
    ]
    groups = [g for g in groups if g[2]]
    total = sum(len(g[2]) for g in groups)

    try:
        cutoff = datetime.fromisoformat(digest["period_end"]) + timedelta(days=14)
    except (ValueError, KeyError, TypeError):
        cutoff = None

    rows = section_head("Pipeline", COLORS["phase_1"]["border"],
                        f"{total} on foot" if total else "")
    if not total:
        rows += empty_section_row("No assessments are currently on foot.")
        return section_table(rows)
    for gi, (label, phase_key, mergers) in enumerate(groups):
        rows += _phase_group_row(label, COLORS[phase_key], len(mergers))
        last_group = gi == len(groups) - 1
        for i, m in enumerate(mergers):
            last = last_group and i == len(mergers) - 1
            divider = "" if last else f"border-bottom:1px solid {ROW_LINE};"
            dt = due_dt(m)
            soon = cutoff is not None and dt is not None and dt <= cutoff
            due_style = (
                f"font-size:12px;font-weight:700;color:{DUE_SOON};"
                if soon
                else f"font-size:12px;color:{BODY_TEXT};"
            )
            waiver = waiver_chip() if m.get("is_waiver") else ""
            rows += (
                f'<tr><td style="padding:9px 0 8px;{divider}" valign="top">'
                f'<a href="{merger_url(m)}" style="color:{INK};font-size:13px;font-weight:600;'
                f'text-decoration:none;line-height:1.45;">{merger_name(m)}</a>{waiver}</td>'
                f'<td width="80" align="right" style="padding:9px 0 8px 12px;{divider}" valign="top">'
                f'<span style="{due_style}">{esc(format_date(m.get("end_of_determination_period")))}</span>'
                "</td></tr>"
            )
    return section_table(rows)

# ---------------------------------------------------------------------------
# Full email builder
# ---------------------------------------------------------------------------

def build_html_email(digest: dict) -> str:
    date_range = format_date_range(digest["period_start"], digest["period_end"])
    show_feedback = _is_feedback_week(digest.get("period_start", ""))
    c = _counts(digest)

    sections = (
        build_new_deals(digest["new_deals_notified"])
        + build_decisions(digest)
        + build_pipeline(digest)
    )

    if show_feedback:
        header_cta = (
            "Got thoughts, feedback or any market gossip? Just reply to this email – "
            "we&rsquo;d love to hear from you."
        )
    else:
        header_cta = (
            "Were you forwarded this email? Sign up "
            f'<a href="{SITE_BASE}/digest" '
            f'style="color:{GREEN};text-decoration:underline;">here</a>.'
        )

    preheader_bits = [f"{c['new']} new deals notified", f"{c['cleared']} cleared"]
    if c["ceased"]:
        preheader_bits.append(f"{c['ceased']} ceased")
    if c["referred"]:
        preheader_bits.append(f"{c['referred']} referred to phase 2")
    if c["declined"]:
        preheader_bits.append(f"{c['declined']} declined")
    preheader_bits.append(f"{c['p1'] + c['p2']} ongoing")
    preheader = ", ".join(preheader_bits) + "."

    # Resend replaces {{{RESEND_UNSUBSCRIBE_URL}}} with the real link
    unsub_var = "{{{RESEND_UNSUBSCRIBE_URL}}}"

    side_borders = f"border-left:1px solid {HAIRLINE};border-right:1px solid {HAIRLINE};"

    return f"""<!DOCTYPE html>
<html lang="en" xmlns="http://www.w3.org/1999/xhtml" xmlns:o="urn:schemas-microsoft-com:office:office">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta http-equiv="X-UA-Compatible" content="IE=edge">
  <!--[if mso]>
  <noscript>
    <xml>
      <o:OfficeDocumentSettings>
        <o:PixelsPerInch>96</o:PixelsPerInch>
      </o:OfficeDocumentSettings>
    </xml>
  </noscript>
  <style>table {{border-collapse:collapse;}} td {{font-family:'Segoe UI',Arial,sans-serif;}}</style>
  <![endif]-->
  <style>
    body, table, td, div, p, a, span {{font-family:'Segoe UI',Arial,Helvetica,sans-serif;}}
  </style>
  <title>Weekly merger digest, {esc(date_range)} | Australian Merger Tracker</title>
</head>
<body style="margin:0;padding:0;background-color:{PAGE_BG};font-family:{FONT};">

<div style="display:none;font-size:1px;line-height:1px;max-height:0;max-width:0;opacity:0;overflow:hidden;mso-hide:all;">
  {esc(preheader)}
</div>

<table width="100%" cellpadding="0" cellspacing="0" border="0" role="presentation"
       bgcolor="{PAGE_BG}" style="background-color:{PAGE_BG};">
  <tr>
    <td align="center" style="padding:26px 12px 44px;">

      <!-- ===== OUTER WRAPPER (620px, fixed in Outlook, fluid elsewhere) ===== -->
      <table width="620" cellpadding="0" cellspacing="0" border="0" role="presentation"
             style="width:620px;max-width:100%;">

        <!-- MASTHEAD -->
        <tr>
          <td bgcolor="{GREEN}" style="background-color:{GREEN};padding:26px 30px 22px;font-family:{FONT};">
            <div style="font-size:12px;font-weight:700;letter-spacing:2px;color:{GREEN_TINT};">MERGERS.FYI</div>
            <div style="font-size:24px;font-weight:700;color:#ffffff;line-height:30px;margin-top:6px;">Weekly merger digest</div>
            <div style="font-size:13px;color:#CBDDD2;margin-top:8px;">
              Week of {esc(date_range)}
              &nbsp;&middot;&nbsp;
              <a href="{SITE_BASE}/digest" style="color:#ffffff;text-decoration:underline;">View online</a>
            </div>
          </td>
        </tr>

        <!-- CTA STRIP -->
        <tr>
          <td bgcolor="{GREEN_PALE}" style="background-color:{GREEN_PALE};padding:10px 30px;{side_borders}
                     font-family:{FONT};font-size:12px;color:#3E5F51;font-style:italic;">
            {header_cta}
          </td>
        </tr>

        <!-- LEDE -->
        <tr>
          <td bgcolor="#ffffff" style="background-color:#ffffff;padding:24px 30px 6px;{side_borders}
                     font-family:{FONT};font-size:15px;line-height:23px;color:{BODY_TEXT};">
            {build_lede(c)}
          </td>
        </tr>

        <!-- SCOREBOARD -->
        <tr>
          <td bgcolor="#ffffff" style="background-color:#ffffff;padding:12px 22px 6px;{side_borders}">
            <table width="100%" cellpadding="0" cellspacing="0" border="0" role="presentation">
              <tr><td style="border-bottom:1px solid {ROW_LINE};font-size:1px;line-height:1px;">&nbsp;</td></tr>
            </table>
            {build_scoreboard(c)}
          </td>
        </tr>

        <!-- SECTIONS -->
        <tr>
          <td bgcolor="#ffffff" style="background-color:#ffffff;padding:0 30px 30px;{side_borders}">
            {sections}
          </td>
        </tr>

        <!-- FOOTER -->
        <tr>
          <td bgcolor="#F4F6F5" align="center"
              style="background-color:#F4F6F5;padding:18px 28px;
                     border:1px solid {HAIRLINE};border-top:1px solid {ROW_LINE};
                     font-family:{FONT};">
            <p style="margin:0 0 6px;font-size:12px;color:{MUTED};line-height:19px;">
              You&rsquo;re receiving this because you subscribed to the mergers.fyi weekly digest
              at <a href="{SITE_BASE}" style="color:{GREEN};text-decoration:none;font-weight:600;">mergers.fyi</a>.
            </p>
            <p style="margin:0;font-size:12px;color:{FAINT};">
              <a href="{unsub_var}" style="color:{FAINT};text-decoration:underline;">Unsubscribe</a>
              &nbsp;&middot;&nbsp;
              <a href="{SITE_BASE}/digest" style="color:{FAINT};text-decoration:underline;">View in browser</a>
            </p>
          </td>
        </tr>

      </table>
    </td>
  </tr>
</table>

</body>
</html>"""


def build_subject(digest: dict) -> str:
    """Data-driven subject line, e.g. 'Weekly merger digest: 18 new deals, 20 cleared'."""
    c = _counts(digest)
    date_range = format_date_range(digest["period_start"], digest["period_end"])
    bits = []
    if c["new"]:
        bits.append(f"{c['new']} new {pluralise(c['new'], 'deal')}")
    if c["cleared"]:
        bits.append(
            f"{c['cleared']} cleared" if bits
            else f"{c['cleared']} {pluralise(c['cleared'], 'deal')} cleared"
        )
    if not bits and c["declined"]:
        bits.append(f"{c['declined']} {pluralise(c['declined'], 'deal')} declined")
    if bits:
        return f"Weekly merger digest: {', '.join(bits)}"
    return f"Weekly merger digest: {date_range}"

# ---------------------------------------------------------------------------
# Resend API calls
# ---------------------------------------------------------------------------

def create_broadcast(api_key: str, audience_id: str, subject: str, html: str, name: str, text: str = "") -> str:
    """Create a Resend broadcast draft and return its ID."""
    payload: dict = {
        "audience_id": audience_id,
        "from": SEND_FROM,
        "subject": subject,
        "html": html,
        "name": name,
    }
    if text:
        payload["text"] = text
    resp = requests.post(
        f"{RESEND_API_BASE}/broadcasts",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=30,
    )
    if not resp.ok:
        # Avoid logging resp.text — Resend error bodies can include recipient
        # metadata that would end up in public GitHub Actions logs.
        err_name = "unknown"
        try:
            err_name = str(resp.json().get("name", "unknown"))
        except Exception:
            pass
        print(f"ERROR creating broadcast: {resp.status_code} {err_name}", file=sys.stderr)
        sys.exit(1)
    data = resp.json()
    broadcast_id = data.get("id")
    if not broadcast_id:
        print("ERROR: no broadcast ID in Resend response", file=sys.stderr)
        sys.exit(1)
    return broadcast_id


def send_broadcast(api_key: str, broadcast_id: str) -> None:
    """Trigger sending of a previously created broadcast."""
    resp = requests.post(
        f"{RESEND_API_BASE}/broadcasts/{broadcast_id}/send",
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=30,
    )
    if not resp.ok:
        err_name = "unknown"
        try:
            err_name = str(resp.json().get("name", "unknown"))
        except Exception:
            pass
        print(f"ERROR sending broadcast: {resp.status_code} {err_name}", file=sys.stderr)
        sys.exit(1)

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    api_key = os.environ.get("RESEND_API_KEY", "").strip()
    dry_run = os.environ.get("DRY_RUN", "").lower() == "true"

    audience_mode = (os.environ.get("AUDIENCE", "").strip().lower() or "production")
    if audience_mode not in ("production", "test"):
        print(f"ERROR: AUDIENCE must be 'production' or 'test', got '{audience_mode}'.", file=sys.stderr)
        sys.exit(1)
    is_test = audience_mode == "test"

    # Select the audience explicitly — never fall back from test to production,
    # a misconfigured test send must fail rather than email real subscribers.
    if is_test:
        audience_id = os.environ.get("RESEND_TEST_AUDIENCE_ID", "").strip()
        audience_var = "RESEND_TEST_AUDIENCE_ID"
    else:
        audience_id = os.environ.get("RESEND_AUDIENCE_ID", "").strip()
        audience_var = "RESEND_AUDIENCE_ID"

    if not dry_run:
        if not api_key:
            print("ERROR: RESEND_API_KEY environment variable is not set.", file=sys.stderr)
            sys.exit(1)
        if not audience_id:
            print(f"ERROR: {audience_var} environment variable is not set "
                  f"(required for AUDIENCE={audience_mode}).", file=sys.stderr)
            sys.exit(1)

    print("Loading digest.json…")
    digest = load_digest()

    date_range = format_date_range(digest["period_start"], digest["period_end"])
    subject = build_subject(digest)
    broadcast_name = f"Weekly digest – {date_range}"
    if is_test:
        subject = f"[TEST] {subject}"
        broadcast_name += " (test)"

    print(f"Audience: {audience_mode}")
    print(f"Period: {date_range}")
    print(f"  New deals notified    : {len(digest['new_deals_notified'])}")
    print(f"  Deals cleared         : {len(digest['deals_cleared'])}")
    print(f"  Referred to phase 2   : {len(digest.get('deals_referred_to_phase_2') or [])}")
    print(f"  Deals declined        : {len(digest['deals_declined'])}")
    print(f"  Assessment ceased     : {len(digest.get('deals_assessment_ceased') or [])}")
    print(f"  Ongoing phase 1       : {len(digest['ongoing_phase_1'])}")
    print(f"  Ongoing phase 2       : {len(digest['ongoing_phase_2'])}")

    print("\nBuilding HTML email…")
    html = build_html_email(digest)
    print("Building text email…")
    text = build_text_email(digest)

    if dry_run:
        out_path = Path("/tmp/digest_email_preview.html")
        out_path.write_text(html, encoding="utf-8")
        print(f"\nDRY RUN — email HTML written to {out_path}")
        print(f"Subject: {subject}")
        print("\n--- TEXT VERSION ---\n")
        print(text)
        return

    print(f"\nCreating Resend broadcast '{broadcast_name}'…")
    broadcast_id = create_broadcast(api_key, audience_id, subject, html, broadcast_name, text)
    print(f"Broadcast created: {broadcast_id}")

    print("Sending broadcast…")
    send_broadcast(api_key, broadcast_id)
    print("Broadcast sent successfully.")


if __name__ == "__main__":
    main()
