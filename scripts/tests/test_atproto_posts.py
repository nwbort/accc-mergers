"""Tests for the Bluesky poster.

Two of these matter more than the rest: the seeding rule, which is the only
thing standing between switching posting on and 673 matters landing in a feed,
and the length budget, which a PDS enforces by rejecting the post.
"""

import pytest

from scripts.atproto import config, post_bluesky
from scripts.atproto.client import XrpcError
from scripts.atproto.post_bluesky import (
    MAX_POST_CHARS,
    POST_HASHTAGS,
    hashtag_line,
    link_facets,
    load_state,
    main,
    milestones,
    pending,
    post_record,
    post_text,
    save_state,
    tag_facets,
    upload_card_image,
)


def matter(merger_id="MN-01016", **overrides):
    record = {
        "merger_id": merger_id,
        "merger_name": "Asahi - Warehouse site",
        "status": "Under assessment",
        "stage": "Phase 1 - initial assessment",
        "is_waiver": False,
        "effective_notification_datetime": "2026-08-15T12:00:00Z",
        "merger_description": "Asahi will enter into an agreement for lease.",
        "events": [],
    }
    record.update(overrides)
    return record


BLOB = {"$type": "blob", "ref": {"$link": "bafk"}, "mimeType": "image/png", "size": 3}


class FakeClient:
    def __init__(self, upload_fails=False):
        self.posts = []
        self.uploads = []
        self.upload_fails = upload_fails

    def upload_blob(self, data, mime_type):
        if self.upload_fails:
            raise XrpcError("uploadBlob failed (500 error): boom", status=500)
        self.uploads.append((data, mime_type))
        return BLOB

    def create_record(self, collection, record, validate=None):
        self.posts.append(record)
        return {"uri": f"at://did:plc:example/{collection}/{len(self.posts)}", "cid": "c"}


@pytest.fixture
def state_file(tmp_path, monkeypatch):
    path = tmp_path / "atproto_posts.json"
    monkeypatch.setattr(config, "POST_STATE_PATH", path)
    return path


@pytest.fixture
def fake_client(monkeypatch):
    client = FakeClient()
    monkeypatch.setattr(
        post_bluesky, "open_client", lambda **_kwargs: (client, config.load_identity())
    )
    return client


def use_matters(monkeypatch, matters):
    monkeypatch.setattr(post_bluesky, "load_matters", lambda: matters)


# -- what counts as worth posting -------------------------------------------


def test_a_new_notification_is_one_milestone():
    found = milestones(matter())
    assert [m.key for m in found] == ["MN-01016:notified:2026-08-15"]
    assert found[0].headline == "Notified to the ACCC"


def test_a_waiver_application_is_not_posted_on_arrival():
    """The register only publishes a waiver once it is decided."""
    found = milestones(matter(is_waiver=True, stage="Waiver application"))
    assert found == []


def test_a_decided_waiver_is_posted_as_a_waiver():
    found = milestones(
        matter(
            is_waiver=True,
            stage="Waiver application",
            status="Assessment completed",
            accc_determination="Approved",
            phase_1_determination="Approved",
            phase_1_determination_date="2026-09-05T12:00:00Z",
        )
    )
    assert [m.key for m in found] == ["MN-01016:determined:2026-09-05"]
    assert found[0].headline == "Notification waiver granted"


def test_a_cleared_matter_carries_both_its_arrival_and_its_clearance():
    found = milestones(
        matter(
            status="Assessment completed",
            accc_determination="Approved",
            phase_1_determination="Approved",
            phase_1_determination_date="2026-09-05T12:00:00Z",
        )
    )
    assert [m.headline for m in found] == ["Notified to the ACCC", "Cleared by the ACCC"]


def test_conditions_change_the_wording():
    found = milestones(
        matter(
            accc_determination="Approved",
            has_conditions=True,
            phase_1_determination_date="2026-09-05T12:00:00Z",
        )
    )
    assert found[-1].headline == "Cleared with conditions by the ACCC"


def test_a_blocked_matter_says_so():
    found = milestones(
        matter(accc_determination="Not approved", determination_publication_date="2026-09-05T12:00:00Z")
    )
    assert found[-1].headline == "Not approved by the ACCC"


def test_a_referral_is_posted_once_as_a_referral_not_twice_as_a_determination():
    found = milestones(
        matter(
            stage="Phase 2 - detailed assessment",
            accc_determination="Referred to phase 2",
            phase_1_determination="Referred to phase 2",
            phase_1_determination_date="2026-01-29T12:00:00Z",
        )
    )
    assert [m.headline for m in found] == ["Notified to the ACCC", "Referred to Phase 2"]


def test_a_phase_2_decision_is_not_dated_on_the_day_it_was_referred():
    """MN-65005: the register said "Not approved" before it carried a Phase 2
    date, and the referral's date stood in for it."""
    found = milestones(
        matter(
            stage="Phase 2 - detailed assessment",
            status="Assessment completed",
            accc_determination="Not approved",
            phase_1_determination="Referred to phase 2",
            phase_1_determination_date="2026-04-16T12:00:00Z",
        )
    )
    assert found[-1].headline == "Not approved by the ACCC"
    assert found[-1].key == "MN-01016:determined:undated"
    assert "Apr" not in post_text(found[-1])

    found = milestones(
        matter(
            stage="Phase 2 - detailed assessment",
            status="Assessment completed",
            accc_determination="Not approved",
            events=[
                {"date": "2026-04-16T12:00:00Z", "title": "IAG-RACI - Phase 1 determination"},
                {"date": "2026-09-22T12:00:00Z", "title": "IAG-RACI - Phase 2 determination"},
            ],
            phase_1_determination="Referred to phase 2",
            phase_1_determination_date="2026-04-16T12:00:00Z",
        )
    )
    assert found[-1].key == "MN-01016:determined:2026-09-22"


def test_both_review_forums_get_their_own_milestone():
    found = milestones(
        matter(
            appeal={"filed_date": "2026-07-15", "tribunal_number": "ACT 1 of 2026"},
            judicial_review={"filed_date": "2026-07-17", "case_number": "NSD1310/2026"},
        )
    )
    assert [m.key.split(":")[1] for m in found] == ["notified", "tribunal", "judicial-review"]


def test_routine_timeline_traffic_is_not_a_milestone():
    """Questionnaires and extensions are on the site; posting them is noise."""
    found = milestones(
        matter(
            events=[
                {"date": "2026-08-20T12:00:00Z", "title": "Questionnaire", "is_questionnaire_event": True},
                {"date": "2026-08-25T12:00:00Z", "title": "Timeline extended by 10 business days"},
            ]
        )
    )
    assert [m.key.split(":")[1] for m in found] == ["notified"]


# -- the post itself --------------------------------------------------------


def test_a_post_fits_the_limit_and_keeps_the_link_and_the_matter_id():
    milestone = milestones(matter(merger_name="A " * 400))[0]
    text = post_text(milestone)

    assert len(text) <= MAX_POST_CHARS
    assert "https://mergers.fyi/mergers/MN-01016" in text
    assert text.endswith(hashtag_line())
    assert "MN-01016 ·" in text
    assert "…" in text, "the title is what gives, and it should say so"


def test_the_link_facet_is_measured_in_utf8_bytes():
    """A dash in a party name shifts every byte offset after it."""
    milestone = milestones(matter(merger_name="Asahi – Warehouse"))[0]
    text = post_text(milestone)
    facet = link_facets(text, milestone.url)[0]

    encoded = text.encode("utf-8")
    start, end = facet["index"]["byteStart"], facet["index"]["byteEnd"]
    assert encoded[start:end].decode("utf-8") == milestone.url
    assert start != text.find(milestone.url), "byte and character offsets differ here"


def test_every_post_carries_the_accc_hashtag():
    assert "accc" in POST_HASHTAGS
    assert post_text(milestones(matter())[0]).endswith(hashtag_line())


def test_the_hashtags_are_faceted_so_bluesky_indexes_them_as_tags():
    """An unfaceted hashtag is a run of characters and nothing else."""
    milestone = milestones(matter(merger_name="Asahi – Warehouse"))[0]
    text = post_text(milestone)
    tags = ("accc", "auslaw")

    spans = []
    for tag, facet in zip(tags, tag_facets(text + f" #{tags[1]}", tags)):
        start, end = facet["index"]["byteStart"], facet["index"]["byteEnd"]
        spans.append((text + f" #{tags[1]}").encode("utf-8")[start:end].decode("utf-8"))
        assert facet["features"][0] == {
            "$type": "app.bsky.richtext.facet#tag",
            "tag": tag,
        }
    assert spans == ["#accc", "#auslaw"]


def test_a_hash_in_the_title_is_not_mistaken_for_the_hashtag():
    """The tags are found as a line, so stray text cannot steal their offsets."""
    text = post_text(milestones(matter(merger_name="#accc Holdings - Acme"))[0])
    facet = tag_facets(text)[0]

    assert facet["index"]["byteStart"] == text.encode("utf-8").rfind(b"#accc")


def test_a_post_record_carries_the_link_and_the_tags_in_byte_order():
    record = post_record(milestones(matter())[0], created_at="2026-09-22T00:00:00Z")
    kinds = [facet["features"][0]["$type"] for facet in record["facets"]]

    assert kinds == ["app.bsky.richtext.facet#link"] + [
        "app.bsky.richtext.facet#tag"
    ] * len(POST_HASHTAGS)
    starts = [facet["index"]["byteStart"] for facet in record["facets"]]
    assert starts == sorted(starts)


def test_more_hashtags_leave_less_room_for_the_title(monkeypatch):
    """Whatever the tag list, the post fits and the title is what gives."""
    monkeypatch.setattr(post_bluesky, "POST_HASHTAGS", ("accc", "auslaw", "mergers"))
    milestone = milestones(matter(merger_name="A " * 400))[0]
    text = post_text(milestone)

    assert len(text) <= MAX_POST_CHARS
    assert text.endswith("#accc #auslaw #mergers")
    assert [f["features"][0]["tag"] for f in tag_facets(text, post_bluesky.POST_HASHTAGS)] == [
        "accc",
        "auslaw",
        "mergers",
    ]


def test_the_post_record_is_a_bluesky_post_with_a_link_card():
    record = post_record(milestones(matter())[0], created_at="2026-09-22T00:00:00Z")

    assert record["$type"] == "app.bsky.feed.post"
    assert record["langs"] == ["en-AU"]
    assert record["facets"][0]["features"][0]["$type"] == "app.bsky.richtext.facet#link"
    assert record["embed"]["external"]["uri"] == "https://mergers.fyi/mergers/MN-01016"


def test_the_card_carries_a_thumbnail_only_when_one_was_uploaded():
    milestone = milestones(matter())[0]
    bare = post_record(milestone, created_at="2026-09-22T00:00:00Z")
    pictured = post_record(milestone, created_at="2026-09-22T00:00:00Z", thumb=BLOB)

    assert "thumb" not in bare["embed"]["external"]
    assert pictured["embed"]["external"]["thumb"] == BLOB


def test_the_card_image_is_the_sites_own_og_image():
    assert config.CARD_IMAGE_PATH.name == "og-image.png"
    assert config.CARD_IMAGE_PATH.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
    # Bluesky rejects a thumbnail over 1,000,000 bytes.
    assert config.CARD_IMAGE_PATH.stat().st_size < 1_000_000


def test_a_missing_or_rejected_card_image_falls_back_to_a_text_card(tmp_path):
    assert upload_card_image(FakeClient(), tmp_path / "missing.png") is None
    image = tmp_path / "card.png"
    image.write_bytes(b"png")
    assert upload_card_image(FakeClient(upload_fails=True), image) is None
    client = FakeClient()
    assert upload_card_image(client, image) == BLOB
    assert client.uploads == [(b"png", "image/png")]


def test_a_long_summary_is_trimmed_to_fit_the_card():
    record = post_record(
        milestones(matter(merger_description="x" * 900))[0], created_at="2026-09-22T00:00:00Z"
    )
    assert len(record["embed"]["external"]["description"]) == 300


# -- ordering and state -----------------------------------------------------


def test_a_backlog_drains_oldest_first():
    matters = [
        matter("MN-2", effective_notification_datetime="2026-08-20T12:00:00Z"),
        matter("MN-1", effective_notification_datetime="2026-08-15T12:00:00Z"),
    ]
    assert [m.key for m in pending(matters, {})] == [
        "MN-1:notified:2026-08-15",
        "MN-2:notified:2026-08-20",
    ]


def test_posting_is_off_unless_it_is_switched_on(monkeypatch, state_file, capsys):
    use_matters(monkeypatch, [matter()])
    monkeypatch.delenv("ATPROTO_POST_ENABLED", raising=False)
    monkeypatch.setattr(
        post_bluesky, "open_client", lambda **_kwargs: pytest.fail("must not post")
    )

    assert main([]) == 0
    assert not state_file.exists(), "a disabled run must not consume the seed"
    assert "ATPROTO_POST_ENABLED" in capsys.readouterr().err


def test_the_first_enabled_run_seeds_and_posts_nothing(monkeypatch, state_file, fake_client):
    """Switching posting on must not replay the whole register."""
    use_matters(monkeypatch, [matter("MN-1"), matter("MN-2")])
    monkeypatch.setenv("ATPROTO_POST_ENABLED", "true")

    assert main([]) == 0
    assert fake_client.posts == []
    assert sorted(load_state()["posted"]) == [
        "MN-1:notified:2026-08-15",
        "MN-2:notified:2026-08-15",
    ]


def test_what_happens_after_seeding_is_what_gets_posted(monkeypatch, state_file, fake_client):
    use_matters(monkeypatch, [matter("MN-1")])
    monkeypatch.setenv("ATPROTO_POST_ENABLED", "true")
    main([])

    use_matters(monkeypatch, [matter("MN-1"), matter("MN-2")])
    assert main([]) == 0
    assert len(fake_client.posts) == 1
    assert "MN-2" in fake_client.posts[0]["text"]
    assert fake_client.posts[0]["embed"]["external"]["thumb"] == BLOB


def test_a_posted_milestone_is_never_posted_again(monkeypatch, state_file, fake_client):
    use_matters(monkeypatch, [matter("MN-1")])
    monkeypatch.setenv("ATPROTO_POST_ENABLED", "true")
    main([])
    use_matters(monkeypatch, [matter("MN-1"), matter("MN-2")])
    main([])
    fake_client.posts.clear()

    assert main([]) == 0
    assert fake_client.posts == []


def test_max_posts_caps_a_burst(monkeypatch, state_file, fake_client, capsys):
    use_matters(monkeypatch, [matter("MN-1")])
    monkeypatch.setenv("ATPROTO_POST_ENABLED", "true")
    main([])

    use_matters(monkeypatch, [matter(f"MN-{n}") for n in range(1, 9)])
    assert main(["--max-posts", "3"]) == 0
    assert len(fake_client.posts) == 3
    assert "held over" in capsys.readouterr().out


def test_dry_run_needs_neither_the_switch_nor_credentials(monkeypatch, state_file, capsys):
    use_matters(monkeypatch, [matter()])
    monkeypatch.delenv("ATPROTO_POST_ENABLED", raising=False)
    monkeypatch.setattr(
        post_bluesky, "open_client", lambda **_kwargs: pytest.fail("must not post")
    )

    assert main(["--dry-run"]) == 0
    assert "Notified to the ACCC" in capsys.readouterr().out
    assert not state_file.exists()


def test_state_survives_a_round_trip(state_file):
    save_state({"posted": {"MN-1:notified:2026-08-15": {"uri": "at://x"}}})
    assert load_state()["posted"]["MN-1:notified:2026-08-15"]["uri"] == "at://x"


def test_a_re_dated_milestone_is_not_posted_again(monkeypatch, state_file, fake_client):
    """MN-65005 was announced as not approved three times, once per date the
    register gave its determination."""
    decided = dict(accc_determination="Not approved", status="Assessment completed")
    use_matters(monkeypatch, [matter("MN-1")])
    monkeypatch.setenv("ATPROTO_POST_ENABLED", "true")
    main([])

    use_matters(monkeypatch, [matter("MN-1", determination_publication_date="2026-09-22T12:00:00Z", **decided)])
    main([])
    assert len(fake_client.posts) == 1

    use_matters(monkeypatch, [matter("MN-1", determination_publication_date="2026-09-23T12:00:00Z", **decided)])
    assert main([]) == 0
    assert len(fake_client.posts) == 1


def test_state_written_before_the_fix_still_counts_as_posted():
    state = {"posted": {"MN-1:determined:2026-04-16": {"uri": "at://x"}}}
    decided = matter(
        "MN-1", accc_determination="Not approved", determination_publication_date="2026-09-23T12:00:00Z"
    )
    assert [m.key for m in pending([decided], state)] == ["MN-1:notified:2026-08-15"]


def test_a_referral_and_the_phase_2_decision_after_it_are_both_posted(
    monkeypatch, state_file, fake_client
):
    """Once per kind, not once per matter: the referral must not swallow the
    decision it leads to, nor the decision the public benefit steps after it."""
    use_matters(monkeypatch, [matter("MN-1")])
    monkeypatch.setenv("ATPROTO_POST_ENABLED", "true")
    main([])

    referred = dict(
        stage="Phase 2 - detailed assessment",
        phase_1_determination="Referred to phase 2",
        phase_1_determination_date="2026-04-16T12:00:00Z",
    )
    use_matters(monkeypatch, [matter("MN-1", accc_determination="Referred to phase 2", **referred)])
    main([])

    # Decided before the register carries a date: posted now, dated from the
    # determination document on the timeline, and not again once it has one.
    decided = dict(
        referred,
        status="Assessment completed",
        accc_determination="Not approved",
        events=[{"date": "2026-09-22T12:00:00Z", "title": "Phase 2 determination"}],
    )
    use_matters(monkeypatch, [matter("MN-1", **decided)])
    main([])
    assert len(fake_client.posts) == 2

    decided.update(
        phase_2_determination="Not approved",
        phase_2_determination_date="2026-09-22T12:00:00Z",
    )
    use_matters(monkeypatch, [matter("MN-1", **decided)])
    main([])

    public_benefit = dict(
        decided,
        stage="Public benefit phase",
        status="Under assessment",
        accc_determination=None,
        public_benefit_in_progress=True,
        public_benefit_application_date="2026-10-01T12:00:00Z",
    )
    use_matters(monkeypatch, [matter("MN-1", **public_benefit)])
    main([])

    public_benefit.update(
        public_benefits_determination="Approved",
        public_benefits_determination_date="2026-12-10T12:00:00Z",
        public_benefit_in_progress=False,
    )
    use_matters(monkeypatch, [matter("MN-1", **public_benefit)])
    main([])
    main([])

    assert [post["text"].split(":")[0] for post in fake_client.posts] == [
        "Referred to Phase 2",
        "Not approved by the ACCC",
        "Public benefit determination sought",
        "Cleared by the ACCC on public benefit grounds",
    ]
    assert "22 Sep 2026" in fake_client.posts[1]["text"]
