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
from datetime import datetime
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

# Outlook falls back to Times New Roman unless font-family is set on every
# block-level element, so FONT is stamped on each td/div that holds text.
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
#   * font-family stamped on every td that contains text
#   * width attributes alongside CSS widths
# ---------------------------------------------------------------------------

def merger_link(merger: dict, color: dict) -> str:
    url = f"{SITE_BASE}/mergers/{esc(merger['merger_id'])}"
    name = esc(merger.get("merger_name", merger["merger_id"]))
    return (
        f'<a href="{url}" style="color:{color["dark"]};font-weight:700;'
        f'font-size:14px;text-decoration:none;line-height:1.4;">{name}</a>'
    )


def waiver_chip() -> str:
    # Outlook honours background-color on spans but not padding, so the
    # nbsp padding keeps the chip readable everywhere.
    return (
        ' <span style="background-color:#EEF0EF;color:#6B7280;font-size:10px;'
        'font-weight:700;">&nbsp;WAIVER&nbsp;</span>'
    )


def stat_tile(count: int, label: str, color: dict, anchor: str) -> str:
    url = f"{SITE_BASE}/digest#{anchor}"
    return (
        '<td width="33%" style="padding:4px;" valign="top">'
        f'<a href="{url}" style="text-decoration:none;">'
        '<table width="100%" cellpadding="0" cellspacing="0" border="0" role="presentation">'
        f'<tr><td bgcolor="{color["pale"]}" align="center" '
        f'style="background-color:{color["pale"]};padding:14px 6px 12px;font-family:{FONT};">'
        f'<div style="color:{color["border"]};font-size:24px;font-weight:800;line-height:26px;">{count}</div>'
        f'<div style="color:{color["dark"]};font-size:11px;font-weight:600;line-height:14px;margin-top:5px;">{esc(label)}</div>'
        "</td></tr></table></a></td>"
    )


def stat_grid(tiles: list[str]) -> str:
    rows = ""
    for i in range(0, len(tiles), 3):
        chunk = tiles[i:i + 3]
        while len(chunk) < 3:
            chunk.append('<td width="33%" style="padding:4px;">&nbsp;</td>')
        rows += "<tr>" + "".join(chunk) + "</tr>"
    return (
        '<table width="100%" cellpadding="0" cellspacing="0" border="0" role="presentation">'
        f"{rows}</table>"
    )


def section_header(title: str, color: dict, count: int | None, anchor: str) -> str:
    count_html = (
        f'<td align="right" bgcolor="{color["pale"]}" style="background-color:{color["pale"]};'
        f'padding:12px 16px 11px;font-family:{FONT};font-size:13px;font-weight:700;'
        f'color:{color["dark"]};" valign="middle">{count}</td>'
        if count
        else f'<td bgcolor="{color["pale"]}" style="background-color:{color["pale"]};">&nbsp;</td>'
    )
    return (
        f'<tr><td bgcolor="{color["pale"]}" style="background-color:{color["pale"]};'
        f'border-left:4px solid {color["border"]};padding:12px 16px 11px;'
        f'font-family:{FONT};" valign="middle">'
        f'<a href="{SITE_BASE}/digest#{anchor}" style="text-decoration:none;">'
        f'<span style="font-size:15px;font-weight:700;color:{INK};">{esc(title)}</span></a>'
        f"</td>{count_html}</tr>"
    )


def empty_row(message: str) -> str:
    return (
        f'<tr><td colspan="2" style="padding:14px 16px;'
        f'font-size:13px;color:{FAINT};">{esc(message)}</td></tr>'
    )


def subheading_row(label: str, color: dict) -> str:
    # Pre-uppercased text: Outlook ignores text-transform.
    return (
        f'<tr><td colspan="2" bgcolor="#FAFBFA" style="background-color:#FAFBFA;'
        f'padding:7px 16px 6px;border-bottom:1px solid {ROW_LINE};'
        f'font-size:10px;font-weight:700;color:{color["dark"]};letter-spacing:1px;">'
        f"{esc(label.upper())}</td></tr>"
    )


def item_row(
    merger: dict,
    color: dict,
    date_label: str,
    date_value: str,
    meta_extra: str = "",
    body_html: str = "",
    last: bool = False,
) -> str:
    divider = "" if last else f"border-bottom:1px solid {ROW_LINE};"
    chip = waiver_chip() if merger.get("is_waiver") else ""
    mid = esc(merger.get("merger_id", ""))
    return (
        f'<tr><td colspan="2" style="padding:12px 16px;{divider}">'
        '<table width="100%" cellpadding="0" cellspacing="0" border="0" role="presentation"><tr>'
        f'<td valign="top">{merger_link(merger, color)}{chip}</td>'
        f'<td width="92" align="right" style="padding-left:12px;" valign="top">'
        f'<span style="font-size:10px;font-weight:700;color:{FAINT};letter-spacing:1px;">{esc(date_label.upper())}</span><br>'
        f'<span style="font-size:12px;color:{BODY_TEXT};">{esc(format_date(date_value))}</span></td>'
        "</tr></table>"
        f'<div style="font-size:11px;color:{FAINT};margin-top:3px;">{mid}{meta_extra}</div>'
        f"{body_html}</td></tr>"
    )


def desc_div(text: str) -> str:
    if not text:
        return ""
    return (
        f'<div style="font-size:13px;color:{BODY_TEXT};'
        f'line-height:19px;margin-top:5px;">{esc(text)}</div>'
    )


def determination_div(text: str, color: dict) -> str:
    return (
        f'<div style="font-size:12px;font-weight:700;'
        f'color:{color["dark"]};margin-top:5px;">{esc(text)}</div>'
    )


def section_table(header_row: str, data_rows: str) -> str:
    return (
        '<table width="100%" cellpadding="0" cellspacing="0" border="0" role="presentation" '
        f'style="border:1px solid {HAIRLINE};border-collapse:collapse;">'
        f"{header_row}{data_rows}"
        "</table>"
    )

# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------

def build_new_mergers(mergers: list) -> str:
    c = COLORS["new_merger"]
    hdr = section_header("New mergers notified", c, len(mergers), "new-mergers")
    if not mergers:
        rows = empty_row("No new mergers notified this week.")
    else:
        rows = "".join(
            item_row(
                m, c, "Notified", m.get("effective_notification_datetime"),
                body_html=desc_div(truncate(m.get("merger_description", ""))),
                last=(i == len(mergers) - 1),
            )
            for i, m in enumerate(mergers)
        )
    return section_table(hdr, rows)


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


def build_cleared(mergers: list) -> str:
    c = COLORS["cleared"]
    hdr = section_header("Mergers approved", c, len(mergers), "mergers-approved")
    if not mergers:
        rows = empty_row("No mergers approved this week.")
    else:
        groups = _cleared_groups(mergers)
        rows = ""
        for gi, (label, group_mergers) in enumerate(groups):
            rows += subheading_row(label, c)
            last_group = gi == len(groups) - 1
            for i, m in enumerate(group_mergers):
                det = (
                    m.get("accc_determination")
                    or m.get("phase_1_determination")
                    or m.get("phase_2_determination")
                    or "Approved"
                )
                rows += item_row(
                    m, c, "Cleared", m.get("determination_publication_date"),
                    body_html=determination_div(det, c),
                    last=(last_group and i == len(group_mergers) - 1),
                )
    return section_table(hdr, rows)


def build_declined(mergers: list) -> str:
    c = COLORS["declined"]
    hdr = section_header("Mergers declined", c, len(mergers), "mergers-declined")
    if not mergers:
        rows = empty_row("No mergers declined this week.")
    else:
        rows = ""
        for i, m in enumerate(mergers):
            det = (
                m.get("accc_determination")
                or m.get("phase_1_determination")
                or m.get("phase_2_determination")
                or "Not approved"
            )
            rows += item_row(
                m, c, "Declined", m.get("determination_publication_date"),
                body_html=determination_div(det, c),
                last=(i == len(mergers) - 1),
            )
    return section_table(hdr, rows)


def build_referred_to_phase_2(mergers: list) -> str:
    c = COLORS["phase_2_referral"]
    hdr = section_header("Mergers referred to phase 2", c, len(mergers), "mergers-referred")
    if not mergers:
        rows = empty_row("No mergers referred to phase 2 this week.")
    else:
        rows = ""
        for i, m in enumerate(mergers):
            det = (
                m.get("accc_determination")
                or m.get("phase_1_determination")
                or "Referred to phase 2"
            )
            rows += item_row(
                m, c, "Referred", m.get("phase_1_determination_date"),
                body_html=determination_div(det, c),
                last=(i == len(mergers) - 1),
            )
    return section_table(hdr, rows)


def build_ceased(mergers: list) -> str:
    c = COLORS["ceased"]
    hdr = section_header("Assessment ceased", c, len(mergers), "mergers-ceased")
    rows = "".join(
        item_row(
            m, c, "Ceased", m.get("ceased_date"),
            body_html=determination_div(m.get("stage") or "N/A", c),
            last=(i == len(mergers) - 1),
        )
        for i, m in enumerate(mergers)
    )
    return section_table(hdr, rows)


def build_phase_section(mergers: list, phase_key: str, title: str, anchor: str) -> str:
    c = COLORS[phase_key]
    hdr = section_header(title, c, len(mergers), anchor)
    if not mergers:
        rows = empty_row(f"No ongoing {title.lower().split('–')[0].strip()} mergers.")
    else:
        rows = ""
        for i, m in enumerate(mergers):
            notified = format_date(m.get("effective_notification_datetime"))
            rows += item_row(
                m, c, "Due", m.get("end_of_determination_period"),
                meta_extra=f" &middot; Notified {esc(notified)}",
                body_html=desc_div(truncate(m.get("merger_description", ""), 150)),
                last=(i == len(mergers) - 1),
            )
    return section_table(hdr, rows)

# ---------------------------------------------------------------------------
# Full email builder
# ---------------------------------------------------------------------------

def _section_row(section_html: str) -> str:
    """Wrap a section table in an outer-wrapper row (spacing via td padding,
    since Outlook ignores margins on tables)."""
    return (
        '<tr><td bgcolor="#ffffff" style="background-color:#ffffff;'
        f'padding:0 22px 18px;border-left:1px solid {HAIRLINE};'
        f'border-right:1px solid {HAIRLINE};">{section_html}</td></tr>'
    )


def build_html_email(digest: dict) -> str:
    date_range = format_date_range(digest["period_start"], digest["period_end"])
    show_feedback = _is_feedback_week(digest.get("period_start", ""))
    new_count = len(digest["new_deals_notified"])
    cleared_count = len(digest["deals_cleared"])
    referred_count = len(digest.get("deals_referred_to_phase_2") or [])
    declined_count = len(digest["deals_declined"])
    ceased_mergers = digest.get("deals_assessment_ceased") or []
    ceased_count = len(ceased_mergers)
    phase1_count = len(digest["ongoing_phase_1"])
    phase2_count = len(digest["ongoing_phase_2"])

    tiles = [
        stat_tile(new_count, "New deals", COLORS["new_merger"], "new-mergers"),
        stat_tile(cleared_count, "Cleared", COLORS["cleared"], "mergers-approved"),
    ]
    if ceased_count > 0:
        tiles.append(stat_tile(ceased_count, "Assessment ceased", COLORS["ceased"], "mergers-ceased"))
    tiles += [
        stat_tile(referred_count, "Referred to phase 2", COLORS["phase_2_referral"], "mergers-referred"),
        stat_tile(declined_count, "Declined", COLORS["declined"], "mergers-declined"),
        stat_tile(phase1_count, "Ongoing phase 1", COLORS["phase_1"], "ongoing-phase-1"),
        stat_tile(phase2_count, "Ongoing phase 2", COLORS["phase_2"], "ongoing-phase-2"),
    ]

    sections = (
        _section_row(build_new_mergers(digest["new_deals_notified"]))
        + _section_row(build_cleared(digest["deals_cleared"]))
        + (_section_row(build_ceased(ceased_mergers)) if ceased_mergers else "")
        + _section_row(build_referred_to_phase_2(digest.get("deals_referred_to_phase_2") or []))
        + _section_row(build_declined(digest["deals_declined"]))
        + _section_row(build_phase_section(
            digest["ongoing_phase_1"], "phase_1",
            "Ongoing – phase 1 – initial assessment", "ongoing-phase-1",
        ))
        + _section_row(build_phase_section(
            digest["ongoing_phase_2"], "phase_2",
            "Ongoing – phase 2 – detailed assessment", "ongoing-phase-2",
        ))
    )

    if show_feedback:
        header_cta = (
            "Got thoughts, feedback or any market gossip? Just reply to this email — "
            "we&rsquo;d love to hear from you."
        )
    else:
        header_cta = (
            "Were you forwarded this email? Sign up "
            f'<a href="{SITE_BASE}/digest" '
            f'style="color:{GREEN};text-decoration:underline;">here</a>.'
        )

    preheader_bits = [f"{new_count} new deals notified", f"{cleared_count} cleared"]
    if ceased_count:
        preheader_bits.append(f"{ceased_count} ceased")
    if referred_count:
        preheader_bits.append(f"{referred_count} referred to phase 2")
    if declined_count:
        preheader_bits.append(f"{declined_count} declined")
    preheader_bits.append(f"{phase1_count + phase2_count} ongoing")
    preheader = ", ".join(preheader_bits) + "."

    # Resend replaces {{{RESEND_UNSUBSCRIBE_URL}}} with the real link
    unsub_var = "{{{RESEND_UNSUBSCRIBE_URL}}}"

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
  <title>Weekly mergers digest for {esc(date_range)} | Australian Merger Tracker</title>
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

        <!-- HEADER -->
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
          <td bgcolor="{GREEN_PALE}" style="background-color:{GREEN_PALE};padding:10px 30px;
                     border-left:1px solid {HAIRLINE};border-right:1px solid {HAIRLINE};
                     font-family:{FONT};font-size:12px;color:#3E5F51;font-style:italic;">
            {header_cta}
          </td>
        </tr>

        <!-- AT A GLANCE -->
        <tr>
          <td bgcolor="#ffffff" style="background-color:#ffffff;padding:20px 18px 10px;
                     border-left:1px solid {HAIRLINE};border-right:1px solid {HAIRLINE};">
            <div style="font-family:{FONT};font-size:11px;font-weight:700;color:{FAINT};
                        letter-spacing:1px;margin:0 4px 8px;">THIS WEEK AT A GLANCE</div>
            {stat_grid(tiles)}
          </td>
        </tr>

        <!-- SPACER -->
        <tr>
          <td bgcolor="#ffffff" style="background-color:#ffffff;font-size:1px;line-height:12px;
                     border-left:1px solid {HAIRLINE};border-right:1px solid {HAIRLINE};">&nbsp;</td>
        </tr>

        <!-- SECTIONS -->
        {sections}

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
    subject = f"Weekly mergers digest for {date_range} | Australian Merger Tracker"
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
