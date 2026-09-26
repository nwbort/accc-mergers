"""Tests for the hand-rolled XRPC client."""

import pytest
import requests

from scripts.atproto import client as client_module
from scripts.atproto.client import AtprotoClient, XrpcError

DID_DOC = {
    "id": "did:plc:example",
    "service": [
        {
            "id": "#atproto_pds",
            "type": "AtprotoPersonalDataServer",
            "serviceEndpoint": "https://pds.example.net",
        }
    ],
}


class FakeResponse:
    def __init__(self, status_code=200, payload=None, headers=None, text=""):
        self.status_code = status_code
        self._payload = payload
        self.headers = headers or {}
        self.text = text
        self.content = b"x" if payload is not None or text else b""

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


class FakeHttp:
    """Stands in for ``requests.Session``, recording every call."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def request(self, method, url, json=None, params=None, data=None, headers=None, timeout=None):
        self.calls.append(
            {
                "method": method,
                "url": url,
                "json": json,
                "params": params,
                "data": data,
                "headers": headers or {},
            }
        )
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


@pytest.fixture(autouse=True)
def no_sleeping(monkeypatch):
    """Retries are tested for behaviour, not for how long they take."""
    monkeypatch.setattr(client_module.time, "sleep", lambda _seconds: None)


def logged_in(responses):
    http = FakeHttp(
        [FakeResponse(payload={"did": "did:plc:example", "handle": "mergers.fyi", "accessJwt": "jwt"})]
        + list(responses)
    )
    client = AtprotoClient(service="https://bsky.social", http=http)
    client.login("mergers.fyi", "app-password")
    return client, http


def test_login_follows_the_did_document_to_the_real_pds():
    """bsky.social is an entryway; the repo lives somewhere else."""
    http = FakeHttp(
        [
            FakeResponse(
                payload={
                    "did": "did:plc:example",
                    "handle": "mergers.fyi",
                    "accessJwt": "jwt",
                    "didDoc": DID_DOC,
                }
            ),
            FakeResponse(payload={"uri": "at://x", "cid": "c"}),
        ]
    )
    client = AtprotoClient(service="https://bsky.social", http=http)
    session = client.login("mergers.fyi", "pw")

    assert session.service == "https://pds.example.net"
    client.put_record("fyi.mergers.matter", "MN-1", {"a": 1})
    assert http.calls[1]["url"].startswith("https://pds.example.net/xrpc/")


def test_login_stays_put_when_there_is_no_did_document():
    client, http = logged_in([])
    assert client.session.service == "https://bsky.social"


def test_put_record_sends_the_repo_collection_and_key():
    client, http = logged_in([FakeResponse(payload={"uri": "at://x", "cid": "cid1"})])
    result = client.put_record("fyi.mergers.matter", "MN-01016", {"title": "x"})

    body = http.calls[1]["json"]
    assert body == {
        "repo": "did:plc:example",
        "collection": "fyi.mergers.matter",
        "rkey": "MN-01016",
        "record": {"title": "x"},
    }
    assert "validate" not in body, "unset means the PDS's own best-effort default"
    assert result["cid"] == "cid1"
    assert http.calls[1]["headers"]["Authorization"] == "Bearer jwt"


def test_upload_blob_sends_raw_bytes_with_their_content_type():
    blob = {"$type": "blob", "ref": {"$link": "bafk"}, "mimeType": "image/png", "size": 3}
    client, http = logged_in([FakeResponse(payload={"blob": blob})])

    assert client.upload_blob(b"png", "image/png") == blob
    call = http.calls[-1]
    assert call["url"] == "https://bsky.social/xrpc/com.atproto.repo.uploadBlob"
    assert call["data"] == b"png"
    assert call["json"] is None
    assert call["headers"]["Content-Type"] == "image/png"
    assert call["headers"]["Authorization"] == "Bearer jwt"


def test_validate_is_sent_only_when_asked_for():
    client, http = logged_in([FakeResponse(payload={})])
    client.put_record("fyi.mergers.matter", "MN-1", {}, validate=False)
    assert http.calls[1]["json"]["validate"] is False


def test_get_record_turns_a_missing_record_into_none():
    client, _ = logged_in(
        [FakeResponse(status_code=400, payload={"error": "RecordNotFound", "message": "nope"})]
    )
    assert client.get_record("fyi.mergers.matter", "MN-404") is None


def test_a_bad_request_is_raised_rather_than_retried():
    """Re-sending a record the PDS just rejected only wastes the rate limit."""
    client, http = logged_in(
        [FakeResponse(status_code=400, payload={"error": "InvalidRequest", "message": "bad record"})]
    )
    with pytest.raises(XrpcError) as excinfo:
        client.put_record("fyi.mergers.matter", "MN-1", {})

    assert excinfo.value.error == "InvalidRequest"
    assert len(http.calls) == 2


def test_a_server_error_is_retried():
    client, http = logged_in(
        [
            FakeResponse(status_code=502, text="bad gateway"),
            FakeResponse(payload={"uri": "at://x", "cid": "c"}),
        ]
    )
    assert client.put_record("fyi.mergers.matter", "MN-1", {})["cid"] == "c"
    assert len(http.calls) == 3


def test_a_network_error_is_retried():
    client, http = logged_in(
        [requests.ConnectionError("reset"), FakeResponse(payload={"cid": "c"})]
    )
    assert client.put_record("fyi.mergers.matter", "MN-1", {})["cid"] == "c"


def test_a_short_rate_limit_is_waited_out():
    client, http = logged_in(
        [
            FakeResponse(status_code=429, payload={"error": "RateLimitExceeded"}, headers={"Retry-After": "2"}),
            FakeResponse(payload={"cid": "c"}),
        ]
    )
    assert client.put_record("fyi.mergers.matter", "MN-1", {})["cid"] == "c"


def test_a_long_rate_limit_ends_the_call():
    """A PDS asking for ten minutes means this run should stop, not sleep."""
    client, _ = logged_in(
        [
            FakeResponse(
                status_code=429,
                payload={"error": "RateLimitExceeded"},
                headers={"Retry-After": "600"},
            )
        ]
    )
    with pytest.raises(XrpcError):
        client.put_record("fyi.mergers.matter", "MN-1", {})


def test_writing_without_a_session_is_refused_before_any_request():
    client = AtprotoClient(service="https://bsky.social", http=FakeHttp([]))
    with pytest.raises(XrpcError, match="not logged in"):
        client.put_record("fyi.mergers.matter", "MN-1", {})
