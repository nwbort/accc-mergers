"""Post newly notified, referred, determined and appealed matters to Bluesky.

The records written by ``publish_matters`` are data: complete, addressable and
invisible unless somebody goes looking. This is the other half - the same
milestones as ordinary ``app.bsky.feed.post`` records, so the register shows
up in a feed.

What counts as worth posting is deliberately narrow: a matter arriving, being
referred to phase 2, being decided, the parties applying for a public benefit
determination and that being decided, having its assessment ceased, or going
to the Tribunal or the Federal Court. Questionnaires, timeline extensions and
remedy offers are all on the site and in the records, and posting them would
turn a useful account into a firehose. A waiver application's arrival is not
posted either: the ACCC only publishes a waiver once it has been determined,
so the notification date arrives already spent.

Every post ends with ``POST_HASHTAGS``, faceted so Bluesky's tag search can
see them - it indexes tags from the facet, not from the ``#``.

Two safeguards, because this is the only part of the pipeline that speaks to
people rather than to files:

* Posting needs ``ATPROTO_POST_ENABLED`` on top of the credentials, so adding
  the step to a workflow is not the thing that starts posting.
* The first enabled run *seeds* - it records every milestone on the register
  as already seen and posts nothing - so switching it on cannot dump 673
  matters into a feed. Whatever happens next is what gets posted.

Usage:
    python -m scripts.atproto.post_bluesky [--dry-run] [--max-posts N]
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from scripts.atproto import config
from scripts.atproto.client import XrpcError
from scripts.atproto.connect import open_client
from scripts.atproto.records import load_matters

STATE_VERSION = 1

#: Bluesky's post limit, in graphemes.
MAX_POST_CHARS = 300

#: Posts per run. A day on the register rarely carries more; the cap is there
#: so a re-scrape that rediscovers a batch of matters cannot flood a feed.
DEFAULT_MAX_POSTS = 10

#: Hashtags every post carries, in order. They cost characters the title
#: would otherwise have, so keep the list short.
POST_HASHTAGS = ("accc",)

#: Cleared-vs-blocked wording, keyed by the register's own determination value
#: and whether the matter is a waiver application.
_OUTCOME_HEADLINES = {
    ("Approved", False): "Cleared by the ACCC",
    ("Not opposed", False): "Cleared by the ACCC",
    ("Not approved", False): "Not approved by the ACCC",
    ("Declined", False): "Not approved by the ACCC",
    ("Approved", True): "Notification waiver granted",
    ("Not opposed", True): "Notification waiver granted",
    ("Not approved", True): "Notification waiver refused",
    ("Declined", True): "Notification waiver refused",
}

#: The public benefit determination's outcome -> headline. It is not a second
#: go at the competition test but a different one, so the headline says which.
_PUBLIC_BENEFIT_HEADLINES = {
    "Approved": "Cleared by the ACCC on public benefit grounds",
    "Not opposed": "Cleared by the ACCC on public benefit grounds",
    "Not approved": "Not approved by the ACCC after public benefit review",
    "Declined": "Not approved by the ACCC after public benefit review",
}


@dataclass(frozen=True)
class Milestone:
    """One thing that happened, and the post it becomes."""

    key: str
    date: str
    headline: str
    title: str
    detail: str
    url: str
    summary: str


def milestones(matter: dict) -> list[Milestone]:
    """Everything on this matter that would be worth posting about."""
    merger_id = matter["merger_id"]
    title = matter.get("merger_name") or merger_id
    url = f"{config.SITE_URL}/mergers/{merger_id}"
    summary = (matter.get("merger_description") or "").strip()
    is_waiver = bool(matter.get("is_waiver"))
    found: list[Milestone] = []

    def add(kind: str, date: str | None, headline: str, detail: str) -> None:
        if not date:
            return
        found.append(
            Milestone(
                key=f"{merger_id}:{kind}:{date}",
                date=date,
                headline=headline,
                title=title,
                detail=detail,
                url=url,
                summary=summary,
            )
        )

    notified = _date(matter.get("effective_notification_datetime"))
    # A waiver application is not on the register until it has been decided,
    # so its notification date is only ever learned retrospectively - posting
    # it would announce as news something that was already over when it
    # became visible, seconds before the determination post says so.
    if not is_waiver:
        add(
            "notified",
            notified,
            "Notified to the ACCC",
            _detail(merger_id, matter.get("stage"), notified),
        )

    if matter.get("phase_1_determination") == "Referred to phase 2":
        referred = _date(matter.get("phase_1_determination_date"))
        add(
            "phase-2",
            referred,
            "Referred to Phase 2",
            _detail(merger_id, "Phase 2 - detailed assessment", referred),
        )

    # The competition determination: Phase 2's if there was one, else the
    # headline. Once the parties have applied for a public benefit
    # determination the headline is that application's (empty while it runs),
    # so the phase 1 determination it followed stands in for it.
    public_benefit = matter.get("public_benefits_determination")
    phase_2 = matter.get("phase_2_determination")
    outcome = (
        phase_2
        or (None if public_benefit else matter.get("accc_determination"))
        or matter.get("phase_1_determination")
    )
    # A phase 1 referral is a determination on the register, but it is posted
    # as the referral above; posting it twice would say the same thing in two
    # different voices.
    if outcome and outcome != "Referred to phase 2":
        decided = (
            _date(matter.get("phase_2_determination_date"))
            or _date(matter.get("phase_1_determination_date"))
            or _date(matter.get("determination_publication_date"))
        )
        headline = _OUTCOME_HEADLINES.get((outcome, is_waiver), outcome)
        # has_conditions describes whichever determination now stands, which
        # is only this one until a public benefit determination is made.
        if matter.get("has_conditions") and "Cleared" in headline and not public_benefit:
            headline = "Cleared with conditions by the ACCC"
        stage = "Phase 2 - detailed assessment" if phase_2 else matter.get("stage")
        if not phase_2 and (public_benefit or matter.get("public_benefit_in_progress")):
            stage = "Phase 1 - initial assessment"
        add("determined", decided, headline, _detail(merger_id, stage, decided))

    applied = _date(matter.get("public_benefit_application_date"))
    add(
        "public-benefit",
        applied,
        "Public benefit determination sought",
        _detail(merger_id, "Public benefit phase", applied),
    )

    if public_benefit:
        decided = _date(matter.get("public_benefits_determination_date"))
        headline = _PUBLIC_BENEFIT_HEADLINES.get(public_benefit, public_benefit)
        if matter.get("has_conditions") and headline.startswith("Cleared"):
            headline = headline.replace("Cleared", "Cleared with conditions", 1)
        add("public-benefit-determined", decided, headline,
            _detail(merger_id, "Public benefit phase", decided))

    if matter.get("status") == "Assessment ceased":
        add(
            "ceased",
            _date(matter.get("ceased_date")) or notified,
            "Assessment ceased",
            _detail(merger_id, matter.get("stage"), None),
        )

    appeal = matter.get("appeal") or {}
    add(
        "tribunal",
        _date(appeal.get("filed_date")),
        "Under review in the Competition Tribunal",
        _detail(merger_id, appeal.get("tribunal_number"), _date(appeal.get("filed_date"))),
    )

    review = matter.get("judicial_review") or {}
    add(
        "judicial-review",
        _date(review.get("filed_date")),
        "Under judicial review in the Federal Court",
        _detail(merger_id, review.get("case_number"), _date(review.get("filed_date"))),
    )

    return found


def post_text(milestone: Milestone) -> str:
    """Lay out the post, trimming the title rather than anything structural.

    The URL has to survive intact - it is the only part of the post that does
    any work - and so does the matter id, so the title is the one thing that
    gives if the 300-character budget is tight.
    """
    tags = hashtag_line()
    tail = f"\n\n{milestone.detail}\n{milestone.url}" + (f"\n\n{tags}" if tags else "")
    budget = MAX_POST_CHARS - len(tail) - len(milestone.headline) - len(": ")
    title = milestone.title
    if budget < 1:
        # Nothing sensible left to trim to; drop the title entirely.
        return f"{milestone.headline}{tail}"
    if len(title) > budget:
        title = title[: budget - 1].rstrip() + "…"
    return f"{milestone.headline}: {title}{tail}"


def hashtag_line(tags: tuple[str, ...] | None = None) -> str:
    """The trailing hashtag line, e.g. ``#accc #mergers``."""
    tags = POST_HASHTAGS if tags is None else tags
    return " ".join(f"#{tag}" for tag in tags)


def link_facets(text: str, url: str) -> list[dict]:
    """A single link facet over ``url``, in UTF-8 byte offsets as the spec wants."""
    encoded = text.encode("utf-8")
    start = encoded.find(url.encode("utf-8"))
    if start < 0:
        return []
    feature = {"$type": "app.bsky.richtext.facet#link", "uri": url}
    return [_facet(start, url, feature)]


def tag_facets(text: str, tags: tuple[str, ...] | None = None) -> list[dict]:
    """One facet per hashtag, located as a line so a ``#`` in the title cannot
    be mistaken for one. The byte range covers the ``#``; the feature does not.
    """
    tags = POST_HASHTAGS if tags is None else tags
    line = hashtag_line(tags)
    encoded = text.encode("utf-8")
    start = encoded.rfind(line.encode("utf-8")) if line else -1
    if start < 0:
        return []

    found = []
    for tag in tags:
        hashtag = f"#{tag}"
        feature = {"$type": "app.bsky.richtext.facet#tag", "tag": tag}
        found.append(_facet(start, hashtag, feature))
        start += len(hashtag.encode("utf-8")) + 1
    return found


def facets(text: str, url: str) -> list[dict]:
    """Every facet a post carries, in byte order as the spec wants."""
    return link_facets(text, url) + tag_facets(text)


def post_record(milestone: Milestone, *, created_at: str) -> dict:
    """The ``app.bsky.feed.post`` record for one milestone."""
    text = post_text(milestone)
    record: dict = {
        "$type": config.POST_COLLECTION,
        "text": text,
        "createdAt": created_at,
        "langs": ["en-AU"],
    }
    found = facets(text, milestone.url)
    if found:
        record["facets"] = found

    # An external embed gives the post a card without needing a blob upload,
    # which would mean fetching and re-encoding an image on every post.
    embed_description = milestone.summary.replace("\n", " ").strip()
    record["embed"] = {
        "$type": "app.bsky.embed.external",
        "external": {
            "uri": milestone.url,
            "title": milestone.title[:300],
            "description": (
                embed_description[:299] + "…"
                if len(embed_description) > 300
                else embed_description
            ),
        },
    }
    return record


def load_state(path: Path | None = None) -> dict:
    path = Path(path) if path else config.POST_STATE_PATH
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("version") != STATE_VERSION:
        return {}
    payload.setdefault("posted", {})
    return payload


def save_state(state: dict, path: Path | None = None) -> None:
    path = Path(path) if path else config.POST_STATE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    state["version"] = STATE_VERSION
    path.write_text(
        json.dumps(state, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def pending(matters: list[dict], state: dict) -> list[Milestone]:
    """Milestones not yet posted, oldest first so a backlog drains in order."""
    posted = state.get("posted", {})
    found = [m for matter in matters for m in milestones(matter) if m.key not in posted]
    found.sort(key=lambda m: (m.date, m.key))
    return found


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
    state = load_state()
    due = pending(matters, state)

    if args.dry_run:
        print(f"{len(due)} milestone(s) due:")
        for milestone in due[: args.max_posts]:
            print("-" * 60)
            print(post_text(milestone))
        return 0

    if not config.posting_enabled():
        print(
            "ATPROTO_POST_ENABLED is not set - skipping "
            f"({len(due)} milestone(s) would be due). See docs/atproto.md.",
            file=sys.stderr,
        )
        return 0

    # Seeding happens on the first *enabled* run, not the first run of any
    # kind, so switching posting on never replays the whole register.
    if not state:
        state = {"posted": {m.key: {"seeded": True} for matter in matters for m in milestones(matter)}}
        save_state(state)
        print(f"Seeded {len(state['posted'])} existing milestone(s); nothing posted.")
        return 0

    if not due:
        print("Nothing to post.")
        return 0

    opened = open_client(pause=1.0)
    if opened is None:
        return 0
    client, _ = opened

    failures = 0
    try:
        for milestone in due[: args.max_posts]:
            created_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            try:
                result = client.create_record(
                    config.POST_COLLECTION, post_record(milestone, created_at=created_at)
                )
            except XrpcError as exc:
                print(f"  FAILED  {milestone.key}: {exc}", file=sys.stderr)
                failures += 1
                continue
            state["posted"][milestone.key] = {
                "uri": result.get("uri", ""),
                "postedAt": created_at,
            }
            print(f"  posted  {milestone.key}")
    finally:
        save_state(state)

    remaining = max(0, len(due) - args.max_posts)
    if remaining:
        print(f"{remaining} milestone(s) held over to the next run.")
    if failures:
        return 1
    return 0


def _facet(start: int, span: str, feature: dict) -> dict:
    """One facet over ``span``, measured in UTF-8 bytes rather than characters."""
    return {
        "index": {"byteStart": start, "byteEnd": start + len(span.encode("utf-8"))},
        "features": [feature],
    }


def _detail(merger_id: str, phase, date: str | None) -> str:
    parts = [merger_id]
    if phase:
        parts.append(str(phase))
    if date:
        parts.append(_pretty_date(date))
    return " · ".join(parts)


def _pretty_date(date: str) -> str:
    try:
        parsed = datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        return date
    return f"{parsed.day} {parsed.strftime('%b %Y')}"


def _date(value) -> str | None:
    if not isinstance(value, str) or len(value) < 10:
        return None
    return value[:10]


if __name__ == "__main__":
    sys.exit(main())
