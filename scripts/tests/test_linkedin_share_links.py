"""Tests for the LinkedIn share-link notifier.

What matters: the link opens the composer with the whole post in it, a
milestone is only recorded once its notification is delivered, and the
notifier steps aside the moment the API poster is switched on.
"""

from urllib.parse import parse_qs, urlparse

import pytest

from scripts.atproto.post_bluesky import load_state, milestones, save_state
from scripts.linkedin import config, share_links
from scripts.linkedin.share_links import main, share_text, share_url


def matter(merger_id="MN-01016", **overrides):
    record = {
        "merger_id": merger_id,
        "merger_name": "Asahi - Warehouse site (Vic)",
        "status": "Under assessment",
        "stage": "Phase 1 - initial assessment",
        "is_waiver": False,
        "effective_notification_datetime": "2026-08-15T12:00:00Z",
        "merger_description": "Asahi (**Asahi**) will enter into a lease.",
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
    monkeypatch.setenv("LINKEDIN_SHARE_LINKS", "true")
    monkeypatch.setenv("NTFY_TOPIC", "topic")
    monkeypatch.delenv("LINKEDIN_POST_ENABLED", raising=False)


class Sent(list):
    """Milestone keys handed to ntfy; ``fail`` makes every delivery fail."""

    fail = False


@pytest.fixture
def sent(monkeypatch):
    calls = Sent()

    def fake_notify(milestone, **kwargs):
        calls.append(milestone.key)
        return not calls.fail

    monkeypatch.setattr(share_links, "notify", fake_notify)
    return calls


def use_matters(monkeypatch, matters):
    monkeypatch.setattr(share_links, "load_matters", lambda: matters)


def test_the_link_opens_the_composer_with_the_whole_post():
    (milestone,) = milestones(matter())
    query = parse_qs(urlparse(share_url(milestone)).query)
    assert query["shareActive"] == ["true"]
    assert query["text"] == [share_text(milestone)]


def test_the_text_is_plain_and_carries_the_matter_link_before_the_tags():
    (milestone,) = milestones(matter())
    lines = share_text(milestone).split("\n\n")
    assert lines[0] == "Notified to the ACCC: Asahi - Warehouse site (Vic)"
    assert "\\" not in share_text(milestone)  # no little-format escapes
    # The kind keeps a re-share at the next milestone from hitting LinkedIn's
    # cached preview of the last one.
    assert lines[-2] == "https://mergers.fyi/mergers/MN-01016?m=notified"
    assert lines[-1] == "#accc"


def test_first_run_seeds(state_file, configured, sent, monkeypatch):
    use_matters(monkeypatch, [matter()])
    assert main([]) == 0
    assert sent == []
    assert list(load_state(state_file)["posted"]) == ["MN-01016:notified:2026-08-15"]


def test_a_new_milestone_is_sent_once(state_file, configured, sent, monkeypatch):
    save_state({"posted": {"MN-01016:notified:2026-08-15": {"seeded": True}}}, state_file)
    use_matters(monkeypatch, [matter(), matter("MN-02000")])
    assert main([]) == 0
    assert sent == ["MN-02000:notified:2026-08-15"]
    assert load_state(state_file)["posted"]["MN-02000:notified:2026-08-15"]["shareLink"]
    assert main([]) == 0
    assert sent == ["MN-02000:notified:2026-08-15"]


def test_an_undelivered_link_is_retried_next_run(state_file, configured, sent, monkeypatch):
    save_state({"posted": {}, "seeded": True}, state_file)
    use_matters(monkeypatch, [matter()])
    sent.fail = True
    assert main([]) == 1
    assert "MN-01016:notified:2026-08-15" not in load_state(state_file)["posted"]


def test_it_stands_down_when_the_api_poster_is_on(state_file, configured, sent, monkeypatch):
    monkeypatch.setenv("LINKEDIN_POST_ENABLED", "true")
    save_state({"posted": {}, "seeded": True}, state_file)
    use_matters(monkeypatch, [matter()])
    assert main([]) == 0
    assert sent == []


@pytest.mark.parametrize("missing", ["LINKEDIN_SHARE_LINKS", "NTFY_TOPIC"])
def test_it_needs_its_switch_and_a_topic(state_file, configured, sent, monkeypatch, missing):
    monkeypatch.delenv(missing)
    use_matters(monkeypatch, [matter()])
    assert main([]) == 0
    assert sent == []
    assert not state_file.exists()


def test_notify_offers_the_link_to_copy(monkeypatch):
    captured = {}

    class Response:
        status_code = 200

    def fake_post(url, json, headers, timeout):
        captured.update(url=url, json=json, headers=headers)
        return Response()

    monkeypatch.setattr(share_links.requests, "post", fake_post)
    (milestone,) = milestones(matter())
    assert share_links.notify(milestone, topic="t", server="https://ntfy.sh/", token="tok")
    assert captured["url"] == "https://ntfy.sh"
    assert captured["json"]["topic"] == "t"
    assert captured["json"]["click"] == milestone.url  # the app drops a share link's text
    copy, view = captured["json"]["actions"]
    assert copy == {"action": "copy", "label": "Copy LinkedIn link", "value": share_url(milestone)}
    assert view["url"] == milestone.url
    assert captured["json"]["message"] == share_url(milestone)
    assert captured["headers"] == {"Authorization": "Bearer tok"}



class Live:
    """A fake mergers.fyi that starts serving ``record`` after ``after`` polls."""

    def __init__(self, record, after=0):
        self.record, self.after, self.calls = record, after, 0

    def __call__(self, url, params, headers, timeout):
        self.calls += 1
        deployed = self.calls > self.after
        record = self.record

        class Response:
            status_code = 200

            @staticmethod
            def json():
                if not deployed:
                    raise ValueError("index.html is not JSON")  # SPA fallback
                return record

        return Response()


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


def test_a_link_waits_until_its_matter_is_deployed():
    record = matter()
    (milestone,) = milestones(record)
    clock, fetch = Clock(), Live(record, after=2)
    ready = share_links.wait_for_deploy(
        [milestone], {"MN-01016": record}, timeout=300, fetch=fetch, sleep=clock.sleep, clock=clock,
    )
    assert ready == [milestone]
    assert fetch.calls == 3


def test_an_older_deploy_of_the_matter_does_not_count():
    record = matter()
    stale = {**record, "og_card": "notified-to-the-accc.png", "status": "Older"}
    (milestone,) = milestones(record)
    clock = Clock()
    ready = share_links.wait_for_deploy(
        [milestone], {"MN-01016": record}, timeout=60, poll=20,
        fetch=Live(stale), sleep=clock.sleep, clock=clock,
    )
    assert ready == []


def test_an_undeployed_matter_is_left_for_the_next_run(state_file, configured, sent, monkeypatch):
    save_state({"posted": {}, "seeded": True}, state_file)
    use_matters(monkeypatch, [matter()])
    monkeypatch.setattr(share_links, "wait_for_deploy", lambda batch, by_id, timeout: [])
    assert main(["--wait-for-deploy", "60"]) == 0
    assert sent == []
    assert "MN-01016:notified:2026-08-15" not in load_state(state_file)["posted"]
