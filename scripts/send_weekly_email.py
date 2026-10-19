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
    BANNER                   — Which message the strip under the masthead carries:
                               'social' (default) invites readers to follow the
                               LinkedIn and Bluesky accounts, 'signup' asks a
                               forwarded reader to subscribe. Feedback weeks
                               override either with the feedback ask.
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

from scripts.constants import merger_status
from scripts.constants.tribunal import APPEAL_OUTCOME_LABELS, appeal_type_label
from scripts.date_utils import parse_iso_datetime

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

SITE_BASE = "https://mergers.fyi"
BLUESKY_URL = "https://bsky.app/profile/mergers.fyi"
LINKEDIN_URL = "https://www.linkedin.com/company/mergers-fyi"

BANNERS = ("social", "signup")
DEFAULT_BANNER = "social"


def banner_choice() -> str:
    """The BANNER env var, or the default when unset. Validated in main()."""
    return os.environ.get("BANNER", "").strip().lower() or DEFAULT_BANNER
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
    "tribunal_appeal":  {"border": "#2563eb", "pale": "#DBEAFE", "dark": "#1D4ED8"},
    "phase_1":          {"border": "#B8935C", "pale": "#FCECC9", "dark": "#8A6B3E"},
    "phase_2":          {"border": "#52489c", "pale": "#E8E5F3", "dark": "#3A3372"},
}

GREEN = "#335145"          # site primary
GREEN_PALE = "#EAF1EC"     # banner background
GREEN_ON_PALE = "#2C4A3E"  # banner text
FOOTER_TEXT = "#CBDDD2"    # links on the green footer
FOOTER_MUTED = "#A9C6B6"   # small print on the green footer
WORDMARK_DOT = "#10b981"   # the accent "." in the mergers.fyi wordmark
INK = "#111827"            # headings, matter names, figures
BODY_TEXT = "#4B5563"
MUTED = "#6B7280"
LINE = "#E5E7EB"           # row dividers
TILE_BG = "#F9FAFB"        # scoreboard tiles
PAGE_BG = "#F3F4F1"
DUE_SOON = "#92400E"       # text on the amber pill for imminent deadlines
DUE_SOON_BG = "#FEF3C7"

# Outlook falls back to Times New Roman unless font-family is set; the
# embedded <style> block covers modern clients and the MSO conditional
# covers Outlook, so FONT is only stamped on structural elements.
FONT = "'Segoe UI',Arial,Helvetica,sans-serif"
# Matter IDs. Consolas ships with every Windows install, so Outlook gets it.
MONO = "Consolas,'SF Mono',Menlo,monospace"

# Layout primitives. Outlook's Word renderer ignores padding on <span>/<div>
# backgrounds, border-radius and max-width, so every fill is a bgcolor'd <td>
# and the 640px column is pinned by a ghost table inside an MSO conditional.
TABLE = 'cellpadding="0" cellspacing="0" border="0" role="presentation"'
FULL_TABLE = f'width="100%" {TABLE}'

# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_digest() -> dict:
    digest_path = (
        Path(__file__).parent.parent
        / "frontend" / "public" / "data" / "digest.json"
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


def with_conditions(merger: dict) -> bool:
    """True when a cleared deal was cleared subject to conditions.

    The register publishes a conditional clearance as a plain "Approved" and
    carries the conditions separately in ``has_conditions`` (set by
    enrichment.detect_has_conditions and passed through the digest summary),
    so the flag is the only signal here. Mirrors the frontend's
    isConditionalApproval(). Older digest snapshots predate the field, in
    which case nothing is marked.
    """
    return bool(merger.get("has_conditions"))


def conditions_note(n: int) -> str:
    """The bracketed rider on a clearance count, e.g. ' (2 with conditions)'."""
    return f" ({n} with conditions)" if n else ""


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


def build_text_email(digest: dict, banner: str | None = None) -> str:
    """Build a plain-text version of the weekly digest email."""
    banner = banner or banner_choice()
    date_range = format_date_range(digest["period_start"], digest["period_end"])

    cleared_conditions = conditions_note(
        sum(1 for m in digest["deals_cleared"] if with_conditions(m))
    )
    referred = digest.get("deals_referred_to_phase_2") or []
    ceased = digest.get("deals_assessment_ceased") or []
    appealed = digest.get("deals_appealed_to_tribunal") or []
    tribunal_decided = digest.get("deals_decided_by_tribunal") or []
    ongoing_appeals = digest.get("ongoing_tribunal_appeals") or []

    lines = [
        "Australian Merger Tracker weekly digest",
        f"Week of {date_range}",
        f"{SITE_BASE}/digest",
        "",
        "SUMMARY",
        "-------",
        f"New deals notified   : {len(digest['new_deals_notified'])}",
        f"Cleared              : {len(digest['deals_cleared'])}{cleared_conditions}",
    ]
    if ceased:
        lines.append(f"Assessment ceased    : {len(ceased)}")
    lines += [
        f"Referred to phase 2  : {len(referred)}",
        f"Declined             : {len(digest['deals_declined'])}",
    ]
    if appealed:
        lines.append(f"Appealed to tribunal : {len(appealed)}")
    if tribunal_decided:
        lines.append(f"Decided by tribunal  : {len(tribunal_decided)}")
    lines += [
        f"Ongoing phase 1      : {len(digest['ongoing_phase_1'])}",
        f"Ongoing phase 2      : {len(digest['ongoing_phase_2'])}",
    ]
    if digest.get('ongoing_public_benefit'):
        lines.append(f"Public benefit phase : {len(digest['ongoing_public_benefit'])}")
    if ongoing_appeals:
        lines.append(f"Under appeal         : {len(ongoing_appeals)}")
    lines.append("")

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
                [
                    m.get("merger_name", m["merger_id"])
                    + (" (with conditions)" if with_conditions(m) else ""),
                    format_date(m.get("determination_publication_date")),
                ]
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

    if appealed:
        appealed_rows = [
            [
                m.get("merger_name", m["merger_id"]),
                format_date((m.get("appeal") or {}).get("filed_date")),
                appeal_type_label(m.get("appeal")),
            ]
            for m in appealed
        ]
        lines.append(_text_section("APPEALED TO TRIBUNAL", ["Merger", "Filed", "Type"], appealed_rows, ""))
        lines.append("")
        lines.append("")

    if tribunal_decided:
        tribunal_rows = [
            [
                m.get("merger_name", m["merger_id"]),
                format_date((m.get("appeal") or {}).get("concluded_date")),
                APPEAL_OUTCOME_LABELS.get((m.get("appeal") or {}).get("outcome"), "N/A"),
            ]
            for m in tribunal_decided
        ]
        lines.append(_text_section("DECIDED BY TRIBUNAL", ["Merger", "Concluded", "Outcome"], tribunal_rows, ""))
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

    if digest.get("ongoing_public_benefit"):
        public_benefit_rows = [
            [m.get("merger_name", m["merger_id"]), format_date(m.get("end_of_determination_period"))]
            for m in digest["ongoing_public_benefit"]
        ]
        lines.append(_text_section("ONGOING – PUBLIC BENEFIT PHASE", ["Merger", "Determination due"], public_benefit_rows, ""))
        lines.append("")

    if ongoing_appeals:
        appeal_rows = [
            [
                m.get("merger_name", m["merger_id"]),
                format_date((m.get("appeal") or {}).get("filed_date")),
                format_date(hearing) if (hearing := (m.get("appeal") or {}).get("hearing_date")) else "TBC",
                appeal_type_label(m.get("appeal")),
            ]
            for m in ongoing_appeals
        ]
        lines.append(_text_section("ONGOING ACT APPEALS", ["Merger", "Filed", "Hearing", "Type"], appeal_rows, ""))
        lines.append("")
        lines.append("")

    unsub_var = "{{{RESEND_UNSUBSCRIBE_URL}}}"
    footer = [
        "--",
        "You're receiving this because you subscribed at mergers.fyi.",
        f"Unsubscribe: {unsub_var}",
    ]
    if _is_feedback_week(digest.get("period_start", "")):
        footer.insert(0, "Got thoughts, feedback or any market gossip? Just reply to this email - we'd love to hear from you.")
    elif banner == "social":
        footer.insert(0, "Follow mergers.fyi for new deals and decisions as they happen:")
        footer.insert(1, f"LinkedIn: {LINKEDIN_URL}")
        footer.insert(2, f"Bluesky:  {BLUESKY_URL}")
    if footer[0] != "--":
        footer.insert(footer.index("--"), "")
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
    """An inline label, for use mid-line after a matter name.

    Outlook honours background-color on spans but not padding, so the nbsp
    padding keeps the chip readable everywhere. Where a label leads its own
    line, ``pill`` gives a properly padded cell instead.
    """
    return (
        f'<span style="background-color:{pale};color:{dark};font-size:10px;'
        f'font-weight:700;letter-spacing:0.6px;">&nbsp;{label}&nbsp;</span>'
    )


def waiver_chip() -> str:
    return " " + chip("WAIVER", "#EEF0EF", MUTED)


def pill(label: str, pale: str, dark: str, size: int = 10) -> str:
    """A padded label cell. A <td> is the only element Outlook pads."""
    return (
        f'<td bgcolor="{pale}" style="background-color:{pale};padding:3px 8px;'
        f'font-size:{size}px;font-weight:700;letter-spacing:0.6px;color:{dark};'
        f'white-space:nowrap;">{label}</td>'
    )


def pill_line(pills: list[str], meta: str) -> str:
    """Pills followed by a meta line, kept on one row in every client."""
    gap = '<td width="6" style="font-size:1px;line-height:1px;">&nbsp;</td>'
    cells = "".join(p + gap for p in pills)
    return (
        f"<table {TABLE}><tr>{cells}"
        f'<td style="font-size:12px;line-height:18px;color:{MUTED};">{meta}</td></tr></table>'
    )


def matter_id(merger: dict, color: str = MUTED) -> str:
    return (
        f'<span style="font-family:{MONO};font-size:12px;color:{color};">'
        f'{esc(merger.get("merger_id", ""))}</span>'
    )


def _counts(digest: dict) -> dict:
    return {
        "new": len(digest["new_deals_notified"]),
        "cleared": len(digest["deals_cleared"]),
        "cleared_with_conditions": sum(
            1 for m in digest["deals_cleared"] if with_conditions(m)
        ),
        "referred": len(digest.get("deals_referred_to_phase_2") or []),
        "declined": len(digest["deals_declined"]),
        "ceased": len(digest.get("deals_assessment_ceased") or []),
        "appealed": len(digest.get("deals_appealed_to_tribunal") or []),
        "p1": len(digest["ongoing_phase_1"]),
        "p2": len(digest["ongoing_phase_2"]),
        "pb": len(digest.get("ongoing_public_benefit") or []),
        "on_appeal": len(digest.get("ongoing_tribunal_appeals") or []),
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

    # A conditional clearance is published as a plain "Approved", so the lede
    # spells the split out rather than letting it read as a clean sweep.
    conditions = conditions_note(c.get("cleared_with_conditions", 0))

    sentences = []
    if c["new"] and c["cleared"]:
        sentences.append(
            f"The ACCC was notified of {b(c['new'])} new {pluralise(c['new'], 'deal')} "
            f"this week and cleared {b(c['cleared'])}{conditions}."
        )
    elif c["new"]:
        sentences.append(
            f"The ACCC was notified of {b(c['new'])} new {pluralise(c['new'], 'deal')} this week, "
            "and cleared none."
        )
    elif c["cleared"]:
        sentences.append(
            f"The ACCC cleared {b(c['cleared'])} {pluralise(c['cleared'], 'deal')}{conditions} "
            "this week, with no new deals notified."
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
    if c["appealed"]:
        mid.append(
            f"{bw(c['appealed'])} {pluralise(c['appealed'], 'deal was', 'deals were')} "
            "appealed to the Tribunal"
        )
    if mid:
        sentence = join_and(mid)
        # Capitalise the first letter, skipping the <strong …> markup
        sentences.append(re.sub(r">([a-z])", lambda m: ">" + m.group(1).upper(), sentence, count=1) + ".")

    # A public benefit application keeps the matter live, so it counts as on
    # foot alongside the two review phases (as it does in the pipeline).
    stages = [
        (n, where) for n, where in (
            (c["p1"], "in phase 1"),
            (c["p2"], "in phase 2"),
            (c.get("pb", 0), "in the public benefit phase"),
        ) if n
    ]
    ongoing = sum(n for n, _ in stages)
    if ongoing:
        if len(stages) == 1:
            split = f", all {stages[0][1]}"
        else:
            split = " – " + join_and([f"{b(n)} {where}" for n, where in stages])
        sentences.append(
            f"{b(ongoing)} {pluralise(ongoing, 'assessment remains', 'assessments remain')} "
            f"on foot{split}."
        )

    if c["on_appeal"]:
        sentences.append(
            f"{b(c['on_appeal'])} {pluralise(c['on_appeal'], 'matter remains', 'matters remain')} "
            "under appeal at the Tribunal."
        )

    return " ".join(sentences)


def _tiles(cells: list[tuple]) -> str:
    """One row of scoreboard tiles, each topped with its outcome colour."""
    tds = []
    # Tiles and the gaps between them split the row by percentage, so the
    # tiles stay equal whatever their labels and the gaps survive narrowing.
    gap = 2
    share = f"{(100 - gap * (len(cells) - 1)) // len(cells)}%"
    for i, (n, label, color, anchor) in enumerate(cells):
        if i:
            tds.append(f'<td width="{gap}%" style="font-size:1px;line-height:1px;">&nbsp;</td>')
        tds.append(
            f'<td class="tile" width="{share}" valign="top" bgcolor="{TILE_BG}" style="background-color:{TILE_BG};'
            f'border-top:3px solid {color["border"]};padding:12px 14px;">'
            f'<a href="{SITE_BASE}/digest#{anchor}" style="text-decoration:none;">'
            f'<span class="tile-n" style="font-size:28px;line-height:32px;font-weight:700;color:{INK};">{n}</span><br>'
            f'<span style="font-size:12px;line-height:16px;color:{MUTED};">{label}</span>'
            "</a></td>"
        )
    return f'<table {FULL_TABLE}><tr>{"".join(tds)}</tr></table>'


def _eyebrow(text: str) -> str:
    return (
        f'<div style="font-size:11px;font-weight:700;letter-spacing:1.4px;'
        f'color:{MUTED};padding-bottom:8px;">{text.upper()}</div>'
    )


def build_scoreboard(c: dict) -> str:
    """Linked figures under the lede: this week's outcomes, then what is on foot."""
    week = [
        (c["new"], "New deals", COLORS["new_merger"], "new-mergers"),
        (c["cleared"], "Cleared", COLORS["cleared"], "mergers-approved"),
    ]
    if c["ceased"]:
        week.append((c["ceased"], "Ceased", COLORS["ceased"], "mergers-ceased"))
    if c["appealed"]:
        week.append((c["appealed"], "Appealed", COLORS["tribunal_appeal"], "mergers-appealed"))
    week += [
        (c["referred"], "To phase 2", COLORS["phase_2_referral"], "mergers-referred"),
        (c["declined"], "Declined", COLORS["declined"], "mergers-declined"),
    ]
    on_foot = [
        (c["p1"], "In phase 1", COLORS["phase_1"], "ongoing-phase-1"),
        (c["p2"], "In phase 2", COLORS["phase_2"], "ongoing-phase-2"),
    ]
    if c["pb"]:
        on_foot.append((c["pb"], "Public benefit", COLORS["phase_2"], "ongoing-public-benefit"))
    if c["on_appeal"]:
        on_foot.append((c["on_appeal"], "On appeal", COLORS["tribunal_appeal"], "ongoing-tribunal-appeals"))
    return (
        _eyebrow("This week") + _tiles(week)
        + '<div style="font-size:1px;line-height:16px;">&nbsp;</div>'
        + _eyebrow("On foot") + _tiles(on_foot)
    )


def section_head(title: str, accent: str, right_text: str = "") -> str:
    """A section title over a heavy rule. ``accent`` colours the rows, not the
    head, so every section reads with the same weight."""
    rule = f"border-bottom:2px solid {INK};"
    return (
        f'<tr><td style="padding:40px 0 12px;{rule}font-size:22px;line-height:28px;'
        f'font-weight:700;color:{INK};" valign="bottom">{esc(title)}</td>'
        f'<td align="right" style="padding:40px 0 14px;{rule}font-size:13px;'
        f'color:{MUTED};white-space:nowrap;" valign="bottom">{esc(right_text) or "&nbsp;"}</td></tr>'
    )


def empty_section_row(message: str) -> str:
    return (
        f'<tr><td colspan="2" style="padding:16px 0;font-size:14px;'
        f'color:{MUTED};font-style:italic;">{esc(message)}</td></tr>'
    )


def section_table(rows: str) -> str:
    return f"<table {FULL_TABLE}>{rows}</table>"


def bar_row(color: str, inner: str, last: bool) -> str:
    """A list row with a slim outcome-coloured rule down its left edge."""
    divider = "" if last else f"border-bottom:1px solid {LINE};"
    return (
        f'<tr><td colspan="2" style="padding:18px 0;{divider}">'
        f"<table {FULL_TABLE}><tr>"
        f'<td width="3" bgcolor="{color}" style="background-color:{color};font-size:1px;line-height:1px;">&nbsp;</td>'
        f'<td width="16" style="font-size:1px;line-height:1px;">&nbsp;</td>'
        f'<td valign="top">{inner}</td></tr></table></td></tr>'
    )


def row_title(merger: dict, size: int = 15) -> str:
    return (
        f'<a href="{merger_url(merger)}" style="color:{INK};font-size:{size}px;'
        f'line-height:{size + 6}px;font-weight:700;text-decoration:none;">{merger_name(merger)}</a>'
    )


def row_detail(text: str) -> str:
    return (
        f'<div style="font-size:13px;line-height:19px;color:{BODY_TEXT};padding-top:6px;">{text}</div>'
        if text else ""
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
            meta_bits = [
                matter_id(m, c["border"]),
                f"Notified {esc(format_date(m.get('effective_notification_datetime')))}",
            ]
            if m.get("end_of_determination_period"):
                meta_bits.append(
                    f"Decision due {esc(format_date(m.get('end_of_determination_period')))}"
                )
            desc = truncate(m.get("merger_description", ""))
            desc_html = (
                f'<div style="font-size:14px;line-height:21px;color:{BODY_TEXT};'
                f'padding-top:8px;">{esc(desc)}</div>'
                if desc else ""
            )
            waiver = waiver_chip() if m.get("is_waiver") else ""
            rows += bar_row(c["border"], (
                f"{row_title(m, 16)}{waiver}"
                f'<div style="font-size:12px;line-height:18px;color:{MUTED};padding-top:4px;">'
                f'{" &nbsp;&middot;&nbsp; ".join(meta_bits)}</div>'
                f"{desc_html}"
            ), last=i == len(mergers) - 1)
    return section_table(rows)


# Decision groups, in the order the Decisions section lists them: the
# tribunal's decisions first, then the ACCC's from the latest stage back.
TRIBUNAL, PUBLIC_BENEFIT, PHASE_2, PHASE_1, WAIVER = (
    "tribunal", "public_benefit", "phase_2", "phase_1", "waiver",
)
_DECISION_GROUP_ORDER = [TRIBUNAL, PUBLIC_BENEFIT, PHASE_2, PHASE_1, WAIVER]
_DECISION_GROUP_LABELS = {
    TRIBUNAL: "Tribunal",
    PUBLIC_BENEFIT: "Public benefit",
    PHASE_2: "Phase 2",
    PHASE_1: "Phase 1",
    WAIVER: "Waiver",
}
_STAGE_GROUPS = {
    merger_status.PUBLIC_BENEFITS: PUBLIC_BENEFIT,
    merger_status.PHASE_2: PHASE_2,
    merger_status.PHASE_1: PHASE_1,
    merger_status.WAIVER: WAIVER,
}

# Within a group the least routine outcomes lead: adverse ones (a refusal, a
# referral to phase 2), then anything else out of the ordinary (a ceased
# assessment, a withdrawn appeal), then clearances.
_ADVERSE, _OTHER, _CLEARANCE = 0, 1, 2


def _determination_group(merger: dict) -> str:
    """The stage whose determination put a cleared or declined deal in the
    digest. A Phase 2 outcome caught on its own date after the matter moved on
    to the public benefit phase has no public benefit determination yet, so it
    stays a Phase 2 decision."""
    if merger.get("public_benefits_determination"):
        return PUBLIC_BENEFIT
    if merger.get("phase_2_determination"):
        return PHASE_2
    if merger.get("is_waiver"):
        return WAIVER
    return PHASE_1


_CLEARED_GROUP_LABELS = {
    PUBLIC_BENEFIT: "Public benefit phase",
    PHASE_2: "Phase 2 – detailed assessment",
    PHASE_1: "Phase 1 – initial assessment",
    WAIVER: "Waiver",
}


def _cleared_groups(mergers: list) -> list[tuple[str, list]]:
    """Return non-empty (label, items) groups, latest stage first."""
    return [
        (label, items)
        for group, label in _CLEARED_GROUP_LABELS.items()
        if (items := [m for m in mergers if _determination_group(m) == group])
    ]


_GENERIC_DETERMINATIONS = {"approved", "not approved", "declined", "referred to phase 2"}


def _specific(det: str) -> str:
    """A determination worth printing: blank for the generic outcomes the chip
    already states."""
    return det if det.lower() not in _GENERIC_DETERMINATIONS else ""


def _headline_determination(m: dict) -> str:
    return (
        m.get("accc_determination")
        or m.get("public_benefits_determination")
        or m.get("phase_1_determination")
        or m.get("phase_2_determination")
        or ""
    )


def _tribunal_entry(m: dict) -> dict:
    appeal = m.get("appeal") or {}
    effective = appeal.get("effective_determination") or ""
    if effective in merger_status.BLOCKED_DETERMINATIONS:
        chip_label, color, rank = "DECLINED", COLORS["declined"], _ADVERSE
    elif effective in merger_status.CLEARED_DETERMINATIONS:
        chip_label, color, rank = "CLEARED", COLORS["cleared"], _CLEARANCE
    else:
        chip_label, color, rank = "TRIBUNAL", COLORS["tribunal_appeal"], _OTHER
    return {
        "merger": m,
        "chip_label": chip_label,
        "color": color,
        "context": _DECISION_GROUP_LABELS[TRIBUNAL],
        "date": appeal.get("concluded_date"),
        "detail": APPEAL_OUTCOME_LABELS.get(appeal.get("outcome"), ""),
        "group": TRIBUNAL,
        "rank": rank,
    }


def _decision_entries(digest: dict) -> list[dict]:
    """Flatten the week's outcomes into one list, grouped tribunal → public
    benefit → phase 2 → phase 1 → waiver, and within each group declines and
    referrals to phase 2 first, then ceased assessments, then clearances."""
    entries = [_tribunal_entry(m) for m in digest.get("deals_decided_by_tribunal") or []]
    for m in digest["deals_cleared"]:
        group = _determination_group(m)
        entries.append({
            "merger": m,
            "chip_label": "CLEARED",
            "color": COLORS["cleared"],
            "context": _DECISION_GROUP_LABELS[group],
            "date": (
                m.get("determination_publication_date")
                or m.get("phase_2_determination_date")
            ),
            "detail": _specific(_headline_determination(m)),
            "group": group,
            "rank": _CLEARANCE,
            "with_conditions": with_conditions(m),
        })
    for m in digest.get("deals_referred_to_phase_2") or []:
        det = m.get("accc_determination") or m.get("phase_1_determination") or ""
        entries.append({
            "merger": m,
            "chip_label": "TO PHASE 2",
            "color": COLORS["phase_2_referral"],
            "context": "Phase 1 determination",
            "date": m.get("phase_1_determination_date"),
            "detail": _specific(det),
            "group": PHASE_1,
            "rank": _ADVERSE,
        })
    for m in digest["deals_declined"]:
        group = _determination_group(m)
        entries.append({
            "merger": m,
            "chip_label": "DECLINED",
            "color": COLORS["declined"],
            "context": _DECISION_GROUP_LABELS[group],
            "date": (
                m.get("determination_publication_date")
                or m.get("phase_2_determination_date")
            ),
            "detail": _specific(_headline_determination(m)),
            "group": group,
            "rank": _ADVERSE,
        })
    for m in digest.get("deals_assessment_ceased") or []:
        entries.append({
            "merger": m,
            "chip_label": "CEASED",
            "color": COLORS["ceased"],
            "context": m.get("stage") or "",
            "date": m.get("ceased_date"),
            "detail": "",
            "group": _STAGE_GROUPS.get(merger_status.stage_phase(m.get("stage")), PHASE_1),
            "rank": _OTHER,
        })
    # Stable sort, so each bucket's own date order survives within a rank.
    entries.sort(key=lambda e: (_DECISION_GROUP_ORDER.index(e["group"]), e["rank"]))
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
            meta_bits = [x for x in (
                e["context"],
                esc(format_date(e["date"])),
                esc(m.get("merger_id", "")),
            ) if x]
            waiver = waiver_chip() if m.get("is_waiver") and e["chip_label"] != "CLEARED" else ""
            # The register records a conditional clearance as a plain
            # "Approved", so the row says so rather than letting it read as an
            # unconditional clearance.
            pills = [pill(e["chip_label"], e["color"]["pale"], e["color"]["dark"])]
            if e.get("with_conditions"):
                pills.append(pill("WITH CONDITIONS", e["color"]["pale"], e["color"]["dark"]))
            rows += bar_row(e["color"]["border"], (
                f"{row_title(m)}{waiver}"
                f'<div style="padding-top:7px;">{pill_line(pills, " &middot; ".join(meta_bits))}</div>'
                f'{row_detail(esc(e["detail"]))}'
            ), last=i == len(entries) - 1)
    return section_table(rows)


def _appeal_rows(mergers: list, chip_label: str, show_hearing: bool) -> str:
    """Render the shared appeal row body for the two tribunal sections.

    "Appealed to tribunal" (this week's filings) and "Ongoing ACT appeals" (the
    live snapshot) draw an identical row — merger link, chip, meta line,
    appellant/tribunal-number detail — and differ only in the chip's wording and
    in whether the hearing date appears in the meta line. Kept as one renderer
    so the two can't drift apart.
    """
    rows = ""
    c = COLORS["tribunal_appeal"]
    for i, m in enumerate(mergers):
        appeal = m.get("appeal") or {}
        hearing = (
            f"Hearing {esc(format_date(appeal['hearing_date']))}"
            if show_hearing and appeal.get("hearing_date") else ""
        )
        meta_bits = [x for x in (
            appeal_type_label(appeal),
            f"Filed {esc(format_date(appeal.get('filed_date')))}",
            hearing,
            esc(m.get("merger_id", "")),
        ) if x]
        detail_bits = []
        if appeal.get("appellant"):
            detail_bits.append(f"Lodged by {esc(appeal['appellant'])}")
        if appeal.get("tribunal_number"):
            detail_bits.append(esc(appeal["tribunal_number"]))
        rows += bar_row(c["border"], (
            f"{row_title(m)}"
            f'<div style="padding-top:7px;">{pill_line([pill(chip_label, c["pale"], c["dark"])], " &middot; ".join(meta_bits))}</div>'
            f'{row_detail(" &middot; ".join(detail_bits))}'
        ), last=i == len(mergers) - 1)
    return rows


def build_tribunal_appeals(mergers: list) -> str:
    """Deals taken to the Australian Competition Tribunal for review this week."""
    c = COLORS["tribunal_appeal"]
    rows = section_head("Appealed to tribunal", c["border"],
                        f"{len(mergers)} this week" if mergers else "")
    if not mergers:
        rows += empty_section_row("No deals were appealed to the tribunal this week.")
    else:
        # This week's filings have no hearing listed yet often enough that the
        # date would read as noise; the ongoing section carries it instead.
        rows += _appeal_rows(mergers, "APPEALED", show_hearing=False)
    return section_table(rows)


def _phase_group_row(label: str, color: dict, count: int) -> str:
    return (
        f'<tr><td colspan="2" style="padding:18px 0 8px;"><table {TABLE}><tr>'
        f'{pill(esc(label.upper()), color["pale"], color["dark"])}'
        f'<td style="padding-left:8px;font-size:12px;color:{MUTED};">{count}</td>'
        "</tr></table></td></tr>"
    )


def build_pipeline(digest: dict) -> str:
    """All ongoing assessments as a compact list, grouped by phase (public
    benefit, then phase 2, first) and sorted by decision due date within each group. Dates due
    within a fortnight are picked out on an amber pill."""
    far_future = datetime(9999, 1, 1, tzinfo=timezone.utc)

    def due_dt(m: dict):
        return parse_iso_datetime(m.get("end_of_determination_period") or "")

    groups = [
        # Shares the phase 2 colour: a public benefit application only follows
        # a Phase 2 determination, and it is the later, weightier stage.
        ("Public benefit phase", "phase_2", sorted(digest.get("ongoing_public_benefit") or [], key=lambda m: due_dt(m) or far_future)),
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
    col_head = f"padding:14px 0 0;font-size:11px;font-weight:700;letter-spacing:1px;color:{MUTED};"
    rows += (
        f'<tr><td style="{col_head}">MATTER</td>'
        f'<td align="right" style="{col_head}">DECISION DUE</td></tr>'
    )
    for label, phase_key, mergers in groups:
        rows += _phase_group_row(label, COLORS[phase_key], len(mergers))
        for m in mergers:
            divider = f"border-bottom:1px solid {LINE};"
            dt = due_dt(m)
            soon = cutoff is not None and dt is not None and dt <= cutoff
            due = esc(format_date(m.get("end_of_determination_period")))
            due_html = (
                f'<table {TABLE} align="right"><tr>{pill(due, DUE_SOON_BG, DUE_SOON, 12)}</tr></table>'
                if soon
                else f'<span style="font-size:13px;color:{BODY_TEXT};">{due}</span>'
            )
            waiver = waiver_chip() if m.get("is_waiver") else ""
            rows += (
                f'<tr><td style="padding:10px 16px 10px 0;{divider}font-size:14px;line-height:20px;" valign="top">'
                f'<a href="{merger_url(m)}" style="color:{INK};text-decoration:none;">{merger_name(m)}</a>{waiver}</td>'
                f'<td width="110" align="right" style="padding:10px 0;{divider}" valign="top">{due_html}</td></tr>'
            )
    return section_table(rows)


def build_ongoing_appeals(mergers: list) -> str:
    """Deals with a current appeal on foot at the Australian Competition
    Tribunal — a live snapshot, not just this week's new filings."""
    c = COLORS["tribunal_appeal"]
    rows = section_head("Ongoing ACT appeals", c["border"],
                        f"{len(mergers)} on foot" if mergers else "")
    if not mergers:
        rows += empty_section_row("No matters are currently under appeal.")
    else:
        rows += _appeal_rows(mergers, "ON APPEAL", show_hearing=True)
    return section_table(rows)

# ---------------------------------------------------------------------------
# Full email builder
# ---------------------------------------------------------------------------

def _wordmark(dot: str, size: int, color: str) -> str:
    return (
        f'<span style="font-size:{size}px;font-weight:800;color:{color};">'
        f'mergers<span style="color:{dot};">.</span>fyi</span>'
    )


def build_html_email(digest: dict, banner: str | None = None) -> str:
    banner = banner or banner_choice()
    date_range = format_date_range(digest["period_start"], digest["period_end"])
    show_feedback = _is_feedback_week(digest.get("period_start", ""))
    c = _counts(digest)

    appealed = digest.get("deals_appealed_to_tribunal") or []
    ongoing_appeals = digest.get("ongoing_tribunal_appeals") or []
    sections = (
        build_new_deals(digest["new_deals_notified"])
        + build_decisions(digest)
        + (build_tribunal_appeals(appealed) if appealed else "")
        + build_pipeline(digest)
        + (build_ongoing_appeals(ongoing_appeals) if ongoing_appeals else "")
    )

    link_style = f"color:{GREEN};text-decoration:underline;font-weight:700;"
    if show_feedback:
        header_cta = (
            "Got thoughts, feedback or any market gossip? Just reply to this email – "
            "we&rsquo;d love to hear from you."
        )
    elif banner == "social":
        header_cta = (
            "mergers.fyi is now on social media &ndash; follow us on "
            f'<a href="{LINKEDIN_URL}" style="{link_style}">LinkedIn</a> and '
            f'<a href="{BLUESKY_URL}" style="{link_style}">Bluesky</a> '
            "for new deals and decisions as they happen."
        )
    else:
        header_cta = (
            "Were you forwarded this email? Sign up "
            f'<a href="{SITE_BASE}/digest" style="{link_style}">here</a>.'
        )

    preheader_bits = [f"{c['new']} new deals notified", f"{c['cleared']} cleared"]
    if c["ceased"]:
        preheader_bits.append(f"{c['ceased']} ceased")
    if c["referred"]:
        preheader_bits.append(f"{c['referred']} referred to phase 2")
    if c["declined"]:
        preheader_bits.append(f"{c['declined']} declined")
    if c["appealed"]:
        preheader_bits.append(f"{c['appealed']} appealed to tribunal")
    preheader_bits.append(f"{c['p1'] + c['p2'] + c['pb']} ongoing")
    if c["on_appeal"]:
        preheader_bits.append(f"{c['on_appeal']} under appeal")
    preheader = ", ".join(preheader_bits) + "."

    # Resend replaces {{{RESEND_UNSUBSCRIBE_URL}}} with the real link
    unsub_var = "{{{RESEND_UNSUBSCRIBE_URL}}}"

    white = 'bgcolor="#ffffff" style="background-color:#ffffff;'
    gutter = "padding-left:40px;padding-right:40px;"

    return f"""<!DOCTYPE html>
<html lang="en" xmlns="http://www.w3.org/1999/xhtml" xmlns:o="urn:schemas-microsoft-com:office:office">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta http-equiv="X-UA-Compatible" content="IE=edge">
  <meta name="x-apple-disable-message-reformatting">
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
    @media only screen and (max-width:620px) {{
      .gutter {{padding-left:20px !important;padding-right:20px !important;}}
      .headline {{font-size:28px !important;line-height:34px !important;}}
      .tile {{padding:10px 8px !important;}}
      .tile-n {{font-size:22px !important;line-height:26px !important;}}
    }}
  </style>
  <title>Weekly merger digest, {esc(date_range)} | Australian Merger Tracker</title>
</head>
<body style="margin:0;padding:0;background-color:{PAGE_BG};font-family:{FONT};">

<div style="display:none;font-size:1px;line-height:1px;max-height:0;max-width:0;opacity:0;overflow:hidden;mso-hide:all;">
  {esc(preheader)}
</div>

<table {FULL_TABLE} bgcolor="{PAGE_BG}" style="background-color:{PAGE_BG};">
  <tr>
    <td align="center" style="padding:28px 12px 48px;">

      <!-- ===== OUTER WRAPPER =====
           Fluid up to 640px. Chrome-based clients won't shrink a table below a
           fixed width, so the cap is max-width; Outlook ignores max-width, so
           the ghost table pins it to 640px there. -->
      <!--[if mso]><table width="640" align="center" {TABLE}><tr><td><![endif]-->
      <table {FULL_TABLE} style="width:100%;max-width:640px;">

        <!-- TOP RULE -->
        <tr>
          <td bgcolor="{GREEN}" height="6" style="background-color:{GREEN};font-size:1px;line-height:6px;">&nbsp;</td>
        </tr>

        <!-- MASTHEAD -->
        <tr>
          <td class="gutter" {white}{gutter}padding-top:28px;font-family:{FONT};">
            <table {FULL_TABLE}>
              <tr>
                <td valign="middle">{_wordmark(WORDMARK_DOT, 17, GREEN)}</td>
                <td align="right" valign="middle" style="font-size:13px;color:{MUTED};">
                  {esc(date_range)}&nbsp;&nbsp;&middot;&nbsp;&nbsp;<a href="{SITE_BASE}/digest" style="color:{GREEN};font-weight:600;text-decoration:none;">View online</a>
                </td>
              </tr>
            </table>
          </td>
        </tr>

        <!-- HEADLINE + LEDE -->
        <tr>
          <td class="gutter" {white}{gutter}padding-top:36px;font-family:{FONT};">
            <div class="headline" style="font-size:34px;line-height:40px;font-weight:700;color:{INK};letter-spacing:-0.5px;">Your week in<br>Australian mergers</div>
            <div style="font-size:16px;line-height:26px;color:{BODY_TEXT};padding-top:16px;">{build_lede(c)}</div>
          </td>
        </tr>

        <!-- SCOREBOARD -->
        <tr>
          <td class="gutter" {white}{gutter}padding-top:28px;">
            {build_scoreboard(c)}
          </td>
        </tr>

        <!-- BANNER -->
        <tr>
          <td class="gutter" {white}{gutter}padding-top:28px;">
            <table {FULL_TABLE}>
              <tr>
                <td bgcolor="{GREEN_PALE}" style="background-color:{GREEN_PALE};border-left:3px solid {GREEN};
                           padding:14px 18px;font-family:{FONT};font-size:13px;line-height:20px;color:{GREEN_ON_PALE};">
                  {header_cta}
                </td>
              </tr>
            </table>
          </td>
        </tr>

        <!-- SECTIONS -->
        <tr>
          <td class="gutter" {white}{gutter}padding-bottom:44px;">
            {sections}
          </td>
        </tr>

        <!-- FOOTER -->
        <tr>
          <td class="gutter" bgcolor="{GREEN}" style="background-color:{GREEN};{gutter}padding-top:28px;padding-bottom:28px;font-family:{FONT};">
            <table {FULL_TABLE}>
              <tr>
                <td valign="middle"><a href="{SITE_BASE}" style="text-decoration:none;">{_wordmark("#6EE7B7", 15, "#ffffff")}</a></td>
                <td align="right" valign="middle" style="font-size:12px;">
                  <a href="{SITE_BASE}/digest" style="color:{FOOTER_TEXT};text-decoration:underline;">View in browser</a>
                  &nbsp;&nbsp;
                  <a href="{unsub_var}" style="color:{FOOTER_TEXT};text-decoration:underline;">Unsubscribe</a>
                </td>
              </tr>
              <tr>
                <td colspan="2" style="padding-top:10px;font-size:12px;line-height:18px;color:{FOOTER_MUTED};">
                  You&rsquo;re receiving this because you subscribed to the mergers.fyi weekly digest
                  at <a href="{SITE_BASE}" style="color:#ffffff;text-decoration:none;font-weight:600;">mergers.fyi</a>.
                </td>
              </tr>
            </table>
          </td>
        </tr>

      </table>
      <!--[if mso]></td></tr></table><![endif]-->
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

    banner = banner_choice()
    if banner not in BANNERS:
        print(f"ERROR: BANNER must be one of {', '.join(BANNERS)}, got '{banner}'.", file=sys.stderr)
        sys.exit(1)

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
    print(f"Banner: {banner}")
    print(f"Period: {date_range}")
    print(f"  New deals notified    : {len(digest['new_deals_notified'])}")
    print(f"  Deals cleared         : {len(digest['deals_cleared'])}")
    print(f"  Referred to phase 2   : {len(digest.get('deals_referred_to_phase_2') or [])}")
    print(f"  Deals declined        : {len(digest['deals_declined'])}")
    print(f"  Assessment ceased     : {len(digest.get('deals_assessment_ceased') or [])}")
    print(f"  Appealed to tribunal  : {len(digest.get('deals_appealed_to_tribunal') or [])}")
    print(f"  Ongoing phase 1       : {len(digest['ongoing_phase_1'])}")
    print(f"  Ongoing phase 2       : {len(digest['ongoing_phase_2'])}")

    print("\nBuilding HTML email…")
    html = build_html_email(digest, banner)
    print("Building text email…")
    text = build_text_email(digest, banner)

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
