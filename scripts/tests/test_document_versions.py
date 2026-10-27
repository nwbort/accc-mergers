"""Tests for scripts/document_versions.py: retiring byte-identical re-uploads."""

import json

from scripts import document_versions
from scripts.document_versions import (
    backfill,
    document_files,
    prune_superseded,
    record_superseded,
    retired_url_gh,
)
from scripts.extract_mergers import _merge_events
from scripts.generate.static_data.enrichment import slim_for_site

MID = "MN-30003"
BASE = "https://www.accc.gov.au/system/files/public-merger-register/documents/"
DATE = "2026-02-09T12:00:00Z"


def _event(name, title="MicroStar-Konvoy - Questionnaire", date=DATE):
    served = name[:-5] + ".pdf" if name.endswith(".docx") else name
    return {
        "date": date,
        "title": title,
        "display_title": title,
        "url": BASE + name.replace(" ", "%20"),
        "url_gh": f"/mergers/{MID}/{served}",
        "status": "live",
    }


def _write(folder, name, data):
    folder.mkdir(parents=True, exist_ok=True)
    (folder / name).write_bytes(data)


class TestDocumentFiles:
    def test_pdf_is_both_original_and_served(self):
        assert document_files(_event("Notice_3.pdf")) == ("Notice_3.pdf", "Notice_3.pdf")

    def test_docx_is_compared_on_the_original_and_served_as_its_pdf(self):
        assert document_files(_event("Q - 9 Feb_4.docx")) == ("Q - 9 Feb_4.docx", "Q - 9 Feb_4.pdf")

    def test_no_served_path_means_no_file(self):
        assert document_files({"url": BASE + "x.pdf"}) == (None, None)


class TestRecordSuperseded:
    def test_records_the_old_url_title_and_date(self):
        old = _event("Q_3.docx", title="Questionnaire - MicroStar")
        new = _event("Q_4.docx")
        record_superseded(old, new, today="2026-10-27")
        assert new["previous_versions"] == [{
            "url": old["url"],
            "url_gh": old["url_gh"],
            "title": "Questionnaire - MicroStar",
            "date": DATE,
            "superseded_on": "2026-10-27",
        }]

    def test_carries_earlier_history_forward(self):
        first = _event("Q_2.docx", title="First title")
        second = _event("Q_3.docx", title="Second title")
        third = _event("Q_4.docx")
        record_superseded(first, second, today="2026-10-01")
        record_superseded(second, third, today="2026-10-27")
        assert [v["title"] for v in third["previous_versions"]] == ["First title", "Second title"]

    def test_a_document_moved_back_to_an_old_url_drops_that_entry(self):
        a, b = _event("Q_3.docx"), _event("Q_4.docx")
        record_superseded(a, b)
        back = _event("Q_3.docx")
        record_superseded(b, back)
        assert [v["url"] for v in back["previous_versions"]] == [b["url"]]


class TestPruneSuperseded:
    def _pair(self, tmp_path, old_bytes, new_bytes, ext="pdf"):
        folder = tmp_path / MID
        old, new = _event(f"Q_3.{ext}"), _event(f"Q_4.{ext}")
        _write(folder, f"Q_3.{ext}", old_bytes)
        _write(folder, f"Q_4.{ext}", new_bytes)
        if ext == "docx":
            _write(folder, "Q_3.pdf", b"converted old")
            _write(folder, "Q_4.pdf", b"converted new")
        record_superseded(old, new)
        return folder, new

    def test_identical_copy_is_deleted_and_marked_retired(self, tmp_path):
        folder, new = self._pair(tmp_path, b"same", b"same")
        assert prune_superseded(MID, [new], tmp_path) == ["Q_3.pdf"]
        assert not (folder / "Q_3.pdf").exists()
        assert (folder / "Q_4.pdf").exists()
        version = new["previous_versions"][0]
        assert version["identical"] is True and version["retired"] is True
        assert len(version["sha256"]) == 64

    def test_different_copy_is_kept(self, tmp_path):
        folder, new = self._pair(tmp_path, b"old", b"new")
        assert prune_superseded(MID, [new], tmp_path) == []
        assert (folder / "Q_3.pdf").exists()
        version = new["previous_versions"][0]
        assert version["identical"] is False and "retired" not in version

    def test_docx_compared_on_original_and_takes_its_pdf_with_it(self, tmp_path):
        # The converted PDFs differ (conversion is never byte-stable) but the
        # DOCX files match, so the old pair goes.
        folder, new = self._pair(tmp_path, b"same", b"same", ext="docx")
        assert sorted(prune_superseded(MID, [new], tmp_path)) == ["Q_3.docx", "Q_3.pdf"]
        assert sorted(p.name for p in folder.iterdir()) == ["Q_4.docx", "Q_4.pdf"]

    def test_nothing_happens_while_the_new_file_is_missing(self, tmp_path):
        folder, new = self._pair(tmp_path, b"same", b"same")
        (folder / "Q_4.pdf").unlink()
        assert prune_superseded(MID, [new], tmp_path) == []
        assert (folder / "Q_3.pdf").exists()
        assert "identical" not in new["previous_versions"][0]

    def test_a_file_another_event_still_uses_is_kept(self, tmp_path):
        folder, new = self._pair(tmp_path, b"same", b"same")
        other = _event("Q_3.pdf", title="Some other row")
        assert prune_superseded(MID, [new, other], tmp_path) == []
        assert (folder / "Q_3.pdf").exists()

    def test_a_tribunal_reference_keeps_the_file(self, tmp_path):
        folder, new = self._pair(tmp_path, b"same", b"same")
        assert prune_superseded(MID, [new], tmp_path, extra_referenced={"Q_3.pdf"}) == []
        assert (folder / "Q_3.pdf").exists()

    def test_is_idempotent(self, tmp_path):
        _, new = self._pair(tmp_path, b"same", b"same")
        prune_superseded(MID, [new], tmp_path)
        before = json.dumps(new, sort_keys=True)
        assert prune_superseded(MID, [new], tmp_path) == []
        assert json.dumps(new, sort_keys=True) == before


class TestMergeEventsRecordsReuploads:
    """The re-bind in _merge_events is what feeds prune_superseded."""

    def test_reupload_rebind_records_the_previous_version(self):
        existing = {"events": [_event("Q_3.docx", title="Questionnaire")]}
        scraped = [_event("Q_4.docx", title="Questionnaire")]
        merged = _merge_events(scraped, existing, MID, set())
        assert [e["url"] for e in merged] == [scraped[0]["url"]]
        assert [v["url"] for v in merged[0]["previous_versions"]] == [existing["events"][0]["url"]]

    def test_history_survives_a_plain_rescrape(self):
        current = _event("Q_4.docx")
        current["previous_versions"] = [{"url": BASE + "Q_3.docx", "title": "Old"}]
        merged = _merge_events([_event("Q_4.docx")], {"events": [current]}, MID, set())
        assert merged[0]["previous_versions"] == current["previous_versions"]

    def test_healing_a_stored_removed_duplicate_records_it(self):
        removed = dict(_event("Q_3.docx"), status="removed")
        live = _event("Q_4.docx")
        merged = _merge_events([dict(live)], {"events": [removed, live]}, MID, set())
        assert len(merged) == 1
        assert [v["url"] for v in merged[0]["previous_versions"]] == [removed["url"]]


class TestSlimForSite:
    def test_history_stays_internal_and_retired_paths_are_published(self):
        event = _event("Q_4.pdf")
        event["previous_versions"] = [
            {"url_gh": f"/mergers/{MID}/Q_2.pdf", "identical": False},
            {"url_gh": f"/mergers/{MID}/Q_3.pdf", "identical": True, "retired": True},
        ]
        slim = slim_for_site({"merger_id": MID, "events": [event]})
        assert "previous_versions" not in slim["events"][0]
        assert slim["events"][0]["retired_url_gh"] == [f"/mergers/{MID}/Q_3.pdf"]
        assert "previous_versions" in event  # input left unmutated

    def test_no_retired_copies_adds_nothing(self):
        slim = slim_for_site({"merger_id": MID, "events": [_event("Q_4.pdf")]})
        assert "retired_url_gh" not in slim["events"][0]
        assert retired_url_gh(_event("Q_4.pdf")) == []


class TestBackfill:
    def _setup(self, tmp_path, monkeypatch):
        monkeypatch.setattr(document_versions, "tribunal_referenced_files", lambda: {})
        folder = tmp_path / MID
        _write(folder, "Q_4.docx", b"same")
        _write(folder, "Q_4.pdf", b"converted")
        _write(folder, "Q_3.docx", b"same")
        _write(folder, "Q_3.pdf", b"converted earlier")
        _write(folder, "Q_2.docx", b"different")
        _write(folder, "Q_2.pdf", b"converted different")
        _write(folder, "Unrelated_1.pdf", b"same")
        return folder, [{"merger_id": MID, "events": [_event("Q_4.docx")]}]

    def test_dry_run_reports_without_touching_anything(self, tmp_path, monkeypatch):
        folder, mergers = self._setup(tmp_path, monkeypatch)
        report = backfill(mergers, tmp_path)
        assert report == {"retired": [f"{MID}/Q_3.docx"], "different": [f"{MID}/Q_2.docx"]}
        assert len(list(folder.iterdir())) == 7
        assert "previous_versions" not in mergers[0]["events"][0]

    def test_apply_retires_identical_copies_with_their_pdf(self, tmp_path, monkeypatch):
        folder, mergers = self._setup(tmp_path, monkeypatch)
        report = backfill(mergers, tmp_path, apply=True, today="2026-10-27")
        assert report["retired"] == [f"{MID}/Q_3.docx", f"{MID}/Q_3.pdf"]
        assert sorted(p.name for p in folder.iterdir()) == [
            "Q_2.docx", "Q_2.pdf", "Q_4.docx", "Q_4.pdf", "Unrelated_1.pdf"]
        (version,) = mergers[0]["events"][0]["previous_versions"]
        assert version["url_gh"] == f"/mergers/{MID}/Q_3.pdf"
        assert version["retired"] is True and version["identical"] is True
        # Then prune leaves the backfilled record alone.
        assert prune_superseded(MID, mergers[0]["events"], tmp_path) == []
