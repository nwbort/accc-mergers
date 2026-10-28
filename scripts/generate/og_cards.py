"""Generic Open Graph cards: one image per kind of milestone, not per matter.

A merger page's link preview (LinkedIn, Slack, iMessage...) used to show the
site's one shared ``og-image.png`` whatever had happened to the matter. A card
per matter would mean ~800 more files against Pages' 20,000-file cap, and
redrawing one on every status change; but the preview already prints the
page's title (the merger's name) under the image, so the image only has to say
*what happened*. That is a short, fixed list - the headlines the Bluesky and
LinkedIn posters announce (``post_bluesky.milestones``) - so each gets one
card, in the colour the site gives that outcome, and a page points at the one
for its latest milestone.

Two halves:

* :func:`current_card` names the card a matter's page should show. The
  generator stores it in each ``mergers/{id}.json`` as ``og_card``, so the
  Pages Function that answers link-preview bots, the prerenderer and the SPA
  all read one answer rather than each re-deriving the milestone rules.
* Running this module draws the cards into ``frontend/public/og/``. They are
  committed, and only need redrawing when :data:`CARDS` or the card design
  changes (a test fails if one is missing).

Usage:
    python -m scripts.generate.og_cards
"""

from __future__ import annotations

import sys
from pathlib import Path

from scripts.atproto.card_image import render_status_card
from scripts.atproto.post_bluesky import Milestone, milestones
from scripts.generate.static_data.prune import prune_stale_files
from scripts.paths import REPO_ROOT
from scripts.slug import slugify

OG_DIR = REPO_ROOT / "frontend" / "public" / "og"

#: Every headline ``milestones()`` emits, with the milestone kind that picks
#: its colour. A headline missing here (an outcome the register has never
#: used) gets no card, and its page keeps the shared image.
CARDS: tuple[tuple[str, str], ...] = (
    ("notified", "Notified to the ACCC"),
    ("phase-2", "Referred to Phase 2"),
    ("determined", "Cleared by the ACCC"),
    ("determined", "Cleared with conditions by the ACCC"),
    ("determined", "Not approved by the ACCC"),
    ("determined", "Notification waiver granted"),
    ("determined", "Notification waiver refused"),
    ("public-benefit", "Public benefit determination sought"),
    ("public-benefit-determined", "Cleared by the ACCC on public benefit grounds"),
    ("public-benefit-determined", "Cleared with conditions by the ACCC on public benefit grounds"),
    ("public-benefit-determined", "Not approved by the ACCC after public benefit review"),
    ("ceased", "Assessment ceased"),
    ("tribunal", "Under review in the Competition Tribunal"),
    ("judicial-review", "Under judicial review in the Federal Court"),
)

_FILES = {headline: f"{slugify(headline)}.png" for _, headline in CARDS}


def card_for(milestone: Milestone) -> str | None:
    """The card file name (``cleared-by-the-accc.png``) for one milestone."""
    return _FILES.get(milestone.headline)


def current_card(matter: dict) -> str | None:
    """The card for a matter's latest milestone, or ``None`` for the shared image.

    Latest by date, ties going to the later milestone in ``milestones()``'s
    own order (ceased after notified on the same day); an undated
    determination sorts last, as it does in the posting queue. A Tribunal or
    Federal Court review only counts while it is still running: once it
    concludes, the card falls back to the determination it was about.
    """
    found = [
        m for m in milestones(matter)
        if not (_kind(m) in _LIVE_FLAGS and not matter.get(_LIVE_FLAGS[_kind(m)]))
    ]
    if not found:
        return None
    _, latest = max(enumerate(found), key=lambda pair: (pair[1].date, pair[0]))
    return card_for(latest)


# Review milestones, and the flag that says the review is still running.
_LIVE_FLAGS = {"tribunal": "under_appeal", "judicial-review": "under_judicial_review"}


def _kind(milestone: Milestone) -> str:
    return milestone.key.split(":")[1]


def write_cards(out_dir: Path = OG_DIR) -> list[str]:
    """Draw every card into ``out_dir``, pruning any no longer in :data:`CARDS`."""
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for kind, headline in CARDS:
        png = render_status_card(kind=kind, headline=headline)
        if png is None:
            raise RuntimeError("no usable font found; cannot draw the cards")
        (out_dir / _FILES[headline]).write_bytes(png)
        written.append(_FILES[headline])
    prune_stale_files(out_dir, set(written), pattern="*.png", label="og cards")
    return written


def main() -> int:
    for name in write_cards():
        print(f"wrote {OG_DIR.relative_to(REPO_ROOT) / name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
