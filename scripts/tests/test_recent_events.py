"""Tests for the recent-events feed (static_data.outputs.recent_events)."""

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from scripts.generate.static_data.outputs.recent_events import TYPES, classify, generate


@pytest.mark.parametrize(
    "event, expected",
    [
        ({"title": "Merger notified to ACCC", "phase": "Phase 1"}, "notified"),
        ({"title": "Phase 1 consultation", "is_questionnaire_event": True}, "questionnaire"),
        ({"title": "Coles - supermarket site in Kirkwood (QLD) - Questionnaire"}, "questionnaire"),
        ({"title": "Acrow - Ausgroup Industrial Services - Phase 1 Quesionnaire"}, "questionnaire"),
        (
            {"title": "Phase 1 - initial assessment determination: Approved",
             "phase": "Phase 1", "is_determination_event": True},
            "phase_1_determination",
        ),
        (
            {"title": "Phase 2 - detailed assessment determination: Not approved",
             "phase": "Phase 2", "is_determination_event": True},
            "phase_2_determination",
        ),
        (
            {"title": "Notification waiver determination published",
             "phase": "Waiver", "is_determination_event": True},
            "waiver_determination",
        ),
        (
            {"title": "Consideration of Notification ceased – Phase 2 fee not paid by due date",
             "phase": "Phase 2", "is_determination_event": True},
            "ceased",
        ),
        ({"title": "Timeline extended by 12 business days – following request by parties"},
         "timeline_extension"),
        ({"title": "ACCC decided to extend the Phase 1 determination period following receipt"},
         "timeline_extension"),
        ({"title": "Remedy offer - Zoetis - Neogen Genomics Business - 2 November 2026"}, "remedy_offer"),
        ({"title": "Draft s87B Undertaking - 28 July 2026 - IAG - RACI"}, "remedy_offer"),
        ({"title": "Zoetis-Neogen - Questionnaire - Remedy Offer - 4 November 2026"},
         "remedy_questionnaire"),
        ({"title": "ACCC accepted s87B undertaking"}, "undertaking_accepted"),
        ({"title": "Summary of Notice of Competition Concerns"}, "competition_concerns"),
        ({"title": "Zoetis - Neogen Genomics Business - Phase 2 Notice"}, "phase_2_referral"),
        ({"title": "Decision to Proceed to a Phase 2 review"}, "phase_2_referral"),
        ({"title": "ACCC decided notification is subject to Phase 2 review"}, "phase_2_referral"),
        ({"title": "IAG-RACI - Phase 2 Statement of Reasons"}, "reasons"),
        ({"title": "Phase 2 determination - Summary of reasons"}, "reasons"),
        ({"title": "Summary of IAG/RACI's claimed public benefits"}, "public_benefit"),
        (
            {"title": "In accordance with s 51ABZ of the CCA the ACCC decided that the "
                      "notification ... is materially incomplete."},
            "materially_incomplete",
        ),
        (
            {"title": "USCO provided additional information in response to the ACCC's decision "
                      "under s 51ABY of the CCA. The effective notification date is 5 November 2026."},
            "notification_completed",
        ),
        ({"title": "Directions", "is_appeal": True}, "tribunal"),
        ({"title": "Orders", "is_appeal": True, "review_forum": "federal_court"}, "federal_court"),
        ({"title": "6-month extension granted for Acquisition to be put into effect"}, "other"),
    ],
)
def test_classify(event, expected):
    assert classify(event) == expected
    assert expected in TYPES


NOW = datetime(2026, 11, 9, 10, 0, tzinfo=ZoneInfo("Australia/Sydney"))


def _merger(merger_id, events, **extra):
    return {"merger_id": merger_id, "merger_name": f"Matter {merger_id}", "events": events, **extra}


def test_generate_window_and_order():
    mergers = [
        _merger("MN-1", [
            {"title": "Merger notified to ACCC", "date": "2026-11-02T12:00:00Z"},
            {"title": "Phase 1 consultation", "date": "2026-11-03T12:00:00Z",
             "url_gh": "/mergers/MN-1/q.pdf"},
            {"title": "Too old", "date": "2026-10-20T12:00:00Z"},
            {"title": "Future", "date": "2026-11-12T12:00:00Z"},
        ]),
        _merger("MN-2", [
            {"title": "Timeline extended by 5 business days", "date": "2026-11-09T12:00:00Z"},
        ]),
    ]
    result = generate(mergers, days_back=14, now=NOW)
    assert [e["type"] for e in result["events"]] == ["timeline_extension", "questionnaire", "notified"]
    assert result["count"] == 3
    assert result["events"][1]["url_gh"] == "/mergers/MN-1/q.pdf"
    assert "url_gh" not in result["events"][2]


def test_generate_skips_suspended():
    mergers = [
        _merger("MN-1", [{"title": "Merger notified to ACCC", "date": "2026-11-02T12:00:00Z"}],
                status="Assessment suspended"),
    ]
    assert generate(mergers, now=NOW)["events"] == []
