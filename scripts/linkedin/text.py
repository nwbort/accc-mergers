"""How a milestone reads as a LinkedIn post.

Shared by ``webhook`` (which hands the post to the Make.com scenario) and
``share_links`` (which hands it to a person). The milestones themselves are
``scripts.atproto.post_bluesky``'s, chosen by the same ``milestones()``; only
the wording differs:

* LinkedIn allows 3,000 characters rather than 300, so a post carries the
  matter's description as well as its headline, name and identifier.
* Make's LinkedIn module passes the post's text to LinkedIn unchanged, and
  LinkedIn reads it in its "little" text format, in which ``#``, ``(``, ``*``
  and a dozen other characters are markup - an unescaped ``(`` can truncate a
  post. So :func:`post_text` escapes every piece of register text and writes
  the hashtags as ``{hashtag|\\#|accc}`` templates, and :func:`preview` turns
  that back into plain text for anywhere that wants plain text.
"""

from __future__ import annotations

import re

from scripts.atproto.post_bluesky import (
    POST_HASHTAGS,
    Milestone,
    first_sentence,
    plain_text,
)

#: LinkedIn's commentary limit, in characters.
MAX_POST_CHARS = 3000

#: The most of the matter's description that goes into the post. It carries
#: the description's first sentence, which says what the deal is; this cap is
#: for the rare one that runs on.
SUMMARY_CHARS = 500

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
    """The post's commentary, without the link, in little format."""
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
