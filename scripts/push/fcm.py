"""Tell the Android app what changed in a deploy, over Firebase Cloud Messaging.

The app (nwbort/accc-mergers-app) used to learn about changes to what it
follows only by checking every couple of hours. Now each phone subscribes to
one FCM *topic* per thing it follows, and this script, run after each deploy,
sends a message to the topic of every file that changed. The follow list stays
on the phone: nothing here knows who follows what, only which files moved.

What changed is read off ``data/manifest.json`` (``scripts/generate/
data_manifest.py``), the same file the app's check starts from: the live one is
compared with the one this script last saw, kept between runs in the Actions
cache (``--state``). The first run, and the first after the cache is evicted,
only records it.

Topics (``Push.Topics`` in the app's ``notify/Push.kt``: change both or neither):

* ``merger-{id}``: that merger's detail file changed.
* ``industry-{stem}``: ``industries/{stem}.json`` changed (``G``, ``_orphans``),
  which is every followed industry under that division.
* ``list``: new merger ids, or a change to which matters are in Phase 2, for
  the app's new-filing alerts and "follow every Phase 2 matter".
* ``all``: sent alone, in place of the rest, when a deploy changes more than
  ``MAX_TOPICS`` of them (a regeneration that touches every file) or the
  manifest's format. Every subscribed phone is on it.

A message carries no news, only "check now": the app runs its usual check, which
decides what's news, so a change that isn't costs one check that finds nothing.
Each is collapsible (``collapse_key``) and lives a day, so a phone offline for a
while gets one when it reconnects, not a backlog. Merger messages are high
priority, the rest normal, since Android lowers the priority of an app whose
high-priority messages don't end in a notification.

``--wait-for-deploy``: the manifest checked out here says what this commit will
deploy; the script waits until the live one has caught up with it, so a phone
told to check finds the new data. If it hasn't after the deadline, whatever is
live is compared, and the rest is left for the next run. A run with no earlier
manifest sends nothing, so it doesn't wait: it records what is live.

Credentials: ``FCM_SERVICE_ACCOUNT``, a Firebase service account key (JSON),
with which this signs its own OAuth token (no Google client library). Without
it the script skips, touching nothing, as for ntfy and ATProto.

Usage:
    python -m scripts.push.fcm --state PATH [--wait-for-deploy SECONDS] [--dry-run]
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import time
from pathlib import Path

import requests

from scripts.generate.data_manifest import FORMAT, build_manifest
from scripts.paths import REPO_ROOT

LIVE_MANIFEST_URL = "https://mergers.fyi/data/manifest.json"
DATA_DIR = REPO_ROOT / "frontend" / "public" / "data"

ALL = "all"
LIST = "list"

#: More changed topics than this and one ``all`` message goes instead.
MAX_TOPICS = 100

#: How often to look at the live manifest while waiting for a deploy.
DEPLOY_POLL_SECONDS = 20

SCOPE = "https://www.googleapis.com/auth/firebase.messaging"
SEND_URL = "https://fcm.googleapis.com/v1/projects/{project}/messages:send"
TIMEOUT = 30


def merger_topic(merger_id: str) -> str:
    return f"merger-{merger_id}"


def industry_topic(stem: str) -> str:
    return f"industry-{stem}"


def changed_topics(previous: dict, current: dict) -> list[str]:
    """The topics to message for the change from *previous* to *current*."""
    if previous.get("format") != current.get("format"):
        return [ALL]
    topics: list[str] = []
    before, after = previous.get("mergers", {}), current.get("mergers", {})
    topics += [merger_topic(mid) for mid in sorted(after) if mid in before and before[mid] != after[mid]]
    before_ind, after_ind = previous.get("industries", {}), current.get("industries", {})
    topics += [industry_topic(stem) for stem in sorted(after_ind) if before_ind.get(stem) != after_ind[stem]]
    new_ids = set(after) - set(before)
    if new_ids or set(previous.get("phase2_current", [])) != set(current.get("phase2_current", [])):
        topics.append(LIST)
    return [ALL] if len(topics) > MAX_TOPICS else topics


def caught_up(previous: dict | None, expected: dict, live: dict | None) -> bool:
    """Whether *live* serves at least what *expected* (this checkout) changed.

    Every entry this checkout changes must have moved off its *previous* value
    on the live site: to the expected value, or to a newer one deployed since.
    """
    if live is None:
        return False
    if previous is None:
        return live == expected
    for key in ("mergers", "industries"):
        before, want, have = previous.get(key, {}), expected.get(key, {}), live.get(key, {})
        for name, value in want.items():
            if before.get(name) != value and have.get(name) == before.get(name):
                return False
    if set(previous.get("phase2_current", [])) != set(expected.get("phase2_current", [])):
        if set(live.get("phase2_current", [])) == set(previous.get("phase2_current", [])):
            return False
    return True


def fetch_live(fetch=requests.get) -> dict | None:
    """The deployed manifest, or None if it can't be read (or isn't one this understands)."""
    try:
        resp = fetch(
            LIVE_MANIFEST_URL,
            params={"t": int(time.time())},
            headers={"Cache-Control": "no-cache"},
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        manifest = resp.json()
    except (requests.RequestException, ValueError) as exc:
        print(f"Couldn't read {LIVE_MANIFEST_URL}: {exc}", file=sys.stderr)
        return None
    if not isinstance(manifest, dict) or not manifest.get("mergers"):
        return None
    return manifest


def wait_for_deploy(
    previous: dict | None,
    expected: dict,
    *,
    timeout: float,
    poll: float = DEPLOY_POLL_SECONDS,
    fetch=requests.get,
    sleep=time.sleep,
    clock=time.monotonic,
) -> dict | None:
    """The live manifest once it has caught up with *expected*, or as it is at the deadline."""
    start = clock()
    deadline = start + timeout
    while True:
        live = fetch_live(fetch)
        if caught_up(previous, expected, live):
            return live
        now = clock()
        if now >= deadline:
            print(f"Live manifest not caught up after {timeout:.0f}s; sending what is live", flush=True)
            return live
        print(f"  live manifest not caught up yet ({now - start:.0f}s of {timeout:.0f}s)", flush=True)
        sleep(poll)


# --- FCM ---------------------------------------------------------------------


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def signed_jwt(account: dict, now: int) -> str:
    """The service account's assertion for Google's OAuth token endpoint (RS256)."""
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding

    header = {"alg": "RS256", "typ": "JWT", "kid": account.get("private_key_id", "")}
    claims = {
        "iss": account["client_email"],
        "scope": SCOPE,
        "aud": account.get("token_uri", "https://oauth2.googleapis.com/token"),
        "iat": now,
        "exp": now + 3600,
    }
    signing_input = f"{_b64(json.dumps(header).encode())}.{_b64(json.dumps(claims).encode())}"
    key = serialization.load_pem_private_key(account["private_key"].encode(), password=None)
    signature = key.sign(signing_input.encode(), padding.PKCS1v15(), hashes.SHA256())
    return f"{signing_input}.{_b64(signature)}"


def access_token(account: dict, post=requests.post) -> str:
    resp = post(
        account.get("token_uri", "https://oauth2.googleapis.com/token"),
        data={
            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
            "assertion": signed_jwt(account, int(time.time())),
        },
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def message(topic: str) -> dict:
    return {
        "message": {
            "topic": topic,
            "data": {"check": "1"},
            "android": {
                "priority": "HIGH" if topic.startswith("merger-") else "NORMAL",
                "ttl": "86400s",
                "collapse_key": "check",
            },
        }
    }


def send(topics: list[str], account: dict, post=requests.post) -> int:
    """Send one message per topic; the number that failed."""
    token = access_token(account, post=post)
    url = SEND_URL.format(project=account["project_id"])
    failures = 0
    for topic in topics:
        try:
            resp = post(url, json=message(topic), headers={"Authorization": f"Bearer {token}"}, timeout=TIMEOUT)
            resp.raise_for_status()
            print(f"  sent {topic}")
        except requests.RequestException as exc:
            failures += 1
            body = getattr(getattr(exc, "response", None), "text", "")
            print(f"  failed {topic}: {exc} {body[:200]}", file=sys.stderr)
    return failures


# --- state and entry point -----------------------------------------------------


def load_state(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def save_state(path: Path, manifest: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, separators=(",", ":")), encoding="utf-8")


def service_account() -> dict | None:
    raw = os.environ.get("FCM_SERVICE_ACCOUNT", "").strip()
    if not raw:
        return None
    return json.loads(raw)


def main(argv: list[str] | None = None, *, fetch=requests.get, post=requests.post, sleep=time.sleep) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--state", type=Path, required=True, help="the manifest last seen, kept between runs")
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR, help="the data this checkout deploys")
    parser.add_argument("--wait-for-deploy", type=float, default=0, metavar="SECONDS")
    parser.add_argument("--dry-run", action="store_true", help="print the topics; send and record nothing")
    args = parser.parse_args(argv)

    account = service_account()
    if account is None and not args.dry_run:
        print("FCM_SERVICE_ACCOUNT is not set - skipping. See docs/android-push.md.", file=sys.stderr)
        return 0

    previous = load_state(args.state)
    expected = build_manifest(args.data_dir)
    # With nothing recorded there is nothing to send, so nothing to wait for:
    # record whatever is live. (Waiting would need the live manifest to match
    # this checkout exactly, which a deploy that hasn't happened never does.)
    if previous is not None and args.wait_for_deploy > 0:
        live = wait_for_deploy(previous, expected, timeout=args.wait_for_deploy, fetch=fetch, sleep=sleep)
    else:
        live = fetch_live(fetch)
    if live is None:
        print("No live manifest to compare; nothing sent")
        return 0
    if live.get("format") != FORMAT:
        print(f"Live manifest is format {live.get('format')}, this script knows {FORMAT}")

    if previous is None:
        print("No earlier manifest: recording this one, sending nothing")
        if not args.dry_run:
            save_state(args.state, live)
        return 0

    topics = changed_topics(previous, live)
    print(f"{len(topics)} topic(s) to message")
    if args.dry_run:
        for topic in topics:
            print(f"  {topic}")
        return 0
    failures = send(topics, account, post=post) if topics else 0
    # Recorded even after a failure: a missed message only delays a check
    # until the app's own schedule, where re-sending would repeat every other.
    save_state(args.state, live)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
