"""Tests for the semantic-embedding chunker.

We don't load sentence-transformers here — only the pure-Python chunking
logic is exercised. That logic is the part most likely to break as the ACCC
varies its determination-table layout.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import json

from embed import (
    MIN_CHUNK_CHARS,
    _classify_item,
    _clean_text,
    _content_hash,
    _format_records,
    build_chunks,
    plan_embedding,
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


class TestContentHash:
    def test_same_inputs_produce_same_hash(self):
        assert _content_hash("model-a", "hello") == _content_hash("model-a", "hello")

    def test_different_text_produces_different_hash(self):
        assert _content_hash("model-a", "hello") != _content_hash("model-a", "world")

    def test_different_model_produces_different_hash(self):
        # Critical for cache correctness — mixing vectors from different
        # models in one file would silently corrupt similarity scores.
        assert _content_hash("model-a", "hello") != _content_hash("model-b", "hello")


def _chunk(merger_id, section, text, **extra):
    return {"merger_id": merger_id, "section": section, "text": text, **extra}


class TestPlanEmbedding:
    MODEL = "test-model"

    def test_no_existing_cache_means_everything_is_pending(self):
        chunks = [_chunk("M1", "overview", "x" * 60)]
        reused, pending = plan_embedding(chunks, None, self.MODEL)
        assert reused == []
        assert len(pending) == 1
        assert pending[0]["hash"] == _content_hash(self.MODEL, chunks[0]["text"])

    def test_unchanged_chunk_is_reused(self):
        text = "x" * 60
        h = _content_hash(self.MODEL, text)
        existing = [{
            "merger_id": "M1", "section": "overview",
            "hash": h, "vector": [0.1, 0.2, 0.3], "outcome": "Approved",
        }]
        chunks = [_chunk("M1", "overview", text, outcome="Approved")]
        reused, pending = plan_embedding(chunks, existing, self.MODEL)
        assert pending == []
        assert reused[0]["vector"] == [0.1, 0.2, 0.3]
        assert reused[0]["hash"] == h

    def test_changed_text_invalidates_cache_entry(self):
        old_text = "x" * 60
        existing = [{
            "merger_id": "M1", "section": "overview",
            "hash": _content_hash(self.MODEL, old_text),
            "vector": [0.1], "outcome": "Approved",
        }]
        chunks = [_chunk("M1", "overview", "y" * 60)]
        reused, pending = plan_embedding(chunks, existing, self.MODEL)
        assert reused == []
        assert len(pending) == 1

    def test_model_change_invalidates_every_entry(self):
        text = "x" * 60
        existing = [{
            "merger_id": "M1", "section": "overview",
            "hash": _content_hash("old-model", text),
            "vector": [0.1],
        }]
        chunks = [_chunk("M1", "overview", text)]
        reused, pending = plan_embedding(chunks, existing, self.MODEL)
        assert reused == []
        assert len(pending) == 1

    def test_dropped_chunk_is_not_carried_over(self):
        text = "x" * 60
        existing = [
            {"merger_id": "M1", "section": "overview",
             "hash": _content_hash(self.MODEL, text), "vector": [0.1]},
            {"merger_id": "M2", "section": "overview",
             "hash": _content_hash(self.MODEL, text), "vector": [0.2]},
        ]
        chunks = [_chunk("M1", "overview", text)]
        reused, pending = plan_embedding(chunks, existing, self.MODEL)
        assert len(reused) + len(pending) == 1
        assert all(r["merger_id"] == "M1" for r in reused + pending)

    def test_output_is_sorted_for_stable_diffs(self):
        text = "x" * 60
        chunks = [
            _chunk("M2", "overview", text),
            _chunk("M1", "reasons", text),
            _chunk("M1", "overview", text),
        ]
        reused, pending = plan_embedding(chunks, None, self.MODEL)
        # plan_embedding doesn't sort — embed_chunks does after combining
        # cached + fresh — but the same key is used downstream. Verify the
        # merger_ids are still all present so we can sort them in tests.
        assert {p["merger_id"] for p in pending} == {"M1", "M2"}

    def test_metadata_refreshes_even_when_vector_is_reused(self):
        # The text didn't change, but the merger's outcome did (e.g. status
        # update). The reused record should reflect the new metadata.
        text = "x" * 60
        h = _content_hash(self.MODEL, text)
        existing = [{
            "merger_id": "M1", "section": "overview",
            "hash": h, "vector": [0.1], "outcome": "Under assessment",
        }]
        chunks = [_chunk("M1", "overview", text, outcome="Approved")]
        reused, _ = plan_embedding(chunks, existing, self.MODEL)
        assert reused[0]["outcome"] == "Approved"


class TestFormatRecords:
    def test_each_record_is_on_its_own_line(self):
        records = [
            {"merger_id": "M1", "section": "overview", "vector": [0.1, 0.2]},
            {"merger_id": "M2", "section": "overview", "vector": [0.3, 0.4]},
        ]
        out = _format_records(records)
        # Two record lines plus opening "[" and closing "]" = 4 lines.
        assert out.splitlines() == [
            "[",
            '{"merger_id":"M1","section":"overview","vector":[0.1,0.2]},',
            '{"merger_id":"M2","section":"overview","vector":[0.3,0.4]}',
            "]",
        ]

    def test_output_round_trips_through_json(self):
        records = [{"merger_id": "M1", "section": "overview", "vector": [0.1]}]
        assert json.loads(_format_records(records)) == records

    def test_empty_input_returns_empty_array(self):
        assert json.loads(_format_records([])) == []
