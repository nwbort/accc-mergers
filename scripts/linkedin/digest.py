"""Post the weekly digest to the LinkedIn page, through the same Make.com webhook.

Run by ``send-weekly-email.yml`` straight after a **production** send, and
never after a test send or a dry run: the workflow step is gated on both, and
this refuses to send unless ``AUDIENCE`` says production as well, so a test run
can't reach the page even if the gate is edited away.

The post is a headline (:func:`headline`) and the email's opening summary
paragraph (the lede, ``send_weekly_email.build_lede``, as plain text),
linking to /digest.
It goes to ``LINKEDIN_WEBHOOK_URL`` in the same shape as a milestone
(``webhook.payload``), so the scenario that posts milestones posts this too,
with no change in Make. ``kind`` is ``"digest"`` for a scenario that wants to
tell the two apart.

No state is kept: the workflow runs once a week, and re-running it re-sends
the email as well, so a re-run is a deliberate repeat of both.

Usage:
    python -m scripts.linkedin.digest [--dry-run]
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys

from scripts import send_weekly_email as swe
from scripts.atproto import config as atproto_config
from scripts.atproto.post_bluesky import CARD_DESCRIPTION_CHARS, first_sentence
from scripts.linkedin import config
from scripts.linkedin.text import MAX_POST_CHARS, escape, hashtag_templates, preview
from scripts.generate.og_cards import DIGEST_CARD
from scripts.linkedin.webhook import deliver

DIGEST_URL = f"{atproto_config.SITE_URL}/digest"
HEADLINE = "Weekly merger digest"


TAGLINE = "your week in Australian mergers"


def _count(n: int) -> str:
    """A callout's count opening the headline: spelled out and capitalised."""
    return swe._NUMBER_WORDS.get(n, str(n)).capitalize()


def headline(digest: dict) -> str:
    """The post's opening line, e.g. "42 deals cleared, 4 new ones notified:
    your week in Australian mergers".

    The larger of the week's clearances and new notifications leads (cleared
    on a tie). A week with a deal blocked or referred to phase 2 leads
    with that instead, since those are the rare outcomes worth stopping a
    scroll for: "One deal sent to phase 2, 42 cleared and 4 new ones notified:
    …" ("One deal blocked, two sent to phase 2, …" when both). A week
    with nothing at all is "A quiet week in Australian mergers".
    """
    c = swe._counts(digest)
    # Only the opening item says "deal(s)": "One deal sent to phase 2,
    # 42 cleared and 4 new ones notified".
    callouts = [(c["declined"], "blocked"), (c["referred"], "sent to phase 2")]
    counts = sorted([(c["cleared"], "cleared"), (c["new"], "new")],
                    key=lambda pair: pair[0], reverse=True)  # stable: cleared wins a tie
    has_callout = any(n for n, _ in callouts)

    phrases = []
    for n, what in callouts + counts:
        if not n:
            continue
        first = not phrases
        if what == "new":
            noun = swe.pluralise(n, "deal" if first else "one")
            phrases.append(f"{n} new {noun} notified")
            continue
        # Counts stay digits, as in the email; a callout's are spelled out.
        if what == "cleared":
            number = str(n)
        else:
            number = _count(n) if first else swe._NUMBER_WORDS.get(n, str(n))
        noun = f" {swe.pluralise(n, 'deal')}" if first else ""
        phrases.append(f"{number}{noun} {what}")

    if not phrases:
        return "A quiet week in Australian mergers"
    lead = swe.join_and(phrases) if has_callout else ", ".join(phrases)
    return f"{lead}: {TAGLINE}"


def summary(digest: dict) -> str:
    """The email's lede as plain text."""
    lede = swe.build_lede(swe._counts(digest))
    return html.unescape(re.sub(r"<[^>]+>", "", lede))


def commentary(digest: dict) -> str:
    """The post without the link, in LinkedIn's little format."""
    parts = [escape(headline(digest)), escape(summary(digest))]
    tags = hashtag_templates()
    if tags:
        parts.append(tags)
    text = "\n\n".join(parts)
    return text if len(text) <= MAX_POST_CHARS else text[: MAX_POST_CHARS - 1] + "…"


def payload(digest: dict) -> dict:
    """What the webhook receives: a milestone's keys, so one scenario posts both."""
    little = commentary(digest)
    plain = preview(little)
    lede = summary(digest)
    date_range = swe.format_date_range(digest["period_start"], digest["period_end"])
    tags = preview(hashtag_templates())
    text = "\n\n".join(p for p in (headline(digest), lede, DIGEST_URL, tags) if p)
    return {
        "kind": "digest",
        "key": f"digest:{digest['period_end'][:10]}",
        "matter_id": "",
        "date": digest["period_end"][:10],
        "headline": HEADLINE,
        "title": f"{HEADLINE}: {date_range}",
        # A text post: the whole post, link included, as for a milestone.
        "text": text,
        "commentary": plain,
        "commentary_little": little,
        "url": DIGEST_URL,
        "description": first_sentence(lede, CARD_DESCRIPTION_CHARS),
        "image_url": f"{atproto_config.SITE_URL}/og/{DIGEST_CARD}",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                        help="Print the payload. Sends nothing.")
    args = parser.parse_args(argv)

    body = payload(swe.load_digest())
    if args.dry_run:
        print(json.dumps(body, indent=2, ensure_ascii=False))
        return 0

    audience = os.environ.get("AUDIENCE", "").strip().lower() or "production"
    if audience != "production":
        print(f"AUDIENCE is '{audience}', not production - not posting to LinkedIn.")
        return 0

    url = config.webhook_url()
    if not url:
        print("LINKEDIN_WEBHOOK_URL is not set - skipping. See docs/linkedin.md.",
              file=sys.stderr)
        return 0

    if not deliver(body, url=url, api_key=config.webhook_api_key()):
        return 1
    print(f"Sent {body['key']} to the LinkedIn webhook.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
