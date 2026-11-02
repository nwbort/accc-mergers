"""Tests for how a milestone reads as a LinkedIn post.

Which milestones get posted is ``post_bluesky.milestones()`` and is tested
there. What is LinkedIn's own: escaping into the little text format (Make's
LinkedIn module passes text through unchanged, and an unescaped ``(``
truncates a post), the hashtag templates, and the description's opening.
"""

from scripts.atproto.post_bluesky import milestones
from scripts.linkedin import text
from scripts.linkedin.text import escape, post_text, preview, unescape


def matter(merger_id="MN-01016", **overrides):
    record = {
        "merger_id": merger_id,
        "merger_name": "Asahi - Warehouse site (Vic)",
        "status": "Under assessment",
        "stage": "Phase 1 - initial assessment",
        "is_waiver": False,
        "effective_notification_datetime": "2026-08-15T12:00:00Z",
        "merger_description": "Asahi (**Asahi**) will enter into a lease #1.",
        "events": [],
    }
    record.update(overrides)
    return record


def test_reserved_characters_are_escaped_and_round_trip():
    raw = r"A (B) #c *d* _e_ [f] {g} <h> @i ~j | \k"
    escaped = escape(raw)
    assert "(" not in escaped.replace("\\(", "")
    assert unescape(escaped) == raw


def test_post_text_escapes_register_text_but_not_the_hashtag_template():
    (milestone,) = milestones(matter())
    little = post_text(milestone)
    assert little.startswith(r"Notified to the ACCC: Asahi - Warehouse site \(Vic\)")
    assert r"lease \#1." in little
    assert "**" not in little  # Markdown flattened before escaping
    assert little.endswith(r"{hashtag|\#|accc}")


def test_preview_reads_as_linkedin_shows_it():
    (milestone,) = milestones(matter())
    shown = preview(post_text(milestone))
    assert shown.splitlines()[0] == "Notified to the ACCC: Asahi - Warehouse site (Vic)"
    assert shown.endswith("#accc")


def test_a_long_description_is_trimmed():
    (milestone,) = milestones(matter(merger_description="word " * 400))
    little = post_text(milestone)
    assert len(little) < text.MAX_POST_CHARS
    assert "…" in little


def test_the_post_carries_the_first_sentence():
    deal = (
        "Asahi Holdings (Australia) Pty Ltd proposes to enter into an agreement "
        "for lease with GPT for a warehouse site on Tilburn Road, Deer Park."
    )
    (milestone,) = milestones(
        matter(merger_description=f"{deal} Asahi makes beer. GPT owns property.")
    )
    assert text.summary_text(milestone) == deal
    assert "makes beer" not in preview(post_text(milestone))
