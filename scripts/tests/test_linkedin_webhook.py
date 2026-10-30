"""Tests for the LinkedIn webhook poster.

What matters: the payload carries the post in every shape a scenario might
map, a milestone is only recorded once the webhook accepts it, the webhook URL
never reaches the log, and exactly one of the API poster, the webhook and the
share links handles a milestone.
"""

import pytest
import requests

from scripts.atproto.post_bluesky import load_state, milestones, save_state
from scripts.linkedin import config, share_links, webhook
from scripts.linkedin.webhook import main, payload

URL = "https://hook.eu1.make.com/secret-token"


def matter(merger_id="MN-01016", **overrides):
    record = {
        "merger_id": merger_id,
        "merger_name": "Asahi - Warehouse site (Vic)",
        "status": "Under assessment",
        "stage": "Phase 1 - initial assessment",
        "is_waiver": False,
        "effective_notification_datetime": "2026-08-15T12:00:00Z",
        "merger_description": "Asahi (**Asahi**) will enter into a lease.",
        "og_card": "notified-to-the-accc.png",
        "events": [],
    }
    record.update(overrides)
    return record


@pytest.fixture
def state_file(tmp_path, monkeypatch):
    path = tmp_path / "linkedin_posts.json"
    monkeypatch.setattr(config, "POST_STATE_PATH", path)
    return path


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setenv("LINKEDIN_WEBHOOK_URL", URL)
    monkeypatch.setenv("LINKEDIN_WEBHOOK_API_KEY", "key")
    monkeypatch.delenv("LINKEDIN_POST_ENABLED", raising=False)


@pytest.fixture(autouse=True)
def slept(monkeypatch):
    calls = []
    monkeypatch.setattr(webhook.time, "sleep", calls.append)
    return calls


class Sent(list):
    """Payload keys handed to the webhook; ``fail`` makes every delivery fail."""

    fail = False


@pytest.fixture
def sent(monkeypatch):
    calls = Sent()

    def fake_deliver(body, *, url, api_key):
        assert (url, api_key) == (URL, "key")
        calls.append(body["key"])
        return not calls.fail

    monkeypatch.setattr(webhook, "deliver", fake_deliver)
    return calls


def use_matters(monkeypatch, matters):
    monkeypatch.setattr(webhook, "load_matters", lambda: matters)


def test_the_payload_offers_the_post_as_text_and_as_a_link_post():
    record = matter()
    (milestone,) = milestones(record)
    body = payload(milestone, record)
    assert body["key"] == "MN-01016:notified:2026-08-15"
    assert body["matter_id"] == "MN-01016"
    assert body["headline"] == "Notified to the ACCC"
    assert body["url"] == "https://mergers.fyi/mergers/MN-01016?m=notified"
    # The text post carries the link to unfurl; the link post's commentary
    # doesn't, since the link travels as the card.
    assert body["url"] in body["text"]
    assert body["url"] not in body["commentary"]
    assert body["commentary"].startswith("Notified to the ACCC: Asahi - Warehouse site (Vic)")
    assert "\\" not in body["text"] + body["commentary"]
    assert "\\(Vic\\)" in body["commentary_little"]
    assert body["commentary"].endswith("#accc")
    assert body["description"] == "Asahi (Asahi) will enter into a lease."
    assert body["image_url"] == "https://mergers.fyi/og/notified-to-the-accc.png"


def test_a_matter_without_a_card_falls_back_to_the_site_image():
    record = matter(og_card=None)
    (milestone,) = milestones(record)
    assert payload(milestone, record)["image_url"] == "https://mergers.fyi/og-image.png"


def test_first_run_seeds(state_file, configured, sent, monkeypatch):
    use_matters(monkeypatch, [matter()])
    assert main([]) == 0
    assert sent == []
    assert list(load_state(state_file)["posted"]) == ["MN-01016:notified:2026-08-15"]


def test_it_carries_on_from_the_share_links_state(state_file, configured, sent, monkeypatch):
    save_state({"posted": {"MN-01016:notified:2026-08-15": {"shareLink": True}}}, state_file)
    use_matters(monkeypatch, [matter(), matter("MN-02000")])
    assert main([]) == 0
    assert sent == ["MN-02000:notified:2026-08-15"]
    assert load_state(state_file)["posted"]["MN-02000:notified:2026-08-15"]["webhook"]
    assert main([]) == 0
    assert sent == ["MN-02000:notified:2026-08-15"]


def test_posts_are_spaced_out(state_file, configured, sent, slept, monkeypatch):
    save_state({"posted": {}, "seeded": True}, state_file)
    use_matters(monkeypatch, [matter(), matter("MN-02000"), matter("MN-03000")])
    assert main([]) == 0
    assert len(sent) == 3
    assert slept == [webhook.POST_SPACING_SECONDS] * 2


def test_a_refused_milestone_is_retried_next_run(state_file, configured, sent, monkeypatch):
    save_state({"posted": {}, "seeded": True}, state_file)
    use_matters(monkeypatch, [matter()])
    sent.fail = True
    assert main([]) == 1
    assert "MN-01016:notified:2026-08-15" not in load_state(state_file)["posted"]


def test_max_posts_holds_the_rest_over(state_file, configured, sent, monkeypatch):
    save_state({"posted": {}, "seeded": True}, state_file)
    use_matters(monkeypatch, [matter(), matter("MN-02000"), matter("MN-03000")])
    assert main(["--max-posts", "2"]) == 0
    assert len(sent) == 2


def test_an_undeployed_matter_is_left_for_the_next_run(state_file, configured, sent, monkeypatch):
    save_state({"posted": {}, "seeded": True}, state_file)
    use_matters(monkeypatch, [matter()])
    monkeypatch.setattr(webhook, "wait_for_deploy", lambda batch, by_id, timeout: [])
    assert main(["--wait-for-deploy", "60"]) == 0
    assert sent == []
    assert "MN-01016:notified:2026-08-15" not in load_state(state_file)["posted"]


def test_it_stands_down_when_the_api_poster_is_on(state_file, configured, sent, monkeypatch):
    monkeypatch.setenv("LINKEDIN_POST_ENABLED", "true")
    save_state({"posted": {}, "seeded": True}, state_file)
    use_matters(monkeypatch, [matter()])
    assert main([]) == 0
    assert sent == []


def test_it_needs_a_url(state_file, configured, sent, monkeypatch):
    monkeypatch.delenv("LINKEDIN_WEBHOOK_URL")
    use_matters(monkeypatch, [matter()])
    assert main([]) == 0
    assert sent == []
    assert not state_file.exists()


def test_share_links_stand_down_while_the_webhook_is_set(state_file, configured, monkeypatch):
    monkeypatch.setenv("LINKEDIN_SHARE_LINKS", "true")
    monkeypatch.setenv("NTFY_TOPIC", "topic")
    save_state({"posted": {}, "seeded": True}, state_file)
    monkeypatch.setattr(share_links, "load_matters", lambda: [matter()])
    notified = []
    monkeypatch.setattr(share_links, "notify", lambda milestone, **kw: notified.append(milestone))
    assert share_links.main([]) == 0
    assert notified == []


def test_deliver_posts_json_and_reports_status(monkeypatch):
    captured = {}

    class Response:
        status_code = 200

    def fake_post(url, json, headers, timeout):
        captured.update(url=url, json=json, headers=headers)
        return Response()

    monkeypatch.setattr(webhook.requests, "post", fake_post)
    assert webhook.deliver({"key": "k"}, url=URL)
    assert captured == {"url": URL, "json": {"key": "k"}, "headers": {}}
    assert webhook.deliver({"key": "k"}, url=URL, api_key="key")
    assert captured["headers"] == {"x-make-apikey": "key"}

    Response.status_code = 410
    assert not webhook.deliver({"key": "k"}, url=URL)


def test_a_failed_delivery_does_not_log_the_url(monkeypatch, capsys):
    def boom(url, json, headers, timeout):
        raise requests.ConnectionError(f"Max retries exceeded with url: {url}")

    monkeypatch.setattr(webhook.requests, "post", boom)
    assert not webhook.deliver({"key": "k"}, url=URL)
    out = capsys.readouterr()
    assert "secret-token" not in out.out + out.err


def test_a_sample_sends_the_latest_milestone_and_records_nothing(state_file, configured, sent, monkeypatch):
    save_state({"posted": {"MN-02000:notified:2026-09-01": {"seeded": True}}}, state_file)
    use_matters(monkeypatch, [
        matter(),
        matter("MN-02000", effective_notification_datetime="2026-09-01T12:00:00Z"),
    ])
    assert main(["--sample"]) == 0
    assert sent == ["MN-02000:notified:2026-09-01"]  # already posted, sent anyway
    assert list(load_state(state_file)["posted"]) == ["MN-02000:notified:2026-09-01"]
