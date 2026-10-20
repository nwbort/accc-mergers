"""Tests for the generic link-preview cards.

The card a page shows is chosen here and rendered by three JavaScript copies
that only read the name, so what matters is that the name is right for the
matter's latest milestone, and that every name it can give is a file that is
actually deployed.
"""

import json

import pytest

from scripts.atproto import post_bluesky
from scripts.atproto.card_image import render_status_card
from scripts.generate import og_cards
from scripts.generate.og_cards import CARDS, OG_DIR, card_for, current_card
from scripts.generate.static_data.outputs import individual


def matter(**overrides):
    record = {
        "merger_id": "MN-01016",
        "merger_name": "Asahi - Warehouse site",
        "status": "Under assessment",
        "stage": "Phase 1 - initial assessment",
        "is_waiver": False,
        "effective_notification_datetime": "2026-08-15T12:00:00Z",
    }
    record.update(overrides)
    return record


def decided(**overrides):
    return matter(**{
        "status": "Assessment completed",
        "accc_determination": "Approved",
        "phase_1_determination": "Approved",
        "phase_1_determination_date": "2026-09-10T12:00:00Z",
        **overrides,
    })


def test_every_card_is_committed():
    missing = [name for name in og_cards._FILES.values() if not (OG_DIR / name).is_file()]
    assert not missing, f"run `python -m scripts.generate.og_cards` to draw {missing}"


def test_no_stray_cards_are_deployed():
    assert {p.name for p in OG_DIR.glob("*.png")} == set(og_cards._FILES.values())


def test_every_outcome_headline_has_a_card():
    headlines = {headline for _, headline in CARDS}
    for headline in (
        *post_bluesky._OUTCOME_HEADLINES.values(),
        *post_bluesky._PUBLIC_BENEFIT_HEADLINES.values(),
    ):
        assert headline in headlines
    # The conditional variants are built by string, not looked up.
    assert "Cleared with conditions by the ACCC" in headlines
    assert "Cleared with conditions by the ACCC on public benefit grounds" in headlines


def test_an_open_matter_shows_the_notified_card():
    assert current_card(matter()) == "notified-to-the-accc.png"


def test_a_decided_matter_shows_its_outcome():
    assert current_card(decided()) == "cleared-by-the-accc.png"
    assert current_card(decided(has_conditions=True)) == "cleared-with-conditions-by-the-accc.png"
    assert current_card(
        decided(is_waiver=True, accc_determination="Not approved", phase_1_determination="Not approved")
    ) == "notification-waiver-refused.png"


def test_an_undated_determination_still_counts_as_latest():
    record = matter(status="Assessment completed", accc_determination="Approved")
    assert current_card(record) == "cleared-by-the-accc.png"


def test_a_same_day_cessation_beats_the_notification():
    record = matter(status="Assessment ceased")
    assert current_card(record) == "assessment-ceased.png"


def test_a_running_tribunal_review_shows_until_it_concludes():
    appeal = {"filed_date": "2026-10-01", "tribunal_number": "ACT 3 of 2026"}
    running = decided(appeal=appeal, under_appeal=True)
    assert current_card(running) == "under-review-in-the-competition-tribunal.png"
    concluded = decided(appeal=appeal, under_appeal=False)
    assert current_card(concluded) == "cleared-by-the-accc.png"


def test_an_unknown_outcome_falls_back_to_the_shared_image():
    record = decided(accc_determination="Something new", phase_1_determination="Something new")
    assert current_card(record) is None


def test_card_for_names_by_headline():
    (milestone,) = post_bluesky.milestones(matter())
    assert card_for(milestone) == "notified-to-the-accc.png"


def test_detail_files_carry_the_card(tmp_path):
    individual.generate([decided()], tmp_path)
    record = json.loads((tmp_path / "mergers" / "MN-01016.json").read_text())
    assert record["og_card"] == "cleared-by-the-accc.png"


@pytest.mark.parametrize("kind,headline", CARDS[:3])
def test_status_cards_render_as_open_graph_pngs(kind, headline):
    png = render_status_card(kind=kind, headline=headline)
    if png is None:
        pytest.skip("no usable font on this machine")
    assert png.startswith(b"\x89PNG")
    # Width and height from the IHDR chunk: 1200x630, the size the tags declare.
    assert int.from_bytes(png[16:20], "big") == 1200
    assert int.from_bytes(png[20:24], "big") == 630
