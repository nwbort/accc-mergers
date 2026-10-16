"""Push a ready-to-post LinkedIn link to a phone for each new milestone.

The stopgap for while the API route is unavailable: no LinkedIn app, no token,
no approval. For each milestone ``post_linkedin`` would post, this builds a
``linkedin.com/feed/?shareActive=true&text=...`` link, which opens LinkedIn's
own composer with the post already written, and sends it as an ntfy
notification (``NTFY_TOPIC``) whose "Copy LinkedIn link" button puts the link
on the clipboard, to paste into a browser. It has to be a browser: a phone
hands linkedin.com links to the LinkedIn app, which opens without the text, so
tapping the notification itself opens the matter page instead. The text is in
the notification body too. Nothing is posted until a person presses Post.

The post is the same one the API would make, as plain text rather than in
LinkedIn's "little" format (the composer escapes what a person types). The
link to the matter page goes in the text, ahead of the hashtags, so LinkedIn
unfurls it into the page's own preview card.

It shares ``data/processed/linkedin_posts.json`` with ``post_linkedin``: the
first run seeds it, a milestone is recorded once its notification is
delivered, and when the API is switched on it picks up from where the links
left off rather than re-announcing them. It stands down once
``LINKEDIN_POST_ENABLED`` is set, so the two can't both handle a milestone.

Usage:
    python -m scripts.linkedin.share_links [--dry-run] [--max-links N]
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from urllib.parse import urlencode

import requests

from scripts.atproto.post_bluesky import (
    DEFAULT_MAX_POSTS,
    Milestone,
    load_state,
    milestones,
    pending,
    save_state,
)
from scripts.atproto.records import load_matters
from scripts.linkedin import config
from scripts.linkedin.post_linkedin import hashtag_templates, preview, summary_text

SHARE_URL = "https://www.linkedin.com/feed/"


def share_text(milestone: Milestone) -> str:
    """The post as a person would type it, with the matter link to unfurl."""
    parts = [f"{milestone.headline}: {milestone.title}"]
    summary = summary_text(milestone)
    if summary:
        parts.append(summary)
    parts.append(milestone.detail)
    parts.append(milestone.url)
    tags = preview(hashtag_templates())
    if tags:
        parts.append(tags)
    return "\n\n".join(parts)


def share_url(milestone: Milestone) -> str:
    """A link that opens LinkedIn's composer with the post filled in."""
    return f"{SHARE_URL}?{urlencode({'shareActive': 'true', 'text': share_text(milestone)})}"


def notify(milestone: Milestone, *, topic: str, server: str, token: str = "") -> bool:
    """Send one milestone's link to ntfy. ``True`` if the server took it."""
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    try:
        response = requests.post(
            server.rstrip("/"),
            json={
                "topic": topic,
                "title": f"Post to LinkedIn: {milestone.headline}"[:200],
                "message": share_text(milestone)[:4000],
                # Not the share link: a phone hands linkedin.com links to the
                # LinkedIn app, which opens without the text. The link is
                # copied instead, to paste into a browser.
                "click": milestone.url,
                "tags": ["linkedin"],
                "actions": [
                    {"action": "copy", "label": "Copy LinkedIn link", "value": share_url(milestone)},
                    {"action": "view", "label": "Open matter", "url": milestone.url},
                ],
            },
            headers=headers,
            timeout=20,
        )
    except requests.RequestException as exc:
        print(f"  ntfy failed for {milestone.key}: {exc}", file=sys.stderr)
        return False
    if response.status_code >= 300:
        # The body can echo the topic back, so it is not logged.
        print(f"  ntfy refused {milestone.key} (HTTP {response.status_code})", file=sys.stderr)
        return False
    return True


def share_links_enabled() -> bool:
    return os.environ.get("LINKEDIN_SHARE_LINKS", "").strip().lower() in {"1", "true", "yes"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the links that are due. Sends nothing and writes no state.",
    )
    parser.add_argument("--max-links", type=int, default=DEFAULT_MAX_POSTS)
    args = parser.parse_args(argv)

    matters = load_matters()
    state = load_state(config.POST_STATE_PATH)
    due = pending(matters, state)

    if args.dry_run:
        print(f"{len(due)} milestone(s) due:")
        for milestone in due[: args.max_links]:
            print("-" * 60)
            print(share_text(milestone))
            print(f"[link: {share_url(milestone)}]")
        return 0

    if config.posting_enabled():
        print("LINKEDIN_POST_ENABLED is set - the API poster has this; skipping.")
        return 0
    if not share_links_enabled():
        print("LINKEDIN_SHARE_LINKS is not set - skipping. See docs/linkedin.md.",
              file=sys.stderr)
        return 0
    topic = os.environ.get("NTFY_TOPIC", "").strip()
    if not topic:
        print("NTFY_TOPIC is not set - nowhere to send the links; skipping.", file=sys.stderr)
        return 0

    if not state:
        state = {"posted": {m.key: {"seeded": True} for matter in matters for m in milestones(matter)}}
        save_state(state, config.POST_STATE_PATH)
        print(f"Seeded {len(state['posted'])} existing milestone(s); nothing sent.")
        return 0

    if not due:
        print("Nothing to share.")
        return 0

    server = os.environ.get("NTFY_SERVER", "").strip() or "https://ntfy.sh"
    token = os.environ.get("NTFY_TOKEN", "").strip()
    failures = 0
    try:
        for milestone in due[: args.max_links]:
            if not notify(milestone, topic=topic, server=server, token=token):
                failures += 1
                continue
            state["posted"][milestone.key] = {
                "shareLink": True,
                "sentAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            }
            print(f"  link sent  {milestone.key}")
    finally:
        save_state(state, config.POST_STATE_PATH)

    remaining = max(0, len(due) - args.max_links)
    if remaining:
        print(f"{remaining} milestone(s) held over to the next run.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
