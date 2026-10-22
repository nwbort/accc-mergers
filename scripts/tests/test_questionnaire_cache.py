"""The questionnaire parse cache, and the re-downloads the dedup step drops."""

import json

from scripts.parse import parse_questionnaire as pq


def _matter(tmp_path, files):
    """A matters dir holding MN-1 with ``{filename: bytes}``."""
    matter = tmp_path / "matters" / "MN-1"
    matter.mkdir(parents=True)
    for name, content in files.items():
        (matter / name).write_bytes(content)
    return tmp_path / "matters"


def _fake_parse(monkeypatch):
    """Stub the PDF parse with one fixed deadline; return the list of paths parsed."""
    parsed = []

    def fake(path):
        parsed.append(path)
        return {"deadline": "1 May 2026", "deadline_iso": "2026-05-01", "questions": []}

    monkeypatch.setattr(pq, "parse_questionnaire_pdf", fake)
    return parsed


def _persist(tmp_path, results, dup_shas):
    """Write results as extract_mergers does, and read the caches back."""
    path = tmp_path / "questionnaire_data.json"
    payload = dict(results)
    if dup_shas:
        payload[pq._DUP_CACHE_KEY] = dup_shas
    path.write_text(json.dumps(payload))
    return pq._build_caches_from_existing(path)


def test_dropped_redownload_is_not_reparsed_next_run(tmp_path, monkeypatch):
    matters = _matter(tmp_path, {
        "Foo - Questionnaire.pdf": b"first upload",
        "Foo - Questionnaire_0.pdf": b"re-upload, same deadline",
    })
    parsed = _fake_parse(monkeypatch)

    dup_shas = {}
    first = pq.process_all_questionnaires(str(matters), cache={}, neg_cache=set(),
                                          dup_shas=dup_shas)
    assert len(parsed) == 2
    assert "all_questionnaires" not in first["MN-1"]
    assert len(dup_shas) == 1

    cache, neg = _persist(tmp_path, first, dup_shas)
    parsed.clear()
    dup_again = {}
    second = pq.process_all_questionnaires(str(matters), cache=cache, neg_cache=neg,
                                           dup_shas=dup_again)

    assert parsed == []
    assert second == first
    assert dup_again == dup_shas


def test_without_alias_map_the_dropped_copy_is_reparsed(tmp_path, monkeypatch):
    """The behaviour the alias map exists to fix."""
    matters = _matter(tmp_path, {
        "Foo - Questionnaire.pdf": b"first upload",
        "Foo - Questionnaire_0.pdf": b"re-upload, same deadline",
    })
    parsed = _fake_parse(monkeypatch)
    first = pq.process_all_questionnaires(str(matters), cache={}, neg_cache=set())

    cache, neg = _persist(tmp_path, first, {})
    parsed.clear()
    pq.process_all_questionnaires(str(matters), cache=cache, neg_cache=neg)

    assert [p.rsplit("/", 1)[1] for p in parsed] == ["Foo - Questionnaire_0.pdf"]


def test_alias_to_a_sha_no_longer_cached_is_ignored(tmp_path):
    path = tmp_path / "questionnaire_data.json"
    path.write_text(json.dumps({pq._DUP_CACHE_KEY: {"dropped": "gone"}}))

    cache, neg = pq._build_caches_from_existing(path)

    assert cache == {}
    assert neg == set()
