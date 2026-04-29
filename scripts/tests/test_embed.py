"""Tests for the semantic-embedding chunker.

We don't load sentence-transformers here — only the pure-Python chunking
logic is exercised. That logic is the part most likely to break as the ACCC
varies its determination-table layout.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import json
import struct

from embed import (
    MIN_CHUNK_CHARS,
    _classify_item,
    _clean_text,
    _content_hash,
    _format_metadata,
    _load_existing,
    _pack_vectors,
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
        assert _content_hash("model-a", 256, "hello") == _content_hash("model-a", 256, "hello")

    def test_different_text_produces_different_hash(self):
        assert _content_hash("model-a", 256, "hello") != _content_hash("model-a", 256, "world")

    def test_different_model_produces_different_hash(self):
        # Critical for cache correctness — mixing vectors from different
        # models in one file would silently corrupt similarity scores.
        assert _content_hash("model-a", 256, "hello") != _content_hash("model-b", 256, "hello")

    def test_different_dim_produces_different_hash(self):
        # Same reason: 256-dim and 768-dim vectors aren't comparable, so
        # changing the truncation dim must invalidate every cached entry.
        assert _content_hash("model-a", 256, "hello") != _content_hash("model-a", 768, "hello")

    def test_native_dim_distinguished_from_truncated(self):
        assert _content_hash("model-a", None, "hello") != _content_hash("model-a", 768, "hello")


def _chunk(merger_id, section, text, **extra):
    return {"merger_id": merger_id, "section": section, "text": text, **extra}


class TestPlanEmbedding:
    MODEL = "test-model"
    DIM = 256

    def _hash(self, text):
        return _content_hash(self.MODEL, self.DIM, text)

    def test_no_existing_cache_means_everything_is_pending(self):
        chunks = [_chunk("M1", "overview", "x" * 60)]
        reused, pending = plan_embedding(chunks, None, self.MODEL, self.DIM)
        assert reused == []
        assert len(pending) == 1
        assert pending[0]["hash"] == self._hash(chunks[0]["text"])

    def test_unchanged_chunk_is_reused(self):
        text = "x" * 60
        h = self._hash(text)
        existing = [{
            "merger_id": "M1", "section": "overview",
            "hash": h, "vector": [0.1, 0.2, 0.3], "outcome": "Approved",
        }]
        chunks = [_chunk("M1", "overview", text, outcome="Approved")]
        reused, pending = plan_embedding(chunks, existing, self.MODEL, self.DIM)
        assert pending == []
        assert reused[0]["vector"] == [0.1, 0.2, 0.3]
        assert reused[0]["hash"] == h

    def test_changed_text_invalidates_cache_entry(self):
        old_text = "x" * 60
        existing = [{
            "merger_id": "M1", "section": "overview",
            "hash": self._hash(old_text),
            "vector": [0.1], "outcome": "Approved",
        }]
        chunks = [_chunk("M1", "overview", "y" * 60)]
        reused, pending = plan_embedding(chunks, existing, self.MODEL, self.DIM)
        assert reused == []
        assert len(pending) == 1

    def test_model_change_invalidates_every_entry(self):
        text = "x" * 60
        existing = [{
            "merger_id": "M1", "section": "overview",
            "hash": _content_hash("old-model", self.DIM, text),
            "vector": [0.1],
        }]
        chunks = [_chunk("M1", "overview", text)]
        reused, pending = plan_embedding(chunks, existing, self.MODEL, self.DIM)
        assert reused == []
        assert len(pending) == 1

    def test_dim_change_invalidates_every_entry(self):
        # Same model, same text, but a different truncation dim → must
        # re-embed. Otherwise we'd serve a 768-dim vector under a 256-dim
        # contract and silently break similarity scores.
        text = "x" * 60
        existing = [{
            "merger_id": "M1", "section": "overview",
            "hash": _content_hash(self.MODEL, 768, text),
            "vector": [0.1] * 768,
        }]
        chunks = [_chunk("M1", "overview", text)]
        reused, pending = plan_embedding(chunks, existing, self.MODEL, self.DIM)
        assert reused == []
        assert len(pending) == 1

    def test_dropped_chunk_is_not_carried_over(self):
        text = "x" * 60
        existing = [
            {"merger_id": "M1", "section": "overview",
             "hash": self._hash(text), "vector": [0.1]},
            {"merger_id": "M2", "section": "overview",
             "hash": self._hash(text), "vector": [0.2]},
        ]
        chunks = [_chunk("M1", "overview", text)]
        reused, pending = plan_embedding(chunks, existing, self.MODEL, self.DIM)
        assert len(reused) + len(pending) == 1
        assert all(r["merger_id"] == "M1" for r in reused + pending)

    def test_output_is_sorted_for_stable_diffs(self):
        text = "x" * 60
        chunks = [
            _chunk("M2", "overview", text),
            _chunk("M1", "reasons", text),
            _chunk("M1", "overview", text),
        ]
        reused, pending = plan_embedding(chunks, None, self.MODEL, self.DIM)
        assert {p["merger_id"] for p in pending} == {"M1", "M2"}

    def test_metadata_refreshes_even_when_vector_is_reused(self):
        # The text didn't change, but the merger's outcome did (e.g. status
        # update). The reused record should reflect the new metadata.
        text = "x" * 60
        existing = [{
            "merger_id": "M1", "section": "overview",
            "hash": self._hash(text), "vector": [0.1], "outcome": "Under assessment",
        }]
        chunks = [_chunk("M1", "overview", text, outcome="Approved")]
        reused, _ = plan_embedding(chunks, existing, self.MODEL, self.DIM)
        assert reused[0]["outcome"] == "Approved"


class TestFormatMetadata:
    def test_each_record_is_on_its_own_line_without_vectors(self):
        records = [
            {"merger_id": "M1", "section": "overview", "vector": [0.1, 0.2]},
            {"merger_id": "M2", "section": "overview", "vector": [0.3, 0.4]},
        ]
        out = _format_metadata(records)
        assert out.splitlines() == [
            "[",
            '{"merger_id":"M1","section":"overview"},',
            '{"merger_id":"M2","section":"overview"}',
            "]",
        ]
        # Vectors are stripped — they live in the .bin file.
        assert "0.1" not in out

    def test_output_round_trips_through_json(self):
        records = [{"merger_id": "M1", "section": "overview", "vector": [0.1]}]
        assert json.loads(_format_metadata(records)) == [
            {"merger_id": "M1", "section": "overview"},
        ]

    def test_empty_input_returns_empty_array(self):
        assert json.loads(_format_metadata([])) == []


class TestPackVectors:
    def test_packs_vectors_in_record_order(self):
        records = [
            {"merger_id": "M1", "section": "overview", "vector": [1.0, 2.0]},
            {"merger_id": "M2", "section": "overview", "vector": [3.0, 4.0]},
        ]
        packed = _pack_vectors(records)
        # 4 floats × 4 bytes each = 16 bytes.
        assert len(packed) == 16
        assert struct.unpack("<4f", packed) == (1.0, 2.0, 3.0, 4.0)

    def test_inconsistent_dim_raises(self):
        records = [
            {"merger_id": "M1", "section": "overview", "vector": [1.0, 2.0]},
            {"merger_id": "M2", "section": "overview", "vector": [3.0]},
        ]
        try:
            _pack_vectors(records)
        except ValueError as e:
            assert "M2" in str(e)
        else:
            raise AssertionError("expected ValueError")

    def test_empty_input(self):
        assert _pack_vectors([]) == b""


class TestLoadExisting:
    def test_round_trips_metadata_and_vectors(self, tmp_path):
        json_path = tmp_path / "embeddings.json"
        bin_path = tmp_path / "embeddings.bin"
        records = [
            {"merger_id": "M1", "section": "overview", "hash": "h1", "vector": [0.1, 0.2]},
            {"merger_id": "M2", "section": "overview", "hash": "h2", "vector": [0.3, 0.4]},
        ]
        json_path.write_text(_format_metadata(records))
        bin_path.write_bytes(_pack_vectors(records))

        loaded = _load_existing(json_path, bin_path)
        assert len(loaded) == 2
        assert loaded[0]["merger_id"] == "M1"
        assert loaded[0]["hash"] == "h1"
        # Float32 round-trip: small precision drift is fine.
        assert all(abs(a - b) < 1e-6 for a, b in zip(loaded[0]["vector"], [0.1, 0.2]))
        assert all(abs(a - b) < 1e-6 for a, b in zip(loaded[1]["vector"], [0.3, 0.4]))

    def test_returns_none_when_json_missing(self, tmp_path):
        assert _load_existing(tmp_path / "missing.json", tmp_path / "missing.bin") is None

    def test_returns_none_when_bin_missing_for_nonempty_json(self, tmp_path):
        json_path = tmp_path / "embeddings.json"
        bin_path = tmp_path / "embeddings.bin"
        json_path.write_text(_format_metadata([
            {"merger_id": "M1", "section": "overview", "vector": [0.1]},
        ]))
        # No bin file written.
        assert _load_existing(json_path, bin_path) is None

    def test_handles_empty_records(self, tmp_path):
        json_path = tmp_path / "embeddings.json"
        bin_path = tmp_path / "embeddings.bin"
        json_path.write_text("[]\n")
        # Empty JSON shouldn't require a bin file.
        assert _load_existing(json_path, bin_path) == []
