"""Tests for the semantic-embedding chunker.

We don't load sentence-transformers here — only the pure-Python chunking
logic is exercised. That logic is the part most likely to break as the ACCC
varies its determination-table layout.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from embed import (
    MIN_CHUNK_CHARS,
    _classify_item,
    _clean_text,
    build_chunks,
)


class TestClassifyItem:
    def test_known_items_map_to_canonical_sections(self):
        assert _classify_item("Notified acquisition") == "overview"
        assert _classify_item("Acquisition") == "overview"
        assert _classify_item("Parties to the Acquisition") == "parties"
        assert _classify_item("Parties to the\nAcquisition") == "parties"
        assert _classify_item("Overlap and relationship\nbetween the parties") == "overlap"
        assert _classify_item("Overlap between the\nparties") == "overlap"
        assert _classify_item("Relationship between the\nparties") == "overlap"
        assert _classify_item("Explanation for\ndetermination") == "reasons"
        assert _classify_item("Reasons for determination") == "reasons"
        assert _classify_item("Industry background") == "industry_background"

    def test_skipped_items_return_none(self):
        assert _classify_item("Date of determination") is None
        assert _classify_item("Applications for review") is None
        assert _classify_item("Determination") is None

    def test_unknown_item_returns_none(self):
        assert _classify_item("Some random row") is None
        assert _classify_item("") is None

    def test_malformed_explanation_rows_still_classify(self):
        # ACCC tables sometimes leak bullet markers / numbering into the item
        # column ("Explanation for\ndetermination\n•"). These should still
        # resolve to ``reasons`` via the prefix fallback.
        assert _classify_item("Explanation for\ndetermination\n•") == "reasons"
        assert _classify_item("Explanation for\ndetermination\n1.\n2.") == "reasons"


class TestCleanText:
    def test_collapses_whitespace_runs_within_lines(self):
        assert _clean_text("foo    bar\t\tbaz") == "foo bar baz"

    def test_preserves_paragraph_breaks(self):
        assert _clean_text("para 1\n\npara 2") == "para 1\n\npara 2"

    def test_collapses_three_or_more_blank_lines(self):
        assert _clean_text("a\n\n\n\nb") == "a\n\nb"

    def test_handles_empty_input(self):
        assert _clean_text("") == ""
        assert _clean_text(None) == ""


def _merger(
    merger_id="MN-00001",
    description="A long enough merger description that easily clears the minimum chunk threshold for embedding.",
    table=None,
    acquirers=None,
    targets=None,
    anzsic=None,
    determination="Approved",
    pub_date="2025-09-05T12:00:00Z",
):
    events = []
    if table is not None:
        events.append({"determination_table_content": table})
    return {
        "merger_id": merger_id,
        "merger_name": f"{merger_id} test merger",
        "merger_description": description,
        "acquirers": acquirers or [{"name": "Acquirer Co"}],
        "targets": targets or [{"name": "Target Co"}],
        "other_parties": [],
        "anzsic_codes": anzsic or [{"code": "121", "name": "Beverage Manufacturing"}],
        "accc_determination": determination,
        "determination_publication_date": pub_date,
        "events": events,
    }


class TestBuildChunks:
    def test_full_determination_produces_one_chunk_per_section(self):
        long = "x" * (MIN_CHUNK_CHARS + 10)
        merger = _merger(table=[
            {"item": "Notified acquisition", "details": long},
            {"item": "Parties to the\nAcquisition", "details": long},
            {"item": "Overlap between the\nparties", "details": long},
            {"item": "Explanation for\ndetermination", "details": long},
            {"item": "Date of determination", "details": "5 September 2025"},
        ])
        chunks = build_chunks([merger])
        sections = {c["section"] for c in chunks}
        assert sections == {"overview", "parties", "overlap", "reasons"}

    def test_short_chunks_are_skipped(self):
        merger = _merger(description="too short", table=[
            {"item": "Notified acquisition", "details": "tiny"},
        ])
        # Both the description and the table row are below MIN_CHUNK_CHARS,
        # and they get merged into ``overview`` — the merged text is still
        # short, so the merger drops out entirely.
        assert build_chunks([merger]) == []

    def test_merger_with_no_table_falls_back_to_description(self):
        merger = _merger(table=None)
        chunks = build_chunks([merger])
        assert len(chunks) == 1
        assert chunks[0]["section"] == "overview"
        assert chunks[0]["merger_id"] == "MN-00001"

    def test_metadata_is_attached_to_each_chunk(self):
        long = "x" * (MIN_CHUNK_CHARS + 10)
        merger = _merger(table=[{"item": "Explanation for\ndetermination", "details": long}])
        chunk = build_chunks([merger])[0]
        assert chunk["merger_name"] == "MN-00001 test merger"
        assert chunk["parties"] == ["Acquirer Co", "Target Co"]
        assert chunk["industry"] == [{"code": "121", "name": "Beverage Manufacturing"}]
        assert chunk["outcome"] == "Approved"
        assert chunk["date"] == "2025-09-05"
        assert chunk["year"] == 2025

    def test_repeated_section_rows_are_combined(self):
        long = "y" * (MIN_CHUNK_CHARS + 10)
        merger = _merger(description="", table=[
            {"item": "Overlap between the\nparties", "details": long},
            {"item": "Relationship between the\nparties", "details": long},
        ])
        chunks = [c for c in build_chunks([merger]) if c["section"] == "overlap"]
        assert len(chunks) == 1

    def test_merger_without_id_is_skipped(self):
        merger = _merger()
        merger["merger_id"] = None
        assert build_chunks([merger]) == []

    def test_description_is_prepended_to_overview(self):
        long_desc = "DESC " * 20
        long_row = "ROW " * 20
        merger = _merger(description=long_desc, table=[
            {"item": "Notified acquisition", "details": long_row},
        ])
        overview = next(c for c in build_chunks([merger]) if c["section"] == "overview")
        # Description appears before the row text in the combined chunk.
        # We can't see the text in the test (build_chunks keeps it though),
        # so check ordering via index lookup.
        assert overview["text"].index("DESC") < overview["text"].index("ROW")
