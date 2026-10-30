"""Hand each new milestone to a webhook that posts it to the LinkedIn page.

The route for while LinkedIn's own API is out of reach: a Make.com scenario
(or Zapier, Pipedream, n8n - anything with a custom webhook trigger and a
LinkedIn company page action) holds the LinkedIn connection, and this POSTs
it one JSON object per milestone. Make's free plan is enough, because a
webhook only spends credits when it is called, where an RSS watcher spends
one on every poll whether or not anything is new.

The milestones are ``post_linkedin``'s, chosen by the same ``milestones()``,
and the post is the same one, offered in the shapes a scenario might want
(see ``payload``): plain text with the link in it, for a text post; the
commentary without the link plus the link, title, description and card
image, for a link post; and the commentary in LinkedIn's "little" format, for
a module that passes text straight to the Posts API, where an unescaped ``(``
can truncate a post.

It runs inside ``pipeline.yml``, beside ``post_bluesky`` and
``post_linkedin``, so its state lands in the same commit as the data it
describes. Unlike ``share_links`` it doesn't wait for the deploy: the post
carries its own card (title, description, and one of the committed ``og/``
images), so LinkedIn never scrapes the page and can't cache a stale preview.
The cost is that a reader who clicks through on a brand-new matter in the
minute or two before Pages deploys lands before its page exists, as on
Bluesky. ``--wait-for-deploy`` is still there for a run that wants it.

It shares ``data/processed/linkedin_posts.json`` with the other two: the first
run seeds it if it doesn't exist, and a milestone is recorded once the webhook
accepts it. Accepted is all this can know - a scenario that fails afterwards
(an expired LinkedIn connection, say) is Make's to report and retry, not this
run's. It stands down once ``LINKEDIN_POST_ENABLED`` is set, and
``share_links`` stands down while ``LINKEDIN_WEBHOOK_URL`` is set, so only one
of the three handles a milestone.

Usage:
    python -m scripts.linkedin.webhook [--dry-run] [--max-posts N]
        [--wait-for-deploy SECONDS]
    python -m scripts.linkedin.webhook --sample    # teach a scenario the shape
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone

import requests

from scripts.atproto import config as atproto_config
from scripts.atproto.post_bluesky import (
    CARD_DESCRIPTION_CHARS,
    DEFAULT_MAX_POSTS,
    Milestone,
    first_sentence,
    load_state,
    milestones,
    pending,
    plain_text,
    save_state,
)
from scripts.atproto.records import load_matters
from scripts.linkedin import config
from scripts.linkedin.post_linkedin import post_text, preview
from scripts.linkedin.share_links import _matter_id, page_link, share_text, wait_for_deploy

#: Gap between posts when several are due, so the page doesn't publish a
#: burst at once.
POST_SPACING_SECONDS = 5

#: The site-wide card, for a matter whose detail file names none.
FALLBACK_IMAGE = "og-image.png"


def image_url(matter: dict) -> str:
    """The generic card for the matter's latest milestone, as the site serves it."""
    card = matter.get("og_card")
    path = f"og/{card}" if card else FALLBACK_IMAGE
    return f"{atproto_config.SITE_URL}/{path}"


def payload(milestone: Milestone, matter: dict) -> dict:
    """What the webhook receives for one milestone.

    The keys are what a scenario maps from, so renaming one breaks the
    scenario: add rather than rename.
    """
    commentary = post_text(milestone)
    return {
        "key": milestone.key,
        "matter_id": _matter_id(milestone),
        "date": milestone.date,
        "headline": milestone.headline,
        "title": milestone.title,
        # A text post: the whole post, link included, for LinkedIn to unfurl.
        "text": share_text(milestone),
        # A link post: the link travels as the card, so it isn't in the text.
        "commentary": preview(commentary),
        "commentary_little": commentary,
        "url": page_link(milestone),
        "description": first_sentence(plain_text(milestone.summary), CARD_DESCRIPTION_CHARS),
        "image_url": image_url(matter),
    }


#: The header a Make webhook with API key authentication reads.
API_KEY_HEADER = "x-make-apikey"


def deliver(body: dict, *, url: str, api_key: str = "") -> bool:
    """POST one payload. ``True`` if the webhook accepted it."""
    headers = {API_KEY_HEADER: api_key} if api_key else {}
    try:
        response = requests.post(url, json=body, headers=headers, timeout=30)
    except requests.RequestException as exc:
        # requests puts the URL in the message, and the URL is the secret.
        print(f"  webhook failed for {body['key']}: {type(exc).__name__}", file=sys.stderr)
        return False
    if response.status_code >= 300:
        print(f"  webhook refused {body['key']} (HTTP {response.status_code})", file=sys.stderr)
        return False
    return True


def send_sample(matters: list[dict], by_id: dict[str, dict]) -> int:
    """Send the latest milestone on the register, recording nothing."""
    url = config.webhook_url()
    if not url:
        print("LINKEDIN_WEBHOOK_URL is not set - nowhere to send the sample.", file=sys.stderr)
        return 1
    every = [m for matter in matters for m in milestones(matter)]
    if not every:
        print("No milestones on the register to sample.", file=sys.stderr)
        return 1
    latest = max(every, key=lambda m: m.date)
    if not deliver(payload(latest, by_id[_matter_id(latest)]), url=url,
                   api_key=config.webhook_api_key()):
        return 1
    print(f"Sent {latest.key} as a sample; nothing recorded.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the payloads that are due. Sends nothing and writes no state.",
    )
    parser.add_argument("--max-posts", type=int, default=DEFAULT_MAX_POSTS)
    parser.add_argument(
        "--wait-for-deploy",
        type=float,
        default=0,
        metavar="SECONDS",
        help="Send a milestone only once mergers.fyi serves this run's data for "
        "its matter, waiting up to this long. 0 (the default) sends straight away.",
    )
    parser.add_argument(
        "--sample",
        action="store_true",
        help="Send the register's latest milestone to LINKEDIN_WEBHOOK_URL, "
        "whether or not it has been posted, and record nothing - so a scenario "
        "can learn the payload's shape (Make's \"Redetermine data structure\").",
    )
    args = parser.parse_args(argv)

    matters = load_matters()
    by_id = {matter["merger_id"]: matter for matter in matters}

    if args.sample:
        return send_sample(matters, by_id)
    state = load_state(config.POST_STATE_PATH)
    due = pending(matters, state)

    if args.dry_run:
        print(f"{len(due)} milestone(s) due:")
        for milestone in due[: args.max_posts]:
            print("-" * 60)
            print(json.dumps(payload(milestone, by_id[_matter_id(milestone)]), indent=2,
                             ensure_ascii=False))
        return 0

    if config.posting_enabled():
        print("LINKEDIN_POST_ENABLED is set - the API poster has this; skipping.")
        return 0
    url = config.webhook_url()
    if not url:
        print("LINKEDIN_WEBHOOK_URL is not set - skipping. See docs/linkedin.md.",
              file=sys.stderr)
        return 0

    if not state:
        state = {"posted": {m.key: {"seeded": True} for matter in matters for m in milestones(matter)}}
        save_state(state, config.POST_STATE_PATH)
        print(f"Seeded {len(state['posted'])} existing milestone(s); nothing sent.")
        return 0

    if not due:
        print("Nothing to post.")
        return 0

    api_key = config.webhook_api_key()
    batch = due[: args.max_posts]
    if args.wait_for_deploy > 0:
        batch = wait_for_deploy(batch, by_id, timeout=args.wait_for_deploy)
    failures = 0
    spacing_due = False
    try:
        for milestone in batch:
            if spacing_due:
                time.sleep(POST_SPACING_SECONDS)
                spacing_due = False
            if not deliver(payload(milestone, by_id[_matter_id(milestone)]), url=url,
                           api_key=api_key):
                failures += 1
                continue
            spacing_due = True
            state["posted"][milestone.key] = {
                "webhook": True,
                "sentAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            }
            print(f"  sent  {milestone.key}")
    finally:
        save_state(state, config.POST_STATE_PATH)

    remaining = max(0, len(due) - args.max_posts)
    if remaining:
        print(f"{remaining} milestone(s) held over to the next run.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
