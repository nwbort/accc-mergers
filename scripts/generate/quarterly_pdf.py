"""The quarterly report as a PDF — ``reports/mergers-fyi-quarterly-merger-report-{YYYY}Q{n}.pdf``.

A printable, attachable twin of the /quarterly page, drawn from the same
``quarterly.json`` block so the two can't disagree: the same headline figures,
the same "in brief" sentences (written by the generator, not here), the same
charts, pre-notification estimates and list of post-phase-1 milestones.

One file per quarter in quarterly.json, which publishes complete quarters
only. Every quarter is redrawn on
every run rather than frozen, because late register changes (a refused waiver
re-filed weeks later, a re-dated determination) still move its figures — and
the output is byte-for-byte deterministic (reportlab's ``invariant`` mode, no
timestamps in the content), so a redraw with nothing new is not a diff and
the pipeline commits a PDF only when its contents moved.

Called by ``generate_static_data`` straight after it writes quarterly.json;
``python -m scripts.generate.quarterly_pdf`` redraws from the committed JSON.
"""

import json
import re
from datetime import date
from pathlib import Path

from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.legends import Legend
from reportlab.graphics.shapes import Drawing, Rect, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    KeepTogether,
    ListFlowable,
    ListItem,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from xml.sax.saxutils import escape

from scripts.generate.static_data.outputs.quarterly import format_rate, percent_change
from scripts.generate.static_data.prune import prune_stale_files
from scripts.paths import REPO_ROOT
from scripts.slug import industry_path, merger_path

SITE = "https://mergers.fyi"
DATA_DIR = REPO_ROOT / "frontend" / "public" / "data"
REPORTS_DIRNAME = "reports"

# The site's palette (frontend/src/constants/chartColors.js, tailwind.config.js).
PRIMARY = colors.HexColor("#335145")
TEAL = colors.HexColor("#6b8f7f")
CORAL = colors.HexColor("#e07a5f")    # chartColors accent: pre-notification
SAGE = colors.HexColor("#8cafa0")
INK = colors.HexColor("#111827")
MUTED = colors.HexColor("#6b7280")
RULE = colors.HexColor("#e5e7eb")
PANEL = colors.HexColor("#f8fafc")
# Text colours for a median's move (tailwind's declined-dark / cleared-dark):
# slower is adverse for a deal, faster favourable.
SLOWER = "#C42A38"
FASTER = "#047857"

PAGE_W, PAGE_H = A4
MARGIN = 16 * mm
# SimpleDocTemplate's frame pads its text area by 6pt a side; a table sized to
# the full margin-to-margin width overhangs that and is re-centred, sitting
# 6pt left of the paragraphs around it.
FRAME_PADDING = 6
CONTENT_W = PAGE_W - 2 * MARGIN - 2 * FRAME_PADDING
BAND_H = 14 * mm

_STYLE = {
    "title": ParagraphStyle("title", fontName="Helvetica-Bold", fontSize=26, leading=30, textColor=INK),
    "subtitle": ParagraphStyle("subtitle", fontName="Helvetica", fontSize=10.5, leading=14, textColor=MUTED),
    "h2": ParagraphStyle("h2", fontName="Helvetica-Bold", fontSize=12, leading=15, textColor=INK, spaceAfter=1),
    "caption": ParagraphStyle("caption", fontName="Helvetica", fontSize=8.5, leading=11, textColor=MUTED),
    "label": ParagraphStyle("label", fontName="Helvetica", fontSize=7, leading=9, textColor=MUTED),
    "value": ParagraphStyle("value", fontName="Helvetica-Bold", fontSize=20, leading=23, textColor=INK),
    "body": ParagraphStyle("body", fontName="Helvetica", fontSize=9.5, leading=13, textColor=INK),
    "small": ParagraphStyle("small", fontName="Helvetica", fontSize=8.5, leading=11, textColor=INK),
    "small_right": ParagraphStyle(
        "small_right", fontName="Helvetica-Bold", fontSize=8.5, leading=11, textColor=INK, alignment=TA_RIGHT,
    ),
    "band": ParagraphStyle("band", fontName="Helvetica-Bold", fontSize=9.5, leading=12, textColor=colors.white),
}


def _page_path(q: dict) -> str:
    """The quarter's own page, ``/quarterly/26Q3``."""
    return f"/quarterly/{q['url_key']}"


def _number(value) -> str:
    if value is None:
        return "–"
    return str(int(value)) if float(value).is_integer() else f"{value:.1f}"


def _days(value) -> str:
    return "–" if value is None else f"{_number(value)} business days"


def _long_date(iso: str) -> str:
    d = date.fromisoformat(iso[:10])
    return f"{d.day} {d.strftime('%B %Y')}"


def _short_date(iso: str) -> str:
    d = date.fromisoformat(iso[:10])
    return f"{d.day:02d} {d.strftime('%b %Y')}"


def _p(text: str, style: str) -> Paragraph:
    return Paragraph(text, _STYLE[style])


def _url(path: str) -> str:
    return SITE + path


def _a(text: str, url: str, colour: str | None = None) -> str:
    """Inline link markup. Links into the site are set in the surrounding
    text's own colour unless ``colour`` says otherwise, so a page reads as
    text rather than a wall of blue, while every heading, figure label and
    name still goes somewhere."""
    attr = f' color="{colour}"' if colour else ""
    return f'<link href="{escape(url)}"{attr}>{text}</link>'


def _h2(text: str, path: str | None = None) -> Paragraph:
    return _p(_a(text, _url(path)) if path else text, "h2")


def _section(*flowables) -> KeepTogether:
    """A section that moves to the next page whole rather than splitting.

    Every section is wrapped in one, so a heading never strands at the foot of
    a page and no table or paragraph breaks across pages. One taller than a
    whole page (a very long milestones list) still has to split; KeepTogether
    then falls back to splitting it between rows.
    """
    return KeepTogether(list(flowables))


# --- Headline tiles ----------------------------------------------------------

def _volume_delta(value, before, previous_label, compare) -> str:
    change = percent_change(value, before) if compare else None
    if change is None:
        return ""
    sign = "+" if change > 0 else "−" if change < 0 else ""
    text = "Level" if change == 0 else f"{sign}{abs(change)}%"
    return f'<font color="#4b5563">{text} on {previous_label}</font>'


def _timing_delta(value, before, previous_label) -> str:
    if value is None or before is None:
        return ""
    delta = round(value - before, 1)
    if delta == 0:
        return f'<font color="#4b5563">Same as {previous_label}</font>'
    unit = "day" if abs(delta) == 1 else "days"
    colour = SLOWER if delta > 0 else FASTER
    word = "slower" if delta > 0 else "faster"
    return f'<font color="{colour}">{_number(abs(delta))} {unit} {word} than {previous_label}</font>'


def _tiles(q: dict, prev: dict | None) -> Table:
    n, w = q["notifications"], q["waivers"]
    label = prev["label"] if prev else ""
    compare = prev is not None
    tiles = [
        (_a("NOTIFICATIONS FILED", _url("/mergers")), _number(n["filed"]),
         _volume_delta(n["filed"], prev and prev["notifications"]["filed"], label, compare)),
        (_a("WAIVERS DECIDED", _url("/mergers")), _number(w["decided"]),
         _volume_delta(w["decided"], prev and prev["waivers"]["decided"], label, compare)),
        (_a("PHASE 1 MEDIAN", _url("/current-status")), f'{_number(n["timing"]["median"])}<font size="9" color="#6b7280"> business days</font>',
         _timing_delta(n["timing"]["median"], prev and prev["notifications"]["timing"]["median"], label)),
        (_a("WAIVER MEDIAN", _url("/current-status")), f'{_number(w["timing"]["median"])}<font size="9" color="#6b7280"> business days</font>',
         _timing_delta(w["timing"]["median"], prev and prev["waivers"]["timing"]["median"], label)),
    ]
    cells = [[[_p(t, "label"), Spacer(1, 3), _p(v, "value"), Spacer(1, 2), _p(d, "caption")] for t, v, d in tiles]]
    table = Table(cells, colWidths=[CONTENT_W / 4] * 4)
    table.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.6, RULE),
        ("LINEBEFORE", (1, 0), (-1, 0), 0.6, RULE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
    ]))
    return table


_MD_LINK = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")
_MD_BOLD = re.compile(r"\*\*(.+?)\*\*|__(.+?)__")
_MD_ITALIC = re.compile(r"(?<![*\w])\*(?!\s)(.+?)(?<!\s)\*(?!\*)|(?<![_\w])_(?!\s)(.+?)(?<!\s)_(?![_\w])")


def inline_markdown(text: str) -> str:
    """The markdown commentary is written in, as reportlab paragraph markup.

    Only the inline subset a point in a bulleted brief can use: links, bold,
    italics and line breaks. Everything else passes through as text, escaped,
    so a stray ``<`` can't break the paragraph parser.
    """
    links = []

    def stash(match):
        links.append((match.group(1), match.group(2)))
        return f"\x00{len(links) - 1}\x00"

    out = escape(_MD_LINK.sub(stash, text))
    out = _MD_BOLD.sub(lambda m: f"<b>{m.group(1) or m.group(2)}</b>", out)
    out = _MD_ITALIC.sub(lambda m: f"<i>{m.group(1) or m.group(2)}</i>", out)
    for index, (label, url) in enumerate(links):
        out = out.replace(f"\x00{index}\x00", _a(escape(label), url, "#335145"))
    return out.replace("\n\n", "<br/><br/>").replace("\n", " ")


def _commentary_point(entry: dict) -> str:
    text = inline_markdown(entry["commentary"])
    if entry.get("author"):
        text += f' <font color="#6b7280">\u2014 {escape(entry["author"])}</font>'
    return text


def _brief(q: dict) -> Table:
    points = [escape(f) for f in q.get("findings", [])]
    # Hand-written commentary, after the generated points: each its own point.
    points += [_commentary_point(entry) for entry in q.get("commentary", [])]
    items = ListFlowable(
        [ListItem(_p(point, "body"), leftIndent=10, value="\u2022") for point in points],
        bulletType="bullet", bulletColor=PRIMARY, leftIndent=10, bulletFontSize=9,
    )
    table = Table([[[_p("THE QUARTER IN BRIEF", "label"), Spacer(1, 4), items]]], colWidths=[CONTENT_W])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), PANEL),
        ("BOX", (0, 0), (-1, -1), 0.6, RULE),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
    ]))
    return table


# --- Charts ------------------------------------------------------------------

def _legend(x: float, y: float, pairs: list[tuple[colors.Color, str]]) -> Legend:
    legend = Legend()
    legend.x, legend.y = x, y
    legend.alignment = "right"
    legend.columnMaximum = 1
    legend.fontName, legend.fontSize = "Helvetica", 7.5
    legend.fillColor = MUTED
    legend.dx = legend.dy = 7
    legend.deltax = 0
    legend.dxTextSpace = 4
    legend.colorNamePairs = pairs
    legend.strokeWidth = 0
    legend.boxAnchor = "sw"
    legend.autoXPadding = 14
    return legend


def _style_axes(chart: VerticalBarChart) -> None:
    chart.valueAxis.valueMin = 0
    chart.valueAxis.labels.fontName = "Helvetica"
    chart.valueAxis.labels.fontSize = 7
    chart.valueAxis.labels.fillColor = MUTED
    chart.valueAxis.strokeColor = colors.white
    chart.valueAxis.visibleGrid = True
    chart.valueAxis.gridStrokeColor = RULE
    chart.valueAxis.gridStrokeWidth = 0.4
    chart.categoryAxis.labels.fontName = "Helvetica"
    chart.categoryAxis.labels.fontSize = 7
    chart.categoryAxis.labels.fillColor = MUTED
    chart.categoryAxis.strokeColor = RULE
    chart.categoryAxis.visibleTicks = False
    chart.bars.strokeColor = None


_AXIS_STEPS = (1, 2, 5, 10, 15, 20, 25, 50, 100, 200, 250, 500, 1000)


def _axis(chart: VerticalBarChart, value: float) -> None:
    """Four round gridline steps covering ``value``, so every tick is a whole number."""
    step = next((s for s in _AXIS_STEPS if s * 4 >= value), _AXIS_STEPS[-1])
    chart.valueAxis.valueMax = step * 4
    chart.valueAxis.valueStep = step


def _volume_chart(quarters: list[dict], selected: dict) -> Drawing:
    width, height = CONTENT_W, 62 * mm
    drawing = Drawing(width, height)
    series = [
        ("Notifications filed", lambda q: q["notifications"]["filed"], PRIMARY),
        ("Phase 1 reviews concluded", lambda q: q["notifications"]["phase_1_decided"], SAGE),
        ("Waivers decided", lambda q: q["waivers"]["decided"], TEAL),
    ]
    chart = VerticalBarChart()
    chart.x, chart.y = 26, 40
    chart.width, chart.height = width - 34, height - 50
    chart.data = [[get(q) for q in quarters] for _, get, _ in series]
    chart.categoryAxis.categoryNames = [q["label"] for q in quarters]
    _style_axes(chart)
    _axis(chart, max(max(row) for row in chart.data) or 1)
    chart.barSpacing = 1.5
    chart.groupSpacing = 14
    for i, (_, _, colour) in enumerate(series):
        chart.bars[i].fillColor = colour
        # The selected quarter in full colour, the others faded behind it.
        for j, q in enumerate(quarters):
            if q["quarter"] != selected["quarter"]:
                chart.bars[(i, j)].fillColor = colors.Color(colour.red, colour.green, colour.blue, alpha=0.4)
    drawing.add(chart)
    drawing.add(_legend(26, 0, [(c, name) for name, _, c in series]))
    return drawing


def _shares(buckets: list[int]) -> list[float]:
    total = sum(buckets)
    return [round(n / total * 100, 1) if total else 0 for n in buckets]


def _timing_chart(buckets: list[str], current: dict, previous: dict | None, colour,
                  width: float = CONTENT_W / 2 - 6) -> Drawing:
    height = 52 * mm
    drawing = Drawing(width, height)
    chart = VerticalBarChart()
    chart.x, chart.y = 24, 48
    chart.width, chart.height = width - 30, height - 54
    data, pairs = [], []
    faded = colors.Color(colour.red, colour.green, colour.blue, alpha=0.35)
    if previous:
        data.append(_shares(previous["timing"]["buckets"]))
        pairs.append((faded, previous["label"]))
    data.append(_shares(current["timing"]["buckets"]))
    pairs.append((colour, current["label"]))
    chart.data = data
    chart.categoryAxis.categoryNames = buckets
    _style_axes(chart)
    _axis(chart, max(max(row) for row in data) or 1)
    chart.valueAxis.labelTextFormat = "%d%%"
    chart.barSpacing = 1
    chart.groupSpacing = 5
    for i, (fill, _) in enumerate(pairs):
        chart.bars[i].fillColor = fill
    drawing.add(chart)
    drawing.add(String(chart.x + chart.width / 2, 26, "Business days", fontName="Helvetica",
                       fontSize=7, fillColor=MUTED, textAnchor="middle"))
    drawing.add(_legend(24, 0, pairs))
    return drawing


# --- Sections ----------------------------------------------------------------

def _card(title: str, rows: list, *, width: float) -> Table:
    """A titled card: a primary-green band over its contents, as on the page."""
    table = Table([[_p(title, "band")]] + [[r] for r in rows], colWidths=[width])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), PRIMARY),
        ("BOX", (0, 0), (-1, -1), 0.6, RULE),
        ("LEFTPADDING", (0, 0), (-1, -1), 9),
        ("RIGHTPADDING", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, 0), 5),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 5),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    return table


def _outcome_card(title, rate, granted, decided, rows, footnote, width) -> Table:
    stats = Table(
        [[_p(label, "small"), _p(str(value), "small_right")] for label, value in rows],
        colWidths=[width * 0.55 - 9, width * 0.45 - 9],
    )
    stats.setStyle(TableStyle([
        ("LINEABOVE", (0, 0), (-1, -1), 0.4, RULE),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    body = [
        _p("CLEARANCE RATE", "label"),
        _p(f'<font size="28">{format_rate(rate)}</font>', "value"),
        Spacer(1, 9),
        _p(f"{granted} of {decided} approved", "caption"),
        Spacer(1, 6),
        stats,
    ]
    if footnote:
        body += [Spacer(1, 5), _p(footnote, "caption")]
    return _card(title, [body], width=width)


def _outcomes(q: dict) -> Table:
    n, w = q["notifications"], q["waivers"]
    half = CONTENT_W / 2 - 5
    waiver_card = _outcome_card(
        "Waivers", w["clearance_rate"], w["granted"], w["decided"],
        [("Average when granted", _days(w["average_granted"])),
         ("Average when refused", _days(w["average_refused"])),
         ("Refused", w["refused"])],
        f'{w["refused_refiled"]} of {w["refused"]} refused waivers have since been '
        + _a("re-filed as a notification", _url("/refiled-notifications"), "#335145") + "."
        if w["refused"] else None,
        half,
    )
    p1_rows = [
        ("Average when approved", _days(n["average_cleared"])),
        ("Average when referred", _days(n["average_referred"])),
        (_a("Referred to phase 2", _url("/phase-2")), n["referred_to_phase_2"]),
    ]
    if n["refused"]:
        p1_rows.append(("Not approved", n["refused"]))
    if n["ceased"]:
        p1_rows.append(("Ceased in phase 1", n["ceased"]))
    p1_card = _outcome_card(
        "Notifications – phase 1", n["clearance_rate"], n["cleared"], n["phase_1_decided"],
        p1_rows, None, half,
    )
    row = Table([[waiver_card, p1_card]], colWidths=[CONTENT_W / 2] * 2)
    row.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (0, 0), 5),
        ("LEFTPADDING", (1, 0), (1, 0), 5),
        ("RIGHTPADDING", (1, 0), (1, 0), 0),
    ]))
    return row


def _timing(payload: dict, q: dict, prev: dict | None) -> list:
    buckets = payload["duration_buckets"]
    cells = []
    for title, key, colour in (("Waiver timing", "waivers", TEAL), ("Phase 1 timing", "notifications", PRIMARY)):
        current = {"label": q["label"], "timing": q[key]["timing"]}
        before = {"label": prev["label"], "timing": prev[key]["timing"]} if prev else None
        t = q[key]["timing"]
        cells.append([
            _h2(title, "/analysis"),
            _p(f"Share of decisions by business days taken – median {_days(t['median'])}, "
               f"90% within {_days(t['p90'])}", "caption"),
            Spacer(1, 4),
            _timing_chart(buckets, current, before, colour),
        ])
    row = Table([cells], colWidths=[CONTENT_W / 2] * 2)
    row.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))
    return [row]


def _pre_notification(payload: dict, q: dict, prev: dict | None) -> list:
    pre = q.get("pre_notification") or {}
    if not pre.get("count"):
        return []
    before = (prev or {}).get("pre_notification") or {}
    change = ""
    if before.get("median") is not None:
        delta = round(pre["median"] - before["median"], 1)
        if delta == 0:
            change = f'<font color="#4b5563">Same as {prev["label"]}</font>'
        else:
            colour = SLOWER if delta > 0 else FASTER
            word = "longer" if delta > 0 else "shorter"
            change = f'<font color="{colour}">{_number(abs(delta))} {word} than {prev["label"]}</font>'

    def stat(label, value, extra=""):
        cell = [_p(label.upper(), "label"), Spacer(1, 2),
                _p(f'{_number(value)}<font size="9" color="#6b7280"> business days</font>', "value")]
        if extra:
            cell += [Spacer(1, 1), _p(extra, "caption")]
        return cell + [Spacer(1, 8)]

    stats = stat("Median", pre["median"], change) + stat("Average", pre["average"]) + stat("90% within", pre["p90"])
    current = {"label": q["label"], "timing": pre}
    previous = {"label": prev["label"], "timing": before} if before.get("count") else None
    chart = _timing_chart(payload["pre_notification_buckets"], current, previous, CORAL,
                          width=CONTENT_W / 2 + 20 * mm)
    row = Table([[stats, chart]], colWidths=[CONTENT_W / 2 - 20 * mm, CONTENT_W / 2 + 20 * mm])
    row.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    return [
        _h2("Pre-notification", "/current-status"),
        _p(f"Estimated time the {pre['count']} notifications filed this quarter spent with the ACCC before "
           "filing, as a share of those notifications", "caption"),
        Spacer(1, 6),
        row,
    ]


def _industries(q: dict) -> list:
    flow = [_h2("Where the deals were", "/industries"),
            _p("Notifications filed and waivers decided, by ANZSIC division", "caption"),
            Spacer(1, 6)]
    top = q["industries"]
    if not top:
        return flow + [_p("No matters this quarter.", "caption")]
    biggest = top[0]["count"]
    bar_w = CONTENT_W * 0.42
    rows = []
    for industry in top:
        bar = Drawing(bar_w, 7)
        bar.add(Rect(0, 0, bar_w, 6, rx=3, ry=3, fillColor=colors.HexColor("#f3f4f6"), strokeColor=None))
        bar.add(Rect(0, 0, bar_w * industry["count"] / biggest, 6, rx=3, ry=3, fillColor=PRIMARY, strokeColor=None))
        name = _a(escape(industry["name"]), _url(industry_path(industry["code"], industry["name"])))
        rows.append([_p(name, "small"), bar, _p(str(industry["count"]), "small_right")])
    table = Table(rows, colWidths=[CONTENT_W * 0.48, bar_w + 6, CONTENT_W * 0.10 - 6])
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    flow.append(table)
    return flow


def _milestones(q: dict) -> list:
    flow = [_h2("Beyond phase 1", "/phase-2"),
            _p("Phase 2 referrals and outcomes, public benefit applications, and Tribunal and court reviews",
               "caption"),
            Spacer(1, 6)]
    if not q["milestones"]:
        return flow + [_p("Nothing went beyond phase 1 this quarter.", "caption")]
    rows = []
    for m in q["milestones"]:
        url = SITE + merger_path(m["merger_id"], m["merger_name"])
        matter = f'<link href="{escape(url)}" color="#335145">{escape(m["merger_name"])}</link>'
        if m.get("detail"):
            matter += f' <font color="#6b7280">· {escape(m["detail"])}</font>'
        rows.append([
            _p(f'<font color="#6b7280">{_short_date(m["date"])}</font>', "small"),
            _p(f'<b>{escape(m["label"])}</b>', "small"),
            _p(matter, "small"),
        ])
    table = Table(rows, colWidths=[24 * mm, 48 * mm, CONTENT_W - 72 * mm], repeatRows=0)
    table.setStyle(TableStyle([
        ("LINEABOVE", (0, 0), (-1, -1), 0.4, RULE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return flow + [table]


def _appeals(q: dict) -> list:
    appeals = q.get("appeals") or {}
    matters = appeals.get("matters") or []
    flow = [
        _h2("Tribunal reviews"),
        _p("Applications to the Australian Competition Tribunal for review of an ACCC determination, "
           "live at some point in the quarter", "caption"),
        Spacer(1, 6),
    ]
    if not matters:
        return flow + [_p("No Tribunal reviews were live this quarter.", "caption")]
    flow += [
        _p(f'<b>{appeals["lodged"]}</b> lodged \u00b7 <b>{appeals["concluded"]}</b> concluded \u00b7 '
           f'<b>{appeals["open_at_end"]}</b> open at quarter end', "small"),
        Spacer(1, 5),
    ]
    rows = [[_p(f'<font color="#6b7280">{h}</font>', "label") for h in ("MATTER", "MERGER", "APPLICANT", "STATUS")]]
    for m in matters:
        number = _a(escape(m["tribunal_number"] or ""), m["tribunal_url"], "#335145") if m.get("tribunal_url") \
            else escape(m["tribunal_number"] or "")
        merger = _a(escape(m["merger_name"]), _url(merger_path(m["merger_id"], m["merger_name"])), "#335145")
        rows.append([
            _p(f"<b>{number}</b><br/><font color=\"#6b7280\">lodged {_short_date(m['filed_date'])}</font>", "small"),
            _p(merger, "small"),
            _p(escape(m.get("appellant") or "\u2013"), "small"),
            _p(escape(m["note"]), "small"),
        ])
    table = Table(rows, colWidths=[32 * mm, CONTENT_W - 32 * mm - 24 * mm - 62 * mm, 24 * mm, 62 * mm], repeatRows=1)
    table.setStyle(TableStyle([
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, RULE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return flow + [table]


def _page_decorations(quarter: dict):
    page_url = SITE + _page_path(quarter)
    # The band and footer line up with the text, not the bare page margin.
    EDGE = MARGIN + FRAME_PADDING

    def draw(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(PRIMARY)
        canvas.rect(0, PAGE_H - BAND_H, PAGE_W, BAND_H, stroke=0, fill=1)
        canvas.setFillColor(colors.white)
        canvas.setFont("Helvetica-Bold", 11)
        canvas.drawString(EDGE, PAGE_H - BAND_H + 5 * mm, "australian merger tracker")
        canvas.linkURL(SITE, (EDGE, PAGE_H - BAND_H, EDGE + 60 * mm, PAGE_H), relative=0)
        canvas.setFont("Helvetica", 9)
        canvas.drawRightString(PAGE_W - EDGE, PAGE_H - BAND_H + 5 * mm, f"Quarterly report · {quarter['label']}")
        canvas.setStrokeColor(RULE)
        canvas.setLineWidth(0.5)
        canvas.line(EDGE, 13 * mm, PAGE_W - EDGE, 13 * mm)
        canvas.setFillColor(MUTED)
        canvas.setFont("Helvetica", 7)
        source, site, rest = "Source: ACCC acquisitions register, via ", "mergers.fyi", ". Data CC BY 4.0. Not legal advice."
        canvas.drawString(EDGE, 9 * mm, source)
        x = EDGE + canvas.stringWidth(source, "Helvetica", 7)
        site_w = canvas.stringWidth(site, "Helvetica", 7)
        canvas.setFillColor(PRIMARY)
        canvas.drawString(x, 9 * mm, site)
        canvas.linkURL(SITE, (x, 8 * mm, x + site_w, 11.5 * mm), relative=0)
        canvas.setFillColor(MUTED)
        canvas.drawString(x + site_w, 9 * mm, rest)
        canvas.drawRightString(PAGE_W - EDGE, 9 * mm, f"{page_url}  ·  {doc.page}")
        canvas.linkURL(page_url, (PAGE_W - EDGE - 80 * mm, 7 * mm, PAGE_W - EDGE, 12 * mm), relative=0)
        canvas.restoreState()

    return draw


def build_pdf(payload: dict, quarter_key: str, path: Path) -> None:
    """Draw one quarter's report to ``path``."""
    quarters = payload["quarters"]
    index = next(i for i, q in enumerate(quarters) if q["quarter"] == quarter_key)
    q = quarters[index]
    prev = quarters[index - 1] if index > 0 else None

    doc = SimpleDocTemplate(
        str(path), pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN, topMargin=BAND_H + 9 * mm, bottomMargin=18 * mm,
        title=f"Quarterly merger report – {q['label']}",
        author="mergers.fyi", subject="Australian merger regime: quarterly report",
        creator="mergers.fyi", invariant=1,
    )
    page = _url(_page_path(q))
    story = [
        _p(_a(f"Quarterly report: {q['label']}", page), "title"),
        Spacer(1, 3),
        _p(f"Australia's merger regime, {_long_date(q['start'])} \u2013 {_long_date(q['end'])}", "subtitle"),
        Spacer(1, 10),
        _section(_tiles(q, prev), Spacer(1, 8), _brief(q)),
        Spacer(1, 14),
        _section(
            _h2("Volume by quarter", "/analysis"),
            _p("Waivers reach the ACCC's register only once decided, so they are counted when decided", "caption"),
            Spacer(1, 6),
            _volume_chart(quarters, q),
        ),
        Spacer(1, 12),
        _section(_outcomes(q)),
        Spacer(1, 14),
        _section(*_timing(payload, q, prev)),
        Spacer(1, 12),
        _section(*_pre_notification(payload, q, prev)),
        Spacer(1, 12),
        _section(*_industries(q)),
        Spacer(1, 14),
        _section(*_appeals(q)),
        Spacer(1, 14),
        _section(*_milestones(q)),
    ]
    decorate = _page_decorations(q)
    doc.build(story, onFirstPage=decorate, onLaterPages=decorate)


def generate(payload: dict, out_dir: Path) -> list[str]:
    """Draw a PDF for every quarter in ``payload``; prune the rest.

    quarterly.json publishes complete quarters only, so this never draws a
    quarter still in progress.

    Returns the file names written. A quarter's file is only rewritten when its
    bytes change, so an unchanged report keeps its mtime as well as its hash.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for q in payload.get("quarters", []):
        name = q["report_pdf"]
        target = out_dir / name
        scratch = out_dir / f".{name}.tmp"
        build_pdf(payload, q["quarter"], scratch)
        if target.exists() and target.read_bytes() == scratch.read_bytes():
            scratch.unlink()
        else:
            scratch.replace(target)
        written.append(name)
    # Every PDF in reports/ is this generator's, so prune by extension: that
    # also clears files left under an earlier naming scheme.
    prune_stale_files(out_dir, set(written), pattern="*.pdf", label=REPORTS_DIRNAME)
    return written


def main() -> None:
    payload = json.loads((DATA_DIR / "quarterly.json").read_text(encoding="utf-8"))
    names = generate(payload, DATA_DIR / REPORTS_DIRNAME)
    print(f"✓ Drew {len(names)} quarterly report PDF(s): {', '.join(names)}")


if __name__ == "__main__":
    main()
