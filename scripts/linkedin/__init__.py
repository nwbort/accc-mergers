"""Posting mergers.fyi's register milestones to LinkedIn.

The LinkedIn twin of ``scripts.atproto.post_bluesky``: the same milestones,
chosen by the same code, posted as LinkedIn article posts. Only the transport
and the post's layout differ. See ``docs/linkedin.md``.

Like every other publisher in the pipeline it is a no-op without credentials,
so a fork, a pull-request run or an unconfigured repo skips quietly.
"""
