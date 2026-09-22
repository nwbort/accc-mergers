"""Tests for the incremental matter publisher and the connect gate."""

import json

import pytest

from scripts.atproto import config, connect, publish_matters
from scripts.atproto.client import Session, XrpcError
from scripts.atproto.publish_matters import load_state, main, plan, save_state

NOW = "2026-09-22T00:00:00Z"


def matter(merger_id="MN-01016", **overrides):
    record = {
        "merger_id": merger_id,
        "merger_name": f"Matter {merger_id}",
        "status": "Under assessment",
        "stage": "Phase 1 - initial assessment",
        "is_waiver": False,
        "effective_notification_datetime": "2026-08-15T12:00:00Z",
        "events": [],
    }
    record.update(overrides)
    return record


class FakeClient:
    def __init__(self, fail_on=()):
        self.written = {}
        self.deleted = []
        self.fail_on = set(fail_on)

    def put_record(self, collection, rkey, record, validate=None):
        if rkey in self.fail_on:
            raise XrpcError(f"refused {rkey}")
        self.written[rkey] = record
        return {"uri": f"at://did:plc:example/{collection}/{rkey}", "cid": f"cid-{rkey}"}

    def delete_record(self, collection, rkey):
        self.deleted.append(rkey)


@pytest.fixture
def state_file(tmp_path, monkeypatch):
    path = tmp_path / "atproto_records.json"
    monkeypatch.setattr(config, "RECORD_STATE_PATH", path)
    return path


@pytest.fixture
def fake_client(monkeypatch):
    client = FakeClient()
    monkeypatch.setattr(
        publish_matters, "open_client", lambda **_kwargs: (client, config.load_identity())
    )
    return client


def use_matters(monkeypatch, matters):
    monkeypatch.setattr(publish_matters, "load_matters", lambda: matters)


# -- planning ---------------------------------------------------------------


def test_a_first_run_writes_everything():
    writes, deletions = plan([matter("MN-1"), matter("MN-2")], {"records": {}}, now=NOW)
    assert [rkey for rkey, _ in writes] == ["MN-1", "MN-2"]
    assert deletions == []


def test_an_unchanged_matter_is_not_rewritten():
    matters = [matter("MN-1")]
    writes, _ = plan(matters, {"records": {}}, now=NOW)
    state = {"records": {"MN-1": {"digest": publish_matters.record_digest(writes[0][1])}}}

    assert plan(matters, state, now="2027-01-01T00:00:00Z") == ([], [])


def test_a_changed_matter_is_rewritten_and_restamped():
    matters = [matter("MN-1")]
    first, _ = plan(matters, {"records": {}}, now=NOW)
    state = {"records": {"MN-1": {"digest": publish_matters.record_digest(first[0][1])}}}

    changed = [matter("MN-1", status="Assessment completed")]
    writes, _ = plan(changed, state, now="2027-01-01T00:00:00Z")
    assert [rkey for rkey, _ in writes] == ["MN-1"]
    assert writes[0][1]["indexedAt"] == "2027-01-01T00:00:00Z"


def test_a_matter_that_left_the_dataset_is_deleted():
    """Keeps the collection in step with the self-pruning generated data."""
    state = {"records": {"MN-1": {"digest": "x"}, "MN-GONE": {"digest": "y"}}}
    _, deletions = plan([matter("MN-1")], state, now=NOW)
    assert deletions == ["MN-GONE"]


# -- state ------------------------------------------------------------------


def test_state_survives_a_round_trip(state_file):
    save_state({"records": {"MN-1": {"digest": "abc"}}})
    assert load_state()["records"]["MN-1"]["digest"] == "abc"


def test_a_state_file_from_a_future_format_is_discarded_not_trusted(state_file):
    state_file.write_text(json.dumps({"version": 99, "records": {"MN-1": {"digest": "abc"}}}))
    assert load_state() == {"version": publish_matters.STATE_VERSION, "records": {}}


def test_a_missing_state_file_is_an_empty_state(state_file):
    assert load_state()["records"] == {}


# -- the run ----------------------------------------------------------------


def test_a_run_writes_records_and_remembers_them(monkeypatch, state_file, fake_client):
    use_matters(monkeypatch, [matter("MN-1"), matter("MN-2")])

    assert main([]) == 0
    assert sorted(fake_client.written) == ["MN-1", "MN-2"]
    assert sorted(load_state()["records"]) == ["MN-1", "MN-2"]
    assert load_state()["records"]["MN-1"]["cid"] == "cid-MN-1"


def test_a_second_run_writes_nothing(monkeypatch, state_file, fake_client):
    use_matters(monkeypatch, [matter("MN-1")])
    main([])
    fake_client.written.clear()

    assert main([]) == 0
    assert fake_client.written == {}


def test_dry_run_touches_neither_the_network_nor_the_state(monkeypatch, state_file):
    use_matters(monkeypatch, [matter("MN-1")])
    monkeypatch.setattr(
        publish_matters,
        "open_client",
        lambda **_kwargs: pytest.fail("dry run must not open a session"),
    )

    assert main(["--dry-run"]) == 0
    assert not state_file.exists()


def test_limit_leaves_the_rest_for_the_next_run(monkeypatch, state_file, fake_client):
    use_matters(monkeypatch, [matter(f"MN-{n}") for n in range(5)])

    assert main(["--limit", "2"]) == 0
    assert len(fake_client.written) == 2

    fake_client.written.clear()
    main(["--limit", "2"])
    assert len(fake_client.written) == 2


def test_one_rejected_record_fails_the_run_but_keeps_the_others(
    monkeypatch, state_file, fake_client
):
    fake_client.fail_on = {"MN-2"}
    use_matters(monkeypatch, [matter("MN-1"), matter("MN-2"), matter("MN-3")])

    assert main([]) == 1
    assert sorted(load_state()["records"]) == ["MN-1", "MN-3"]


def test_a_deleted_matter_leaves_the_state(monkeypatch, state_file, fake_client):
    use_matters(monkeypatch, [matter("MN-1"), matter("MN-2")])
    main([])

    use_matters(monkeypatch, [matter("MN-1")])
    assert main([]) == 0
    assert fake_client.deleted == ["MN-2"]
    assert sorted(load_state()["records"]) == ["MN-1"]


def test_no_credentials_is_a_skip_not_a_failure(monkeypatch, state_file):
    use_matters(monkeypatch, [matter("MN-1")])
    monkeypatch.delenv("ATPROTO_APP_PASSWORD", raising=False)

    assert main([]) == 0


# -- credentials ------------------------------------------------------------


def test_no_password_means_no_credentials(monkeypatch):
    monkeypatch.delenv("ATPROTO_APP_PASSWORD", raising=False)
    assert config.load_credentials() is None


def test_login_defaults_to_the_did_not_the_intended_handle(monkeypatch):
    """During setup the account does not yet hold the handle in identity.json."""
    monkeypatch.setenv("ATPROTO_APP_PASSWORD", "pw")
    monkeypatch.setenv("ATPROTO_DID", "did:plc:example")
    monkeypatch.delenv("ATPROTO_IDENTIFIER", raising=False)

    assert config.load_credentials().identifier == "did:plc:example"


def test_an_explicit_identifier_overrides_the_did(monkeypatch):
    monkeypatch.setenv("ATPROTO_APP_PASSWORD", "pw")
    monkeypatch.setenv("ATPROTO_DID", "did:plc:example")
    monkeypatch.setenv("ATPROTO_IDENTIFIER", "mergers-fyi.bsky.social")

    assert config.load_credentials().identifier == "mergers-fyi.bsky.social"


# -- the connect gate -------------------------------------------------------


def test_connect_skips_without_a_password(monkeypatch, capsys):
    monkeypatch.delenv("ATPROTO_APP_PASSWORD", raising=False)
    assert connect.open_client() is None
    assert "ATPROTO_APP_PASSWORD" in capsys.readouterr().err


def test_connect_refuses_a_session_for_the_wrong_account(monkeypatch, capsys):
    """A password for the wrong account would republish the register elsewhere."""
    monkeypatch.setenv("ATPROTO_APP_PASSWORD", "pw")
    monkeypatch.setenv("ATPROTO_DID", "did:plc:ours")

    class WrongAccount:
        def __init__(self, **_kwargs):
            pass

        def login(self, identifier, password):
            return Session(
                did="did:plc:theirs",
                handle="someone.else",
                access_jwt="jwt",
                service="https://pds.example.net",
            )

    monkeypatch.setattr(connect, "AtprotoClient", WrongAccount)

    assert connect.open_client() is None
    assert "Refusing to publish" in capsys.readouterr().err


def test_connect_accepts_a_session_for_the_configured_account(monkeypatch):
    monkeypatch.setenv("ATPROTO_APP_PASSWORD", "pw")
    monkeypatch.setenv("ATPROTO_DID", "did:plc:ours")

    class RightAccount:
        def __init__(self, **_kwargs):
            pass

        def login(self, identifier, password):
            return Session(
                did="did:plc:ours",
                handle="mergers.fyi",
                access_jwt="jwt",
                service="https://pds.example.net",
            )

    monkeypatch.setattr(connect, "AtprotoClient", RightAccount)

    opened = connect.open_client()
    assert opened is not None
