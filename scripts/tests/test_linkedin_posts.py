"""Tests for the LinkedIn poster.

Which milestones get posted is ``post_bluesky.milestones()`` and is tested
there. What is LinkedIn's own: escaping into the little text format (an
unescaped ``(`` truncates a post), the seeding rule against its own state
file, the read-back, and coping with a token that cannot read back at all.
"""

import pytest

from scripts.linkedin import config, post_linkedin
from scripts.linkedin.client import LinkedInError
from scripts.linkedin.post_linkedin import (
    already_posted,
    escape,
    main,
    post_body,
    post_text,
    preview,
    unescape,
)
from scripts.atproto.post_bluesky import load_state, milestones, save_state

AUTHOR = "urn:li:organization:123"


def matter(merger_id="MN-01016", **overrides):
    record = {
        "merger_id": merger_id,
        "merger_name": "Asahi - Warehouse site (Vic)",
        "status": "Under assessment",
        "stage": "Phase 1 - initial assessment",
        "is_waiver": False,
        "effective_notification_datetime": "2026-08-15T12:00:00Z",
        "merger_description": "Asahi (**Asahi**) will enter into a lease #1.",
        "events": [],
    }
    record.update(overrides)
    return record


class FakeClient:
    author = AUTHOR

    def __init__(self):
        self.posts = []
        self.uploads = []
        self.listed = []
        self.list_error = None

    def list_posts(self, count=100):
        if self.list_error:
            raise self.list_error
        return list(reversed(self.listed + self.posts))[:count]

    def upload_image(self, data):
        self.uploads.append(data)
        return f"urn:li:image:{len(self.uploads)}"

    def create_post(self, body):
        body = dict(body, id=f"urn:li:share:{len(self.posts) + 1}")
        self.posts.append(body)
        return body["id"]


@pytest.fixture
def state_file(tmp_path, monkeypatch):
    path = tmp_path / "linkedin_posts.json"
    monkeypatch.setattr(config, "POST_STATE_PATH", path)
    return path


@pytest.fixture
def enabled(monkeypatch):
    monkeypatch.setenv("LINKEDIN_POST_ENABLED", "true")


@pytest.fixture
def fake_client(monkeypatch):
    client = FakeClient()
    monkeypatch.setattr(post_linkedin, "open_client", lambda: client)
    monkeypatch.setattr(post_linkedin, "render_card", lambda **_: b"png")
    return client


def use_matters(monkeypatch, matters):
    monkeypatch.setattr(post_linkedin, "load_matters", lambda: matters)


# -- the little text format ---------------------------------------------------


def test_reserved_characters_are_escaped_and_round_trip():
    text = r"A (B) #c *d* _e_ [f] {g} <h> @i ~j | \k"
    escaped = escape(text)
    assert "(" not in escaped.replace("\\(", "")
    assert unescape(escaped) == text


def test_post_text_escapes_register_text_but_not_the_hashtag_template():
    (milestone,) = milestones(matter())
    text = post_text(milestone)
    assert text.startswith(r"Notified to the ACCC: Asahi - Warehouse site \(Vic\)")
    assert r"lease \#1." in text
    assert "**" not in text  # Markdown flattened before escaping
    assert text.endswith(r"{hashtag|\#|accc}")


def test_preview_reads_as_linkedin_shows_it():
    (milestone,) = milestones(matter())
    shown = preview(post_text(milestone))
    assert shown.splitlines()[0] == "Notified to the ACCC: Asahi - Warehouse site (Vic)"
    assert shown.endswith("#accc")


def test_a_long_description_is_trimmed():
    (milestone,) = milestones(matter(merger_description="word " * 400))
    text = post_text(milestone)
    assert len(text) < post_linkedin.MAX_POST_CHARS
    assert "…" in text


def test_post_body_is_an_article_card_linking_the_matter():
    (milestone,) = milestones(matter())
    body = post_body(milestone, author=AUTHOR, thumbnail="urn:li:image:9")
    article = body["content"]["article"]
    assert body["author"] == AUTHOR
    assert body["visibility"] == "PUBLIC"
    assert article["source"] == "https://mergers.fyi/mergers/MN-01016"
    assert article["thumbnail"] == "urn:li:image:9"
    assert article["description"] == "Asahi (Asahi) will enter into a lease #1."


# -- read-back -----------------------------------------------------------------


def test_already_posted_matches_link_and_whole_headline():
    (milestone,) = milestones(matter())
    posted = post_body(milestone, author=AUTHOR) | {"id": "urn:li:share:1"}
    assert already_posted(milestone, [posted]) == "urn:li:share:1"

    other_matter = dict(posted, content={"article": {"source": "https://mergers.fyi/mergers/X"}})
    assert already_posted(milestone, [other_matter]) is None

    other_kind = dict(posted, commentary="Notified to the ACCC again: x")
    assert already_posted(milestone, [other_kind]) is None


# -- the run -------------------------------------------------------------------


def test_nothing_happens_without_the_switch(state_file, fake_client, monkeypatch):
    use_matters(monkeypatch, [matter()])
    assert main([]) == 0
    assert fake_client.posts == []
    assert not state_file.exists()


def test_first_enabled_run_seeds_and_posts_nothing(state_file, enabled, fake_client, monkeypatch):
    use_matters(monkeypatch, [matter()])
    assert main([]) == 0
    assert fake_client.posts == []
    assert list(load_state(state_file)["posted"]) == ["MN-01016:notified:2026-08-15"]


def test_a_new_milestone_is_posted_once(state_file, enabled, fake_client, monkeypatch):
    save_state({"posted": {"MN-01016:notified:2026-08-15": {"seeded": True}}}, state_file)
    use_matters(monkeypatch, [matter(), matter("MN-02000", merger_name="New deal")])

    assert main([]) == 0
    assert len(fake_client.posts) == 1
    assert fake_client.posts[0]["content"]["article"]["source"].endswith("/MN-02000")
    assert fake_client.posts[0]["content"]["article"]["thumbnail"] == "urn:li:image:1"
    assert load_state(state_file)["posted"]["MN-02000:notified:2026-08-15"]["urn"] == "urn:li:share:1"

    assert main([]) == 0
    assert len(fake_client.posts) == 1


def test_a_post_from_a_lost_run_is_recovered_not_repeated(
    state_file, enabled, fake_client, monkeypatch
):
    save_state({"posted": {"MN-01016:notified:2026-08-15": {"seeded": True}}}, state_file)
    new = matter("MN-02000", merger_name="New deal")
    (milestone,) = milestones(new)
    fake_client.listed = [post_body(milestone, author=AUTHOR) | {"id": "urn:li:share:77"}]
    use_matters(monkeypatch, [matter(), new])

    assert main([]) == 0
    assert fake_client.posts == []
    entry = load_state(state_file)["posted"]["MN-02000:notified:2026-08-15"]
    assert entry == {"urn": "urn:li:share:77", "recovered": True}


def test_a_token_that_cannot_read_back_still_posts(state_file, enabled, fake_client, monkeypatch):
    save_state({"posted": {}, "seeded": True}, state_file)
    fake_client.list_error = LinkedInError("forbidden", status=403)
    use_matters(monkeypatch, [matter()])

    assert main([]) == 0
    assert len(fake_client.posts) == 1


def test_any_other_read_back_failure_posts_nothing(state_file, enabled, fake_client, monkeypatch):
    save_state({"posted": {}, "seeded": True}, state_file)
    fake_client.list_error = LinkedInError("boom", status=500)
    use_matters(monkeypatch, [matter()])

    assert main([]) == 1
    assert fake_client.posts == []


def test_no_credentials_is_a_skip(state_file, enabled, monkeypatch):
    for name in ("LINKEDIN_AUTHOR_URN", "LINKEDIN_ACCESS_TOKEN", "LINKEDIN_REFRESH_TOKEN"):
        monkeypatch.delenv(name, raising=False)
    save_state({"posted": {}, "seeded": True}, state_file)
    use_matters(monkeypatch, [matter()])
    assert main([]) == 0


def test_credentials_need_an_author_and_a_token(monkeypatch):
    for name in ("LINKEDIN_AUTHOR_URN", "LINKEDIN_ACCESS_TOKEN", "LINKEDIN_REFRESH_TOKEN",
                 "LINKEDIN_CLIENT_ID", "LINKEDIN_CLIENT_SECRET"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("LINKEDIN_ACCESS_TOKEN", "t")
    assert config.load_credentials() is None
    monkeypatch.setenv("LINKEDIN_AUTHOR_URN", AUTHOR)
    assert config.load_credentials().access_token == "t"

    monkeypatch.delenv("LINKEDIN_ACCESS_TOKEN")
    monkeypatch.setenv("LINKEDIN_REFRESH_TOKEN", "r")
    assert config.load_credentials() is None  # a refresh token alone is not enough
    monkeypatch.setenv("LINKEDIN_CLIENT_ID", "id")
    monkeypatch.setenv("LINKEDIN_CLIENT_SECRET", "secret")
    assert config.load_credentials().refreshable


# -- the client ------------------------------------------------------------------


class FakeResponse:
    def __init__(self, status=200, body=None, headers=None):
        self.status_code = status
        self._body = body or {}
        self.headers = headers or {}
        self.text = ""

    def json(self):
        return self._body


class FakeHttp:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def _next(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return self.responses.pop(0)

    request = put = post = _next


def test_client_sends_the_versioned_headers_and_returns_the_post_urn():
    from scripts.linkedin.client import LinkedInClient

    http = FakeHttp(FakeResponse(201, headers={"x-restli-id": "urn:li:share:5"}))
    client = LinkedInClient(access_token="tok", author=AUTHOR, version="202609", http=http)
    assert client.create_post({"author": AUTHOR}) == "urn:li:share:5"
    (method, url), kwargs = http.calls[0]
    assert (method, url) == ("POST", "https://api.linkedin.com/rest/posts")
    assert kwargs["headers"]["LinkedIn-Version"] == "202609"
    assert kwargs["headers"]["X-Restli-Protocol-Version"] == "2.0.0"
    assert kwargs["headers"]["Authorization"] == "Bearer tok"


def test_client_uploads_an_image_in_two_steps():
    from scripts.linkedin.client import LinkedInClient

    http = FakeHttp(
        FakeResponse(200, {"value": {"uploadUrl": "https://up", "image": "urn:li:image:1"}}),
        FakeResponse(201),
    )
    client = LinkedInClient(access_token="tok", author=AUTHOR, http=http)
    assert client.upload_image(b"png") == "urn:li:image:1"
    assert http.calls[0][1]["json"] == {"initializeUploadRequest": {"owner": AUTHOR}}
    assert http.calls[1][0] == ("https://up",)


def test_a_refresh_token_mints_a_fresh_access_token():
    from scripts.linkedin.client import mint_access_token

    creds = config.Credentials(author=AUTHOR, refresh_token="r", client_id="i", client_secret="s")
    http = FakeHttp(FakeResponse(200, {"access_token": "fresh"}))
    assert mint_access_token(creds, http) == "fresh"
    assert http.calls[0][1]["data"]["grant_type"] == "refresh_token"


def test_a_client_error_is_not_retried():
    from scripts.linkedin.client import LinkedInClient

    http = FakeHttp(FakeResponse(403, {"message": "ACCESS_DENIED"}))
    client = LinkedInClient(access_token="tok", author=AUTHOR, http=http)
    with pytest.raises(LinkedInError) as raised:
        client.list_posts()
    assert raised.value.status == 403
    assert len(http.calls) == 1
