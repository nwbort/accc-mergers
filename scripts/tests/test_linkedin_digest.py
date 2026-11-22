"""Tests for the weekly digest's LinkedIn post.

What matters: it reads as the email's subject and lede, links to /digest,
carries the milestone payload's keys (so the same Make scenario posts it), and
never sends unless the run is a production one.
"""

import pytest

from scripts.linkedin import digest as li_digest

URL = "https://hook.eu1.make.com/secret-token"


def _digest():
    return {
        "period_start": "2026-03-02T00:00:00+11:00",
        "period_end": "2026-03-08T23:59:59+11:00",
        "new_deals_notified": [{"merger_id": "MN-1"}, {"merger_id": "MN-2"}],
        "deals_cleared": [{"merger_id": "MN-3", "has_conditions": False}],
        "deals_referred_to_phase_2": [],
        "deals_declined": [],
        "deals_assessment_ceased": [],
        "deals_appealed_to_tribunal": [],
        "ongoing_phase_1": [{"merger_id": "MN-1"}],
        "ongoing_phase_2": [],
        "ongoing_tribunal_appeals": [],
    }


@pytest.fixture
def sent(monkeypatch):
    calls = []
    monkeypatch.setattr(li_digest.swe, "load_digest", _digest)
    monkeypatch.setattr(li_digest, "deliver",
                        lambda body, url, api_key="": calls.append(body) or True)
    return calls


def test_summary_is_the_lede_without_markup():
    text = li_digest.summary(_digest())
    assert "<" not in text
    assert text.startswith("The ACCC was notified of 2 new deals this week and cleared 1.")


def test_payload_links_to_the_digest_and_keeps_the_milestone_keys():
    body = li_digest.payload(_digest())
    milestone_keys = {
        "key", "matter_id", "date", "headline", "title", "text", "commentary",
        "commentary_little", "url", "description", "image_url",
    }
    assert milestone_keys <= set(body)
    assert body["kind"] == "digest"
    assert body["url"] == "https://mergers.fyi/digest"
    assert body["key"] == "digest:2026-03-08"
    assert body["commentary"].startswith("Weekly merger digest: 2 new deals, 1 cleared\n\nThe ACCC")
    assert "https://mergers.fyi/digest" in body["text"]
    assert "https://mergers.fyi/digest" not in body["commentary"]
    assert "{hashtag|\\#|accc}" in body["commentary_little"]


def test_sends_on_a_production_run(sent, monkeypatch):
    monkeypatch.setenv("LINKEDIN_WEBHOOK_URL", URL)
    monkeypatch.setenv("AUDIENCE", "production")
    assert li_digest.main([]) == 0
    assert [b["key"] for b in sent] == ["digest:2026-03-08"]


def test_never_sends_on_a_test_run(sent, monkeypatch):
    monkeypatch.setenv("LINKEDIN_WEBHOOK_URL", URL)
    monkeypatch.setenv("AUDIENCE", "test")
    assert li_digest.main([]) == 0
    assert sent == []


def test_dry_run_sends_nothing(sent, monkeypatch):
    monkeypatch.setenv("LINKEDIN_WEBHOOK_URL", URL)
    assert li_digest.main(["--dry-run"]) == 0
    assert sent == []


def test_skips_without_the_webhook(sent, monkeypatch):
    monkeypatch.delenv("LINKEDIN_WEBHOOK_URL", raising=False)
    monkeypatch.setenv("AUDIENCE", "production")
    assert li_digest.main([]) == 0
    assert sent == []


def test_a_refused_post_fails_the_step(monkeypatch):
    monkeypatch.setattr(li_digest.swe, "load_digest", _digest)
    monkeypatch.setattr(li_digest, "deliver", lambda body, url, api_key="": False)
    monkeypatch.setenv("LINKEDIN_WEBHOOK_URL", URL)
    monkeypatch.setenv("AUDIENCE", "production")
    assert li_digest.main([]) == 1
