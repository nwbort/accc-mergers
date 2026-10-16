"""Post newly notified, referred, determined and appealed matters to LinkedIn.

The same milestones as ``scripts.atproto.post_bluesky``, chosen by the same
``milestones()`` - so what counts as worth posting, and which date a milestone
carries, can only ever be decided in one place. What differs is the medium:

* LinkedIn allows 3,000 characters rather than 300, so a post carries the
  matter's description as well as its headline, name and identifier.
* The commentary is in LinkedIn's "little" text format, in which ``#``, ``(``,
  ``*`` and a dozen other characters are markup. Every piece of register text
  is escaped, and the hashtags go in as ``{hashtag|\\#|accc}`` templates.
* The link travels as the post's article card, with the same per-milestone
  image Bluesky's cards carry (``scripts/atproto/card_image.py``). LinkedIn
  never scrapes a link given through the API, so without the card there would
  be no preview at all.

The safeguards are Bluesky's, with one difference:

* Posting needs ``LINKEDIN_POST_ENABLED`` on top of the credentials.
* The first enabled run seeds - records every milestone as seen and posts
  nothing - against its own state file, so switching LinkedIn on months after
  Bluesky cannot replay the months in between.
* The author's recent posts are read back before posting, so a run whose
  state never reached ``main`` is not posted twice. That needs read access to
  the author's posts, which a company page with the Community Management API
  has and a personal profile on a self-serve app does not (``r_member_social``
  is restricted). There a 403 on the read-back is reported and the run posts
  without the check, rather than never posting at all.

Usage:
    python -m scripts.linkedin.post_linkedin [--dry-run] [--max-posts N]
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from scripts.atproto import config as atproto_config
from scripts.atproto.card_image import render_card
from scripts.atproto.post_bluesky import (
    CARD_DESCRIPTION_CHARS,
    DEFAULT_MAX_POSTS,
    POST_HASHTAGS,
    Milestone,
    load_state,
    milestones,
    first_sentence,
    pending,
    plain_text,
    save_state,
)
from scripts.atproto.records import load_matters
from scripts.linkedin import config
from scripts.linkedin.client import LinkedInClient, LinkedInError, mint_access_token

#: LinkedIn's commentary limit, in characters.
MAX_POST_CHARS = 3000

#: The most of the matter's description that goes into the post. It carries
#: the description's first sentence, which says what the deal is; this cap is
#: for the rare one that runs on.
SUMMARY_CHARS = 500

#: Posts read back to catch a milestone that went out on a lost run.
RECENT_POSTS_CHECKED = 100

#: Characters the little format treats as markup.
_RESERVED = re.compile(r"([\\|{}@\[\]()<>#*_~])")
_UNESCAPE = re.compile(r"\\([\\|{}@\[\]()<>#*_~])")


def escape(text: str) -> str:
    """Escape ``text`` so the little format shows it verbatim."""
    return _RESERVED.sub(r"\\\1", text)


def unescape(text: str) -> str:
    return _UNESCAPE.sub(r"\1", text)


def preview(commentary: str) -> str:
    """Commentary as LinkedIn will show it: templates rendered, escapes gone."""
    return unescape(re.sub(r"\{hashtag\|\\?([#＃])\|([^}]*)\}", r"\1\2", commentary))


def hashtag_templates(tags: tuple[str, ...] | None = None) -> str:
    """The trailing hashtag line, as little-format hashtag templates."""
    tags = POST_HASHTAGS if tags is None else tags
    return " ".join(f"{{hashtag|\\#|{tag}}}" for tag in tags)


def summary_text(milestone: Milestone) -> str:
    return first_sentence(plain_text(milestone.summary), SUMMARY_CHARS)


def post_text(milestone: Milestone) -> str:
    """The post's commentary, already in little format."""
    parts = [escape(f"{milestone.headline}: {milestone.title}")]
    summary = summary_text(milestone)
    if summary:
        parts.append(escape(summary))
    parts.append(escape(milestone.detail))
    tags = hashtag_templates()
    if tags:
        parts.append(tags)
    text = "\n\n".join(parts)
    # Only an absurd title could get here; trim it rather than be refused.
    return text if len(text) <= MAX_POST_CHARS else text[: MAX_POST_CHARS - 1] + "…"


def post_body(milestone: Milestone, *, author: str, thumbnail: str | None = None) -> dict:
    """The ``/rest/posts`` request body for one milestone."""
    article = {
        "source": milestone.url,
        "title": milestone.title[:400],
    }
    description = first_sentence(plain_text(milestone.summary), CARD_DESCRIPTION_CHARS)
    if description:
        article["description"] = description
    if thumbnail:
        article["thumbnail"] = thumbnail
    return {
        "author": author,
        "commentary": post_text(milestone),
        "visibility": "PUBLIC",
        "distribution": {
            "feedDistribution": "MAIN_FEED",
            "targetEntities": [],
            "thirdPartyDistributionChannels": [],
        },
        "content": {"article": article},
        "lifecycleState": "PUBLISHED",
        "isReshareDisabledByAuthor": False,
    }


def already_posted(milestone: Milestone, recent: list[dict]) -> str | None:
    """The URN of a recent post that already announced ``milestone``.

    Matched as on Bluesky: the article's link (the matter) and the headline
    the commentary opens with (the kind of milestone), compared whole so one
    headline that prefixes another cannot match it.
    """
    for post in recent:
        source = (((post.get("content") or {}).get("article")) or {}).get("source")
        first_line = unescape(post.get("commentary") or "").split("\n", 1)[0]
        if source == milestone.url and (
            first_line == milestone.headline
            or first_line.startswith(f"{milestone.headline}: ")
        ):
            return post.get("id", "")
    return None


class _Thumbnails:
    """Per-milestone card images, falling back to the site's shared image.

    The shared image is uploaded at most once, and only if some card needs it.
    A failure costs a post its picture, never the post.
    """

    def __init__(self, client: LinkedInClient, shared_path: Path | None = None):
        self.client = client
        self.shared_path = Path(shared_path) if shared_path else atproto_config.CARD_IMAGE_PATH
        self._shared: str | None = None
        self._shared_tried = False

    def for_milestone(self, milestone: Milestone) -> str | None:
        png = render_card(
            key=milestone.key,
            headline=milestone.headline,
            title=milestone.title,
            detail=milestone.detail,
        )
        if png is not None:
            try:
                return self.client.upload_image(png)
            except LinkedInError as exc:
                print(f"  card upload failed for {milestone.key} ({exc}); using the shared image",
                      file=sys.stderr)
        return self.shared()

    def shared(self) -> str | None:
        if not self._shared_tried:
            self._shared_tried = True
            try:
                self._shared = self.client.upload_image(self.shared_path.read_bytes())
            except (OSError, LinkedInError) as exc:
                print(f"  no shared card image ({exc}); posting without a thumbnail",
                      file=sys.stderr)
        return self._shared


def open_client() -> LinkedInClient | None:
    """An authenticated client, or ``None`` with the reason printed."""
    creds = config.load_credentials()
    if creds is None:
        print(
            "LINKEDIN_AUTHOR_URN and a LinkedIn token are not both set - skipping. "
            "See docs/linkedin.md.",
            file=sys.stderr,
        )
        return None
    try:
        token = mint_access_token(creds)
    except LinkedInError as exc:
        print(f"LinkedIn login failed: {exc}. See docs/linkedin.md.", file=sys.stderr)
        return None
    print(f"Posting to LinkedIn as {creds.author}")
    return LinkedInClient(access_token=token, author=creds.author, pause=1.0)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the posts that are due. Needs no credentials and writes no state.",
    )
    parser.add_argument("--max-posts", type=int, default=DEFAULT_MAX_POSTS)
    args = parser.parse_args(argv)

    matters = load_matters()
    state = load_state(config.POST_STATE_PATH)
    due = pending(matters, state)

    if args.dry_run:
        print(f"{len(due)} milestone(s) due:")
        for milestone in due[: args.max_posts]:
            print("-" * 60)
            print(preview(post_text(milestone)))
            print(f"[card: {milestone.url}]")
        return 0

    if not config.posting_enabled():
        print(
            "LINKEDIN_POST_ENABLED is not set - skipping "
            f"({len(due)} milestone(s) would be due). See docs/linkedin.md.",
            file=sys.stderr,
        )
        return 0

    if not state:
        state = {"posted": {m.key: {"seeded": True} for matter in matters for m in milestones(matter)}}
        save_state(state, config.POST_STATE_PATH)
        print(f"Seeded {len(state['posted'])} existing milestone(s); nothing posted.")
        return 0

    if not due:
        print("Nothing to post.")
        return 0

    client = open_client()
    if client is None:
        return 0

    try:
        recent = client.list_posts(RECENT_POSTS_CHECKED)
    except LinkedInError as exc:
        if exc.status == 401:
            print(f"LinkedIn token rejected ({exc}); replace it. See docs/linkedin.md.",
                  file=sys.stderr)
            return 1
        if exc.status != 403:
            print(f"Could not read back recent posts ({exc}); posting nothing.", file=sys.stderr)
            return 1
        print(
            "  this token cannot read the author's posts back (no r_organization_social / "
            "r_member_social); posting without the duplicate check.",
            file=sys.stderr,
        )
        recent = []

    fresh = []
    for milestone in due:
        urn = already_posted(milestone, recent)
        if urn is None:
            fresh.append(milestone)
            continue
        state["posted"][milestone.key] = {"urn": urn, "recovered": True}
        print(f"  already posted  {milestone.key}")
    if len(fresh) < len(due):
        save_state(state, config.POST_STATE_PATH)
    due = fresh
    if not due:
        print("Nothing to post.")
        return 0

    thumbnails = _Thumbnails(client)
    failures = 0
    try:
        for milestone in due[: args.max_posts]:
            body = post_body(milestone, author=client.author,
                             thumbnail=thumbnails.for_milestone(milestone))
            try:
                urn = client.create_post(body)
            except LinkedInError as exc:
                print(f"  FAILED  {milestone.key}: {exc}", file=sys.stderr)
                failures += 1
                if exc.status == 401:
                    # Every later post would be refused the same way.
                    break
                continue
            state["posted"][milestone.key] = {
                "urn": urn,
                "postedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            }
            print(f"  posted  {milestone.key}")
    finally:
        save_state(state, config.POST_STATE_PATH)

    remaining = max(0, len(due) - args.max_posts)
    if remaining:
        print(f"{remaining} milestone(s) held over to the next run.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
