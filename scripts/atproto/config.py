"""Identity, collections and on-disk state for the ATmosphere publishers.

Two kinds of configuration, kept apart on purpose:

* ``atproto/identity.json`` is tracked. It holds the site's DID, its handle and
  the PDS its repo lives on - all of them public by design (the DID is served
  at ``/.well-known/atproto-did`` so the handle resolves at all), so there is
  nothing to hide and a lot to gain from having one committed copy that the
  publishers, the build and the docs all read.
* Credentials come from the environment only, and never from a file. An
  ATProto app password can write anything into the repo it opens, including
  posts, so it is a repository secret like any other.

A missing DID or missing credentials is a *skip*, not an error: the pipeline
runs on forks and on pull requests where no secret is available, and a data
pipeline should not go red because it could not reach a social network.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from scripts.paths import REPO_ROOT

#: Tracked identity file. Public values only - see the module docstring.
IDENTITY_PATH = REPO_ROOT / "atproto" / "identity.json"

#: Lexicon schemas published under the site's own NSID authority.
LEXICON_DIR = REPO_ROOT / "atproto" / "lexicons"

#: NSID authority the site controls. ``mergers.fyi`` reversed - which is the
#: whole point of using the site's own domain: an NSID under ``fyi.mergers``
#: resolves, via a ``_lexicon.mergers.fyi`` DNS TXT record, to the DID below
#: and so to the schemas this repo publishes. Nobody else can claim it.
NSID_AUTHORITY = "fyi.mergers"

#: Collection holding one record per ACCC matter.
MATTER_COLLECTION = "fyi.mergers.matter"

#: Where a PDS keeps published lexicon schemas, one record per NSID.
SCHEMA_COLLECTION = "com.atproto.lexicon.schema"

#: Bluesky's post collection.
POST_COLLECTION = "app.bsky.feed.post"

#: Digests of the matter records last written, so a run only rewrites what
#: actually changed. Committed by the pipeline alongside the rest of
#: ``data/processed``.
RECORD_STATE_PATH = REPO_ROOT / "data" / "processed" / "atproto_records.json"

#: Matter events already posted to Bluesky, so a re-run cannot repost them.
POST_STATE_PATH = REPO_ROOT / "data" / "processed" / "atproto_posts.json"

#: Generated merger detail files - the same JSON the site itself serves, which
#: is deliberately what gets republished: the ATmosphere records should say
#: what the site says, not what some parallel view of the pipeline says.
MATTER_DATA_DIR = REPO_ROOT / "frontend" / "public" / "data" / "mergers"

SITE_URL = "https://mergers.fyi"

#: Thumbnail for a post's link card: the site's own Open Graph image, so a
#: card on Bluesky looks like the one any other link preview of the site shows.
CARD_IMAGE_PATH = REPO_ROOT / "frontend" / "public" / "og-image.png"

DEFAULT_SERVICE = "https://bsky.social"


@dataclass(frozen=True)
class Identity:
    """The site's public ATProto identity."""

    did: str
    handle: str
    service: str

    @property
    def configured(self) -> bool:
        """Whether a DID has been filled in (see ``docs/atproto.md``)."""
        return bool(self.did)


@dataclass(frozen=True)
class Credentials:
    """Login for the repo the publishers write to."""

    identifier: str
    password: str


def load_identity(path: Path | None = None) -> Identity:
    """Read ``atproto/identity.json``, with the environment able to override.

    ``ATPROTO_DID``/``ATPROTO_SERVICE`` win over the file so a throwaway
    account can be pointed at without editing tracked configuration - which is
    how the publishers get exercised against a test repo before the real one
    exists.
    """
    path = Path(path) if path is not None else IDENTITY_PATH
    raw: dict = {}
    if path.exists():
        raw = json.loads(path.read_text(encoding="utf-8"))

    return Identity(
        did=(os.environ.get("ATPROTO_DID") or raw.get("did") or "").strip(),
        handle=(raw.get("handle") or "mergers.fyi").strip(),
        service=(
            os.environ.get("ATPROTO_SERVICE")
            or raw.get("service")
            or DEFAULT_SERVICE
        ).strip(),
    )


def load_credentials() -> Credentials | None:
    """Return the app-password login, or ``None`` when it is not configured.

    The identifier defaults to the **DID**, not the handle, so the only secret
    a deployment has to set is the password itself. ``createSession`` takes
    either, and the DID is the one that is always true: the handle in this file
    is the one the site intends to use, which during setup is a handle the
    account has not been given yet, and after a migration may briefly be one it
    no longer holds. ``ATPROTO_IDENTIFIER`` overrides both.
    """
    password = os.environ.get("ATPROTO_APP_PASSWORD", "").strip()
    if not password:
        return None

    identity = load_identity()
    identifier = (
        os.environ.get("ATPROTO_IDENTIFIER", "").strip()
        or identity.did
        or identity.handle
    )
    if not identifier:
        return None

    return Credentials(identifier=identifier, password=password)


def posting_enabled() -> bool:
    """Whether Bluesky posting is switched on.

    Deliberately a second switch on top of the credentials. Records in a custom
    collection are inert data that nobody sees unless they go looking; a post
    lands in people's feeds. Wiring the step into the pipeline should not be
    the thing that starts posting.
    """
    return os.environ.get("ATPROTO_POST_ENABLED", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }
