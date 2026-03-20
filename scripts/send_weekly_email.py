#!/usr/bin/env python3
"""Send the mergers.fyi weekly digest email via Resend.

Reads digest.json, builds an HTML email, creates a Resend broadcast,
and sends it to the configured audience.

Required environment variables:
    RESEND_API_KEY      — Resend API key
    RESEND_AUDIENCE_ID  — Resend audience ID to send to

Optional environment variables:
    DRY_RUN             — If set to 'true', prints the HTML and exits without sending
    SEND_FROM           — Sender address (default: mergers.fyi weekly digest <digest@mergers.fyi>)
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
SEND_FROM = os.environ.get("SEND_FROM", "mergers.fyi weekly digest <digest@mergers.fyi>")

# Colour palette matching tailwind.config.js
COLORS = {
    "new_merger": {"border": "#5B3758", "pale": "#F3EBF2", "dark": "#3D2539"},
    "cleared":    {"border": "#10b981", "pale": "#D1FAE5", "dark": "#059669"},
    "declined":   {"border": "#f49097", "pale": "#FEE7E9", "dark": "#E8636C"},
    "phase_1":    {"border": "#B8935C", "pale": "#FCECC9", "dark": "#8A6B3E"},
    "phase_2":    {"border": "#52489c", "pale": "#E8E5F3", "dark": "#3A3372"},
}

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
            return f"{start_day}\u2013{end_day} {end_month} {year}"
        return f"{start_day} {start_month} \u2013 {end_day} {end_month} {year}"
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
    return cut + "\u2026"


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

    lines = [
        "mergers.fyi weekly digest",
        f"Week of {date_range}",
        f"{SITE_BASE}/digest",
        "",
        "SUMMARY",
        "-------",
        f"New deals notified : {len(digest['new_deals_notified'])}",
        f"Cleared            : {len(digest['deals_cleared'])}",
        f"Declined           : {len(digest['deals_declined'])}",
        f"Ongoing phase 1    : {len(digest['ongoing_phase_1'])}",
        f"Ongoing phase 2    : {len(digest['ongoing_phase_2'])}",
        "",
    ]

    new_rows = [
        [m.get("merger_name", m["merger_id"]), format_date(m.get("effective_notification_datetime"))]
        for m in digest["new_deals_notified"]
    ]
    lines.append(_text_section("NEW MERGERS NOTIFIED", ["Merger", "Notified"], new_rows, "No new mergers notified this week."))
    lines.append("")
    lines.append("")

    cleared_rows = [
        [m.get("merger_name", m["merger_id"]), format_date(m.get("determination_publication_date"))]
        for m in digest["deals_cleared"]
    ]
    lines.append(_text_section("MERGERS APPROVED", ["Merger", "Date"], cleared_rows, "No mergers approved this week."))
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
    lines.append(_text_section("ONGOING \u2013 PHASE 1 \u2013 INITIAL ASSESSMENT", ["Merger", "Notified"], phase1_rows, "No ongoing phase 1 mergers."))
    lines.append("")
    lines.append("")

    phase2_rows = [
        [m.get("merger_name", m["merger_id"]), format_date(m.get("effective_notification_datetime"))]
        for m in digest["ongoing_phase_2"]
    ]
    lines.append(_text_section("ONGOING \u2013 PHASE 2 \u2013 DETAILED ASSESSMENT", ["Merger", "Notified"], phase2_rows, "No ongoing phase 2 mergers."))
    lines.append("")

    unsub_var = "{{{RESEND_UNSUBSCRIBE_URL}}}"
    lines += [
        "--",
        "You're receiving this because you subscribed at mergers.fyi.",
        f"Unsubscribe: {unsub_var}",
    ]

    return "\n".join(lines)


def merger_link(merger: dict, color: dict) -> str:
    url = f"{SITE_BASE}/mergers/{esc(merger['merger_id'])}"
    name = esc(merger.get("merger_name", merger["merger_id"]))
    return (
        f'<a href="{url}" style="color:{color["border"]};font-weight:600;'
        f'font-size:13px;text-decoration:none;line-height:1.4;">{name}</a>'
    )

# ---------------------------------------------------------------------------
# Email HTML building blocks
# ---------------------------------------------------------------------------

def stat_card(count: int, label: str, color: dict, anchor: str) -> str:
    url = f"{SITE_BASE}/digest#{anchor}"
    return (
        f'<td width="20%" style="padding:4px 3px;">'
        f'<a href="{url}" style="text-decoration:none;display:block;">'
        f'<table width="100%" cellpadding="0" cellspacing="0" border="0">'
        f'<tr><td style="background:{color["pale"]};border-radius:8px;'
        f'padding:12px 6px;text-align:center;border:1px solid {color["border"]}33;">'
        f'<div style="color:{color["border"]};font-size:26px;font-weight:700;line-height:1;">'
        f"{count}</div>"
        f'<div style="color:{color["dark"]};font-size:11px;font-weight:500;'
        f'margin-top:4px;line-height:1.3;">{esc(label)}</div>'
        f"</td></tr></table></a></td>"
    )


def section_header_row(title: str, color: dict, num_cols: int) -> str:
    return (
        f'<tr><td colspan="{num_cols}" style="background:{color["pale"]};'
        f'border-left:4px solid {color["border"]};padding:13px 18px 11px;'
        f'border-bottom:1px solid {color["border"]}33;">'
        f'<span style="font-size:14px;font-weight:600;color:#111827;">'
        f"{esc(title)}</span></td></tr>"
    )


def col_header_row(*cols: str) -> str:
    cells = "".join(
        f'<td style="padding:8px 18px;font-size:11px;font-weight:600;'
        f'color:#6b7280;text-transform:uppercase;letter-spacing:0.05em;'
        f'background:#f9fafb;border-bottom:1px solid #efefef;">'
        f"{esc(c)}</td>"
        for c in cols
    )
    return f"<tr>{cells}</tr>"


def empty_row(message: str, color: dict, num_cols: int) -> str:
    return (
        f'<tr><td colspan="{num_cols}" style="padding:16px 18px;'
        f'font-size:13px;color:{color["border"]}aa;">'
        f"{esc(message)}</td></tr>"
    )


def name_cell(merger: dict, color: dict) -> str:
    mid = esc(merger.get("merger_id", ""))
    waiver = (
        ' <span style="font-size:10px;background:#e5e7eb;color:#6b7280;'
        'padding:1px 4px;border-radius:3px;">Waiver</span>'
        if merger.get("is_waiver")
        else ""
    )
    return (
        f'<td style="padding:11px 18px;vertical-align:top;min-width:180px;">'
        f"{merger_link(merger, color)}{waiver}"
        f'<div style="color:#9ca3af;font-size:11px;margin-top:2px;">{mid}</div>'
        f"</td>"
    )


def date_cell(date_str: str) -> str:
    return (
        f'<td style="padding:11px 18px;vertical-align:top;white-space:nowrap;'
        f'font-size:13px;color:#4b5563;">{esc(format_date(date_str))}</td>'
    )


def text_cell(text: str, bold_color: str | None = None) -> str:
    style = (
        f"color:{bold_color};font-weight:600;"
        if bold_color
        else "color:#4b5563;"
    )
    return (
        f'<td style="padding:11px 18px;vertical-align:top;font-size:13px;'
        f'{style}line-height:1.5;">{esc(text)}</td>'
    )


def section_table(header_row: str, col_row: str, data_rows: str) -> str:
    return (
        '<table width="100%" cellpadding="0" cellspacing="0" border="0" '
        'style="border-radius:10px;overflow:hidden;border:1px solid #e5e7eb;'
        'margin-bottom:20px;">'
        f"{header_row}{col_row}{data_rows}"
        "</table>"
    )

# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------

def _row_divider() -> str:
    return ' style="border-bottom:1px solid #f5f5f5;"'


def build_new_mergers(mergers: list) -> str:
    c = COLORS["new_merger"]
    num_cols = 3
    hdr = section_header_row("New mergers notified", c, num_cols)
    cols = col_header_row("Merger", "Notified", "Summary")
    if not mergers:
        rows = empty_row("No new mergers notified this week.", c, num_cols)
    else:
        rows = ""
        for m in mergers:
            desc = truncate(m.get("merger_description", ""))
            rows += (
                f"<tr{_row_divider()}>"
                f"{name_cell(m, c)}"
                f"{date_cell(m.get('effective_notification_datetime'))}"
                f"{text_cell(desc)}"
                f"</tr>"
            )
    return section_table(hdr, cols, rows)


def build_cleared(mergers: list) -> str:
    c = COLORS["cleared"]
    num_cols = 3
    hdr = section_header_row("Mergers approved", c, num_cols)
    cols = col_header_row("Merger", "Date", "Determination")
    if not mergers:
        rows = empty_row("No mergers approved this week.", c, num_cols)
    else:
        rows = ""
        for m in mergers:
            det = (
                m.get("accc_determination")
                or m.get("phase_1_determination")
                or m.get("phase_2_determination")
                or "Approved"
            )
            rows += (
                f"<tr{_row_divider()}>"
                f"{name_cell(m, c)}"
                f"{date_cell(m.get('determination_publication_date'))}"
                f"{text_cell(det, c['dark'])}"
                f"</tr>"
            )
    return section_table(hdr, cols, rows)


def build_declined(mergers: list) -> str:
    c = COLORS["declined"]
    num_cols = 3
    hdr = section_header_row("Mergers declined", c, num_cols)
    cols = col_header_row("Merger", "Date", "Determination")
    if not mergers:
        rows = empty_row("No mergers declined this week.", c, num_cols)
    else:
        rows = ""
        for m in mergers:
            det = (
                m.get("accc_determination")
                or m.get("phase_1_determination")
                or m.get("phase_2_determination")
                or "Not approved"
            )
            rows += (
                f"<tr{_row_divider()}>"
                f"{name_cell(m, c)}"
                f"{date_cell(m.get('determination_publication_date'))}"
                f"{text_cell(det, c['dark'])}"
                f"</tr>"
            )
    return section_table(hdr, cols, rows)


def build_phase_section(mergers: list, phase_key: str, title: str) -> str:
    c = COLORS[phase_key]
    num_cols = 4
    hdr = section_header_row(title, c, num_cols)
    cols = col_header_row("Merger", "Notified", "Due", "Summary")
    if not mergers:
        rows = empty_row(f"No ongoing {title.lower().split('–')[0].strip()} mergers.", c, num_cols)
    else:
        rows = ""
        for m in mergers:
            desc = truncate(m.get("merger_description", ""), 160)
            rows += (
                f"<tr{_row_divider()}>"
                f"{name_cell(m, c)}"
                f"{date_cell(m.get('effective_notification_datetime'))}"
                f"{date_cell(m.get('end_of_determination_period'))}"
                f"{text_cell(desc)}"
                f"</tr>"
            )
    return section_table(hdr, cols, rows)

# ---------------------------------------------------------------------------
# Full email builder
# ---------------------------------------------------------------------------

def build_html_email(digest: dict) -> str:
    date_range = format_date_range(digest["period_start"], digest["period_end"])
    new_count = len(digest["new_deals_notified"])
    cleared_count = len(digest["deals_cleared"])
    declined_count = len(digest["deals_declined"])
    phase1_count = len(digest["ongoing_phase_1"])
    phase2_count = len(digest["ongoing_phase_2"])

    stat_cards = (
        stat_card(new_count, "New deals", COLORS["new_merger"], "new-mergers")
        + stat_card(cleared_count, "Cleared", COLORS["cleared"], "mergers-approved")
        + stat_card(declined_count, "Declined", COLORS["declined"], "mergers-declined")
        + stat_card(phase1_count, "Ongoing phase\u00a01", COLORS["phase_1"], "ongoing-phase-1")
        + stat_card(phase2_count, "Ongoing phase\u00a02", COLORS["phase_2"], "ongoing-phase-2")
    )

    sections = (
        build_new_mergers(digest["new_deals_notified"])
        + build_cleared(digest["deals_cleared"])
        + build_declined(digest["deals_declined"])
        + build_phase_section(
            digest["ongoing_phase_1"], "phase_1",
            "Ongoing \u2013 phase 1 \u2013 initial assessment"
        )
        + build_phase_section(
            digest["ongoing_phase_2"], "phase_2",
            "Ongoing \u2013 phase 2 \u2013 detailed assessment"
        )
    )

    # Resend replaces {{{RESEND_UNSUBSCRIBE_URL}}} with the real link
    unsub_var = "{{{RESEND_UNSUBSCRIBE_URL}}}"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>mergers.fyi weekly digest for {esc(date_range)}</title>
</head>
<body style="margin:0;padding:0;background-color:#f1f5f9;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,Helvetica,sans-serif;">

<table width="100%" cellpadding="0" cellspacing="0" border="0" role="presentation"
       style="background-color:#f1f5f9;">
  <tr>
    <td align="center" style="padding:28px 16px 40px;">

      <!-- ===== OUTER WRAPPER (max 620px) ===== -->
      <table width="620" cellpadding="0" cellspacing="0" border="0" role="presentation"
             style="max-width:620px;width:100%;">

        <!-- HEADER -->
        <tr>
          <td style="background:#335145;border-radius:12px 12px 0 0;padding:26px 28px 22px;">
            <span style="font-size:18px;font-weight:700;color:#ffffff;letter-spacing:-0.3px;">
              mergers.fyi weekly digest
            </span>
            <br>
            <span style="font-size:13px;color:#a3c4b3;margin-top:6px;display:block;">
              Week of {esc(date_range)}
              &nbsp;&middot;&nbsp;
              <a href="{SITE_BASE}/digest" style="color:#a3c4b3;text-decoration:underline;">
                View online
              </a>
            </span>
          </td>
        </tr>

        <!-- STAT CARDS -->
        <tr>
          <td style="background:#ffffff;padding:18px 20px 14px;
                     border-left:1px solid #e5e7eb;border-right:1px solid #e5e7eb;">
            <table width="100%" cellpadding="0" cellspacing="0" border="0" role="presentation">
              <tr>
                {stat_cards}
              </tr>
            </table>
          </td>
        </tr>

        <!-- DIVIDER -->
        <tr>
          <td style="background:#ffffff;padding:0 20px;
                     border-left:1px solid #e5e7eb;border-right:1px solid #e5e7eb;">
            <hr style="border:none;border-top:1px solid #e9ecef;margin:4px 0 18px;">
          </td>
        </tr>

        <!-- SECTIONS -->
        <tr>
          <td style="background:#ffffff;padding:0 20px 24px;
                     border-left:1px solid #e5e7eb;border-right:1px solid #e5e7eb;">
            {sections}
          </td>
        </tr>

        <!-- FOOTER -->
        <tr>
          <td style="background:#f8fafc;border-radius:0 0 12px 12px;
                     padding:18px 28px;border:1px solid #e5e7eb;border-top:none;
                     text-align:center;">
            <p style="margin:0 0 6px;font-size:12px;color:#6b7280;line-height:1.6;">
              You&rsquo;re receiving this because you subscribed to the mergers.fyi weekly digest
              at <a href="{SITE_BASE}" style="color:#335145;text-decoration:none;font-weight:500;">mergers.fyi</a>.
            </p>
            <p style="margin:0;font-size:12px;color:#9ca3af;">
              <a href="{unsub_var}" style="color:#9ca3af;text-decoration:underline;">Unsubscribe</a>
              &nbsp;&middot;&nbsp;
              <a href="{SITE_BASE}/digest" style="color:#9ca3af;text-decoration:underline;">
                View in browser
              </a>
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
        print(f"ERROR creating broadcast: {resp.status_code} {resp.text}", file=sys.stderr)
        sys.exit(1)
    data = resp.json()
    broadcast_id = data.get("id")
    if not broadcast_id:
        print(f"ERROR: no broadcast ID in response: {data}", file=sys.stderr)
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
        print(f"ERROR sending broadcast: {resp.status_code} {resp.text}", file=sys.stderr)
        sys.exit(1)

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    api_key = os.environ.get("RESEND_API_KEY", "").strip()
    audience_id = os.environ.get("RESEND_AUDIENCE_ID", "").strip()
    dry_run = os.environ.get("DRY_RUN", "").lower() == "true"

    if not dry_run:
        if not api_key:
            print("ERROR: RESEND_API_KEY environment variable is not set.", file=sys.stderr)
            sys.exit(1)
        if not audience_id:
            print("ERROR: RESEND_AUDIENCE_ID environment variable is not set.", file=sys.stderr)
            sys.exit(1)

    print("Loading digest.json…")
    digest = load_digest()

    date_range = format_date_range(digest["period_start"], digest["period_end"])
    subject = f"mergers.fyi weekly digest for {date_range}"
    broadcast_name = f"Weekly digest \u2013 {date_range}"

    print(f"Period: {date_range}")
    print(f"  New deals notified : {len(digest['new_deals_notified'])}")
    print(f"  Deals cleared      : {len(digest['deals_cleared'])}")
    print(f"  Deals declined     : {len(digest['deals_declined'])}")
    print(f"  Ongoing phase 1    : {len(digest['ongoing_phase_1'])}")
    print(f"  Ongoing phase 2    : {len(digest['ongoing_phase_2'])}")

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
