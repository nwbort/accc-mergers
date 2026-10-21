"""Render the link card image for one Bluesky post.

A post's card is what people see in a feed, and the site's one shared Open
Graph image says the same thing under every post. This draws a card that says
what the post is about instead: the milestone's headline, the matter's name
and the register's own identifier, on the colour the site gives that outcome
(see ``frontend/src/constants/outcomeHeader.js``), so a clearance reads green
and a refusal red in a feed the same way they do on the matter page.

Nothing here is written to disk. The PNG is built in memory, uploaded as a
blob and referenced from the post record; the PDS keeps it for as long as the
post exists, and the repository and the Pages deployment never see it - which
matters, because Pages counts files, not bytes.

Rendering is best-effort by design. With no usable font (a bare runner) or any
drawing error, ``render_card`` returns ``None`` and the caller falls back to
the shared image: a post is worth more than its picture.
"""

from __future__ import annotations

import io
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

#: Bluesky crops a card thumbnail to roughly 1.91:1; this is the Open Graph
#: size the site's own image uses.
WIDTH, HEIGHT = 1200, 630

#: The site's generic cards are drawn at twice that (2400x1260). LinkedIn
#: re-encodes what it scrapes and a 1x card came back soft; the extra pixels
#: survive that. Same aspect ratio, so every crop is unchanged. The per-post
#: cards stay at 1x: they are uploaded as blobs, and Bluesky caps those at 1 MB.
STATUS_CARD_SCALE = 2

#: Card fills, keyed by tone. The hexes are the Tailwind 700 shades the site
#: uses for the same outcomes; each clears 4.5:1 against white text.
TONES = {
    "cleared": "#047857",  # emerald-700
    "refused": "#b91c1c",  # red-700
    "ceased": "#7e22ce",  # purple-700
    "phase-2": "#b45309",  # amber-700
    "contested": "#4338ca",  # indigo-700
    "live": "#335145",  # the site's primary
}

#: Bold and regular faces, first hit wins. Liberation and DejaVu are on every
#: Ubuntu runner and most dev machines; the last entries cover macOS.
_BOLD_FONTS = (
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
)
_REGULAR_FONTS = (
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
)

_MARGIN = 80
_MAX_TITLE_LINES = 3
_TITLE_SIZES = (76, 68, 60, 52, 46)


def tone_for(key: str, headline: str) -> str:
    """Which fill a milestone gets, from its key's kind and its headline.

    A determination's colour comes from the headline, because that is where
    the outcome lives: the same ``determined`` kind is a clearance or a refusal.
    """
    kind = key.rsplit(":", 2)[-2] if key.count(":") >= 2 else ""
    if kind in ("determined", "public-benefit-determined"):
        return "refused" if headline.startswith(("Not approved", "Notification waiver refused")) else "cleared"
    if kind == "ceased":
        return "ceased"
    if kind == "phase-2":
        return "phase-2"
    if kind in ("tribunal", "judicial-review"):
        return "contested"
    return "live"


def render_card(*, key: str, headline: str, title: str, detail: str) -> bytes | None:
    """The card as PNG bytes, or ``None`` if it could not be drawn."""
    bold = _find(_BOLD_FONTS)
    regular = _find(_REGULAR_FONTS)
    if bold is None or regular is None:
        return None
    try:
        return _draw(bold, regular, TONES[tone_for(key, headline)], headline, title, detail)
    except (OSError, ValueError):
        return None


def render_status_card(*, kind: str, headline: str) -> bytes | None:
    """A matter-agnostic card for one kind of milestone, or ``None``.

    The site's pages share these as their Open Graph image (see
    ``scripts/generate/og_cards.py``), so it carries no matter name: the
    unfurl prints the page title under it. Same layout and colours as the
    per-post card, with the headline in the title's place, drawn at
    :data:`STATUS_CARD_SCALE` times the size.
    """
    bold = _find(_BOLD_FONTS)
    regular = _find(_REGULAR_FONTS)
    if bold is None or regular is None:
        return None
    try:
        tone = tone_for(f"_:{kind}:_", headline)
        return _draw(bold, regular, TONES[tone], "ACCC merger register", headline,
                     "Every ACCC merger review, tracked", centre=True, scale=STATUS_CARD_SCALE)
    except (OSError, ValueError):
        return None


def _draw(
    bold: str, regular: str, fill: str, headline: str, title: str, detail: str,
    *, centre: bool = False, scale: int = 1,
) -> bytes:
    # The layout is written at 1x; every length goes through px() so a larger
    # card is the same card with more pixels, not a different layout.
    def px(n: int) -> int:
        return n * scale

    width, height, margin = px(WIDTH), px(HEIGHT), px(_MARGIN)
    image = Image.new("RGB", (width, height), fill)
    draw = ImageDraw.Draw(image)
    text_width = width - 2 * margin

    # Full-opacity tints rather than faded white: contrast has to hold.
    white, soft = "#ffffff", "#f3f4f6"

    headline_font = ImageFont.truetype(bold, px(40))
    headline_lines = _wrap(draw, headline, headline_font, text_width)[:2]
    y = px(70)
    for line in headline_lines:
        draw.text((margin, y), line, font=headline_font, fill=soft)
        y += px(52)
    draw.rectangle((margin, y + px(14), margin + px(96), y + px(20)), fill=white)

    # Largest title size that fits, so a short name is loud and a long one is
    # still whole; only a title that fits at no size is cut.
    title_top, title_bottom = y + px(56), height - px(150)
    for size in _TITLE_SIZES:
        font = ImageFont.truetype(bold, px(size))
        lines = _wrap(draw, title, font, text_width)
        line_height = int(px(size) * 1.18)
        if len(lines) <= _MAX_TITLE_LINES and len(lines) * line_height <= title_bottom - title_top:
            break
    else:
        lines = _wrap(draw, title, font, text_width)
        lines = _ellipsise(draw, lines, font, text_width)
    if centre:
        # A one-line headline on a generic card would otherwise sit high over
        # an empty band; centring it in its space keeps the card balanced.
        block = min(len(lines), _MAX_TITLE_LINES) * line_height
        title_top += max(0, (title_bottom - title_top - block) // 2)
    for line in lines[:_MAX_TITLE_LINES]:
        draw.text((margin, title_top), line, font=font, fill=white)
        title_top += line_height

    detail_font = ImageFont.truetype(regular, px(32))
    detail_line = _wrap(draw, detail, detail_font, text_width)[0] if detail else ""
    draw.text((margin, height - px(118)), detail_line, font=detail_font, fill=soft)

    site_font = ImageFont.truetype(bold, px(30))
    draw.text((margin, height - px(68)), "mergers.fyi", font=site_font, fill=soft)

    out = io.BytesIO()
    image.save(out, format="PNG", optimize=True)
    return out.getvalue()


def _find(candidates: tuple[str, ...]) -> str | None:
    return next((path for path in candidates if Path(path).is_file()), None)


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, width: int) -> list[str]:
    """Greedy word wrap by rendered width. A word wider than the line is split."""
    lines: list[str] = []
    current = ""
    for word in text.split():
        trial = f"{current} {word}".strip()
        if draw.textlength(trial, font=font) <= width:
            current = trial
            continue
        if current:
            lines.append(current)
        while draw.textlength(word, font=font) > width and len(word) > 1:
            cut = len(word) - 1
            while cut > 1 and draw.textlength(word[:cut], font=font) > width:
                cut -= 1
            lines.append(word[:cut])
            word = word[cut:]
        current = word
    if current:
        lines.append(current)
    return lines or [""]


def _ellipsise(draw: ImageDraw.ImageDraw, lines: list[str], font, width: int) -> list[str]:
    """Keep the first ``_MAX_TITLE_LINES`` lines, ending the last with ``…``."""
    kept = lines[:_MAX_TITLE_LINES]
    last = kept[-1].rstrip() + "…" if len(lines) > len(kept) else kept[-1]
    while draw.textlength(last, font=font) > width and len(last) > 1:
        last = last[:-2].rstrip() + "…"
    kept[-1] = last
    return kept
