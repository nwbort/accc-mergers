"""A small XRPC client for writing records to an AT Protocol repo.

Deliberately hand-rolled on ``requests`` rather than pulling in an ATProto
SDK. The publishers here need seven endpoints - open a session, put, create,
delete, read and list records, and upload a blob for a link card's thumbnail - and ``scripts/requirements.txt`` is installed on
every pipeline run, so a dependency that exists to save fifty lines is a poor
trade against the install time it costs several times a day.

What this does not do: refresh tokens (a session outlives any run here),
or any read side beyond fetching records back from its own repo. Reach for an SDK if
those are ever needed.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

import requests

#: How long any single XRPC call may take.
TIMEOUT = 30

#: Retries for a call that failed in a way that might not fail again.
MAX_ATTEMPTS = 4

#: Longest a 429's Retry-After will be honoured before giving up on the call.
#: A PDS asking for ten minutes means this run should end, not sleep through
#: the pipeline's timeout.
MAX_BACKOFF = 60


class XrpcError(RuntimeError):
    """An XRPC call failed.

    ``error`` carries the machine-readable name the PDS returned (e.g.
    ``InvalidRequest``, ``RateLimitExceeded``) where there was one.
    """

    def __init__(self, message: str, *, status: int | None = None, error: str = ""):
        super().__init__(message)
        self.status = status
        self.error = error


@dataclass
class Session:
    """An authenticated session against one PDS."""

    did: str
    handle: str
    access_jwt: str
    service: str


@dataclass
class AtprotoClient:
    """Authenticated writer for a single ATProto repo.

    ``pause`` is slept between writes. The PDS rate limits repo writes, and a
    first full publish of the register is several hundred of them in a row;
    trickling them is both politer and less likely to lose the back half of a
    run to a limit that only resets hourly.
    """

    service: str
    pause: float = 0.0
    http: requests.Session = field(default_factory=requests.Session)
    session: Session | None = None

    # -- session ---------------------------------------------------------

    def login(self, identifier: str, password: str) -> Session:
        """Open a session, and follow the account's DID document to its PDS.

        ``createSession`` at an entryway (bsky.social is one) returns the DID
        document, whose ``#atproto_pds`` service is where the repo actually
        lives. Writing there directly rather than through the entryway is what
        the protocol expects and is one less hop per record.
        """
        payload = self._post(
            "com.atproto.server.createSession",
            {"identifier": identifier, "password": password},
            service=self.service,
            authed=False,
        )

        service = _pds_endpoint(payload.get("didDoc")) or self.service
        self.session = Session(
            did=payload["did"],
            handle=payload.get("handle", identifier),
            access_jwt=payload["accessJwt"],
            service=service,
        )
        return self.session

    @property
    def did(self) -> str:
        if self.session is None:
            raise XrpcError("not logged in")
        return self.session.did

    # -- repo writes -----------------------------------------------------

    def put_record(
        self,
        collection: str,
        rkey: str,
        record: dict,
        *,
        validate: bool | None = None,
    ) -> dict:
        """Create or overwrite the record at ``rkey``.

        ``putRecord`` rather than ``applyWrites`` because it is the only
        upsert in the API - ``applyWrites`` offers create and update, each of
        which fails on the wrong side of "does this already exist". An upsert
        keyed on the ACCC's matter id means a publish run never has to know
        what it published last time to be correct; the state file is an
        optimisation, not the source of truth.
        """
        body: dict[str, Any] = {
            "repo": self.did,
            "collection": collection,
            "rkey": rkey,
            "record": record,
        }
        if validate is not None:
            body["validate"] = validate
        return self._write("com.atproto.repo.putRecord", body)

    def create_record(
        self, collection: str, record: dict, *, validate: bool | None = None
    ) -> dict:
        """Append a record with a server-assigned key (a post, say)."""
        body: dict[str, Any] = {
            "repo": self.did,
            "collection": collection,
            "record": record,
        }
        if validate is not None:
            body["validate"] = validate
        return self._write("com.atproto.repo.createRecord", body)

    def delete_record(self, collection: str, rkey: str) -> None:
        """Remove a record. Deleting what is not there is not an error."""
        self._write(
            "com.atproto.repo.deleteRecord",
            {"repo": self.did, "collection": collection, "rkey": rkey},
        )

    def get_record(self, collection: str, rkey: str) -> dict | None:
        """Fetch one record back, or ``None`` if the repo has no such key."""
        try:
            return self._get(
                "com.atproto.repo.getRecord",
                {"repo": self.did, "collection": collection, "rkey": rkey},
            )
        except XrpcError as exc:
            if exc.status == 400 and exc.error == "RecordNotFound":
                return None
            raise

    def list_records(self, collection: str, *, limit: int = 100) -> list[dict]:
        """The newest ``limit`` records in a collection (one page, max 100)."""
        payload = self._get(
            "com.atproto.repo.listRecords",
            {"repo": self.did, "collection": collection, "limit": limit},
        )
        return payload.get("records") or []

    # -- blobs -----------------------------------------------------------

    def upload_blob(self, data: bytes, mime_type: str) -> dict:
        """Upload raw bytes and return the blob reference to embed in a record.

        The PDS holds an upload only until a record references it, so the
        returned blob has to be written into one within the same session.
        """
        payload = self._call(
            "POST",
            "com.atproto.repo.uploadBlob",
            data=data,
            content_type=mime_type,
        )
        return payload["blob"]

    # -- transport -------------------------------------------------------

    def _write(self, nsid: str, body: dict) -> dict:
        result = self._post(nsid, body)
        if self.pause:
            time.sleep(self.pause)
        return result

    def _post(
        self,
        nsid: str,
        body: dict,
        *,
        service: str | None = None,
        authed: bool = True,
    ) -> dict:
        return self._call("POST", nsid, json=body, service=service, authed=authed)

    def _get(self, nsid: str, params: dict) -> dict:
        return self._call("GET", nsid, params=params)

    def _call(
        self,
        method: str,
        nsid: str,
        *,
        json: dict | None = None,
        params: dict | None = None,
        data: bytes | None = None,
        content_type: str | None = None,
        service: str | None = None,
        authed: bool = True,
    ) -> dict:
        base = service or (self.session.service if self.session else self.service)
        url = f"{base.rstrip('/')}/xrpc/{nsid}"

        headers = {}
        if content_type:
            headers["Content-Type"] = content_type
        if authed:
            if self.session is None:
                raise XrpcError(f"{nsid} needs a session; call login() first")
            headers["Authorization"] = f"Bearer {self.session.access_jwt}"

        last: XrpcError | None = None
        for attempt in range(MAX_ATTEMPTS):
            try:
                response = self.http.request(
                    method, url, json=json, params=params, data=data,
                    headers=headers, timeout=TIMEOUT,
                )
            except requests.RequestException as exc:
                last = XrpcError(f"{nsid}: {exc}")
                _sleep_before_retry(attempt)
                continue

            if response.status_code < 400:
                return response.json() if response.content else {}

            error, message = _error_from(response)
            failure = XrpcError(
                f"{nsid} failed ({response.status_code} {error or 'error'}): {message}",
                status=response.status_code,
                error=error,
            )

            # 4xx other than a rate limit is this call's own fault - a bad
            # record, a bad key, an expired password. Retrying re-sends the
            # same broken request.
            if response.status_code == 429:
                delay = _retry_after(response)
                if delay is None or delay > MAX_BACKOFF or attempt == MAX_ATTEMPTS - 1:
                    raise failure
                time.sleep(delay)
                last = failure
                continue
            if response.status_code < 500:
                raise failure

            last = failure
            _sleep_before_retry(attempt)

        raise last or XrpcError(f"{nsid} failed")


def _sleep_before_retry(attempt: int) -> None:
    time.sleep(min(2 ** attempt, MAX_BACKOFF))


def _retry_after(response: requests.Response) -> float | None:
    raw = response.headers.get("Retry-After", "").strip()
    if not raw:
        return 1.0
    try:
        return max(0.0, float(raw))
    except ValueError:
        # An HTTP-date form. Honouring it exactly is not worth a date parse
        # here; treat it as "unknown, too long" and let the caller stop.
        return None


def _error_from(response: requests.Response) -> tuple[str, str]:
    try:
        payload = response.json()
    except ValueError:
        return "", (response.text or "")[:300]
    if not isinstance(payload, dict):
        return "", str(payload)[:300]
    return str(payload.get("error", "")), str(payload.get("message", ""))[:300]


def _pds_endpoint(did_doc: Any) -> str | None:
    """Pull the ``#atproto_pds`` service endpoint out of a DID document."""
    if not isinstance(did_doc, dict):
        return None
    for service in did_doc.get("service") or []:
        if not isinstance(service, dict):
            continue
        if service.get("type") == "AtprotoPersonalDataServer":
            endpoint = service.get("serviceEndpoint")
            if isinstance(endpoint, str) and endpoint.startswith("http"):
                return endpoint
    return None
