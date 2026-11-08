"""Tests for scripts/push/fcm.py."""

import base64
import importlib
import json
import sys
from unittest import mock

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

# test_pipeline.py replaces requests with a MagicMock in sys.modules for the
# whole session, and these tests raise and catch its real exceptions: import
# the real module for fcm, then put the stand-in back for everyone else.
_stand_in = sys.modules.get("requests")
if isinstance(_stand_in, mock.Mock):
    del sys.modules["requests"]
requests = importlib.import_module("requests")
sys.modules.pop("scripts.push.fcm", None)
from scripts.push import fcm  # noqa: E402

if isinstance(_stand_in, mock.Mock):
    sys.modules["requests"] = _stand_in


def _manifest(mergers=None, industries=None, phase2=(), fmt=1):
    return {
        "format": fmt,
        "mergers": dict(mergers or {}),
        "industries": dict(industries or {}),
        "phase2_current": list(phase2),
    }


BASE = _manifest({"MN-1": "a", "MN-2": "b"}, {"G": "g", "_orphans": "o"}, ["MN-2"])


def test_topic_names_match_the_app():
    # Push.Topics in nwbort/accc-mergers-app's notify/Push.kt, whose
    # LogicTest pins the same names: change both or neither.
    assert fcm.merger_topic("MN-01016") == "merger-MN-01016"
    assert fcm.industry_topic("_orphans") == "industry-_orphans"
    assert (fcm.ALL, fcm.LIST) == ("all", "list")


def test_nothing_changed_sends_nothing():
    assert fcm.changed_topics(BASE, json.loads(json.dumps(BASE))) == []


def test_changed_files_message_their_topics():
    cur = _manifest({"MN-1": "a2", "MN-2": "b"}, {"G": "g2", "_orphans": "o", "H": "h"}, ["MN-2"])
    assert fcm.changed_topics(BASE, cur) == ["merger-MN-1", "industry-G", "industry-H"]


def test_new_filing_or_phase2_change_messages_list():
    filed = _manifest({"MN-1": "a", "MN-2": "b", "MN-3": "c"}, BASE["industries"], ["MN-2"])
    # A new merger is no one's follow yet: only the list hears of it.
    assert fcm.changed_topics(BASE, filed) == ["list"]
    phase2 = _manifest(BASE["mergers"], BASE["industries"], ["MN-1", "MN-2"])
    assert fcm.changed_topics(BASE, phase2) == ["list"]


def test_a_removed_merger_is_not_messaged():
    cur = _manifest({"MN-1": "a"}, BASE["industries"], ["MN-2"])
    assert fcm.changed_topics(BASE, cur) == []


def test_too_many_changes_or_a_new_format_send_all():
    many = {f"MN-{i}": "x" for i in range(fcm.MAX_TOPICS + 1)}
    prev = _manifest(many)
    cur = _manifest({k: "y" for k in many})
    assert fcm.changed_topics(prev, cur) == ["all"]
    assert fcm.changed_topics(BASE, {**BASE, "format": 2}) == ["all"]


def test_caught_up_when_every_change_has_moved_on():
    expected = _manifest({"MN-1": "a2", "MN-2": "b"}, BASE["industries"], ["MN-2"])
    assert not fcm.caught_up(BASE, expected, BASE)
    assert fcm.caught_up(BASE, expected, expected)
    # A newer deploy than this checkout counts too.
    newer = _manifest({"MN-1": "a3", "MN-2": "b3"}, BASE["industries"], ["MN-2"])
    assert fcm.caught_up(BASE, expected, newer)
    assert not fcm.caught_up(BASE, expected, None)
    # This checkout changed nothing: whatever is live will do.
    assert fcm.caught_up(BASE, BASE, newer)


def test_caught_up_waits_for_a_phase2_change():
    expected = _manifest(BASE["mergers"], BASE["industries"], ["MN-1", "MN-2"])
    assert not fcm.caught_up(BASE, expected, BASE)
    assert fcm.caught_up(BASE, expected, expected)


class _Resp:
    def __init__(self, body=None, status=200):
        self.body, self.status_code = body, status
        self.text = json.dumps(body)

    def json(self):
        return self.body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code}", response=self)


def test_wait_for_deploy_polls_until_live():
    expected = _manifest({"MN-1": "a2", "MN-2": "b"}, BASE["industries"], ["MN-2"])
    served = iter([BASE, BASE, expected])
    sleeps = []
    live = fcm.wait_for_deploy(
        BASE, expected, timeout=600,
        fetch=lambda *a, **k: _Resp(next(served)),
        sleep=sleeps.append, clock=lambda: 0,
    )
    assert live == expected
    assert len(sleeps) == 2


def test_wait_for_deploy_gives_up_with_what_is_live():
    expected = _manifest({"MN-1": "a2", "MN-2": "b"}, BASE["industries"], ["MN-2"])
    ticks = iter([0, 1000])
    live = fcm.wait_for_deploy(
        BASE, expected, timeout=600,
        fetch=lambda *a, **k: _Resp(BASE), sleep=lambda s: None, clock=lambda: next(ticks),
    )
    assert live == BASE


@pytest.fixture
def account():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    ).decode()
    return {
        "project_id": "mergers-fyi",
        "client_email": "push@mergers-fyi.iam.gserviceaccount.com",
        "private_key_id": "k1",
        "private_key": pem,
        "token_uri": "https://oauth2.googleapis.com/token",
        "_public": key.public_key(),
    }


def _unb64(part):
    return base64.urlsafe_b64decode(part + "=" * (-len(part) % 4))


def test_signed_jwt_verifies(account):
    jwt = fcm.signed_jwt(account, now=1000)
    header, claims, signature = jwt.split(".")
    account["_public"].verify(
        _unb64(signature), f"{header}.{claims}".encode(), padding.PKCS1v15(), hashes.SHA256()
    )
    body = json.loads(_unb64(claims))
    assert body["iss"] == account["client_email"]
    assert body["scope"] == fcm.SCOPE
    assert body["aud"] == account["token_uri"]
    assert body["exp"] - body["iat"] == 3600
    assert json.loads(_unb64(header))["alg"] == "RS256"


def test_messages_are_collapsible_wake_ups():
    merger = fcm.message("merger-MN-1")["message"]
    assert merger["topic"] == "merger-MN-1"
    assert merger["data"] == {"check": "1"}
    assert merger["android"]["priority"] == "HIGH"
    assert merger["android"]["collapse_key"] == "check"
    assert fcm.message("industry-G")["message"]["android"]["priority"] == "NORMAL"


def _data_dir(tmp_path, manifest):
    """A data directory whose build_manifest() gives *manifest*'s merger ids (hashes differ)."""
    (tmp_path / "data" / "mergers").mkdir(parents=True)
    (tmp_path / "data" / "industries").mkdir()
    for mid in manifest["mergers"]:
        (tmp_path / "data" / "mergers" / f"{mid}.json").write_text("{}")
    (tmp_path / "data" / "phase2.json").write_text(json.dumps({"current": []}))
    return tmp_path / "data"


def test_main_skips_without_credentials(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("FCM_SERVICE_ACCOUNT", raising=False)
    state = tmp_path / "state.json"

    def no_fetch(*a, **k):
        raise AssertionError("fetched without credentials")

    assert fcm.main(["--state", str(state)], fetch=no_fetch) == 0
    assert not state.exists()
    assert "FCM_SERVICE_ACCOUNT is not set" in capsys.readouterr().err


def test_main_seeds_then_sends(tmp_path, monkeypatch, account):
    public = account.pop("_public")
    assert public
    monkeypatch.setenv("FCM_SERVICE_ACCOUNT", json.dumps(account))
    state = tmp_path / "state.json"
    data = _data_dir(tmp_path, BASE)
    served = {"manifest": BASE}
    posts = []

    def fetch(url, **kwargs):
        assert url == fcm.LIVE_MANIFEST_URL
        return _Resp(served["manifest"])

    def post(url, **kwargs):
        posts.append((url, kwargs))
        if url == account["token_uri"]:
            return _Resp({"access_token": "tok"})
        return _Resp({"name": "projects/mergers-fyi/messages/1"})

    args = ["--state", str(state), "--data-dir", str(data)]
    # First run: nothing to compare with, so it only records.
    assert fcm.main(args, fetch=fetch, post=post) == 0
    assert posts == []
    assert json.loads(state.read_text()) == BASE

    served["manifest"] = _manifest({"MN-1": "a2", "MN-2": "b"}, BASE["industries"], ["MN-2"])
    assert fcm.main(args, fetch=fetch, post=post) == 0
    sends = [kw for url, kw in posts if "messages:send" in url]
    assert posts[1][0] == fcm.SEND_URL.format(project="mergers-fyi")
    assert [kw["json"]["message"]["topic"] for kw in sends] == ["merger-MN-1"]
    assert sends[0]["headers"]["Authorization"] == "Bearer tok"
    assert json.loads(state.read_text()) == served["manifest"]


def test_main_records_even_when_a_send_fails(tmp_path, monkeypatch, account):
    account.pop("_public")
    monkeypatch.setenv("FCM_SERVICE_ACCOUNT", json.dumps(account))
    state = tmp_path / "state.json"
    fcm.save_state(state, BASE)
    current = _manifest({"MN-1": "a2", "MN-2": "b2"}, BASE["industries"], ["MN-2"])

    def post(url, **kwargs):
        if url == account["token_uri"]:
            return _Resp({"access_token": "tok"})
        return _Resp({"error": "nope"}, status=500 if kwargs["json"]["message"]["topic"] == "merger-MN-1" else 200)

    code = fcm.main(
        ["--state", str(state), "--data-dir", str(_data_dir(tmp_path, BASE))],
        fetch=lambda *a, **k: _Resp(current), post=post,
    )
    assert code == 1
    assert json.loads(state.read_text()) == current


def test_dry_run_needs_no_credentials_and_records_nothing(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("FCM_SERVICE_ACCOUNT", raising=False)
    state = tmp_path / "state.json"
    fcm.save_state(state, BASE)
    current = _manifest({"MN-1": "a2", "MN-2": "b"}, BASE["industries"], ["MN-2"])
    code = fcm.main(
        ["--state", str(state), "--data-dir", str(_data_dir(tmp_path, BASE)), "--dry-run"],
        fetch=lambda *a, **k: _Resp(current),
    )
    assert code == 0
    assert "merger-MN-1" in capsys.readouterr().out
    assert json.loads(state.read_text()) == BASE


def test_first_run_records_without_waiting_for_an_exact_match(tmp_path, monkeypatch, account):
    # With no state, waiting would need live == this checkout exactly: a live
    # site one deploy behind (here, an older manifest shape) would hold the
    # run for the whole deadline only to send nothing.
    account.pop("_public")
    monkeypatch.setenv("FCM_SERVICE_ACCOUNT", json.dumps(account))
    state = tmp_path / "state.json"
    stale = {"format": 1, "mergers": {"MN-1": "a"}, "phase2_current": []}

    def no_sleep(seconds):
        raise AssertionError("waited on a first run")

    code = fcm.main(
        ["--state", str(state), "--data-dir", str(_data_dir(tmp_path, BASE)), "--wait-for-deploy", "900"],
        fetch=lambda *a, **k: _Resp(stale), post=lambda *a, **k: None, sleep=no_sleep,
    )
    assert code == 0
    assert json.loads(state.read_text()) == stale
