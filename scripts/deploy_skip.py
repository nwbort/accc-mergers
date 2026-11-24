"""Should a pipeline commit skip the Cloudflare Pages build?

Some outputs are cut against today's date rather than the register:
``analysis.json``'s ``as_at`` and rolling windows, the 14-day window of
``recent-events.json``, ``upcoming-events.json`` (and, until the sitemap was
dated by the data, ``sitemap.xml``'s lastmods). A run that found nothing new
still rewrites them, and each such commit used to trigger a full Pages build
for data no reader would notice was a few hours old (scheduled runs with no
scrape changes already skip generation and leave them that stale).

This decides, from the paths a commit changes, whether every *deployable* one
is such a date-windowed output. If so the pipeline appends ``[skip ci]`` to the
commit message, which Pages honours: the data is still committed and goes out
with the next commit that deploys. A commit touching anything else that
reaches the deployment (a detail file, the list, a raw document) deploys as
before.

``[skip ci]`` is ignored for ``workflow_run`` triggers, so
``linkedin-share-links.yml`` and ``android-push.yml`` still follow the
pipeline. Their wait-for-deploy checks compare ``mergers/{id}.json`` and the
``manifest.json`` hashes, neither of which a date-only commit can move.

Usage (paths one per line on stdin, e.g. ``git diff --staged --name-only``)::

    git diff --staged --name-only | python -m scripts.deploy_skip

prints ``true`` or ``false``.
"""

import sys
from collections.abc import Iterable

# Cloudflare Pages' build watch paths, as set in the dashboard (not from this
# repo) — keep in step with docs/deployment.md#build-watch-paths. A trailing
# slash is a directory prefix; anything else is an exact file.
WATCH_PATHS = (
    "frontend/",
    "functions/",
    "data/raw/matters/",
    "atproto/identity.json",
    "scripts/build.sh",
    "scripts/generate/data_manifest.py",
    "wrangler.toml",
)

# Outputs that can change with the date alone. The sitemap's lastmods are now
# dated by the data (generate_sitemap.data_lastmod), so it should only move
# alongside a detail file; it is listed so a lastmod-only diff never deploys
# on its own either way.
DATE_WINDOWED_OUTPUTS = frozenset({
    "frontend/public/data/analysis.json",
    "frontend/public/data/recent-events.json",
    "frontend/public/data/upcoming-events.json",
    "frontend/public/sitemap.xml",
})


def is_deployable(path: str) -> bool:
    """Does a change to ``path`` match one of the Pages build watch paths?"""
    return any(
        path.startswith(watch) if watch.endswith("/") else path == watch
        for watch in WATCH_PATHS
    )


def should_skip_deploy(paths: Iterable[str]) -> bool:
    """True when the commit changes deployable paths, all of them date-windowed.

    A commit with no deployable path at all is left alone: Pages already skips
    it, and the marker would also needlessly skip any GitHub push workflow.
    """
    deployable = {p for p in (p.strip() for p in paths) if p and is_deployable(p)}
    return bool(deployable) and deployable <= DATE_WINDOWED_OUTPUTS


def main() -> None:
    print("true" if should_skip_deploy(sys.stdin) else "false")


if __name__ == "__main__":
    main()
