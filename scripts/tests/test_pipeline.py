"""Tests for core pipeline logic: determination parsing, questionnaire parsing,
static data generation, cutoff logic, and extraction helpers."""

import sys
import json
import unittest.mock
from datetime import date, datetime

# Mock heavy transitive imports before importing modules that need them
sys.modules['pdfplumber'] = unittest.mock.MagicMock()
sys.modules['markdownify'] = unittest.mock.MagicMock()
sys.modules['requests'] = unittest.mock.MagicMock()

from scripts.parse.parse_determination import (
    extract_commission_division,
    parse_text_as_table,
    _parse_section_blocks,
)
from scripts.parse.parse_questionnaire import extract_deadline, extract_questions, extract_questions_from_text, _extract_subpoints, _extract_bullets, _has_questionnaire_header
from scripts.cutoff import is_waiver_merger, get_cutoff_date, should_skip_merger
from scripts.extract_mergers import (
    is_safe_url,
    get_serve_filename,
    _extract_consultations,
    _extract_consultation_date,
    _scrape_events,
    detect_inferred_phase_2,
    _infer_determination_date_from_events,
    _extract_anzsic_codes,
    _extract_dates_and_status,
    _merge_events,
    _add_synthetic_events,
    find_pending_phase2_notice_events,
    extract_phase2_notice_data,
    _calculate_missing_end_of_determination_period,
    _is_determination_attachment,
)
from scripts.generate.static_data.business_days import calculate_business_days
from scripts import extract_mergers

from bs4 import BeautifulSoup


# ---------------------------------------------------------------------------
# _merge_events: attachment preservation when ACCC drops a document link
# ---------------------------------------------------------------------------

class TestMergeEventsAttachmentDropped:
    """When the ACCC removes an event's document link but keeps the event as a
    plain (URL-less) timeline row, the previously captured attachment must be
    preserved on a single event rather than spawning a recurring duplicate.

    This is the MN-30003 "subject to Phase 2 review" case: a dedup PR that just
    deletes the URL-less copy is undone by the next scrape because the row keeps
    reappearing. Re-binding it to the existing event fixes the loop at source.
    """

    TITLE = "ACCC decided notification is subject to Phase 2 review"

    def _existing(self):
        return {
            "events": [
                {
                    "date": "2026-04-01T12:00:00Z",
                    "title": self.TITLE,
                    "display_title": self.TITLE,
                    "url": "https://accc.gov.au/.../phase-2-notice.pdf",
                    "url_gh": "/mergers/MN-30003/phase-2-notice.pdf",
                    "status": "live",
                },
            ],
        }

    def test_urlless_row_rebinds_to_attachment_event(self):
        # The page now shows the event only as a plain timeline row (no link).
        scraped = [{"date": "2026-04-01T12:00:00Z", "title": self.TITLE}]
        merged = _merge_events(scraped, self._existing(), "MN-30003", set())

        assert len(merged) == 1, "no duplicate should be created"
        ev = merged[0]
        assert ev["url_gh"] == "/mergers/MN-30003/phase-2-notice.pdf"
        assert ev["url"] == "https://accc.gov.au/.../phase-2-notice.pdf"
        assert ev["status"] == "live", "event is still on the page, not removed"

    def test_one_day_date_shift_still_rebinds(self):
        scraped = [{"date": "2026-04-02T12:00:00Z", "title": self.TITLE}]
        merged = _merge_events(scraped, self._existing(), "MN-30003", set())
        assert len(merged) == 1
        assert merged[0]["url_gh"] == "/mergers/MN-30003/phase-2-notice.pdf"
        assert merged[0]["status"] == "live"

    def test_event_truly_gone_is_marked_removed(self):
        # No matching timeline row: the event really disappeared from the page.
        scraped = [{"date": "2026-05-01T12:00:00Z", "title": "Some other event"}]
        merged = _merge_events(scraped, self._existing(), "MN-30003", set())
        statuses = {e["title"]: e.get("status") for e in merged}
        assert statuses[self.TITLE] == "removed"

    def test_different_title_row_not_consumed(self):
        # A genuinely different URL-less event must remain a separate event and
        # the attachment event is marked removed (its link is gone, no rebind).
        scraped = [{"date": "2026-04-01T12:00:00Z", "title": "Merger notified to ACCC"}]
        merged = _merge_events(scraped, self._existing(), "MN-30003", set())
        titles = sorted(e["title"] for e in merged)
        assert titles == sorted([self.TITLE, "Merger notified to ACCC"])


# ---------------------------------------------------------------------------
# _merge_events: URL-less timeline rows are matched by title regardless of
# which dash character the ACCC happens to render
# ---------------------------------------------------------------------------

class TestMergeEventsUrllessTitleDashVariant:
    """Plain (URL-less) timeline rows, e.g. "Timeline extended by N business
    days ...", are matched across scrapes purely by exact title. The ACCC
    site inconsistently renders the same wording with an en dash '–' in one
    scrape and a plain hyphen '-' in a later one. Without dash-insensitive
    matching, that difference is invisible to a human reader but breaks the
    exact-string match, so the scraper leaves the old title's event alone
    and appends a fresh copy in the new dash style as a separate event —
    and keeps doing so on every subsequent scrape (MN-90008).
    """

    TITLE_EN_DASH = "Timeline extended by 10 business days – following request by parties"
    TITLE_HYPHEN = "Timeline extended by 10 business days - following request by parties"

    def _existing(self, title):
        return {
            "events": [
                {
                    "date": "2026-06-19T12:00:00Z",
                    "title": title,
                    "display_title": title,
                },
            ],
        }

    def test_hyphen_scrape_matches_existing_en_dash_event(self):
        scraped = [{"date": "2026-06-19T12:00:00Z", "title": self.TITLE_HYPHEN}]
        merged = _merge_events(scraped, self._existing(self.TITLE_EN_DASH), "MN-90008", set())
        assert len(merged) == 1, "dash-variant title must not create a duplicate event"

    def test_en_dash_scrape_matches_existing_hyphen_event(self):
        scraped = [{"date": "2026-06-19T12:00:00Z", "title": self.TITLE_EN_DASH}]
        merged = _merge_events(scraped, self._existing(self.TITLE_HYPHEN), "MN-90008", set())
        assert len(merged) == 1, "dash-variant title must not create a duplicate event"

    def test_identical_title_still_matches(self):
        scraped = [{"date": "2026-06-19T12:00:00Z", "title": self.TITLE_HYPHEN}]
        merged = _merge_events(scraped, self._existing(self.TITLE_HYPHEN), "MN-90008", set())
        assert len(merged) == 1

    def test_genuinely_different_title_is_not_matched(self):
        scraped = [{"date": "2026-06-19T12:00:00Z", "title": "A completely different event"}]
        merged = _merge_events(scraped, self._existing(self.TITLE_EN_DASH), "MN-90008", set())
        assert len(merged) == 2


# ---------------------------------------------------------------------------
# _merge_events: re-uploaded documents must not duplicate their event
# ---------------------------------------------------------------------------

class TestMergeEventsDocumentReuploaded:
    """When the ACCC re-uploads a document under a new URL (the CMS appends a
    fresh _N filename suffix), the event must be re-bound to the new URL rather
    than being marked 'removed' alongside a duplicate 'live' event.

    This is the MN-01068 case: every Phase 2 document was re-published under a
    new suffix (e.g. "...March 2026_9.pdf" -> "...March 2026_5.pdf"),
    duplicating four timeline events.
    """

    TITLE = "Summary of Notice of Competition Concerns"
    OLD_URL = "https://accc.gov.au/docs/NOCC%20-%20March%202026_9.pdf"
    NEW_URL = "https://accc.gov.au/docs/NOCC%20-%20March%202026_5.pdf"

    def _existing(self, **extra):
        return {
            "events": [
                {
                    "date": "2026-03-06T12:00:00Z",
                    "title": self.TITLE,
                    "display_title": self.TITLE,
                    "url": self.OLD_URL,
                    "url_gh": "/mergers/MN-01068/NOCC - March 2026_9.pdf",
                    "status": "live",
                    **extra,
                },
            ],
        }

    def _scraped(self, title=None):
        return [
            {
                "date": "2026-03-06T12:00:00Z",
                "title": title or self.TITLE,
                "display_title": title or self.TITLE,
                "url": self.NEW_URL,
                "url_gh": "/mergers/MN-01068/NOCC - March 2026_5.pdf",
                "status": "live",
            },
        ]

    def test_new_url_rebinds_to_existing_event(self):
        merged = _merge_events(self._scraped(), self._existing(), "MN-01068", set())
        assert len(merged) == 1, "no duplicate should be created"
        ev = merged[0]
        assert ev["url"] == self.NEW_URL
        assert ev["status"] == "live"

    def test_rebind_is_case_insensitive(self):
        # ACCC re-cased "Summary of Reasons" -> "Summary of reasons" when
        # re-uploading MN-01068's determination documents.
        merged = _merge_events(
            self._scraped(title=self.TITLE.lower()), self._existing(), "MN-01068", set()
        )
        assert len(merged) == 1
        assert merged[0]["url"] == self.NEW_URL

    def test_rebind_preserves_display_title_and_determination_flag(self):
        existing = self._existing(is_determination_event=True)
        existing["events"][0]["display_title"] = "Custom display title"
        merged = _merge_events(self._scraped(), existing, "MN-01068", set())
        assert len(merged) == 1
        assert merged[0]["display_title"] == "Custom display title"
        assert merged[0]["is_determination_event"] is True

    def test_url_claimed_by_another_existing_event_is_not_rebind_target(self):
        # A scraped URL that exactly matches some other existing event must not
        # be treated as a re-upload of a different event.
        existing = self._existing()
        existing["events"].append(
            {
                "date": "2026-03-06T12:00:00Z",
                "title": "Some other document",
                "display_title": "Some other document",
                "url": self.NEW_URL,
                "status": "live",
            }
        )
        scraped = self._scraped(title="Some other document")
        merged = _merge_events(scraped, existing, "MN-01068", set())
        by_title = {e["title"]: e for e in merged}
        assert by_title["Some other document"]["url"] == self.NEW_URL
        assert by_title[self.TITLE]["status"] == "removed"

    def test_stale_removed_duplicate_is_dropped(self):
        # Data poisoned by scrapes made before the rebind fix contains both the
        # 'removed' old-URL event and a 'live' new-URL duplicate. The next merge
        # must drop the stale copy and keep its flags on the live event.
        existing = {
            "events": [
                {
                    "date": "2026-03-06T12:00:00Z",
                    "title": self.TITLE,
                    "display_title": "Custom display title",
                    "url": self.OLD_URL,
                    "status": "removed",
                    "is_determination_event": True,
                },
                self._scraped()[0],
            ],
        }
        merged = _merge_events(self._scraped(), existing, "MN-01068", set())
        assert len(merged) == 1
        ev = merged[0]
        assert ev["url"] == self.NEW_URL
        assert ev["status"] == "live"
        assert ev["display_title"] == "Custom display title"
        assert ev["is_determination_event"] is True

    def test_genuinely_removed_event_stays_removed(self):
        # No same-title live event: the document really is gone from the page.
        existing = self._existing()
        merged = _merge_events(
            [{"date": "2026-05-01T12:00:00Z", "title": "Some other event"}],
            existing,
            "MN-01068",
            set(),
        )
        statuses = {e["title"]: e.get("status") for e in merged}
        assert statuses[self.TITLE] == "removed"


# ---------------------------------------------------------------------------
# _merge_events: freezing (whole-list and selective)
# ---------------------------------------------------------------------------

class TestMergeEventsFreeze:
    """freeze_events can protect either every event (True) or just the named
    events (a set of titles), while the rest still update from the scrape."""

    FROZEN_TITLE = "Questionnaire - IAG - RACI"
    OTHER_TITLE = "Merger notified to ACCC"

    def _existing(self):
        return {
            "events": [
                {
                    "date": "2026-03-04T12:00:00Z",  # manually set, missing on page
                    "title": self.FROZEN_TITLE,
                    "display_title": self.FROZEN_TITLE,
                    "url": "https://accc.gov.au/.../questionnaire.pdf",
                },
                {
                    "date": "2026-03-03T12:00:00Z",
                    "title": self.OTHER_TITLE,
                    "display_title": self.OTHER_TITLE,
                },
            ],
        }

    def test_freeze_all_preserves_every_event(self):
        # Scrape has a wrong (empty) date for the frozen event and drops the other.
        scraped = [{"date": "", "title": self.FROZEN_TITLE}]
        merged = _merge_events(scraped, self._existing(), "MN-65005", {"MN-65005": True})
        by_title = {e["title"]: e for e in merged}
        assert by_title[self.FROZEN_TITLE]["date"] == "2026-03-04T12:00:00Z"
        assert self.OTHER_TITLE in by_title  # whole list preserved

    def test_selective_freeze_preserves_only_listed_event(self):
        # The page shows the questionnaire with no date and updates the notified date.
        scraped = [
            {"date": "", "title": self.FROZEN_TITLE},
            {"date": "2026-03-05T12:00:00Z", "title": self.OTHER_TITLE},
        ]
        spec = {"MN-65005": {self.FROZEN_TITLE}}
        merged = _merge_events(scraped, self._existing(), "MN-65005", spec)
        by_title = {e["title"]: e for e in merged}
        # Frozen event keeps its manually set date, not the scraped blank.
        assert by_title[self.FROZEN_TITLE]["date"] == "2026-03-04T12:00:00Z"
        # Non-frozen event still picks up the scraped update.
        assert by_title[self.OTHER_TITLE]["date"] == "2026-03-05T12:00:00Z"

    def test_selective_freeze_ignores_reuploaded_url(self):
        # The ACCC re-uploads the frozen doc under a new URL: with the event
        # frozen we must keep the existing copy and not append a duplicate.
        scraped = [{"date": "", "title": self.FROZEN_TITLE,
                    "url": "https://accc.gov.au/.../questionnaire_2.pdf"}]
        spec = {"MN-65005": {self.FROZEN_TITLE}}
        merged = _merge_events(scraped, self._existing(), "MN-65005", spec)
        frozen = [e for e in merged if e["title"] == self.FROZEN_TITLE]
        assert len(frozen) == 1, "no duplicate for the re-uploaded frozen doc"
        assert frozen[0]["url"] == "https://accc.gov.au/.../questionnaire.pdf"

    def test_selective_freeze_leaves_unlisted_titles_alone(self):
        # A title not in the freeze set behaves as if nothing were frozen.
        scraped = [
            {"date": "2026-03-04T12:00:00Z", "title": self.FROZEN_TITLE},
            {"date": "2026-03-06T12:00:00Z", "title": "Brand new event"},
        ]
        spec = {"MN-65005": {self.FROZEN_TITLE}}
        merged = _merge_events(scraped, self._existing(), "MN-65005", spec)
        titles = {e["title"] for e in merged}
        assert "Brand new event" in titles

    def test_unfrozen_merger_is_unaffected(self):
        scraped = [{"date": "2026-03-04T12:00:00Z", "title": self.FROZEN_TITLE}]
        spec = {"MN-99999": {self.FROZEN_TITLE}}  # different merger frozen
        merged = _merge_events(scraped, self._existing(), "MN-65005", spec)
        by_title = {e["title"]: e for e in merged}
        # Not frozen for this merger: normal merge keeps the existing url.
        assert by_title[self.FROZEN_TITLE]["url"].endswith("questionnaire.pdf")


class TestParseFreezeSpec:
    """_parse_freeze_spec maps a frozen_events_mergers.json entry to a spec."""

    def test_true_and_shorthands_freeze_all(self):
        from scripts.extract_mergers import _parse_freeze_spec
        assert _parse_freeze_spec({"freeze_events": True}) is True
        assert _parse_freeze_spec({}) is True
        assert _parse_freeze_spec(None) is True

    def test_list_freezes_named_titles(self):
        from scripts.extract_mergers import _parse_freeze_spec
        assert _parse_freeze_spec({"freeze_events": ["A", "B"]}) == {"A", "B"}
        # An empty/garbage list is not a freeze at all.
        assert _parse_freeze_spec({"freeze_events": []}) is None

    def test_overrides_only_is_not_frozen(self):
        from scripts.extract_mergers import _parse_freeze_spec
        assert _parse_freeze_spec({"_comment": "note"}) is None
        assert _parse_freeze_spec({"status": "Approved"}) is None

    def test_loader_returns_specs_and_overrides(self, tmp_path):
        from scripts.extract_mergers import _load_frozen_events_mergers
        data = {
            "_comment": "top",
            "MN-1": {"freeze_events": True},
            "MN-2": {"freeze_events": ["Only this one"]},
            "MN-3": {"status": "Approved"},
        }
        p = tmp_path / "frozen.json"
        p.write_text(json.dumps(data))
        with unittest.mock.patch.object(
            extract_mergers, "FROZEN_EVENTS_MERGERS_PATH", str(p)
        ):
            specs, overrides = _load_frozen_events_mergers()
        assert specs == {"MN-1": True, "MN-2": {"Only this one"}}
        assert overrides == {"MN-3": {"status": "Approved"}}


class TestAutoFixMissingEventDates:
    """auto_fix_missing_event_dates sets dates on catchable events with no date,
    and selectively freezes only those events (not the whole list) so later
    events still update, while still writing the GitHub-issue payload."""

    QUESTIONNAIRE = "Acme - Target - Questionnaire (13 Jul 2026)"
    OTHER = "Merger notified to ACCC"

    def _merger(self):
        return {
            "merger_id": "MN-77777",
            "merger_name": "Acme / Target",
            "url": "https://accc.gov.au/.../acme-target",
            "events": [
                {"date": "", "title": self.QUESTIONNAIRE},
                {"date": "2026-06-01T12:00:00Z", "title": self.OTHER},
            ],
        }

    def _run(self, tmp_path, mergers):
        frozen_path = tmp_path / "frozen_events_mergers.json"
        missing_path = tmp_path / "missing_event_dates.json"
        with unittest.mock.patch.object(
            extract_mergers, "FROZEN_EVENTS_MERGERS_PATH", str(frozen_path)
        ), unittest.mock.patch.object(
            extract_mergers, "MISSING_EVENT_DATES_PATH", str(missing_path)
        ):
            newly_frozen = extract_mergers.auto_fix_missing_event_dates(mergers, {})
        frozen = json.loads(frozen_path.read_text()) if frozen_path.exists() else {}
        missing = json.loads(missing_path.read_text()) if missing_path.exists() else {}
        return newly_frozen, frozen, missing

    def test_freezes_only_the_fixed_event_titles(self, tmp_path):
        merger = self._merger()
        newly_frozen, frozen, missing = self._run(tmp_path, [merger])

        assert newly_frozen == {"MN-77777"}
        # Selective freeze: a list of titles, not True / whole-list freeze.
        spec = frozen["MN-77777"]["freeze_events"]
        assert spec == [self.QUESTIONNAIRE]
        assert spec is not True
        # The catchable event picked up the date parsed from its title.
        assert merger["events"][0]["date"] == "2026-07-13T12:00:00Z"
        # The other event is untouched (and not frozen).
        assert self.OTHER not in spec

    def test_still_writes_github_issue_payload(self, tmp_path):
        _, _, missing = self._run(tmp_path, [self._merger()])
        assert len(missing["issues"]) == 1
        issue = missing["issues"][0]
        assert issue["merger_id"] == "MN-77777"
        assert "MN-77777" in issue["title"]
        assert issue["body"]

    def test_no_catchable_events_writes_nothing(self, tmp_path):
        merger = {
            "merger_id": "MN-88888",
            "merger_name": "No Questionnaire Co",
            "events": [{"date": "", "title": self.OTHER}],
        }
        newly_frozen, frozen, missing = self._run(tmp_path, [merger])
        assert newly_frozen == set()
        assert frozen == {}
        assert missing == {}


# ---------------------------------------------------------------------------
# _add_synthetic_events: determination outcome goes on the instrument
# ---------------------------------------------------------------------------

class TestAddSyntheticEventsDeterminationTarget:
    """The ACCC publishes the determination instrument alongside "Summary of
    reasons"/"Statement of reasons" documents on the same date. The
    determination outcome (display title + is_determination_event) must attach
    to the instrument, not whichever document happens to come first (MN-01068's
    Phase 2 determination)."""

    DET_TITLE = "Phase 2 - detailed assessment determination: Not approved"

    def _merger(self, events):
        return {
            "merger_id": "MN-01068",
            "stage": "Phase 2 - detailed assessment",
            "accc_determination": "Not approved",
            "determination_publication_date": "2026-07-01T12:00:00Z",
            "effective_notification_datetime": "2025-11-27T12:00:00Z",
            "events": events,
        }

    def _doc(self, title, url):
        return {
            "date": "2026-06-30T12:00:00Z",
            "title": title,
            "display_title": title,
            "url": url,
            "url_gh": f"/mergers/MN-01068/{url.rsplit('/', 1)[-1]}",
            "status": "live",
        }

    def test_outcome_attaches_to_instrument_not_reasons_docs(self):
        merger = self._merger([
            self._doc("Phase 2 determination - Statement of reasons", "https://accc.gov.au/sor.pdf"),
            self._doc("Phase 2 determination - Summary of reasons", "https://accc.gov.au/summary.pdf"),
            self._doc("Phase 2 determination", "https://accc.gov.au/determination.pdf"),
        ])
        _add_synthetic_events(merger)
        flagged = [e for e in merger["events"] if e.get("is_determination_event")]
        assert [e["title"] for e in flagged] == ["Phase 2 determination"]
        assert flagged[0]["display_title"] == self.DET_TITLE

    def test_stale_flag_on_reasons_doc_is_cleared(self):
        # Data written before the instrument was preferred carries the flag and
        # determination display title on a reasons document.
        summary = self._doc("Phase 2 determination - Summary of reasons", "https://accc.gov.au/summary.pdf")
        summary["is_determination_event"] = True
        summary["display_title"] = self.DET_TITLE
        merger = self._merger([
            summary,
            self._doc("Phase 2 determination", "https://accc.gov.au/determination.pdf"),
        ])
        _add_synthetic_events(merger)
        by_title = {e["title"]: e for e in merger["events"]}
        assert "is_determination_event" not in by_title["Phase 2 determination - Summary of reasons"]
        assert (by_title["Phase 2 determination - Summary of reasons"]["display_title"]
                == "Phase 2 determination - Summary of reasons")
        assert by_title["Phase 2 determination"]["is_determination_event"] is True
        assert by_title["Phase 2 determination"]["display_title"] == self.DET_TITLE

    def test_reasons_doc_used_when_it_is_the_only_candidate(self):
        merger = self._merger([
            self._doc("Phase 2 determination - Summary of reasons", "https://accc.gov.au/summary.pdf"),
        ])
        _add_synthetic_events(merger)
        flagged = [e for e in merger["events"] if e.get("is_determination_event")]
        assert [e["title"] for e in flagged] == ["Phase 2 determination - Summary of reasons"]
        assert flagged[0]["display_title"] == self.DET_TITLE


# ---------------------------------------------------------------------------
# parse_determination: extract_commission_division
# ---------------------------------------------------------------------------

class TestExtractCommissionDivision:
    def test_standard_division_sentence(self):
        text = (
            "Some preamble text.\n"
            "Determination made by a division of the Commission constituted by "
            "a direction issued pursuant to section 19 of the Act"
        )
        result = extract_commission_division(text)
        assert result is not None
        assert result.startswith("Determination made by")
        assert "section 19 of the Act" in result

    def test_commissioner_delegation(self):
        text = (
            "Blah blah.\n"
            "Determination made by Commissioner Williams pursuant to a delegation "
            "under section 25(1) of the Act"
        )
        result = extract_commission_division(text)
        assert result is not None
        assert "Commissioner Williams" in result
        assert "section 25(1)" in result

    def test_multiline_match(self):
        text = (
            "Determination made by a division\n"
            "of the Commission constituted by a direction issued\n"
            "pursuant to section 19 of the Act"
        )
        result = extract_commission_division(text)
        assert result is not None
        # Should collapse whitespace
        assert "\n" not in result

    def test_trailing_period_removed(self):
        text = "Determination made by someone pursuant to section 19 of the Act."
        result = extract_commission_division(text)
        assert result is not None
        assert not result.endswith(".")

    def test_no_match(self):
        text = "This document has no commission division information."
        assert extract_commission_division(text) is None

    def test_empty_text(self):
        assert extract_commission_division("") is None

    def test_multiple_matches_returns_last(self):
        text = (
            "Determination made by Commissioner A under section 25(1) of the Act\n"
            "Some intervening text.\n"
            "Determination made by Commissioner B under section 25(1) of the Act"
        )
        result = extract_commission_division(text)
        assert "Commissioner B" in result

    def test_phase2_notice_decision_sentence(self):
        # Phase 2 Notices attribute a "Decision", not a "Determination", and
        # cite the Act by its full name rather than "of the Act".
        text = (
            "Matters the ACCC intends to investigate in Phase 2\n"
            "Decision made by a division of the Commission constituted by a "
            "direction issued pursuant to section 19 of the Competition and "
            "Consumer Act 2010 (Cth)"
        )
        result = extract_commission_division(text)
        assert result is not None
        assert result.startswith("Decision made by")
        assert "Competition and Consumer Act 2010 (Cth)" in result


# ---------------------------------------------------------------------------
# extract_mergers: _is_determination_attachment
# ---------------------------------------------------------------------------

class TestIsDeterminationAttachment:
    def test_true_when_title_says_determination(self):
        assert _is_determination_attachment('Phase 1 - Determination', 'Foo.pdf') is True

    def test_true_when_only_filename_says_determination(self):
        # Regression case: some events are titled with just the merger name
        # (e.g. "Carlyle - BASF Coatings"), even though the attached PDF is a
        # determination — the filename ("...-Determination-...pdf") still
        # says so and previously wasn't checked.
        assert _is_determination_attachment(
            'Carlyle - BASF Coatings', 'Carlyle BASF Coatings -Determination - 18 December 2025.pdf',
        ) is True

    def test_false_for_non_determination_pdf(self):
        assert _is_determination_attachment('Merger notified to ACCC', 'Notification.pdf') is False

    def test_false_for_non_pdf_even_if_title_says_determination(self):
        assert _is_determination_attachment('Phase 1 - Determination', 'Foo.docx') is False

    def test_false_when_title_is_none(self):
        assert _is_determination_attachment(None, 'Notification.pdf') is False


# ---------------------------------------------------------------------------
# parse_determination: parse_text_as_table
# ---------------------------------------------------------------------------

class TestParseTextAsTable:
    def test_single_item(self):
        text = "Notified acquisition\nAcquisition of Company B by Company A"
        result = parse_text_as_table(text)
        assert len(result) == 1
        assert result[0]['item'] == "Notified acquisition"
        assert "Acquisition of Company B" in result[0]['details']

    def test_multiple_items(self):
        text = (
            "Notified acquisition\nAcquisition of B by A\n"
            "Determination\nApproved\n"
            "Date of determination\n15 January 2025"
        )
        result = parse_text_as_table(text)
        assert len(result) == 3
        assert result[0]['item'] == "Notified acquisition"
        assert result[1]['item'] == "Determination"
        assert result[2]['item'] == "Date of determination"

    def test_multiline_details(self):
        text = (
            "Nature of business activities\n"
            "Company A operates in mining.\n"
            "Company B operates in logistics.\n"
            "Market definition\nNational market"
        )
        result = parse_text_as_table(text)
        assert len(result) == 2
        assert "mining" in result[0]['details']
        assert "logistics" in result[0]['details']

    def test_empty_text(self):
        assert parse_text_as_table("") == []

    def test_no_known_items(self):
        text = "Random text\nMore random text"
        assert parse_text_as_table(text) == []

    def test_item_with_inline_detail(self):
        text = "Determination Approved"
        result = parse_text_as_table(text)
        assert len(result) == 1
        assert result[0]['item'] == "Determination"
        assert result[0]['details'] == "Approved"

    def test_skips_blank_lines(self):
        text = (
            "Notified acquisition\n"
            "\n"
            "\n"
            "Acquisition of B by A\n"
            "Determination\nApproved"
        )
        result = parse_text_as_table(text)
        assert len(result) == 2


# ---------------------------------------------------------------------------
# parse_determination: _parse_section_blocks (Statement of reasons structure)
# ---------------------------------------------------------------------------

class TestParseSectionBlocks:
    def test_numbered_paragraph(self):
        text = (
            "2.1. When making a determination in Phase 1, the ACCC undertakes a\n"
            "competition assessment.\n"
        )
        blocks = _parse_section_blocks(text, {})
        assert len(blocks) == 1
        assert blocks[0]['type'] == 'paragraph'
        assert blocks[0]['number'] == '2.1'
        assert 'competition assessment' in blocks[0]['text']

    def test_heading_then_paragraph(self):
        text = (
            "Industry background\n"
            "Mining equipment\n"
            "2.4. Mining equipment refers to various categories.\n"
        )
        heading_info = {
            'Industry background': {'size': 14.0, 'bold': True, 'italic': False},
            'Mining equipment': {'size': 11.0, 'bold': True, 'italic': False},
        }
        blocks = _parse_section_blocks(text, heading_info)
        assert blocks[0] == {'type': 'heading', 'text': 'Industry background'}
        assert blocks[1] == {'type': 'heading', 'text': 'Mining equipment'}
        assert blocks[2]['type'] == 'paragraph'
        assert blocks[2]['number'] == '2.4'

    def test_multiline_heading_merged(self):
        text = (
            "Reduced competition arising from accessing and using competitively\n"
            "significant information about rival OEMs\n"
            "2.19. The ACCC considers...\n"
        )
        heading_info = {
            'Reduced competition arising from accessing and using competitively': {
                'size': 14.0, 'bold': True, 'italic': False,
            },
            'significant information about rival OEMs': {
                'size': 14.0, 'bold': True, 'italic': False,
            },
        }
        blocks = _parse_section_blocks(text, heading_info)
        assert blocks[0]['type'] == 'heading'
        assert 'competitively significant information' in blocks[0]['text']
        # The heading-level fields are stripped from the public output.
        assert '_size' not in blocks[0]
        assert blocks[1]['type'] == 'paragraph'

    def test_different_size_headings_not_merged(self):
        text = (
            "Industry background\n"
            "Mining equipment\n"
        )
        heading_info = {
            'Industry background': {'size': 14.0, 'bold': True, 'italic': False},
            'Mining equipment': {'size': 11.0, 'bold': True, 'italic': False},
        }
        blocks = _parse_section_blocks(text, heading_info)
        assert len(blocks) == 2
        assert blocks[0]['text'] == 'Industry background'
        assert blocks[1]['text'] == 'Mining equipment'

    def test_bullet_list(self):
        text = (
            "2.20. The information types include:\n"
            "• Maintenance strategy\n"
            "• Equipment hire rates\n"
            "• The actual usage and downtime.\n"
        )
        blocks = _parse_section_blocks(text, {})
        assert blocks[0]['type'] == 'paragraph'
        assert blocks[1]['type'] == 'bullet_list'
        assert blocks[1]['items'] == [
            'Maintenance strategy',
            'Equipment hire rates',
            'The actual usage and downtime.',
        ]

    def test_lettered_list_parens(self):
        text = (
            "2.4. Examples of mining equipment include:\n"
            "(a) Large haul trucks\n"
            "(b) Loading equipment\n"
            "(c) Drilling equipment\n"
        )
        blocks = _parse_section_blocks(text, {})
        assert blocks[1]['type'] == 'lettered_list'
        assert [it['letter'] for it in blocks[1]['items']] == ['a', 'b', 'c']
        assert blocks[1]['items'][0]['text'] == 'Large haul trucks'

    def test_lettered_list_period_after_colon(self):
        text = (
            "2.14. The ACCC has considered, by:\n"
            "a. Providing one ability.\n"
            "b. Undermining another ability.\n"
        )
        blocks = _parse_section_blocks(text, {})
        # Paragraph ending with a colon followed by "a." starts a lettered list.
        assert blocks[1]['type'] == 'lettered_list'
        assert blocks[1]['items'][0]['letter'] == 'a'
        assert blocks[1]['items'][1]['letter'] == 'b'

    def test_continuation_lines_joined(self):
        text = (
            "2.1. When making a determination in Phase 1, the ACCC undertakes\n"
            "a competition assessment in accordance with the Act.\n"
        )
        blocks = _parse_section_blocks(text, {})
        assert len(blocks) == 1
        assert 'undertakes a competition assessment' in blocks[0]['text']

    def test_bullet_continuation(self):
        text = (
            "2.20. The types of information include:\n"
            "• The life cycle and maintenance strategy for equipment, including\n"
            "estimates of the costs of maintenance\n"
            "• Parts pricing\n"
        )
        blocks = _parse_section_blocks(text, {})
        bullets = blocks[1]
        assert bullets['type'] == 'bullet_list'
        assert 'estimates of the costs of maintenance' in bullets['items'][0]
        assert bullets['items'][1] == 'Parts pricing'


# ---------------------------------------------------------------------------
# parse_questionnaire: extract_deadline
# ---------------------------------------------------------------------------

class TestExtractDeadline:
    def test_simple_deadline(self):
        text = "Please respond by the date below.\nDeadline to respond: 25 August 2025\nThank you."
        result = extract_deadline(text)
        assert result == "25 August 2025"

    def test_deadline_with_time_and_timezone(self):
        text = "Deadline to respond: 5.00pm (AEDT) on 20 October 2025"
        result = extract_deadline(text)
        assert result == "20 October 2025"

    def test_single_digit_day(self):
        text = "Deadline to respond: 3 November 2025"
        result = extract_deadline(text)
        assert result == "3 November 2025"

    def test_no_deadline(self):
        text = "This questionnaire has no deadline mentioned."
        assert extract_deadline(text) is None

    def test_empty_text(self):
        assert extract_deadline("") is None

    def test_deadline_with_day_name_and_comma(self):
        text = "Deadline to respond: Wednesday, 6 May 2026"
        result = extract_deadline(text)
        assert result == "6 May 2026"

    def test_deadline_with_day_name_without_comma(self):
        # The ACCC template usually omits the comma (e.g. MN-60026).
        text = "Deadline to respond: Tuesday 4 August 2026"
        result = extract_deadline(text)
        assert result == "4 August 2026"

    def test_deadline_with_unbracketed_timezone(self):
        # e.g. MN-30003 / MN-65005 — same template, no brackets on the zone.
        text = "Deadline to respond: 5:00pm AEST on 1 July 2026"
        result = extract_deadline(text)
        assert result == "1 July 2026"

    def test_deadline_with_time_but_no_timezone(self):
        text = "Deadline to respond: 5pm on 1 July 2026"
        result = extract_deadline(text)
        assert result == "1 July 2026"

    def test_deadline_with_newline_in_date(self):
        text = "Deadline to respond: 25\nAugust 2025"
        # The regex uses DOTALL so \s+ matches newlines
        result = extract_deadline(text)
        assert result is not None
        assert "August 2025" in result


# ---------------------------------------------------------------------------
# parse_questionnaire: extract_questions
# ---------------------------------------------------------------------------

def _lines(*specs):
    """Helper to build annotated lines for extract_questions tests.

    Each spec is either a string (plain line) or a tuple (text, is_bold).
    """
    result = []
    for s in specs:
        if isinstance(s, tuple):
            result.append({'text': s[0], 'is_bold': s[1]})
        else:
            result.append({'text': s, 'is_bold': False})
    return result


class TestExtractQuestions:
    def test_simple_numbered_questions(self):
        lines = _lines(
            "Background", "Some background info.",
            ("Questions", True),
            "1. What is the nature of your business?",
            "2. How will this merger affect competition?",
            "3. Are there any barriers to entry?",
        )
        result = extract_questions(lines)
        assert len(result) == 3
        assert result[0]['number'] == 1
        assert "nature of your business" in result[0]['text']
        assert result[2]['number'] == 3

    def test_multiline_question(self):
        lines = _lines(
            ("Questions", True),
            "1. Please describe in detail",
            "the nature of your business",
            "and your market position.",
            "2. Next question.",
        )
        result = extract_questions(lines)
        assert len(result) == 2
        assert "nature of your business" in result[0]['text']
        assert "market position" in result[0]['text']

    def test_no_questions_section(self):
        lines = _lines("This document has no questions heading.")
        assert extract_questions(lines) == []

    def test_stops_at_confidentiality(self):
        lines = _lines(
            ("Questions", True),
            "1. First question?",
            "2. Second question?",
            "Confidentiality",
            "3. This should not be captured.",
        )
        result = extract_questions(lines)
        assert len(result) == 2

    def test_note_between_section_header_and_question_not_terminator(self):
        """MN-40029: a 'Note:' under a section header must not end the parse.

        The note sits between the second section header and its first question.
        Previously it was treated as a terminator, truncating a 10-question
        questionnaire to the 3 questions before the note.
        """
        lines = _lines(
            ("Questions for all stakeholders", True),
            "1. Outline any concerns.",
            "2. Provide additional information.",
            "3. Describe your business.",
            ("Questions for suppliers of hospitality services", True),
            "Note: 'on-premises hospitality services' include bar service,",
            "casual dining and gaming facilities.",
            "4. Identify the characteristics of your venue.",
            "5. Identify alternative suppliers.",
            ("Confidentiality of responses", True),
            "During the ACCC's assessment the ACCC may receive information.",
        )
        result = extract_questions(lines)
        assert [q['number'] for q in result] == [1, 2, 3, 4, 5]
        assert result[3]['section'] == 'Questions for suppliers of hospitality services'
        # The note text must not leak into a question.
        assert all("on-premises hospitality services' include" not in q['text'] for q in result)

    def test_bold_definitional_preamble_not_a_section(self):
        """MN-15028: a bold "In this questionnaire, … includes …" definition
        under the Questions heading is intro prose, not Q1's section."""
        lines = _lines(
            ("Questions", True),
            ("In this questionnaire, liquid waste collection and maintenance services", True),
            "(C&M services) includes the inspection, cleaning and maintenance of drains.",
            "1. Provide a brief description of your business.",
            ("Questions for customers", True),
            "2. Which C&M services does your organisation procure?",
        )
        result = extract_questions(lines)
        assert [q['number'] for q in result] == [1, 2]
        assert result[0]['section'] is None
        assert result[1]['section'] == 'Questions for customers'

    def test_please_note_mid_questions_not_terminator(self):
        """A 'Please note' line within the questions block is skipped, not fatal."""
        lines = _lines(
            ("Questions", True),
            "1. First question?",
            ("Section B", True),
            "Please note that responses may be published.",
            "2. Second question?",
        )
        result = extract_questions(lines)
        assert [q['number'] for q in result] == [1, 2]

    def test_empty_lines(self):
        assert extract_questions([]) == []

    def test_question_with_trailing_page_number(self):
        lines = _lines(
            ("Questions", True),
            "1. What is the relevant market? 5",
            "2. Next question.",
        )
        result = extract_questions(lines)
        assert len(result) == 2
        # Trailing page number should be stripped
        assert not result[0]['text'].endswith("5")

    def test_no_section_field_when_no_sections(self):
        lines = _lines(
            ("Questions", True),
            "1. First question?",
            "2. Second question?",
        )
        result = extract_questions(lines)
        assert len(result) == 2
        assert 'section' not in result[0]
        assert 'section' not in result[1]

    def test_bold_lines_become_section_headers(self):
        lines = _lines(
            ("Questions", True),
            ("General questions", True),
            "1. Describe your business.",
            "2. Outline any concerns.",
            ("Questions for mining customers", True),
            "3. Describe your fleet.",
            "4. Identify alternative suppliers.",
        )
        result = extract_questions(lines)
        assert len(result) == 4
        assert result[0]['section'] == 'General questions'
        assert result[1]['section'] == 'General questions'
        assert result[2]['section'] == 'Questions for mining customers'
        assert result[3]['section'] == 'Questions for mining customers'

    def test_bold_header_mid_question(self):
        """Bold section header between questions saves current question first."""
        lines = _lines(
            ("Questions", True),
            "1. Describe your business.",
            "2. Provide additional info relevant",
            "to the ACCC assessment.",
            ("Independent Repairers", True),
            "3. Identify barriers to entry.",
        )
        result = extract_questions(lines)
        assert len(result) == 3
        assert "to the ACCC assessment" in result[1]['text']
        assert "Independent" not in result[1]['text']
        assert result[0]['section'] is None
        assert result[1]['section'] is None
        assert result[2]['section'] == 'Independent Repairers'

    def test_multiple_bold_sections(self):
        """Any bold non-numbered text works as a section header."""
        lines = _lines(
            ("Questions", True),
            ("General questions", True),
            "1. General Q1.",
            "2. General Q2.",
            ("Questions for OEMs", True),
            "3. OEM Q1.",
            ("Other issues", True),
            "4. Other Q1.",
        )
        result = extract_questions(lines)
        assert len(result) == 4
        assert result[0]['section'] == 'General questions'
        assert result[1]['section'] == 'General questions'
        assert result[2]['section'] == 'Questions for OEMs'
        assert result[3]['section'] == 'Other issues'

    def test_non_bold_non_numbered_line_is_continuation(self):
        """A non-bold, non-numbered line should be treated as continuation text."""
        lines = _lines(
            ("Questions", True),
            "1. First question starts here",
            "and continues on next line.",
            "2. Second question.",
        )
        result = extract_questions(lines)
        assert len(result) == 2
        assert "starts here and continues" in result[0]['text']

    def test_multiline_bold_section_header(self):
        """Consecutive bold lines should be concatenated into one section name."""
        lines = _lines(
            ("Questions", True),
            ("Questions for customers of Event Stream Processing Software and", True),
            ("Integration Software", True),
            "1. Describe your usage.",
            "2. What features matter?",
        )
        result = extract_questions(lines)
        assert len(result) == 2
        assert result[0]['section'] == 'Questions for customers of Event Stream Processing Software and Integration Software'
        assert result[1]['section'] == result[0]['section']

    def test_questions_for_as_sole_heading(self):
        """'Questions for X' is used as the main heading when no plain 'Questions' exists."""
        lines = _lines(
            ("Questions for the parties", True),
            "1. Describe your business.",
        )
        result = extract_questions(lines)
        assert len(result) == 1
        assert result[0]['number'] == 1
        assert result[0]['section'] == 'Questions for the parties'

    def test_questions_for_all_stakeholders_pattern(self):
        """MN-10007 style: two 'Questions for X' sections, no plain 'Questions' heading."""
        lines = _lines(
            ("Questions for all stakeholders", True),
            "1. Describe your business.",
            "2. Outline any concerns.",
            "3. Provide any additional information.",
            ("Questions for stakeholders at the Port of Newcastle", True),
            "Although MAM does not have a direct ownership interest,",
            "the ACCC is considering the extent to which MAM could control.",
            "4. Identify alternative suppliers of stevedoring services.",
            "5. Identify alternative suppliers of grain export terminal services.",
        )
        result = extract_questions(lines)
        assert len(result) == 5
        assert result[0]['section'] == 'Questions for all stakeholders'
        assert result[1]['section'] == 'Questions for all stakeholders'
        assert result[2]['section'] == 'Questions for all stakeholders'
        assert result[3]['section'] == 'Questions for stakeholders at the Port of Newcastle'
        assert result[4]['section'] == 'Questions for stakeholders at the Port of Newcastle'
        assert result[3]['number'] == 4
        assert result[4]['number'] == 5

    def test_heading_with_subtitle(self):
        """Heading like 'Questions – please answer all questions...'"""
        lines = _lines(
            ("Questions – please answer all questions", True),
            ("General questions", True),
            "1. Describe your business.",
            ("Questions for suppliers of ITOM software", True),
            "2. Describe your position.",
        )
        result = extract_questions(lines)
        assert len(result) == 2
        assert result[0]['section'] == 'General questions'
        assert result[1]['section'] == 'Questions for suppliers of ITOM software'

    def test_non_bold_heading(self):
        """Some PDFs have the Questions heading as non-bold (e.g. MN-25004)."""
        lines = _lines(
            "Questions – please answer all questions that are relevant to your business",
            ("General questions", True),
            "1. Describe your business.",
            "2. Outline any concerns.",
            ("Questions for suppliers of ITOM software", True),
            "3. Describe your position.",
        )
        result = extract_questions(lines)
        assert len(result) == 3
        assert result[0]['section'] == 'General questions'
        assert result[0]['number'] == 1
        assert result[2]['section'] == 'Questions for suppliers of ITOM software'

    def test_unbolded_section_header_detected(self):
        """MN-95025: section headers aren't bolded in this PDF. A short,
        capitalised, unpunctuated line directly followed by a numbered
        question is treated as a header rather than glued onto the
        previous question's text."""
        lines = _lines(
            ("Questions", True),
            "1. Provide a brief description of your business or organisation,",
            "including any commercial relationships with Salesforce and/or Contentful.",
            "Alternative suppliers",
            "2. List providers of CRM software that could service your needs.",
            "3. List providers of CMS software that could service your needs.",
            "The Acquisition",
            "4. Outline any concerns regarding the effect on competition.",
        )
        result = extract_questions(lines)
        assert [q['number'] for q in result] == [1, 2, 3, 4]
        assert result[0]['section'] is None
        assert result[1]['section'] == 'Alternative suppliers'
        assert result[2]['section'] == 'Alternative suppliers'
        assert result[3]['section'] == 'The Acquisition'
        assert 'Alternative suppliers' not in result[0]['text']

    def test_unbolded_header_not_confused_with_wrapped_word(self):
        """MN-75003: a single word orphaned onto its own line by word-wrap
        (mid-sentence, no preceding sentence terminator) must stay part of
        the previous question, not be misread as a section header, even
        though it directly precedes the next numbered question."""
        lines = _lines(
            ("Questions", True),
            "1. Which of the following hospitals compete with each other:",
            "a. National Capital Private Hospital and Ramsay's Southern Highlands Private",
            "Hospital",
            "2. Are there any other Ramsay-owned businesses that compete?",
        )
        result = extract_questions(lines)
        assert [q['number'] for q in result] == [1, 2]
        assert 'section' not in result[1] or result[1]['section'] is None
        assert 'Southern Highlands Private Hospital' in result[0]['text']

    def test_page_furniture_dropped_mid_question(self):
        """Bare page numbers and OFFICIAL/SENSITIVE protective markings can
        appear mid-question (page breaks) and must be dropped, not appended
        to the question text."""
        lines = _lines(
            ("Questions", True),
            "1. Outline any concerns regarding the impact on competition.",
            "2",
            "2. Provide any additional information or comments.",
            "OFFICIAL",
            "SENSITIVE",
            "3. Provide a brief description of your business.",
        )
        result = extract_questions(lines)
        assert [q['number'] for q in result] == [1, 2, 3]
        assert result[0]['text'] == 'Outline any concerns regarding the impact on competition.'
        assert result[1]['text'] == 'Provide any additional information or comments.'


class TestExtractQuestionsFromText:
    """Tests for the plain-text fallback used when font data is unavailable."""

    def test_simple_questions(self):
        text = (
            "Questions\n"
            "1. What is your business?\n"
            "2. Any concerns?\n"
        )
        result = extract_questions_from_text(text)
        assert len(result) == 2

    def test_known_section_patterns_detected(self):
        text = (
            "Questions\n"
            "General questions\n"
            "1. Q1.\n"
            "Questions for mining customers\n"
            "2. Q2.\n"
            "Other issues\n"
            "3. Q3.\n"
        )
        result = extract_questions_from_text(text)
        assert len(result) == 3
        assert result[0]['section'] == 'General questions'
        assert result[1]['section'] == 'Questions for mining customers'
        assert result[2]['section'] == 'Other issues'

    def test_no_questions_heading(self):
        assert extract_questions_from_text("No heading here.") == []


class TestHasQuestionnaireHeader:
    """Tests for content-based questionnaire detection (_has_questionnaire_header)."""

    def _patch_pdfplumber(self, first_page_text):
        """Patch pdfplumber via the function's own __globals__ so the test is
        immune to other test files replacing sys.modules['scripts.parse.parse_questionnaire']."""
        page = unittest.mock.MagicMock()
        page.extract_text.return_value = first_page_text
        pdf_obj = unittest.mock.MagicMock()
        pdf_obj.pages = [page]
        mock_pdfplumber = unittest.mock.MagicMock()
        mock_pdfplumber.open.return_value.__enter__.return_value = pdf_obj
        return unittest.mock.patch.dict(
            _has_questionnaire_header.__globals__, {'pdfplumber': mock_pdfplumber}
        )

    def test_detects_questionnaire_header(self):
        with self._patch_pdfplumber("Questionnaire: Acme – Target\nMN-99999"):
            assert _has_questionnaire_header(unittest.mock.MagicMock()) is True

    def test_rejects_determination(self):
        with self._patch_pdfplumber("Determination\nSome content here."):
            assert _has_questionnaire_header(unittest.mock.MagicMock()) is False

    def test_rejects_empty_page(self):
        with self._patch_pdfplumber(""):
            assert _has_questionnaire_header(unittest.mock.MagicMock()) is False

    def test_returns_false_on_exception(self):
        broken = unittest.mock.MagicMock()
        broken.open.side_effect = Exception("bad pdf")
        with unittest.mock.patch.dict(
            _has_questionnaire_header.__globals__, {'pdfplumber': broken}
        ):
            assert _has_questionnaire_header(unittest.mock.MagicMock()) is False


class TestExtractSubpoints:
    def test_inline_comma_separated(self):
        text = (
            "Describe whether your organisation purchases guidewires as a bundled package. "
            "Please address whether guidewires are bundled with any of the following products "
            "that you procure: a. catheters, b. stent retrievers, c. neurovascular coils, "
            "d. flow diverters, and e. liquid embolic agents."
        )
        _, result = _extract_subpoints(text)
        assert len(result) == 5
        assert result[0] == {'letter': 'a', 'text': 'catheters'}
        assert result[1] == {'letter': 'b', 'text': 'stent retrievers'}
        assert result[2] == {'letter': 'c', 'text': 'neurovascular coils'}
        assert result[3] == {'letter': 'd', 'text': 'flow diverters'}
        assert result[4] == {'letter': 'e', 'text': 'liquid embolic agents'}

    def test_stem_is_text_up_to_colon(self):
        text = "Please address the following products that you procure: a. X, and b. Y."
        stem, _ = _extract_subpoints(text)
        assert stem == "Please address the following products that you procure:"

    def test_no_colon_returns_empty(self):
        assert _extract_subpoints("What is your business? a. retail b. wholesale") == (None, [])

    def test_no_subpoints_returns_empty(self):
        assert _extract_subpoints("What is the nature of your business?") == (None, [])

    def test_single_item_returns_empty(self):
        assert _extract_subpoints("Please address: a. only one thing.") == (None, [])

    def test_space_separated_subpoints(self):
        """Sub-points joined from separate PDF lines (no commas)."""
        text = "Please address each of the following: a. item one b. item two c. item three"
        _, result = _extract_subpoints(text)
        assert len(result) == 3
        assert result[0] == {'letter': 'a', 'text': 'item one'}
        assert result[1] == {'letter': 'b', 'text': 'item two'}
        assert result[2] == {'letter': 'c', 'text': 'item three'}

    def test_non_sequential_letters_returns_empty(self):
        text = "Consider: a. first thing, c. third thing skipping b."
        assert _extract_subpoints(text) == (None, [])

    def test_two_items(self):
        text = "Choose between: a. option alpha, and b. option beta."
        _, result = _extract_subpoints(text)
        assert len(result) == 2
        assert result[0] == {'letter': 'a', 'text': 'option alpha'}
        assert result[1] == {'letter': 'b', 'text': 'option beta'}


class TestExtractQuestionsWithSubpoints:
    def test_question_with_lettered_subpoints(self):
        lines = _lines(
            ("Questions", True),
            "1. Please address the following: a. item one, b. item two, and c. item three.",
            "2. Unrelated question.",
        )
        result = extract_questions(lines)
        assert len(result) == 2
        assert 'subpoints' in result[0]
        assert len(result[0]['subpoints']) == 3
        assert result[0]['subpoints'][0] == {'letter': 'a', 'text': 'item one'}
        assert result[0]['subpoints'][2] == {'letter': 'c', 'text': 'item three'}
        assert 'subpoints' not in result[1]

    def test_question_without_subpoints_has_no_field(self):
        lines = _lines(
            ("Questions", True),
            "1. Describe your business.",
        )
        result = extract_questions(lines)
        assert len(result) == 1
        assert 'subpoints' not in result[0]

    def test_multiline_subpoints(self):
        """Sub-points spread across multiple PDF lines are joined then parsed."""
        lines = _lines(
            ("Questions", True),
            "1. Describe bundling across any of the following:",
            "a. catheters, b. stent retrievers,",
            "c. neurovascular coils.",
            "2. Next question.",
        )
        result = extract_questions(lines)
        assert len(result) == 2
        assert 'subpoints' in result[0]
        assert len(result[0]['subpoints']) == 3
        assert result[0]['subpoints'][1]['letter'] == 'b'


class TestExtractBullets:
    BULLET = ''

    def test_basic(self):
        text = f'Explain whether you compete. If so: {self.BULLET} identify which products, and {self.BULLET} respond to questions 19 and 20.'
        _, result = _extract_bullets(text)
        assert result == ['identify which products', 'respond to questions 19 and 20']

    def test_no_colon_returns_empty(self):
        text = f'Some question {self.BULLET} item one {self.BULLET} item two'
        assert _extract_bullets(text) == (None, [])

    def test_stem_is_text_up_to_colon(self):
        text = f'Explain whether you compete. If so: {self.BULLET} item one {self.BULLET} item two.'
        stem, _ = _extract_bullets(text)
        assert stem == 'Explain whether you compete. If so:'

    def test_no_bullet_returns_empty(self):
        assert _extract_bullets('What is your business?') == (None, [])

    def test_strips_trailing_and(self):
        text = f'Describe, including: {self.BULLET} item one, and {self.BULLET} item two.'
        _, result = _extract_bullets(text)
        assert result == ['item one', 'item two']

    def test_no_space_after_bullet(self):
        text = f'Description, including: {self.BULLET}item one, and {self.BULLET}item two.'
        _, result = _extract_bullets(text)
        assert result == ['item one', 'item two']


class TestExtractQuestionsWithBullets:
    BULLET = ''

    def test_question_with_bullets(self):
        lines = _lines(
            ("Questions", True),
            f"1. Describe your experience, including: {self.BULLET} item one, and {self.BULLET} item two.",
            "2. Unrelated question.",
        )
        result = extract_questions(lines)
        assert len(result) == 2
        assert 'bullets' in result[0]
        assert result[0]['bullets'] == ['item one', 'item two']
        assert result[0]['text'] == 'Describe your experience, including:'
        assert 'bullets' not in result[1]

    def test_bullets_take_priority_over_subpoints(self):
        """If both patterns somehow appear, bullets win."""
        lines = _lines(
            ("Questions", True),
            f"1. Address these: {self.BULLET} item one {self.BULLET} item two with a. detail b. more.",
        )
        result = extract_questions(lines)
        assert 'bullets' in result[0]
        assert 'subpoints' not in result[0]


# ---------------------------------------------------------------------------
# cutoff: is_waiver_merger
# ---------------------------------------------------------------------------

class TestIsWaiverMerger:
    def test_waiver_by_id(self):
        assert is_waiver_merger({'merger_id': 'WA-00123', 'stage': ''}) is True

    def test_waiver_by_stage(self):
        assert is_waiver_merger({'merger_id': 'MN-01016', 'stage': 'Waiver - assessment'}) is True

    def test_not_waiver(self):
        assert is_waiver_merger({'merger_id': 'MN-01016', 'stage': 'Phase 1'}) is False

    def test_empty_merger(self):
        assert is_waiver_merger({}) is False


# ---------------------------------------------------------------------------
# cutoff: get_cutoff_date
# ---------------------------------------------------------------------------

class TestGetCutoffDate:
    def test_approved_notification_has_cutoff(self):
        merger = {
            'merger_id': 'MN-01016',
            'accc_determination': 'Approved',
            'determination_publication_date': '2025-01-15T12:00:00Z',
            'stage': 'Phase 1'
        }
        result = get_cutoff_date(merger)
        assert result is not None

    def test_not_approved_no_cutoff(self):
        merger = {
            'merger_id': 'MN-01016',
            'accc_determination': 'Not opposed',
            'determination_publication_date': '2025-01-15T12:00:00Z',
            'stage': 'Phase 1'
        }
        result = get_cutoff_date(merger)
        assert result is None

    def test_waiver_always_has_cutoff_after_determination(self):
        merger = {
            'merger_id': 'WA-00123',
            'accc_determination': 'Not approved',
            'determination_publication_date': '2025-01-15T12:00:00Z',
            'stage': 'Waiver'
        }
        result = get_cutoff_date(merger)
        assert result is not None

    def test_no_determination_date_no_cutoff(self):
        merger = {
            'merger_id': 'MN-01016',
            'accc_determination': 'Approved',
            'determination_publication_date': None,
            'stage': 'Phase 1'
        }
        result = get_cutoff_date(merger)
        assert result is None


# ---------------------------------------------------------------------------
# cutoff: should_skip_merger
# ---------------------------------------------------------------------------

class TestShouldSkipMerger:
    def test_approved_past_cutoff(self):
        merger = {
            'merger_id': 'MN-01016',
            'accc_determination': 'Approved',
            'determination_publication_date': '2024-01-01T12:00:00Z',
            'stage': 'Phase 1'
        }
        # Reference date well after cutoff
        ref = datetime(2025, 1, 1)
        assert should_skip_merger(merger, reference_date=ref) is True

    def test_approved_within_cutoff(self):
        merger = {
            'merger_id': 'MN-01016',
            'accc_determination': 'Approved',
            'determination_publication_date': '2025-01-10T12:00:00Z',
            'stage': 'Phase 1'
        }
        # Reference date within 3 weeks of determination
        ref = datetime(2025, 1, 15)
        assert should_skip_merger(merger, reference_date=ref) is False

    def test_undetermined_never_skipped(self):
        merger = {
            'merger_id': 'MN-01016',
            'stage': 'Phase 1'
        }
        assert should_skip_merger(merger) is False


# ---------------------------------------------------------------------------
# extract_mergers: is_safe_url
# ---------------------------------------------------------------------------

class TestIsSafeUrl:
    def test_valid_accc_url(self):
        assert is_safe_url("https://www.accc.gov.au/some-page") is True

    def test_http_accc_url(self):
        assert is_safe_url("http://www.accc.gov.au/some-page") is True

    def test_subdomain_accc(self):
        assert is_safe_url("https://register.accc.gov.au/some-page") is True

    def test_bare_accc_domain(self):
        assert is_safe_url("https://accc.gov.au/x") is True

    def test_non_accc_domain(self):
        assert is_safe_url("https://example.com/some-page") is False

    def test_ftp_scheme(self):
        assert is_safe_url("ftp://www.accc.gov.au/file") is False
        assert is_safe_url("ftp://accc.gov.au/x") is False

    def test_empty_url(self):
        assert is_safe_url("") is False

    def test_none_url(self):
        assert is_safe_url(None) is False

    def test_javascript_scheme(self):
        assert is_safe_url("javascript:alert(1)") is False

    def test_suffix_domain_bypass(self):
        """A hostname that merely ends with 'accc.gov.au' without a dot
        boundary (e.g. evilaccc.gov.au) must be rejected."""
        assert is_safe_url("https://evilaccc.gov.au/x") is False

    def test_subdomain_of_attacker_domain_bypass(self):
        """accc.gov.au as a prefix of an attacker-controlled domain must
        be rejected."""
        assert is_safe_url("https://accc.gov.au.evil.com/x") is False

    def test_no_host(self):
        assert is_safe_url("/relative/path") is False


# ---------------------------------------------------------------------------
# extract_mergers: get_serve_filename
# ---------------------------------------------------------------------------

class TestGetServeFilename:
    def test_pdf_unchanged(self):
        assert get_serve_filename("document.pdf") == "document.pdf"

    def test_docx_becomes_pdf(self):
        result = get_serve_filename("document.docx")
        assert result == "document.pdf"

    def test_other_extension_unchanged(self):
        assert get_serve_filename("image.png") == "image.png"


# ---------------------------------------------------------------------------
# extract_mergers: _infer_determination_date_from_events
# ---------------------------------------------------------------------------

class TestInferDeterminationDateFromEvents:
    def _base(self):
        return {
            'accc_determination': 'Approved',
            'determination_publication_date': None,
            'events': [],
        }

    def test_infers_date_from_linked_determination_event(self):
        m = self._base()
        m['events'] = [
            {'title': 'Phase 2 determination', 'date': '2026-06-02T12:00:00Z', 'url': 'https://accc.gov.au/det.pdf'},
        ]
        _infer_determination_date_from_events(m)
        assert m['determination_publication_date'] == '2026-06-02T12:00:00Z'

    def test_uses_latest_date_when_multiple_events_same_day(self):
        m = self._base()
        m['events'] = [
            {'title': 'Phase 2 determination - Summary', 'date': '2026-06-02T12:00:00Z', 'url': 'https://accc.gov.au/a.pdf'},
            {'title': 'Phase 2 determination - Statement of reasons', 'date': '2026-06-02T12:00:00Z', 'url': 'https://accc.gov.au/b.pdf'},
        ]
        _infer_determination_date_from_events(m)
        assert m['determination_publication_date'] == '2026-06-02T12:00:00Z'

    def test_uses_latest_date_for_phase1_to_phase2_merger(self):
        # Phase 1 determination document precedes Phase 2 determination document;
        # we must pick the Phase 2 (latest) date, not the Phase 1 (earliest) date.
        m = self._base()
        m['events'] = [
            {'title': 'Phase 1 determination - Referred to Phase 2', 'date': '2026-01-20T12:00:00Z', 'url': 'https://accc.gov.au/p1.pdf'},
            {'title': 'Phase 2 determination', 'date': '2026-06-02T12:00:00Z', 'url': 'https://accc.gov.au/p2.pdf'},
        ]
        _infer_determination_date_from_events(m)
        assert m['determination_publication_date'] == '2026-06-02T12:00:00Z'

    def test_skips_events_without_url(self):
        m = self._base()
        m['events'] = [
            {'title': 'Phase 2 determination', 'date': '2026-06-02T12:00:00Z'},  # no url
        ]
        _infer_determination_date_from_events(m)
        assert m['determination_publication_date'] is None

    def test_no_op_when_determination_publication_date_already_set(self):
        m = self._base()
        m['determination_publication_date'] = '2026-01-01T12:00:00Z'
        m['events'] = [
            {'title': 'Phase 2 determination', 'date': '2026-06-02T12:00:00Z', 'url': 'https://accc.gov.au/det.pdf'},
        ]
        _infer_determination_date_from_events(m)
        assert m['determination_publication_date'] == '2026-01-01T12:00:00Z'

    def test_no_op_when_no_accc_determination(self):
        m = self._base()
        m['accc_determination'] = None
        m['events'] = [
            {'title': 'Phase 2 determination', 'date': '2026-06-02T12:00:00Z', 'url': 'https://accc.gov.au/det.pdf'},
        ]
        _infer_determination_date_from_events(m)
        assert m['determination_publication_date'] is None

    def test_no_op_when_no_determination_events(self):
        m = self._base()
        m['events'] = [
            {'title': 'Merger notified to ACCC', 'date': '2025-10-10T12:00:00Z', 'url': 'https://accc.gov.au/n.pdf'},
        ]
        _infer_determination_date_from_events(m)
        assert m['determination_publication_date'] is None


# ---------------------------------------------------------------------------
# generate_static_data: is_christmas_new_year_period
# ---------------------------------------------------------------------------

# Import after mocks are set up
from scripts.generate.static_data.business_days import (
    is_christmas_new_year_period,
    _count_weekdays_in_range,
    calculate_calendar_days,
    check_holiday_horizon,
    get_latest_holiday_year,
)
from scripts.generate.static_data.enrichment import (
    detect_has_conditions,
    enrich_merger,
    extract_phase_from_event,
    is_phase_2_referral_event,
)
from scripts.generate.static_data.outputs.commentary import generate as generate_commentary_json
from scripts.generate.static_data.outputs.industries import generate_index as generate_industries_json
from scripts.generate.static_data.outputs.questionnaires import generate as generate_questionnaire_files
from scripts.generate.static_data.outputs.noccs import generate as generate_nocc_files
from scripts.parse.parse_nocc import (
    _parse_blocks,
    _group_blocks_into_sections,
    _is_top_level_heading,
    _is_sub_heading,
    _is_nocc_filename,
)


class TestIsChristmasNewYearPeriod:
    def test_christmas_eve(self):
        assert is_christmas_new_year_period(datetime(2025, 12, 24)) is True

    def test_dec_23(self):
        assert is_christmas_new_year_period(datetime(2025, 12, 23)) is True

    def test_dec_22_not_included(self):
        assert is_christmas_new_year_period(datetime(2025, 12, 22)) is False

    def test_jan_1(self):
        assert is_christmas_new_year_period(datetime(2026, 1, 1)) is True

    def test_jan_10(self):
        assert is_christmas_new_year_period(datetime(2026, 1, 10)) is True

    def test_jan_11_not_included(self):
        assert is_christmas_new_year_period(datetime(2026, 1, 11)) is False

    def test_mid_year(self):
        assert is_christmas_new_year_period(datetime(2025, 6, 15)) is False


# ---------------------------------------------------------------------------
# generate_static_data: _count_weekdays_in_range
# ---------------------------------------------------------------------------

class TestCountWeekdaysInRange:
    def test_full_week(self):
        # Mon Jan 6 to Sun Jan 12, 2025 = 5 weekdays
        start = datetime(2025, 1, 6)
        end = datetime(2025, 1, 12)
        assert _count_weekdays_in_range(start, end) == 5

    def test_single_weekday(self):
        # A Monday
        d = datetime(2025, 1, 6)
        assert _count_weekdays_in_range(d, d) == 1

    def test_single_weekend_day(self):
        # A Saturday
        d = datetime(2025, 1, 4)
        assert _count_weekdays_in_range(d, d) == 0

    def test_start_after_end(self):
        start = datetime(2025, 1, 10)
        end = datetime(2025, 1, 5)
        assert _count_weekdays_in_range(start, end) == 0

    def test_two_weeks(self):
        # Mon Jan 6 to Sun Jan 19, 2025 = 10 weekdays
        start = datetime(2025, 1, 6)
        end = datetime(2025, 1, 19)
        assert _count_weekdays_in_range(start, end) == 10

    def test_weekend_only(self):
        # Sat to Sun
        start = datetime(2025, 1, 4)
        end = datetime(2025, 1, 5)
        assert _count_weekdays_in_range(start, end) == 0


# ---------------------------------------------------------------------------
# generate_static_data: calculate_calendar_days
# ---------------------------------------------------------------------------

class TestCalculateCalendarDays:
    def test_same_day(self):
        assert calculate_calendar_days("2025-01-15", "2025-01-15") == 0

    def test_one_day(self):
        assert calculate_calendar_days("2025-01-15", "2025-01-16") == 1

    def test_one_week(self):
        assert calculate_calendar_days("2025-01-01", "2025-01-08") == 7

    def test_none_start(self):
        assert calculate_calendar_days(None, "2025-01-15") is None

    def test_none_end(self):
        assert calculate_calendar_days("2025-01-15", None) is None

    def test_empty_strings(self):
        assert calculate_calendar_days("", "") is None


# ---------------------------------------------------------------------------
# generate_static_data: check_holiday_horizon
# ---------------------------------------------------------------------------

class TestCheckHolidayHorizon:
    def test_current_date_passes(self):
        # The current holiday file (2025-2029) must cover >=15 months ahead
        # of "today" for the real generator run to pass.
        assert check_holiday_horizon() is None

    def test_within_horizon_passes(self):
        latest_year = get_latest_holiday_year()
        # 15 months before Jan 1 of the year after latest_year is well within
        # the covered range.
        today = date(latest_year - 1, 6, 1)
        assert check_holiday_horizon(today=today) is None

    def test_beyond_horizon_warns(self):
        latest_year = get_latest_holiday_year()
        today = date(latest_year + 2, 1, 1)
        message = check_holiday_horizon(today=today)
        assert message is not None
        assert str(latest_year) in message

    def test_just_inside_horizon_passes(self):
        latest_year = get_latest_holiday_year()
        # 15 months ahead of Sep of the year before latest_year lands exactly
        # on latest_year, which the calendar covers.
        today = date(latest_year - 1, 9, 1)
        assert check_holiday_horizon(today=today) is None

    def test_just_outside_horizon_warns(self):
        latest_year = get_latest_holiday_year()
        # 15 months ahead of Oct of the year before latest_year lands in
        # latest_year + 1, which the calendar does not cover.
        today = date(latest_year - 1, 10, 1)
        assert check_holiday_horizon(today=today) is not None


# ---------------------------------------------------------------------------
# generate_static_data: extract_phase_from_event
# ---------------------------------------------------------------------------

class TestExtractPhaseFromEvent:
    def test_phase_1(self):
        assert extract_phase_from_event("Phase 1 - Determination") == "Phase 1"

    def test_phase_2(self):
        assert extract_phase_from_event("Phase 2 - Detailed Assessment") == "Phase 2"

    def test_public_benefits(self):
        assert extract_phase_from_event("Public Benefits Test") == "Public Benefits"

    def test_public_benefits_lowercase(self):
        assert extract_phase_from_event("Applying public benefits test") == "Public Benefits"

    def test_waiver(self):
        assert extract_phase_from_event("Waiver Application") == "Waiver"

    def test_waiver_lowercase(self):
        assert extract_phase_from_event("waiver granted") == "Waiver"

    def test_notified(self):
        assert extract_phase_from_event("Merger notified to ACCC") == "Phase 1"

    def test_no_phase(self):
        assert extract_phase_from_event("Some random event") is None

    def test_none_input(self):
        assert extract_phase_from_event(None) is None

    def test_empty_string(self):
        assert extract_phase_from_event("") is None


# ---------------------------------------------------------------------------
# generate_static_data: enrich_merger
# ---------------------------------------------------------------------------

class TestEnrichMerger:
    def _base_merger(self):
        return {
            'merger_id': 'MN-01016',
            'merger_name': 'Test Merger',
            'accc_determination': 'Approved',
            'determination_publication_date': '2025-03-01T12:00:00Z',
            'stage': 'Phase 1 - preliminary assessment',
            'status': 'Determined',
            'events': [],
            'effective_notification_datetime': '2025-01-15T12:00:00Z',
        }

    def test_normalizes_determination(self):
        m = self._base_merger()
        m['accc_determination'] = 'ACCC Determination Approved'
        result = enrich_merger(m)
        assert result['accc_determination'] == 'Approved'

    def test_adds_is_waiver_false(self):
        result = enrich_merger(self._base_merger())
        assert result['is_waiver'] is False

    def test_adds_is_waiver_true(self):
        m = self._base_merger()
        m['merger_id'] = 'WA-00123'
        result = enrich_merger(m)
        assert result['is_waiver'] is True

    def test_phase_1_determination_set(self):
        result = enrich_merger(self._base_merger())
        assert result['phase_1_determination'] == 'Approved'
        assert result['phase_1_determination_date'] == '2025-03-01T12:00:00Z'

    def test_phase_2_determination_set(self):
        m = self._base_merger()
        m['stage'] = 'Phase 2 - detailed assessment'
        result = enrich_merger(m)
        assert result['phase_2_determination'] == 'Approved'
        assert result['phase_1_determination'] is None

    def test_public_benefits_determination_set(self):
        m = self._base_merger()
        m['stage'] = 'Public Benefits Test'
        result = enrich_merger(m)
        assert result['public_benefits_determination'] == 'Approved'

    def test_phase_2_referral_event(self):
        m = self._base_merger()
        m['accc_determination'] = None
        m['determination_publication_date'] = None
        m['stage'] = 'Phase 2 - detailed assessment'
        m['events'] = [
            {'title': 'Merger subject to Phase 2 review', 'date': '2025-02-15T12:00:00Z'}
        ]
        result = enrich_merger(m)
        assert result['phase_1_determination'] == 'Referred to phase 2'
        assert result['phase_1_determination_date'] == '2025-02-15T12:00:00Z'

    def test_phase_2_referral_event_new_phrasing(self):
        # ACCC changed the event title from "subject to Phase 2 review" to
        # "Decision to Proceed to a Phase 2 review" in 2026 (e.g. MN-65005).
        m = self._base_merger()
        m['accc_determination'] = None
        m['determination_publication_date'] = None
        m['stage'] = 'Phase 2 - detailed assessment'
        m['events'] = [
            {'title': 'Decision to Proceed to a Phase 2 review', 'date': '2026-04-16T12:00:00Z'}
        ]
        result = enrich_merger(m)
        assert result['phase_1_determination'] == 'Referred to phase 2'
        assert result['phase_1_determination_date'] == '2026-04-16T12:00:00Z'

    def test_phase_2_notice_event_is_referral(self):
        # A "Phase 2 Notice" event is the mechanism that moves a matter into
        # Phase 2 (e.g. MN-30002).
        assert is_phase_2_referral_event(
            'Peter Warren - Wakeling Automotive - Phase 2 Notice'
        ) is True

    def test_derives_phase_2_period_end_after_referral(self):
        # MN-05013: the register issued the Phase 2 notice while
        # end_of_determination_period still held the Phase 1 deadline six days
        # later. The Phase 2 clock runs 90 business days from the day after
        # the Phase 1 due date (23 Jul 2026 → BD 1 is 24 Jul, BD 90 is
        # 27 Nov after ACT holidays), regardless of the referral landing a
        # few days before the Phase 1 deadline.
        m = self._base_merger()
        m['accc_determination'] = None
        m['determination_publication_date'] = None
        m['stage'] = 'Phase 1 - initial assessment'
        m['end_of_determination_period'] = '2026-07-23T12:00:00Z'
        m['events'] = [
            {'title': 'Some Merger - Phase 2 Notice', 'date': '2026-07-17T12:00:00Z'}
        ]
        result = enrich_merger(m)
        assert result['end_of_determination_period'] == '2026-11-27T12:00:00Z'
        assert result['end_of_determination_period_derived'] is True

    def test_keeps_genuine_phase_2_period_end(self):
        # Once the register publishes the real Phase 2 date (~90 BDs after the
        # referral, MN-01072's actual dates) it must pass through untouched.
        m = self._base_merger()
        m['accc_determination'] = None
        m['determination_publication_date'] = None
        m['stage'] = 'Phase 2 - detailed assessment'
        m['end_of_determination_period'] = '2026-11-10T12:00:00Z'
        m['events'] = [
            {'title': 'Decision to Proceed to a Phase 2 review', 'date': '2026-07-02T12:00:00Z'}
        ]
        result = enrich_merger(m)
        assert result['end_of_determination_period'] == '2026-11-10T12:00:00Z'
        assert 'end_of_determination_period_derived' not in result

    def test_keeps_period_end_without_referral(self):
        # A Phase 1 matter with no referral event keeps its deadline.
        m = self._base_merger()
        m['accc_determination'] = None
        m['determination_publication_date'] = None
        m['stage'] = 'Phase 1 - initial assessment'
        m['end_of_determination_period'] = '2026-07-23T12:00:00Z'
        m['events'] = [{'title': 'Merger notified to ACCC', 'date': '2026-05-12T12:00:00Z'}]
        result = enrich_merger(m)
        assert result['end_of_determination_period'] == '2026-07-23T12:00:00Z'
        assert 'end_of_determination_period_derived' not in result

    def test_infers_phase_2_when_stage_lags(self):
        # ACCC issued a Phase 2 notice but the register's stage still says
        # Phase 1 — treat the merger as Phase 2 and flag the inference.
        m = self._base_merger()
        m['accc_determination'] = None
        m['determination_publication_date'] = None
        m['stage'] = 'Phase 1 - initial assessment'
        m['events'] = [
            {'title': 'Some Merger - Phase 2 Notice', 'date': '2026-06-02T12:00:00Z'}
        ]
        result = enrich_merger(m)
        assert result['phase_2_inferred'] is True
        assert result['stage'] == 'Phase 2 - detailed assessment'
        # The notice still resolves to a Phase 1 outcome of "Referred to phase 2".
        assert result['phase_1_determination'] == 'Referred to phase 2'
        assert result['phase_1_determination_date'] == '2026-06-02T12:00:00Z'

    def test_no_inference_when_stage_already_phase_2(self):
        # When the register already shows Phase 2, there is nothing to infer.
        m = self._base_merger()
        m['accc_determination'] = None
        m['determination_publication_date'] = None
        m['stage'] = 'Phase 2 - detailed assessment'
        m['events'] = [
            {'title': 'Some Merger - Phase 2 Notice', 'date': '2026-06-02T12:00:00Z'}
        ]
        result = enrich_merger(m)
        assert 'phase_2_inferred' not in result
        assert result['stage'] == 'Phase 2 - detailed assessment'

    def test_no_inference_without_phase_2_event(self):
        m = self._base_merger()
        m['stage'] = 'Phase 1 - initial assessment'
        m['events'] = [{'title': 'Merger notified to ACCC', 'date': '2026-03-05'}]
        result = enrich_merger(m)
        assert 'phase_2_inferred' not in result
        assert result['stage'] == 'Phase 1 - initial assessment'

    def test_inference_does_not_mutate_original_stage(self):
        m = self._base_merger()
        m['stage'] = 'Phase 1 - initial assessment'
        m['events'] = [{'title': 'X - Phase 2 Notice', 'date': '2026-06-02T12:00:00Z'}]
        enrich_merger(m)
        # The genuine stage on the source record must be preserved so the
        # auto-close detection can see when the register actually updates.
        assert m['stage'] == 'Phase 1 - initial assessment'

    def test_adds_commentary(self):
        m = self._base_merger()
        commentary = {
            'MN-01016': {
                'comments': [{'text': 'Interesting merger', 'date': '2025-03-01'}]
            }
        }
        result = enrich_merger(m, commentary)
        assert len(result['comments']) == 1
        assert result['comments'][0]['text'] == 'Interesting merger'

    def test_ensures_anzsic_codes(self):
        m = self._base_merger()
        # No anzsic_codes key
        result = enrich_merger(m)
        assert result['anzsic_codes'] == []

    def test_preserves_existing_anzsic_codes(self):
        m = self._base_merger()
        m['anzsic_codes'] = [{'code': '0600', 'name': 'Mining'}]
        result = enrich_merger(m)
        assert len(result['anzsic_codes']) == 1

    def test_does_not_mutate_original(self):
        m = self._base_merger()
        original_det = m['accc_determination']
        enrich_merger(m)
        assert m['accc_determination'] == original_det

    def test_adds_phase_to_events(self):
        m = self._base_merger()
        m['events'] = [
            {'title': 'Phase 1 - Statement of Issues', 'date': '2025-02-01'},
            {'title': 'Some other event', 'date': '2025-02-10'},
        ]
        result = enrich_merger(m)
        assert result['events'][0]['phase'] == 'Phase 1'
        assert result['events'][1]['phase'] is None

    def test_has_conditions_false_by_default(self):
        result = enrich_merger(self._base_merger())
        assert result['has_conditions'] is False

    def test_has_conditions_false_when_not_approved(self):
        m = self._base_merger()
        m['accc_determination'] = 'Not approved'
        m['accc_determination_raw'] = 'Not approved subject to conditions'
        result = enrich_merger(m)
        assert result['has_conditions'] is False

    def test_has_conditions_true_from_raw_determination(self):
        m = self._base_merger()
        m['accc_determination_raw'] = 'Approved subject to conditions'
        result = enrich_merger(m)
        assert result['has_conditions'] is True

    def test_has_conditions_true_from_determination_table_content(self):
        m = self._base_merger()
        m['events'] = [{
            'title': 'Phase 2 determination',
            'determination_table_content': [
                {'item': 'Conditions', 'details': 'a s 87B undertaking was accepted'},
            ],
        }]
        result = enrich_merger(m)
        assert result['has_conditions'] is True

    def test_has_conditions_true_from_statement_of_reasons(self):
        m = self._base_merger()
        m['events'] = [{
            'title': 'Phase 2 determination - Statement of reasons',
            'determination_statement_of_reasons': [
                {'type': 'paragraph', 'text': 'The ACCC accepted a section 87B undertaking.'},
            ],
        }]
        result = enrich_merger(m)
        assert result['has_conditions'] is True


class TestDetectHasConditions:
    def test_no_conditions_signal(self):
        assert detect_has_conditions({'events': []}) is False

    def test_case_insensitive_match(self):
        m = {'accc_determination_raw': 'APPROVED SUBJECT TO CONDITIONS', 'events': []}
        assert detect_has_conditions(m) is True

    def test_does_not_distinguish_negated_phrasing(self):
        # Documented limitation: "no conditions were imposed" still matches
        # because it contains no condition-indicating phrase to begin with,
        # but a negated phrase that DOES contain one (e.g. "conditions of
        # approval were not required") would still be flagged as a false
        # positive. Covering the non-negated case here.
        m = {'accc_determination_raw': 'Approved', 'events': []}
        assert detect_has_conditions(m) is False

    def test_matches_lettered_list_items_in_statement_of_reasons(self):
        m = {
            'events': [{
                'determination_statement_of_reasons': [
                    {
                        'type': 'lettered_list',
                        'items': [{'letter': 'a', 'text': 'a s 87B undertaking'}],
                    },
                ],
            }],
        }
        assert detect_has_conditions(m) is True


# ---------------------------------------------------------------------------
# extract_mergers: detect_inferred_phase_2
# ---------------------------------------------------------------------------

class TestDetectInferredPhase2:
    def _run(self, mergers, tmp_path, monkeypatch):
        out = tmp_path / "inferred_phase_2.json"
        monkeypatch.setattr(extract_mergers, "INFERRED_PHASE_2_PATH", str(out))
        detect_inferred_phase_2(mergers)
        if not out.exists():
            return None
        with open(out) as f:
            return json.load(f)

    def test_opens_issue_when_stage_lags(self, tmp_path, monkeypatch):
        mergers = [{
            'merger_id': 'MN-30002',
            'merger_name': 'Peter Warren - Wakeling Automotive',
            'url': 'https://accc.gov.au/x',
            'stage': 'Phase 1 - initial assessment',
            'events': [{'title': 'X - Phase 2 Notice', 'date': '2026-06-02T12:00:00Z'}],
        }]
        result = self._run(mergers, tmp_path, monkeypatch)
        assert len(result['open']) == 1
        assert result['open'][0]['merger_id'] == 'MN-30002'
        assert 'MN-30002' in result['open'][0]['title']
        assert result['confirmed'] == []

    def test_confirms_close_when_stage_updates(self, tmp_path, monkeypatch):
        mergers = [{
            'merger_id': 'MN-30002',
            'merger_name': 'Peter Warren - Wakeling Automotive',
            'stage': 'Phase 2 - detailed assessment',
            'events': [{'title': 'X - Phase 2 Notice', 'date': '2026-06-02T12:00:00Z'}],
        }]
        result = self._run(mergers, tmp_path, monkeypatch)
        assert result['open'] == []
        assert result['confirmed'] == ['MN-30002']

    def test_ignores_mergers_without_phase_2_event(self, tmp_path, monkeypatch):
        mergers = [{
            'merger_id': 'MN-00001',
            'merger_name': 'Ordinary Phase 1',
            'stage': 'Phase 1 - initial assessment',
            'events': [{'title': 'Merger notified to ACCC', 'date': '2026-03-05'}],
        }]
        result = self._run(mergers, tmp_path, monkeypatch)
        # Nothing to report → file is removed / never written.
        assert result is None

    def test_removes_stale_file_when_nothing_to_report(self, tmp_path, monkeypatch):
        out = tmp_path / "inferred_phase_2.json"
        out.write_text('{"open": [{"merger_id": "MN-OLD"}], "confirmed": []}')
        monkeypatch.setattr(extract_mergers, "INFERRED_PHASE_2_PATH", str(out))
        detect_inferred_phase_2([{
            'merger_id': 'MN-00001',
            'stage': 'Phase 1 - initial assessment',
            'events': [],
        }])
        assert not out.exists()


# ---------------------------------------------------------------------------
# extract_mergers: _load_known_notification_dates
# ---------------------------------------------------------------------------

class TestLoadKnownNotificationDates:
    def test_loads_date_field_and_skips_entries_without_one(self, tmp_path, monkeypatch):
        path = tmp_path / "known_notification_dates.json"
        path.write_text(json.dumps({
            "MN-50030": {"date": "2026-07-01T12:00:00Z", "note": "missing from page"},
            "MN-BAD": {"note": "no date field, should be skipped"},
        }))
        monkeypatch.setattr(extract_mergers, "KNOWN_NOTIFICATION_DATES_PATH", str(path))
        result = extract_mergers._load_known_notification_dates()
        assert result == {"MN-50030": "2026-07-01T12:00:00Z"}

    def test_missing_file_returns_empty_dict(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            extract_mergers, "KNOWN_NOTIFICATION_DATES_PATH", str(tmp_path / "nope.json")
        )
        assert extract_mergers._load_known_notification_dates() == {}


# ---------------------------------------------------------------------------
# find_pending_phase2_notice_events / extract_phase2_notice_data
# ---------------------------------------------------------------------------

class TestFindPendingPhase2NoticeEvents:
    def test_finds_pending_event_with_downloaded_pdf(self, tmp_path, monkeypatch):
        monkeypatch.setattr(extract_mergers, 'MATTERS_DIR', str(tmp_path))
        matter_dir = tmp_path / 'MN-90009'
        matter_dir.mkdir()
        (matter_dir / 'Notice.pdf').write_bytes(b'%PDF-1.4 fake')
        mergers = [{
            'merger_id': 'MN-90009',
            'events': [{
                'title': 'Trescal - TR Calibration - Phase 2 Notice',
                'url_gh': '/mergers/MN-90009/Notice.pdf',
            }],
        }]
        pending = find_pending_phase2_notice_events(mergers)
        assert len(pending) == 1
        merger_id, event, path = pending[0]
        assert merger_id == 'MN-90009'
        assert event['title'] == 'Trescal - TR Calibration - Phase 2 Notice'
        assert path == str(matter_dir / 'Notice.pdf')

    def test_skips_already_parsed_event(self, tmp_path, monkeypatch):
        monkeypatch.setattr(extract_mergers, 'MATTERS_DIR', str(tmp_path))
        matter_dir = tmp_path / 'MN-01019'
        matter_dir.mkdir()
        (matter_dir / 'Notice.pdf').write_bytes(b'%PDF-1.4 fake')
        mergers = [{
            'merger_id': 'MN-01019',
            'events': [{
                'title': 'ACCC decided notification is subject to Phase 2 review',
                'url_gh': '/mergers/MN-01019/Notice.pdf',
                'phase2_notice_matters_to_investigate': [],
            }],
        }]
        assert find_pending_phase2_notice_events(mergers) == []

    def test_skips_non_phase2_events(self, tmp_path, monkeypatch):
        monkeypatch.setattr(extract_mergers, 'MATTERS_DIR', str(tmp_path))
        mergers = [{
            'merger_id': 'MN-00001',
            'events': [{'title': 'Merger notified to ACCC', 'url_gh': '/mergers/MN-00001/x.pdf'}],
        }]
        assert find_pending_phase2_notice_events(mergers) == []

    def test_skips_event_without_downloaded_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr(extract_mergers, 'MATTERS_DIR', str(tmp_path))
        mergers = [{
            'merger_id': 'MN-90009',
            'events': [{
                'title': 'X - Phase 2 Notice',
                'url_gh': '/mergers/MN-90009/does-not-exist.pdf',
            }],
        }]
        assert find_pending_phase2_notice_events(mergers) == []


class TestExtractPhase2NoticeData:
    def test_parses_pending_and_attaches_result(self, tmp_path, monkeypatch):
        monkeypatch.setattr(extract_mergers, 'MATTERS_DIR', str(tmp_path))
        matter_dir = tmp_path / 'MN-90009'
        matter_dir.mkdir()
        (matter_dir / 'Notice.pdf').write_bytes(b'%PDF-1.4 fake')

        boxes = [{'heading': 'Relevant areas of competition', 'items': ['A matter.']}]
        monkeypatch.setattr(
            extract_mergers, 'parse_phase2_notice_pdf',
            lambda path: {'matters_to_investigate': boxes},
        )

        event = {'title': 'X - Phase 2 Notice', 'url_gh': '/mergers/MN-90009/Notice.pdf'}
        mergers = [{'merger_id': 'MN-90009', 'events': [event]}]

        count = extract_phase2_notice_data(mergers)
        assert count == 1
        assert event['phase2_notice_matters_to_investigate'] == boxes
        # No 'commission_division' key returned by the mock -> stored as None,
        # not left unset, so the field's presence stays a reliable cache signal.
        assert event['phase2_notice_commission_division'] is None

    def test_attaches_decision_commission_division(self, tmp_path, monkeypatch):
        monkeypatch.setattr(extract_mergers, 'MATTERS_DIR', str(tmp_path))
        matter_dir = tmp_path / 'MN-30002'
        matter_dir.mkdir()
        (matter_dir / 'Notice.pdf').write_bytes(b'%PDF-1.4 fake')

        division = (
            'Decision made by a division of the Commission constituted by a '
            'direction issued pursuant to section 19 of the Competition and '
            'Consumer Act 2010 (Cth)'
        )
        monkeypatch.setattr(
            extract_mergers, 'parse_phase2_notice_pdf',
            lambda path: {'matters_to_investigate': [], 'commission_division': division},
        )

        event = {'title': 'X - Phase 2 Notice', 'url_gh': '/mergers/MN-30002/Notice.pdf'}
        mergers = [{'merger_id': 'MN-30002', 'events': [event]}]

        extract_phase2_notice_data(mergers)
        assert event['phase2_notice_commission_division'] == division

    def test_leaves_already_parsed_events_untouched(self, tmp_path, monkeypatch):
        # Ampol-EG Australia's regression case: once an event has a result
        # (even an empty one), it must never be re-parsed on a later run.
        monkeypatch.setattr(extract_mergers, 'MATTERS_DIR', str(tmp_path))
        calls = []
        monkeypatch.setattr(
            extract_mergers, 'parse_phase2_notice_pdf',
            lambda path: calls.append(path) or {'matters_to_investigate': []},
        )
        event = {
            'title': 'ACCC decided notification is subject to Phase 2 review',
            'url_gh': '/mergers/MN-01019/Notice.pdf',
            'phase2_notice_matters_to_investigate': [{'heading': None, 'items': ['Already parsed.']}],
        }
        mergers = [{'merger_id': 'MN-01019', 'events': [event]}]

        count = extract_phase2_notice_data(mergers)
        assert count == 0
        assert calls == []
        assert event['phase2_notice_matters_to_investigate'] == [{'heading': None, 'items': ['Already parsed.']}]

    def test_records_error_and_continues_on_parse_failure(self, tmp_path, monkeypatch):
        monkeypatch.setattr(extract_mergers, 'MATTERS_DIR', str(tmp_path))
        matter_dir = tmp_path / 'MN-90009'
        matter_dir.mkdir()
        (matter_dir / 'Notice.pdf').write_bytes(b'%PDF-1.4 fake')

        def _raise(path):
            raise ValueError('boom')
        monkeypatch.setattr(extract_mergers, 'parse_phase2_notice_pdf', _raise)

        event = {'title': 'X - Phase 2 Notice', 'url_gh': '/mergers/MN-90009/Notice.pdf'}
        mergers = [{'merger_id': 'MN-90009', 'events': [event]}]

        count = extract_phase2_notice_data(mergers)
        assert count == 0
        assert 'phase2_notice_matters_to_investigate' not in event


# ---------------------------------------------------------------------------
# generate_static_data: generate_industries_json
# ---------------------------------------------------------------------------

class TestGenerateIndustriesJson:
    def test_groups_by_industry(self):
        mergers = [
            {'merger_id': 'MN-001', 'anzsic_codes': [{'code': '0600', 'name': 'Mining'}]},
            {'merger_id': 'MN-002', 'anzsic_codes': [{'code': '0600', 'name': 'Mining'}]},
            {'merger_id': 'MN-003', 'anzsic_codes': [{'code': '5400', 'name': 'Transport'}]},
        ]
        result = generate_industries_json(mergers)
        industries = result['industries']
        assert len(industries) == 2
        # Sorted by count descending
        assert industries[0]['name'] == 'Mining'
        assert industries[0]['merger_count'] == 2
        assert industries[1]['name'] == 'Transport'
        assert industries[1]['merger_count'] == 1

    def test_empty_mergers(self):
        result = generate_industries_json([])
        assert result['industries'] == []
        assert result['total_industries'] == 0
        assert result['total_mergers'] == 0

    def test_no_anzsic_codes(self):
        mergers = [{'merger_id': 'MN-001'}]
        result = generate_industries_json(mergers)
        assert result['industries'] == []
        assert result['total_industries'] == 0
        assert result['total_mergers'] == 0

    def test_multiple_codes_per_merger(self):
        mergers = [
            {
                'merger_id': 'MN-001',
                'anzsic_codes': [
                    {'code': '0600', 'name': 'Mining'},
                    {'code': '5400', 'name': 'Transport'}
                ]
            },
        ]
        result = generate_industries_json(mergers)
        assert len(result['industries']) == 2


# ---------------------------------------------------------------------------
# generate_static_data: generate_commentary_json
# ---------------------------------------------------------------------------

class TestGenerateCommentaryJson:
    def test_includes_mergers_with_commentary(self):
        mergers = [
            {
                'merger_id': 'MN-001',
                'merger_name': 'Merger A',
                'status': 'Determined',
                'accc_determination': 'Approved',
                'is_waiver': False,
                'effective_notification_datetime': '2025-01-01',
                'determination_publication_date': '2025-03-01',
                'stage': 'Phase 1',
                'acquirers': [],
                'targets': [],
                'anzsic_codes': [],
                'events': [],
            },
            {
                'merger_id': 'MN-002',
                'merger_name': 'Merger B',
                'status': 'Active',
                'accc_determination': None,
                'is_waiver': False,
                'effective_notification_datetime': '2025-02-01',
                'determination_publication_date': None,
                'stage': 'Phase 1',
                'acquirers': [],
                'targets': [],
                'anzsic_codes': [],
                'events': [],
            },
        ]
        commentary = {
            'MN-001': {
                'comments': [{'text': 'Good merger', 'date': '2025-03-05'}]
            }
        }
        result = generate_commentary_json(mergers, commentary)
        assert result['count'] == 1
        assert result['items'][0]['merger_id'] == 'MN-001'
        assert len(result['items'][0]['comments']) == 1

    def test_no_commentary(self):
        mergers = [{'merger_id': 'MN-001', 'merger_name': 'A', 'events': []}]
        result = generate_commentary_json(mergers, {})
        assert result['count'] == 0
        assert result['items'] == []

    def test_sorted_by_latest_comment_date(self):
        mergers = [
            {
                'merger_id': 'MN-001', 'merger_name': 'A', 'status': 'X',
                'accc_determination': None, 'is_waiver': False,
                'effective_notification_datetime': '2025-01-01',
                'determination_publication_date': None, 'stage': 'Phase 1',
                'acquirers': [], 'targets': [], 'anzsic_codes': [], 'events': [],
            },
            {
                'merger_id': 'MN-002', 'merger_name': 'B', 'status': 'X',
                'accc_determination': None, 'is_waiver': False,
                'effective_notification_datetime': '2025-02-01',
                'determination_publication_date': None, 'stage': 'Phase 1',
                'acquirers': [], 'targets': [], 'anzsic_codes': [], 'events': [],
            },
        ]
        commentary = {
            'MN-001': {'comments': [{'text': 'Old', 'date': '2025-01-01'}]},
            'MN-002': {'comments': [{'text': 'New', 'date': '2025-03-01'}]},
        }
        result = generate_commentary_json(mergers, commentary)
        assert result['items'][0]['merger_id'] == 'MN-002'
        assert result['items'][1]['merger_id'] == 'MN-001'

    def test_under_appeal_flag_and_summary(self):
        mergers = [
            {
                'merger_id': 'MN-001', 'merger_name': 'A', 'status': 'X',
                'accc_determination': 'Not approved', 'is_waiver': False,
                'effective_notification_datetime': '2025-01-01',
                'determination_publication_date': None, 'stage': 'Phase 2',
                'acquirers': [], 'targets': [], 'anzsic_codes': [], 'events': [],
                'under_appeal': True,
                'appeal': {
                    'status': 'current',
                    'outcome': None,
                    'effective_determination': None,
                    'tribunal_number': 'ACT 1 of 2026',
                    'documents': [{'description': 'Application for review'}],
                },
            },
            {
                'merger_id': 'MN-002', 'merger_name': 'B', 'status': 'X',
                'accc_determination': 'Approved', 'is_waiver': False,
                'effective_notification_datetime': '2025-02-01',
                'determination_publication_date': None, 'stage': 'Phase 1',
                'acquirers': [], 'targets': [], 'anzsic_codes': [], 'events': [],
            },
        ]
        commentary = {
            'MN-001': {'comments': [{'text': 'Appealed', 'date': '2025-03-01'}]},
            'MN-002': {'comments': [{'text': 'Cleared', 'date': '2025-01-05'}]},
        }
        result = generate_commentary_json(mergers, commentary)
        items = {item['merger_id']: item for item in result['items']}
        assert items['MN-001']['under_appeal'] is True
        # Only the slim status/outcome/effective_determination fields are
        # carried — not the full documents list.
        assert items['MN-001']['appeal'] == {
            'status': 'current', 'outcome': None, 'effective_determination': None,
        }
        # under_appeal/appeal are omitted entirely rather than set to False —
        # most mergers never had an appeal, so the field would just be noise.
        assert 'under_appeal' not in items['MN-002']
        assert 'appeal' not in items['MN-002']


# ---------------------------------------------------------------------------
# generate_static_data: enrich_merger with questionnaire data
# ---------------------------------------------------------------------------

class TestEnrichMergerQuestionnaire:
    def _base_merger(self):
        return {
            'merger_id': 'MN-01016',
            'merger_name': 'Test Merger',
            'accc_determination': None,
            'determination_publication_date': None,
            'stage': 'Phase 1 - preliminary assessment',
            'status': 'Under assessment',
            'events': [],
            'effective_notification_datetime': '2025-01-15T12:00:00Z',
        }

    def test_has_questionnaire_flag_set_when_data_exists(self):
        m = self._base_merger()
        q_data = {
            'MN-01016': {
                'questions': [{'number': 1, 'text': 'Q1'}],
                'questions_count': 1,
            }
        }
        result = enrich_merger(m, questionnaire_data=q_data)
        assert result.get('has_questionnaire') is True

    def test_no_flag_when_no_questionnaire_data(self):
        m = self._base_merger()
        result = enrich_merger(m, questionnaire_data={})
        assert 'has_questionnaire' not in result

    def test_no_flag_when_questionnaire_data_is_none(self):
        m = self._base_merger()
        result = enrich_merger(m, questionnaire_data=None)
        assert 'has_questionnaire' not in result

    def test_no_flag_when_merger_not_in_data(self):
        m = self._base_merger()
        q_data = {
            'MN-99999': {
                'questions': [{'number': 1, 'text': 'Q1'}],
                'questions_count': 1,
            }
        }
        result = enrich_merger(m, questionnaire_data=q_data)
        assert 'has_questionnaire' not in result

    def test_no_flag_when_questions_list_empty(self):
        m = self._base_merger()
        q_data = {
            'MN-01016': {
                'questions': [],
                'questions_count': 0,
            }
        }
        result = enrich_merger(m, questionnaire_data=q_data)
        assert 'has_questionnaire' not in result

    def test_questionnaire_data_not_embedded(self):
        """Questionnaire data should NOT be embedded in the merger — only a flag."""
        m = self._base_merger()
        q_data = {
            'MN-01016': {
                'deadline': '25 August 2025',
                'deadline_iso': '2025-08-25',
                'file_name': 'Questionnaire.pdf',
                'questions': [{'number': 1, 'text': 'Q1'}],
                'questions_count': 1,
            }
        }
        result = enrich_merger(m, questionnaire_data=q_data)
        assert result.get('has_questionnaire') is True
        assert 'questionnaire' not in result
        assert 'questions' not in result


# ---------------------------------------------------------------------------
# generate_static_data: generate_questionnaire_files
# ---------------------------------------------------------------------------

class TestGenerateQuestionnaireFiles:
    def test_generates_files(self, tmp_path):
        q_data = {
            'MN-01016': {
                'deadline': '25 August 2025',
                'deadline_iso': '2025-08-25',
                'file_name': 'Questionnaire.pdf',
                'questions': [
                    {'number': 1, 'text': 'What is the impact?'},
                    {'number': 2, 'text': 'Describe your business.'},
                ],
                'questions_count': 2,
            },
            'MN-01017': {
                'deadline': '18 August 2025',
                'deadline_iso': '2025-08-18',
                'file_name': 'Q2.pdf',
                'questions': [{'number': 1, 'text': 'Question'}],
                'questions_count': 1,
            },
        }

        count = generate_questionnaire_files(q_data, tmp_path)
        assert count == 2

        # Verify files exist
        q_dir = tmp_path / "questionnaires"
        assert (q_dir / "MN-01016.json").exists()
        assert (q_dir / "MN-01017.json").exists()

        # Verify content
        import json
        with open(q_dir / "MN-01016.json") as f:
            data = json.load(f)
        assert data['deadline'] == '25 August 2025'
        assert data['deadline_iso'] == '2025-08-25'
        assert data['questions_count'] == 2
        assert len(data['questions']) == 2
        assert data['questions'][0]['number'] == 1
        assert data['questions'][0]['text'] == 'What is the impact?'

    def test_skips_entries_without_questions(self, tmp_path):
        q_data = {
            'MN-01016': {
                'questions': [{'number': 1, 'text': 'Q1'}],
                'questions_count': 1,
            },
            'MN-01017': {
                'questions': [],
                'questions_count': 0,
            },
        }

        count = generate_questionnaire_files(q_data, tmp_path)
        assert count == 1

        q_dir = tmp_path / "questionnaires"
        assert (q_dir / "MN-01016.json").exists()
        assert not (q_dir / "MN-01017.json").exists()

    def test_empty_data(self, tmp_path):
        count = generate_questionnaire_files({}, tmp_path)
        assert count == 0

    def test_does_not_include_file_path(self, tmp_path):
        """file_path is an internal path and should not be in the output."""
        q_data = {
            'MN-01016': {
                'file_path': 'matters/MN-01016/Questionnaire.pdf',
                'file_name': 'Questionnaire.pdf',
                'questions': [{'number': 1, 'text': 'Q1'}],
                'questions_count': 1,
            },
        }

        generate_questionnaire_files(q_data, tmp_path)

        import json
        with open(tmp_path / "questionnaires" / "MN-01016.json") as f:
            data = json.load(f)
        assert 'file_path' not in data


# ---------------------------------------------------------------------------
# parse_nocc: filename detection
# ---------------------------------------------------------------------------

class TestIsNoccFilename:
    def test_full_phrase(self):
        assert _is_nocc_filename(
            'Coles_Kalgoorlie - Final - Summary of Notice of Competition Concerns - March 2026.pdf'
        )

    def test_abbreviation(self):
        assert _is_nocc_filename('Ampol_EG - NOCC summary - AR version - 2 March 2026.pdf')

    def test_case_insensitive(self):
        assert _is_nocc_filename('NOTICE OF COMPETITION CONCERNS.PDF')

    def test_must_be_pdf(self):
        assert not _is_nocc_filename('Notice of Competition Concerns.docx')

    def test_unrelated_pdf_rejected(self):
        assert not _is_nocc_filename('Phase 2 Notice - Redacted.pdf')

    def test_questionnaire_rejected(self):
        assert not _is_nocc_filename('Questionnaire - Coles - 28.11.2025.pdf')


# ---------------------------------------------------------------------------
# parse_nocc: heading detection from font metadata
# ---------------------------------------------------------------------------

def _line(text, size=11.04, bold=False, italic=False):
    return {'text': text, 'size': size, 'bold': bold, 'italic': italic, 'y': 0}


class TestIsTopLevelHeading:
    def test_numbered_heading_at_h1_size(self):
        assert _is_top_level_heading(_line('1. Introduction', size=18.0, bold=True))

    def test_numbered_heading_no_space(self):
        # Real NOCCs sometimes drop the space between "1." and the title.
        assert _is_top_level_heading(_line('1.Introduction', size=18.0, bold=True))

    def test_body_sized_numbered_line_is_not_h1(self):
        assert not _is_top_level_heading(_line('1.1. Some paragraph', size=11.04))

    def test_unnumbered_heading_is_not_h1(self):
        assert not _is_top_level_heading(_line('The Acquisition', size=14.0, bold=True))


class TestIsSubHeading:
    def test_bold_14pt(self):
        assert _is_sub_heading(_line('The Acquisition', size=14.04, bold=True))

    def test_regular_14pt(self):
        # Sub-sub-headings such as "Grocery retailing in Australia" render at
        # 14pt without bold and must still be detected.
        assert _is_sub_heading(_line('Grocery retailing in Australia', size=14.04))

    def test_top_level_heading_excluded(self):
        # An H1-sized numbered line is the top-level case and must not also
        # match the sub-heading rule.
        assert not _is_sub_heading(_line('1. Introduction', size=18.0, bold=True))

    def test_numbered_paragraph_excluded(self):
        assert not _is_sub_heading(_line('1.1 Some paragraph', size=14.04, bold=True))

    def test_bullet_excluded(self):
        assert not _is_sub_heading(_line('▪ a point', size=14.04, bold=True))


# ---------------------------------------------------------------------------
# parse_nocc: _parse_blocks
# ---------------------------------------------------------------------------

class TestParseNoccBlocks:
    def test_top_level_heading_then_paragraph(self):
        lines = [
            _line('1. Introduction', size=18.0, bold=True),
            _line('1.1. The ACCC received a notification.', size=11.04),
        ]
        blocks = _parse_blocks(lines)
        assert blocks[0] == {'type': 'heading', 'level': 1, 'text': '1. Introduction'}
        assert blocks[1]['type'] == 'paragraph'
        assert blocks[1]['number'] == '1.1'
        assert 'received a notification' in blocks[1]['text']

    def test_sub_heading_between_paragraphs(self):
        lines = [
            _line('2.1. First paragraph.', size=11.04),
            _line('The Acquisition', size=14.04, bold=True),
            _line('2.2. Second paragraph.', size=11.04),
        ]
        blocks = _parse_blocks(lines)
        assert blocks[0]['type'] == 'paragraph' and blocks[0]['number'] == '2.1'
        assert blocks[1] == {
            'type': 'heading', 'level': 2, 'text': 'The Acquisition',
            '_bold': True, '_italic': False,
        }
        assert blocks[2]['type'] == 'paragraph' and blocks[2]['number'] == '2.2'

    def test_no_space_after_paragraph_number(self):
        lines = [_line('2.4.Coles operates...', size=11.04)]
        blocks = _parse_blocks(lines)
        assert blocks[0]['number'] == '2.4'
        assert blocks[0]['text'] == 'Coles operates...'

    def test_continuation_lines_joined(self):
        lines = [
            _line('1.1. First half', size=11.04),
            _line('and second half.', size=11.04),
        ]
        blocks = _parse_blocks(lines)
        assert len(blocks) == 1
        assert blocks[0]['text'] == 'First half and second half.'

    def test_bullet_list(self):
        lines = [
            _line('1.1. The ACCC considers:', size=11.04),
            _line('▪ first point', size=11.04),
            _line('▪ second point', size=11.04),
        ]
        blocks = _parse_blocks(lines)
        assert blocks[1]['type'] == 'bullet_list'
        assert blocks[1]['items'] == ['first point', 'second point']

    def test_lone_bullet_marker_collects_continuation(self):
        # Some bullet markers render on their own line with the body text on
        # the following line; the parser must keep them as a single item.
        lines = [
            _line('▪', size=11.04),
            _line('the bullet body.', size=11.04),
        ]
        blocks = _parse_blocks(lines)
        assert blocks[0]['type'] == 'bullet_list'
        assert blocks[0]['items'] == ['the bullet body.']

    def test_minus_sign_sub_bullet(self):
        # Nested sub-bullets in NOCCs use the minus-sign character.
        lines = [
            _line('1.1. Headline:', size=11.04),
            _line('−', size=11.04),
            _line('first sub-point', size=11.04),
            _line('−', size=11.04),
            _line('second sub-point', size=11.04),
        ]
        blocks = _parse_blocks(lines)
        # Paragraph followed by a bullet list of two items.
        assert blocks[0]['type'] == 'paragraph'
        assert blocks[1]['type'] == 'bullet_list'
        assert blocks[1]['items'] == ['first sub-point', 'second sub-point']

    def test_lettered_list(self):
        lines = [
            _line('1.1. Examples include:', size=11.04),
            _line('(a) first example', size=11.04),
            _line('(b) second example', size=11.04),
        ]
        blocks = _parse_blocks(lines)
        assert blocks[1]['type'] == 'lettered_list'
        assert [it['letter'] for it in blocks[1]['items']] == ['a', 'b']

    def test_two_line_sub_heading_merged(self):
        lines = [
            _line('Reduced competition arising from', size=14.04, bold=True),
            _line('access to rival information', size=14.04, bold=True),
            _line('1.1. Body.', size=11.04),
        ]
        blocks = _parse_blocks(lines)
        # The two adjacent same-style sub-heading lines collapse to one.
        sub_headings = [b for b in blocks if b['type'] == 'heading' and b.get('level') == 2]
        assert len(sub_headings) == 1
        assert sub_headings[0]['text'] == (
            'Reduced competition arising from access to rival information'
        )

    def test_different_style_sub_headings_kept_separate(self):
        # A bold 14pt section heading immediately followed by an unbold 14pt
        # sub-sub-heading must stay distinct.
        lines = [
            _line('Industry background – grocery retailing', size=14.04, bold=True),
            _line('Grocery retailing in Australia', size=14.04, bold=False),
        ]
        blocks = _parse_blocks(lines)
        sub_headings = [b for b in blocks if b['type'] == 'heading']
        assert len(sub_headings) == 2
        assert sub_headings[0]['text'] == 'Industry background – grocery retailing'
        assert sub_headings[1]['text'] == 'Grocery retailing in Australia'


# ---------------------------------------------------------------------------
# parse_nocc: _group_blocks_into_sections
# ---------------------------------------------------------------------------

class TestGroupBlocksIntoSections:
    def test_groups_under_top_level_headings(self):
        blocks = [
            {'type': 'heading', 'level': 1, 'text': '1. Introduction'},
            {'type': 'paragraph', 'number': '1.1', 'text': 'First.'},
            {'type': 'heading', 'level': 1, 'text': '2. Background'},
            {'type': 'paragraph', 'number': '2.1', 'text': 'Second.'},
        ]
        sections = _group_blocks_into_sections(blocks)
        assert len(sections) == 2
        assert sections[0]['number'] == '1'
        assert sections[0]['title'] == 'Introduction'
        assert sections[0]['blocks'][0]['number'] == '1.1'
        assert sections[1]['number'] == '2'
        assert sections[1]['title'] == 'Background'

    def test_strips_internal_heading_level_and_style_fields(self):
        blocks = [
            {'type': 'heading', 'level': 1, 'text': '1. Introduction'},
            {
                'type': 'heading', 'level': 2, 'text': 'A sub-heading',
                '_bold': True, '_italic': False,
            },
            {'type': 'paragraph', 'number': '1.1', 'text': 'Body.'},
        ]
        sections = _group_blocks_into_sections(blocks)
        sub = sections[0]['blocks'][0]
        # Internal level and style markers are dropped from the public output.
        assert sub == {'type': 'heading', 'text': 'A sub-heading'}

    def test_preamble_kept_when_blocks_precede_first_section(self):
        blocks = [
            {'type': 'paragraph', 'text': 'Stray preamble.'},
            {'type': 'heading', 'level': 1, 'text': '1. Introduction'},
            {'type': 'paragraph', 'number': '1.1', 'text': 'Body.'},
        ]
        sections = _group_blocks_into_sections(blocks)
        assert len(sections) == 2
        assert sections[0]['number'] is None
        assert sections[0]['blocks'][0]['text'] == 'Stray preamble.'
        assert sections[1]['number'] == '1'


# ---------------------------------------------------------------------------
# enrichment: has_nocc flag
# ---------------------------------------------------------------------------

class TestEnrichMergerNocc:
    def _base_merger(self):
        return {
            'merger_id': 'MN-01068',
            'merger_name': 'Test Merger',
            'accc_determination': None,
            'determination_publication_date': None,
            'stage': 'Phase 2',
            'status': 'Under assessment',
            'events': [],
            'effective_notification_datetime': '2025-11-27T12:00:00Z',
        }

    def test_flag_set_when_sections_present(self):
        m = self._base_merger()
        nocc = {'MN-01068': {'sections': [{'number': '1', 'title': 'Introduction', 'blocks': []}]}}
        result = enrich_merger(m, nocc_data=nocc)
        assert result.get('has_nocc') is True

    def test_no_flag_when_nocc_data_missing(self):
        m = self._base_merger()
        result = enrich_merger(m, nocc_data={})
        assert 'has_nocc' not in result

    def test_no_flag_when_merger_not_in_nocc_data(self):
        m = self._base_merger()
        result = enrich_merger(m, nocc_data={'MN-99999': {'sections': [{'blocks': []}]}})
        assert 'has_nocc' not in result

    def test_no_flag_when_sections_empty(self):
        m = self._base_merger()
        result = enrich_merger(m, nocc_data={'MN-01068': {'sections': []}})
        assert 'has_nocc' not in result

    def test_nocc_data_not_embedded(self):
        m = self._base_merger()
        nocc = {'MN-01068': {'sections': [{'number': '1', 'title': 'Introduction', 'blocks': []}]}}
        result = enrich_merger(m, nocc_data=nocc)
        # Only a flag is added; the parsed content is loaded separately.
        assert 'sections' not in result
        assert 'nocc' not in result


# ---------------------------------------------------------------------------
# generate_static_data: NOCC files
# ---------------------------------------------------------------------------

class TestGenerateNoccFiles:
    def test_generates_files(self, tmp_path):
        nocc_data = {
            'MN-01068': {
                'title': 'Coles – Kalgoorlie',
                'matter_id': 'MN-01068',
                'document_type': 'Notice of Competition Concerns – Summary',
                'date': '5 March 2026',
                'date_iso': '2026-03-05',
                'file_name': 'NOCC.pdf',
                'file_path': 'matters/MN-01068/NOCC.pdf',
                'sections': [
                    {'number': '1', 'title': 'Introduction', 'blocks': [
                        {'type': 'paragraph', 'number': '1.1', 'text': 'Body.'},
                    ]},
                ],
            },
        }
        count = generate_nocc_files(nocc_data, tmp_path)
        assert count == 1
        nocc_path = tmp_path / 'noccs' / 'MN-01068.json'
        assert nocc_path.exists()

        import json
        with open(nocc_path) as f:
            data = json.load(f)
        assert data['title'] == 'Coles – Kalgoorlie'
        assert data['date_iso'] == '2026-03-05'
        assert len(data['sections']) == 1
        assert data['sections'][0]['number'] == '1'

    def test_skips_entries_without_sections(self, tmp_path):
        nocc_data = {
            'MN-01068': {'sections': [{'number': '1', 'title': 'X', 'blocks': []}]},
            'MN-01069': {'sections': []},
            'MN-01070': {'error': 'parse failed', 'file_path': 'matters/MN-01070/x.pdf'},
        }
        count = generate_nocc_files(nocc_data, tmp_path)
        assert count == 1
        assert (tmp_path / 'noccs' / 'MN-01068.json').exists()
        assert not (tmp_path / 'noccs' / 'MN-01069.json').exists()
        assert not (tmp_path / 'noccs' / 'MN-01070.json').exists()

    def test_prunes_file_for_a_matter_with_no_nocc_left(self, tmp_path):
        (tmp_path / 'noccs').mkdir(parents=True)
        (tmp_path / 'noccs' / 'MN-09999.json').write_text('{}')
        nocc_data = {
            'MN-01068': {'sections': [{'number': '1', 'title': 'X', 'blocks': []}]},
        }
        generate_nocc_files(nocc_data, tmp_path)
        assert not (tmp_path / 'noccs' / 'MN-09999.json').exists()
        assert (tmp_path / 'noccs' / 'MN-01068.json').exists()

    def test_empty_data(self, tmp_path):
        # Nothing written means nothing pruned — an empty load must not wipe
        # the directory.
        (tmp_path / 'noccs').mkdir(parents=True)
        (tmp_path / 'noccs' / 'MN-01068.json').write_text('{}')
        assert generate_nocc_files({}, tmp_path) == 0
        assert (tmp_path / 'noccs' / 'MN-01068.json').exists()


# ---------------------------------------------------------------------------
# extract_mergers: _extract_anzsic_codes
# ---------------------------------------------------------------------------

class TestExtractAnzsicCodes:
    def test_legacy_field_class(self):
        html = (
            '<div class="field field--name-field-acquisition-anzsic-code '
            'field--type-string field--label-inline clearfix">'
            '<h3 class="field__label">ANZSIC code(s)</h3>'
            '<div class="field__item">5420  Software Publishing;'
            '           6240  Financial Asset Investing</div></div>'
        )
        codes = _extract_anzsic_codes(BeautifulSoup(html, 'html.parser'))
        assert codes == [
            {'code': '5420', 'name': 'Software Publishing'},
            {'code': '6240', 'name': 'Financial Asset Investing'},
        ]

    def test_current_acccgov_field_class(self):
        # The ACCC renamed the field to 'field-acccgov-anzsic-code'.
        html = (
            '<div class="field field--name-field-acccgov-anzsic-code '
            'field--type-entity-reference field--label-inline '
            'field--type-entity-reference--taxonomy_term clearfix">'
            '<h3 class="field__label">ANZSIC code(s)</h3>'
            '<div class="field__item">5420 Software Publishing;'
            '           6240 Financial Asset Investing</div></div>'
        )
        codes = _extract_anzsic_codes(BeautifulSoup(html, 'html.parser'))
        assert codes == [
            {'code': '5420', 'name': 'Software Publishing'},
            {'code': '6240', 'name': 'Financial Asset Investing'},
        ]

    def test_no_anzsic_field(self):
        html = '<div class="field field--name-field-other">nothing here</div>'
        assert _extract_anzsic_codes(BeautifulSoup(html, 'html.parser')) == []


# ---------------------------------------------------------------------------
# extract_mergers: _extract_dates_and_status (accc_determination_raw capture)
# ---------------------------------------------------------------------------

class TestExtractDatesAndStatusDeterminationRaw:
    def _soup(self, determination_text):
        html = (
            '<div class="field field--name-field-acccgov-acquisition-deter">'
            f'{determination_text}</div>'
        )
        return BeautifulSoup(html, 'html.parser')

    def test_captures_raw_when_it_differs_from_normalized(self):
        soup = self._soup('ACCC Determination Approved subject to conditions')
        data = _extract_dates_and_status(soup, 'MN-01000', None)
        assert data['accc_determination'] == 'Approved'
        assert data['accc_determination_raw'] == 'ACCC Determination Approved subject to conditions'

    def test_no_raw_field_when_identical_to_normalized(self):
        soup = self._soup('Approved')
        data = _extract_dates_and_status(soup, 'MN-01000', None)
        assert data['accc_determination'] == 'Approved'
        assert 'accc_determination_raw' not in data


# ---------------------------------------------------------------------------
# extract_mergers: _calculate_missing_end_of_determination_period
# ---------------------------------------------------------------------------

class TestCalculateMissingEndOfDeterminationPeriod:
    """BD 1 of the review period is the day after notification, but
    add_business_days counts its start date as day 1 - the fallback must
    compensate for that mismatch (issue #576)."""

    def test_computed_end_is_exactly_30_business_days_after_notification(self):
        merger_data = {
            'effective_notification_datetime': '2026-05-19T12:00:00Z',
        }
        _calculate_missing_end_of_determination_period(merger_data, 'MN-30008')
        assert calculate_business_days(
            '2026-05-19T12:00:00Z', merger_data['end_of_determination_period']
        ) == 30

    def test_skips_waiver_mergers(self):
        merger_data = {'effective_notification_datetime': '2026-05-19T12:00:00Z'}
        _calculate_missing_end_of_determination_period(merger_data, 'WA-00001')
        assert 'end_of_determination_period' not in merger_data

    def test_does_not_overwrite_existing_value(self):
        merger_data = {
            'effective_notification_datetime': '2026-05-19T12:00:00Z',
            'end_of_determination_period': '2026-07-01T12:00:00Z',
        }
        _calculate_missing_end_of_determination_period(merger_data, 'MN-30008')
        assert merger_data['end_of_determination_period'] == '2026-07-01T12:00:00Z'


# ---------------------------------------------------------------------------
# extract_mergers: consultation section, old and new ACCC page formats
# ---------------------------------------------------------------------------

# Markup the ACCC used until Aug 2026: a prose blurb carrying the deadline, and
# a document table sharing the "Decisions and key events" markup.
OLD_FORMAT_CONSULTATION = '''
<div>
  <h3 class="border-bottom">Consultation</h3>
  <div class="field field--name-field-acccgov-consultation-text field--type-text-long
              field--label-hidden clearfix text-formatted field__item">
    <p>The ACCC has prepared a questionnaire on the Acquisition. Submissions
       should be provided by <strong>21 August 2026</strong> via email.</p>
  </div>
  <div class="field field--name-field-acccgov-consultations table-responsive field__items">
    <table class="table table-striped"><tbody>
      <tr>
        <td class="acccgov-timeline__date"><time datetime="2026-08-14T12:00:00Z">14 Aug 2026</time></td>
        <td>Incubeta - Datisan - Questionnaire</td>
        <td class="acccgov-timeline__file-link">
          <a href="/system/files/public-merger-register/documents/Incubeta%20-%20Datisan%20-%20Questionnaire.docx">Attachment</a>
        </td>
      </tr>
    </tbody></table>
  </div>
</div>
'''

# Markup rolled out from Aug 2026 (MN-40039 among the first): the document table
# is gone and the questionnaire hangs off a structured consultation paragraph.
NEW_FORMAT_CONSULTATION = '''
<div>
  <h3 class="border-bottom">Consultation</h3>
  <h4><div class="field field--name-field-accc-header field--type-string
                  field--label-hidden field__item">Incubeta - Datisan - Questionnaire</div></h4>
  <div class="field field--name-field-acccgov-description field--type-text-long
              field--label-hidden clearfix text-formatted field__item">
    <p>The ACCC has prepared a questionnaire on the Acquisition. Submissions
       should be provided by <strong>21 August 2026</strong> via email.</p>
  </div>
  <div class="field field--label-inline clearfix">
    <div class="field__label">Status</div>
    <div class="field__item">Open</div>
  </div>
  <div class="field field--name-field-acccgov-consult-open-date field--type-datetime
              field--label-inline clearfix">
    <div class="field__label">Open date</div>
    <div class="field__item"><time datetime="2026-08-14T12:00:00Z">14 Aug 2026</time></div>
  </div>
  <div class="field field--name-field-acccgov-consult-close-date field--type-datetime
              field--label-inline clearfix">
    <div class="field__label">Closing date</div>
    <div class="field__item"><time datetime="2026-08-22T12:00:00Z">22 Aug 2026</time></div>
  </div>
  <div class="field field--label-inline">
    <div class="field__label">Questionnaire</div>
    <div class="paragraph paragraph--type--acccgov-questionnaire paragraph--view-mode--default">
      <div class="field field--name-field-acccgov-file field__item">
        <div class="field field--name-file field--type-file field--label-hidden field__item">
          <a href="/system/files/moderated_files/Incubeta%20-%20Datisan%20-%20Questionnaire_0.docx">Attachment</a>
        </div>
      </div>
    </div>
  </div>
</div>
'''

QUESTIONNAIRE_DOCUMENTS_URL = (
    'https://www.accc.gov.au/system/files/public-merger-register/documents/'
    'Incubeta%20-%20Datisan%20-%20Questionnaire.docx'
)
QUESTIONNAIRE_MODERATED_URL = (
    'https://www.accc.gov.au/system/files/moderated_files/'
    'Incubeta%20-%20Datisan%20-%20Questionnaire_0.docx'
)


def _soup(html):
    return BeautifulSoup(html, 'html.parser')


class TestExtractConsultations:
    def test_new_format_is_parsed(self):
        consultations = _extract_consultations(_soup(NEW_FORMAT_CONSULTATION))
        assert len(consultations) == 1
        assert consultations[0] == {
            'title': 'Incubeta - Datisan - Questionnaire',
            'description': consultations[0]['description'],
            'status': 'Open',
            'open_date': '2026-08-14T12:00:00Z',
            'close_date': '2026-08-22T12:00:00Z',
            'document_url': QUESTIONNAIRE_MODERATED_URL,
        }
        assert '21 August 2026' in consultations[0]['description']

    def test_old_format_yields_nothing(self):
        # The old markup has no structured consultation to read; its
        # questionnaire is picked up by the document-table scraper instead.
        assert _extract_consultations(_soup(OLD_FORMAT_CONSULTATION)) == []

    def test_page_without_a_consultation_section(self):
        assert _extract_consultations(_soup('<div><h3 class="border-bottom">Status</h3></div>')) == []

    def test_multiple_consultations_are_split_at_each_header(self):
        second = (NEW_FORMAT_CONSULTATION
                  .split('<h3 class="border-bottom">Consultation</h3>')[1]
                  .rsplit('</div>', 1)[0]
                  .replace('2026-08-22T12:00:00Z', '2026-09-30T12:00:00Z')
                  .replace('Questionnaire_0.docx', 'Questionnaire_1.docx')
                  .replace('Incubeta - Datisan - Questionnaire</div></h4>',
                           'Incubeta - Datisan - Remedy questionnaire</div></h4>'))
        html = NEW_FORMAT_CONSULTATION.rsplit('</div>', 1)[0] + second + '</div>'
        consultations = _extract_consultations(_soup(html))
        assert [c['title'] for c in consultations] == [
            'Incubeta - Datisan - Questionnaire',
            'Incubeta - Datisan - Remedy questionnaire',
        ]
        assert [c['close_date'] for c in consultations] == [
            '2026-08-22T12:00:00Z', '2026-09-30T12:00:00Z',
        ]


class TestExtractConsultationDate:
    def test_new_format_uses_the_closing_date_field(self):
        assert _extract_consultation_date(_soup(NEW_FORMAT_CONSULTATION), None) == {
            'consultation_response_due_date': '2026-08-22T12:00:00Z'
        }

    def test_old_format_still_reads_the_deadline_from_prose(self):
        assert _extract_consultation_date(_soup(OLD_FORMAT_CONSULTATION), None) == {
            'consultation_response_due_date': '2026-08-21T12:00:00Z'
        }

    def test_new_format_falls_back_to_prose_when_closing_date_is_empty(self):
        html = NEW_FORMAT_CONSULTATION.replace(
            '<time datetime="2026-08-22T12:00:00Z">22 Aug 2026</time>', '')
        assert _extract_consultation_date(_soup(html), None) == {
            'consultation_response_due_date': '2026-08-21T12:00:00Z'
        }

    def test_existing_value_is_preserved_once_the_section_disappears(self):
        # The ACCC now deletes the whole consultation section when it closes.
        existing = {'consultation_response_due_date': '2026-08-22T12:00:00Z'}
        assert _extract_consultation_date(_soup('<div></div>'), existing) == existing


class TestScrapeConsultationEvents:
    """The new consultation section must yield the same timeline event the old
    document table did, so the download, DOCX→PDF conversion, questionnaire
    parsing and frontend all keep working unchanged."""

    def _scrape(self, html, monkeypatch):
        monkeypatch.setattr(extract_mergers, 'download_attachment',
                            lambda *a, **k: None)
        return _scrape_events(_soup(html), 'MN-05043')

    def test_new_format_yields_a_questionnaire_event(self, monkeypatch):
        events = self._scrape(NEW_FORMAT_CONSULTATION, monkeypatch)
        assert len(events) == 1
        event = events[0]
        assert event['date'] == '2026-08-14T12:00:00Z'
        assert event['title'] == 'Incubeta - Datisan - Questionnaire'
        assert event['url'] == QUESTIONNAIRE_MODERATED_URL
        assert event['url_gh'] == '/mergers/MN-05043/Incubeta - Datisan - Questionnaire_0.pdf'
        assert event['status'] == 'live'
        assert event['is_questionnaire_event'] is True

    def test_old_format_is_unchanged_and_unflagged(self, monkeypatch):
        events = self._scrape(OLD_FORMAT_CONSULTATION, monkeypatch)
        assert len(events) == 1
        assert events[0]['url'] == QUESTIONNAIRE_DOCUMENTS_URL
        assert 'is_questionnaire_event' not in events[0]

    def test_a_consultation_without_a_document_yields_no_event(self, monkeypatch):
        html = NEW_FORMAT_CONSULTATION.replace('paragraph--type--acccgov-questionnaire', 'x')
        assert self._scrape(html, monkeypatch) == []

    def test_a_page_carrying_both_formats_yields_one_event(self, monkeypatch):
        # Not expected during the rollout, but the same document must never be
        # scraped twice if a page ever renders both.
        both = OLD_FORMAT_CONSULTATION + NEW_FORMAT_CONSULTATION
        events = self._scrape(both, monkeypatch)
        assert len(events) == 1
        assert events[0]['url'] == QUESTIONNAIRE_DOCUMENTS_URL


class TestMergeConsultationQuestionnaireEvents:
    """The questionnaire moved to a new URL — and sometimes a new title and
    date — when a page switched format. The existing event must be re-bound to
    it rather than left 'removed' beside a duplicate."""

    def _existing(self, title='Incubeta - Datisan - Questionnaire',
                  date='2026-08-14T12:00:00Z'):
        return {
            'events': [{
                'date': date,
                'title': title,
                'display_title': title,
                'url': QUESTIONNAIRE_DOCUMENTS_URL,
                'url_gh': '/mergers/MN-05043/Incubeta - Datisan - Questionnaire.pdf',
                'status': 'removed',
            }],
        }

    def _scraped(self, title='Incubeta - Datisan - Questionnaire',
                 date='2026-08-14T12:00:00Z'):
        return [{
            'date': date,
            'title': title,
            'display_title': title,
            'url': QUESTIONNAIRE_MODERATED_URL,
            'url_gh': '/mergers/MN-05043/Incubeta - Datisan - Questionnaire_0.pdf',
            'status': 'live',
            'is_questionnaire_event': True,
        }]

    def test_rebinds_to_the_new_url(self):
        merged = _merge_events(self._scraped(), self._existing(), 'MN-05043', set())
        assert len(merged) == 1
        assert merged[0]['url'] == QUESTIONNAIRE_MODERATED_URL
        assert merged[0]['status'] == 'live'

    def test_rebinds_when_the_consultation_was_retitled_and_redated(self):
        # MN-45024 ("Questionnaire - OEConnection - Epyx" became
        # "OEConnection-Epyx - Phase 1 consultation") and MN-05046 (open date
        # moved two days): neither title nor date survives the move.
        merged = _merge_events(
            self._scraped(title='Incubeta-Datisan - Phase 1 consultation',
                          date='2026-08-21T12:00:00Z'),
            self._existing(), 'MN-05043', set(),
        )
        assert len(merged) == 1
        assert merged[0]['url'] == QUESTIONNAIRE_MODERATED_URL
        assert merged[0]['display_title'] == 'Incubeta - Datisan - Questionnaire'

    def test_a_different_document_is_not_rebound(self):
        scraped = self._scraped()
        scraped[0]['url'] = (
            'https://www.accc.gov.au/system/files/moderated_files/'
            'Incubeta%20-%20Datisan%20-%20Remedy%20questionnaire.docx'
        )
        scraped[0]['title'] = 'Incubeta - Datisan - Remedy questionnaire'
        scraped[0]['date'] = '2026-09-25T12:00:00Z'
        merged = _merge_events(scraped, self._existing(), 'MN-05043', set())
        assert len(merged) == 2

    def test_filename_matching_is_scoped_to_consultation_events(self):
        # An ordinary timeline document keeps the stricter title+date rule, so
        # a same-named file on a different date stays a separate event.
        scraped = self._scraped(title='Some other document', date='2026-09-25T12:00:00Z')
        del scraped[0]['is_questionnaire_event']
        merged = _merge_events(scraped, self._existing(), 'MN-05043', set())
        assert len(merged) == 2


# ---------------------------------------------------------------------------
# Attachment rows the ACCC leaves undated and untitled
# ---------------------------------------------------------------------------

BLANK_ROW_DOCUMENT_TABLE = '''
<div class="table-responsive">
  <table>
    <tbody>
      <tr>
        <td class="acccgov-timeline__date"></td>
        <td></td>
        <td class="acccgov-timeline__file-link">
          <a href="/system/files/public-merger-register/documents/AbbVie%20-%20Apogee%20-%20Questionnaire_0.docx">Attachment</a>
        </td>
      </tr>
    </tbody>
  </table>
</div>
'''


class TestScrapeEventsBlankRow:
    """MN-90027's questionnaire was re-uploaded into a row whose date and title
    cells were both empty. A titleless event renders as a blank timeline row and
    is invisible to every title-based check downstream, so the row is named
    after the document it links to."""

    def _scrape(self, html, monkeypatch):
        monkeypatch.setattr(extract_mergers, 'download_attachment',
                            lambda *a, **k: None)
        return _scrape_events(_soup(html), 'MN-90027')

    def test_a_blank_row_is_named_after_its_attachment(self, monkeypatch):
        events = self._scrape(BLANK_ROW_DOCUMENT_TABLE, monkeypatch)
        assert len(events) == 1
        event = events[0]
        # The extension and the CMS re-upload suffix are dropped, leaving the
        # title the same document carried before it was re-uploaded.
        assert event['title'] == 'AbbVie - Apogee - Questionnaire'
        assert event['display_title'] == 'AbbVie - Apogee - Questionnaire'
        assert event['date'] == ''
        assert event['url'].endswith('AbbVie%20-%20Apogee%20-%20Questionnaire_0.docx')

    def test_a_row_with_neither_title_nor_attachment_is_not_an_event(self, monkeypatch):
        html = BLANK_ROW_DOCUMENT_TABLE.replace(
            '<td class="acccgov-timeline__file-link">', '<td class="x">')
        assert self._scrape(html, monkeypatch) == []

    def test_a_titled_row_keeps_its_own_title(self, monkeypatch):
        html = BLANK_ROW_DOCUMENT_TABLE.replace(
            '<td></td>', '<td>AbbVie - Apogee - Phase 1 determination</td>')
        events = self._scrape(html, monkeypatch)
        assert events[0]['title'] == 'AbbVie - Apogee - Phase 1 determination'


class TestMergeEventsRelocatedDocument:
    """A re-upload whose title no longer matches must re-bind to its event
    rather than be appended beside it as a duplicate.

    MN-90027: the questionnaire came back as "..._0.docx" in an undated row, so
    the scraped event carried no title+date identity at all.
    MN-90008: the remedy offer moved to /system/files/moderated_files/ and was
    re-titled on the way ("Black Rhino - Club Hotel - Remedy Offer - 9 July
    2026" -> "Black Rhino - Club Hotel Motel Roma - Remedy Offer")."""

    TITLE = 'AbbVie - Apogee - Questionnaire'
    OLD_URL = ('https://www.accc.gov.au/system/files/public-merger-register/'
               'documents/AbbVie%20-%20Apogee%20-%20Questionnaire.docx')
    NEW_URL = ('https://www.accc.gov.au/system/files/public-merger-register/'
               'documents/AbbVie%20-%20Apogee%20-%20Questionnaire_0.docx')

    def _existing(self):
        return {
            'events': [{
                'date': '2026-07-28T12:00:00Z',
                'title': self.TITLE,
                'display_title': self.TITLE,
                'url': self.OLD_URL,
                'url_gh': '/mergers/MN-90027/AbbVie - Apogee - Questionnaire.pdf',
                'status': 'live',
            }],
        }

    def _scraped(self, **extra):
        event = {
            'date': '',
            'title': self.TITLE,
            'display_title': self.TITLE,
            'url': self.NEW_URL,
            'url_gh': '/mergers/MN-90027/AbbVie - Apogee - Questionnaire_0.pdf',
            'status': 'live',
        }
        event.update(extra)
        return [event]

    def test_rebinds_to_the_reuploaded_url(self):
        merged = _merge_events(self._scraped(), self._existing(), 'MN-90027', set())
        assert len(merged) == 1, 'no duplicate should be created'
        assert merged[0]['url'] == self.NEW_URL
        assert merged[0]['status'] == 'live'

    def test_the_existing_date_and_display_title_survive(self):
        # The re-upload is undated, so the date already recorded for the event
        # is the only one there is; it must not be replaced with the blank.
        merged = _merge_events(self._scraped(date='', title='', display_title=''),
                               self._existing(), 'MN-90027', set())
        assert len(merged) == 1
        assert merged[0]['display_title'] == self.TITLE

    # MN-90008's remedy offer: the same file, on the same date, re-titled and
    # moved out of /documents/ into /moderated_files/.
    RELOCATED_URL = ('https://www.accc.gov.au/system/files/moderated_files/'
                     'AbbVie%20-%20Apogee%20-%20Questionnaire.docx')

    def test_rebinds_a_retitled_document_that_moved_directory(self):
        merged = _merge_events(
            self._scraped(date='2026-07-28T12:00:00Z',
                          title='AbbVie - Apogee - Phase 1 consultation',
                          url=self.RELOCATED_URL),
            self._existing(), 'MN-90027', set(),
        )
        assert len(merged) == 1
        assert merged[0]['url'] == self.RELOCATED_URL

    def test_a_retitled_reupload_that_stayed_put_is_a_separate_event(self):
        # Within one directory the filename is too weak a signal to override
        # the title: "X.pdf" and "X_5.pdf" normalise alike, so a re-upload
        # there keeps the stricter title+date rule.
        merged = _merge_events(
            self._scraped(date='2026-07-28T12:00:00Z',
                          title='Some other document'),
            self._existing(), 'MN-90027', set(),
        )
        assert len(merged) == 2

    def test_the_date_still_has_to_agree(self):
        # The filename fallback is kept honest by the date: a same-named
        # document on another date is a separate timeline entry.
        merged = _merge_events(
            self._scraped(date='2026-09-25T12:00:00Z', title='Some other document'),
            self._existing(), 'MN-90027', set(),
        )
        assert len(merged) == 2

    def test_a_stale_removed_copy_is_dropped_once_the_live_one_exists(self):
        # MN-90008's shape: data already carries both the 'removed' copy under
        # the old URL and the re-titled 'live' copy under the relocated one.
        relocated = self._scraped(date='2026-07-28T12:00:00Z',
                                  title='AbbVie - Apogee - Phase 1 consultation',
                                  url=self.RELOCATED_URL)
        existing = self._existing()
        existing['events'][0]['status'] = 'removed'
        existing['events'].append(relocated[0])
        merged = _merge_events(relocated, existing, 'MN-90027', set())
        assert len(merged) == 1
        assert merged[0]['url'] == self.RELOCATED_URL
        assert merged[0]['status'] == 'live'

    def test_a_different_undated_document_is_not_rebound(self):
        merged = _merge_events(
            self._scraped(url=('https://www.accc.gov.au/system/files/'
                               'public-merger-register/documents/'
                               'AbbVie%20-%20Apogee%20-%20Remedy.docx')),
            self._existing(), 'MN-90027', set(),
        )
        assert len(merged) == 2
