"""Tests for the merger -> ``fyi.mergers.matter`` mapping."""

import pytest

from scripts.atproto.records import (
    event_kind,
    matter_record,
    matter_rkey,
    record_digest,
)

NOW = "2026-09-22T00:00:00Z"


def build(**overrides) -> dict:
    merger = {
        "merger_id": "MN-01016",
        "merger_name": "Asahi - Warehouse site",
        "url": "https://www.accc.gov.au/public-registers/example",
        "status": "Assessment completed",
        "stage": "Phase 1 - initial assessment",
        "is_waiver": False,
        "effective_notification_datetime": "2025-08-15T12:00:00Z",
        "original_notification_datetime": "2025-08-15T12:00:00Z",
        "acquirers": [
            {"name": "ASAHI HOLDINGS", "identifier_type": "ABN", "identifier": "48 135 315 767"}
        ],
        "targets": [{"name": "GPT PLATFORM"}],
        "other_parties": [],
        "anzsic_codes": [{"code": "121", "name": "Beverage Manufacturing"}],
        "events": [],
    }
    merger.update(overrides)
    return merger


# -- keys -------------------------------------------------------------------


def test_matter_rkey_passes_an_accc_matter_id_through():
    assert matter_rkey("MN-01016") == "MN-01016"
    assert matter_rkey("WA-95041") == "WA-95041"


@pytest.mark.parametrize("bad", ["", ".", "..", "MN 01016", "MN/01016", "MN#1"])
def test_matter_rkey_refuses_anything_a_pds_would_reject(bad):
    with pytest.raises(ValueError):
        matter_rkey(bad)


# -- shape ------------------------------------------------------------------


def test_record_carries_the_required_fields():
    record = matter_record(build(), indexed_at=NOW)
    for field in ("$type", "matterId", "title", "matterType", "status", "url", "indexedAt"):
        assert field in record
    assert record["$type"] == "fyi.mergers.matter"
    assert record["url"] == "https://mergers.fyi/mergers/MN-01016"
    assert record["registerUrl"].startswith("https://www.accc.gov.au/")


def test_dates_are_published_as_dates_not_invented_timestamps():
    """The register publishes dates; the pipeline's midday UTC is storage."""
    record = matter_record(build(), indexed_at=NOW)
    assert record["notifiedOn"] == "2025-08-15"


def test_original_notification_is_omitted_when_the_clock_was_never_reset():
    record = matter_record(build(), indexed_at=NOW)
    assert "originallyNotifiedOn" not in record


def test_original_notification_is_kept_when_the_clock_was_reset():
    record = matter_record(
        build(original_notification_datetime="2025-07-01T12:00:00Z"), indexed_at=NOW
    )
    assert record["originallyNotifiedOn"] == "2025-07-01"


def test_empty_collections_are_left_out_entirely():
    record = matter_record(build(), indexed_at=NOW)
    assert "otherParties" not in record
    assert "determinations" not in record
    assert "appeals" not in record


def test_waivers_are_typed_as_waivers():
    assert matter_record(build(is_waiver=True), indexed_at=NOW)["matterType"] == "waiver"


def test_party_identifiers_survive_verbatim():
    record = matter_record(build(), indexed_at=NOW)
    assert record["acquirers"][0] == {
        "name": "ASAHI HOLDINGS",
        "identifierType": "ABN",
        "identifier": "48 135 315 767",
    }


def test_summary_is_truncated_rather_than_dropped():
    record = matter_record(build(merger_description="x" * 9000), indexed_at=NOW)
    assert len(record["summary"]) == 6000
    assert record["summary"].endswith("…")


# -- determinations ---------------------------------------------------------


def test_a_phase_2_matter_keeps_both_of_its_determinations():
    record = matter_record(
        build(
            stage="Phase 2 - detailed assessment",
            phase_1_determination="Referred to phase 2",
            phase_1_determination_date="2026-01-29T12:00:00Z",
            phase_2_determination="Not approved",
            phase_2_determination_date="2026-07-01T12:00:00Z",
            accc_determination="Not approved",
        ),
        indexed_at=NOW,
    )
    assert [d["outcome"] for d in record["determinations"]] == [
        "Referred to phase 2",
        "Not approved",
    ]
    assert record["determinations"][0]["phase"] == "Phase 1 - initial assessment"


def test_a_waiver_falls_back_to_the_headline_determination():
    record = matter_record(
        build(
            is_waiver=True,
            stage="Waiver application",
            accc_determination="Approved",
            determination_publication_date="2026-01-20T12:00:00Z",
        ),
        indexed_at=NOW,
    )
    assert record["determinations"] == [
        {"outcome": "Approved", "phase": "Waiver application", "decidedOn": "2026-01-20"}
    ]


def test_conditions_attach_to_the_clearance_not_the_referral():
    record = matter_record(
        build(
            phase_1_determination="Referred to phase 2",
            phase_1_determination_date="2026-01-29T12:00:00Z",
            phase_2_determination="Approved",
            phase_2_determination_date="2026-06-02T12:00:00Z",
            has_conditions=True,
        ),
        indexed_at=NOW,
    )
    assert "withConditions" not in record["determinations"][0]
    assert record["determinations"][1]["withConditions"] is True


def test_the_determination_document_comes_from_the_matching_event():
    record = matter_record(
        build(
            phase_1_determination="Approved",
            phase_1_determination_date="2025-09-05T12:00:00Z",
            events=[
                {
                    "date": "2025-09-05T12:00:00Z",
                    "title": "Phase 1 Determination",
                    "phase": "Phase 1",
                    "is_determination_event": True,
                    "url": "https://www.accc.gov.au/determination.pdf",
                }
            ],
        ),
        indexed_at=NOW,
    )
    assert record["determinations"][0]["documentUrl"] == (
        "https://www.accc.gov.au/determination.pdf"
    )


# -- appeals ----------------------------------------------------------------


def test_both_review_forums_are_published_side_by_side():
    record = matter_record(
        build(
            appeal={
                "tribunal_number": "ACT 1 of 2026",
                "tribunal_url": "https://www.competitiontribunal.gov.au/act-1-of-2026",
                "appellant": "Coles",
                "filed_date": "2026-07-15",
                "status": "current",
                "outcome": None,
            },
            judicial_review={
                "applicant": "Coles",
                "filed_date": "2026-07-17",
                "case_number": "NSD1310/2026",
                "case_url": "https://www.comcourts.gov.au/nsd1310",
            },
        ),
        indexed_at=NOW,
    )
    assert [a["forum"] for a in record["appeals"]] == [
        "australian-competition-tribunal",
        "federal-court-of-australia",
    ]
    assert "outcome" not in record["appeals"][0]


# -- events -----------------------------------------------------------------


@pytest.mark.parametrize(
    "event,expected",
    [
        ({"is_appeal": True, "title": "Directions"}, "appeal"),
        ({"is_determination_event": True, "title": "Whatever"}, "determination"),
        # The flag wins over the title: the ACCC's new consultation sections
        # don't always say "questionnaire" (see CLAUDE.md).
        ({"is_questionnaire_event": True, "title": "OEConnection - Phase 1 consultation"}, "questionnaire"),
        ({"title": "Merger notified to ACCC"}, "notification"),
        ({"title": "Summary of Notice of Competition Concerns"}, "competition-concerns-notice"),
        ({"title": "ACCC decided notification is subject to phase 2 review"}, "phase-2-referral"),
        ({"title": "Timeline extended by 10 business days"}, "timeline-extension"),
        ({"title": "Remedy offer - 29 July 2026"}, "remedy-offer"),
        ({"title": "ACCC accepted s87B undertaking"}, "undertaking"),
        ({"title": "Something else entirely"}, "other"),
    ],
)
def test_event_kinds(event, expected):
    assert event_kind(event) == expected


def test_events_are_sorted_oldest_first_and_undated_ones_dropped():
    record = matter_record(
        build(
            events=[
                {"date": "2025-09-05T12:00:00Z", "title": "Later"},
                {"title": "No date at all"},
                {"date": "2025-08-15T12:00:00Z", "title": "Earlier"},
            ]
        ),
        indexed_at=NOW,
    )
    assert [e["title"] for e in record["events"]] == ["Earlier", "Later"]


def test_display_title_wins_over_the_raw_register_title():
    record = matter_record(
        build(
            events=[
                {
                    "date": "2025-09-05T12:00:00Z",
                    "title": "Asahi - ... - Phase 1 Determination",
                    "display_title": "Phase 1 determination: Approved",
                }
            ]
        ),
        indexed_at=NOW,
    )
    assert record["events"][0]["title"] == "Phase 1 determination: Approved"


# -- digest -----------------------------------------------------------------


def test_digest_ignores_when_the_record_was_written():
    """Otherwise every pipeline run would rewrite every record."""
    early = matter_record(build(), indexed_at="2026-01-01T00:00:00Z")
    late = matter_record(build(), indexed_at="2026-09-22T00:00:00Z")
    assert record_digest(early) == record_digest(late)


def test_digest_moves_when_the_matter_does():
    before = matter_record(build(), indexed_at=NOW)
    after = matter_record(build(status="Assessment ceased"), indexed_at=NOW)
    assert record_digest(before) != record_digest(after)
