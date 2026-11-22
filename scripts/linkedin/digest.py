"""Post the weekly digest to the LinkedIn page, through the same Make.com webhook.

Run by ``send-weekly-email.yml`` straight after a **production** send, and
never after a test send or a dry run: the workflow step is gated on both, and
this refuses to send unless ``AUDIENCE`` says production as well, so a test run
can't reach the page even if the gate is edited away.

The post is the email's subject line and its opening summary paragraph (the
lede, ``send_weekly_email.build_lede``, as plain text), linking to /digest.
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
from scripts.linkedin.webhook import FALLBACK_IMAGE, deliver

DIGEST_URL = f"{atproto_config.SITE_URL}/digest"
HEADLINE = "Weekly merger digest"


def summary(digest: dict) -> str:
    """The email's lede as plain text."""
    lede = swe.build_lede(swe._counts(digest))
    return html.unescape(re.sub(r"<[^>]+>", "", lede))


def commentary(digest: dict) -> str:
    """The post without the link, in LinkedIn's little format."""
    parts = [escape(swe.build_subject(digest)), escape(summary(digest))]
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
    text = "\n\n".join(p for p in (swe.build_subject(digest), lede, DIGEST_URL, tags) if p)
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
        "image_url": f"{atproto_config.SITE_URL}/{FALLBACK_IMAGE}",
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
