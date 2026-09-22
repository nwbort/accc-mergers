"""Tests for the ``fyi.mergers.*`` lexicons and their publisher.

The lexicons are load-bearing in the same way ``slugify()`` is: a schema whose
id disagrees with its filename, or whose refs point at defs that don't exist,
publishes perfectly happily and then fails only in somebody else's client.
"""

import json

import pytest

from scripts.atproto import config
from scripts.atproto.publish_lexicons import (
    dns_instructions,
    load_lexicons,
    schema_record,
    validate_lexicon,
)

LEXICONS = load_lexicons()


def test_repository_ships_the_matter_lexicon():
    assert {lexicon["id"] for lexicon in LEXICONS} == {
        "fyi.mergers.defs",
        "fyi.mergers.matter",
    }


@pytest.mark.parametrize("lexicon", LEXICONS, ids=lambda lex: lex["id"])
def test_every_lexicon_sits_under_the_site_authority(lexicon):
    assert lexicon["id"].startswith(f"{config.NSID_AUTHORITY}.")


@pytest.mark.parametrize("lexicon", LEXICONS, ids=lambda lex: lex["id"])
def test_every_ref_resolves(lexicon):
    """Every ``ref`` points at a def that exists in one of our own lexicons."""
    by_id = {lex["id"]: lex for lex in LEXICONS}
    known_external = {"com.atproto.label.defs", "com.atproto.repo.strongRef"}

    for ref in _refs(lexicon):
        nsid, _, name = ref.partition("#")
        nsid = nsid or lexicon["id"]
        if nsid in known_external:
            continue
        assert nsid in by_id, f"{lexicon['id']} refers to unknown lexicon {nsid}"
        assert name in by_id[nsid]["defs"], f"{lexicon['id']} refers to missing def {ref}"


def test_matter_record_is_keyed_by_the_matter_id():
    """The key strategy is what makes a matter addressable without a lookup."""
    main = next(lex for lex in LEXICONS if lex["id"] == "fyi.mergers.matter")["defs"]["main"]
    assert main["type"] == "record"
    assert main["key"] == "any"


def test_validate_rejects_an_id_that_disagrees_with_its_filename(tmp_path):
    path = tmp_path / "fyi.mergers.matter.json"
    with pytest.raises(ValueError, match="does not match the filename"):
        validate_lexicon({"lexicon": 1, "id": "fyi.mergers.other", "defs": {}}, path)


def test_validate_rejects_a_foreign_authority(tmp_path):
    path = tmp_path / "app.bsky.feed.post.json"
    with pytest.raises(ValueError, match="outside the fyi.mergers authority"):
        validate_lexicon(
            {"lexicon": 1, "id": "app.bsky.feed.post", "defs": {"main": {}}}, path
        )


def test_validate_rejects_a_missing_lexicon_version(tmp_path):
    path = tmp_path / "fyi.mergers.thing.json"
    with pytest.raises(ValueError, match='expected "lexicon": 1'):
        validate_lexicon({"id": "fyi.mergers.thing", "defs": {"main": {}}}, path)


def test_schema_record_carries_the_lexicon_verbatim():
    lexicon = next(lex for lex in LEXICONS if lex["id"] == "fyi.mergers.defs")
    record = schema_record(lexicon)
    assert record["$type"] == "com.atproto.lexicon.schema"
    assert record["id"] == lexicon["id"]
    assert record["defs"] == lexicon["defs"]


def test_dns_instructions_collapse_to_one_record_per_authority():
    """Both NSIDs differ only in their last segment, so one TXT record covers them."""
    lines = dns_instructions(LEXICONS)
    assert len(lines) == 1
    assert lines[0].startswith("_lexicon.mergers.fyi")


def test_lexicon_files_are_valid_json_on_disk():
    for path in sorted(config.LEXICON_DIR.glob("*.json")):
        json.loads(path.read_text(encoding="utf-8"))


def _refs(node) -> list:
    """Every ``ref`` string anywhere in a lexicon, including inside arrays."""
    found = []
    if isinstance(node, dict):
        if isinstance(node.get("ref"), str):
            found.append(node["ref"])
        for value in node.get("refs", []) or []:
            if isinstance(value, str):
                found.append(value)
        for value in node.values():
            found.extend(_refs(value))
    elif isinstance(node, list):
        for value in node:
            found.extend(_refs(value))
    return found
