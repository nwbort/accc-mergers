"""Opening an authenticated session, or explaining why there isn't one.

Every entry point starts the same way and, crucially, ends the same way when
the repo is not configured: a printed reason and a zero exit. The pipeline
runs on forks and pull requests with no secrets at all, and the rule this repo
already follows for ntfy holds here too - a data pipeline does not go red
because it could not reach a social network.
"""

from __future__ import annotations

import sys

from scripts.atproto import config
from scripts.atproto.client import AtprotoClient, XrpcError


def open_client(*, pause: float = 0.0) -> tuple[AtprotoClient, config.Identity] | None:
    """Log in and return the client, or ``None`` with the reason printed.

    The DID in ``atproto/identity.json`` is checked against the one the login
    actually produced. They differ when a password for the wrong account gets
    set, and the failure that would cause - the whole register republished
    into a stranger's repo - is not one worth discovering afterwards.
    """
    identity = config.load_identity()
    credentials = config.load_credentials()

    if credentials is None:
        print(
            "ATPROTO_APP_PASSWORD is not set - skipping. See docs/atproto.md.",
            file=sys.stderr,
        )
        return None

    client = AtprotoClient(service=identity.service, pause=pause)
    try:
        session = client.login(credentials.identifier, credentials.password)
    except XrpcError as exc:
        print(f"ATProto login failed: {exc}", file=sys.stderr)
        return None

    if identity.configured and session.did != identity.did:
        print(
            f"Refusing to publish: logged in as {session.did} but "
            f"atproto/identity.json names {identity.did}.",
            file=sys.stderr,
        )
        return None

    print(f"Publishing as {session.handle} ({session.did}) via {session.service}")
    return client, identity
