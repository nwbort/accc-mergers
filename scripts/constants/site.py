"""Site-wide constants: the GitHub repository slug and public site URLs.

Single source of truth for values that scripts embed in generated PR/issue
bodies and reports (previously copy-pasted per script).
"""

#: GitHub repository slug, used to build links to blobs, branches and workflows.
REPO = "nwbort/accc-mergers"

#: Base URL for merger detail pages on the public site.
MERGERS_FYI_BASE = "https://mergers.fyi/mergers"


def mergers_fyi_url(merger_id: str) -> str:
    """Return the public mergers.fyi detail-page URL for a merger."""
    return f"{MERGERS_FYI_BASE}/{merger_id}"
