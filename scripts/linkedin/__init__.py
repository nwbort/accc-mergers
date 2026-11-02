"""Posting mergers.fyi's register milestones to LinkedIn.

The LinkedIn twin of ``scripts.atproto.post_bluesky``: the same milestones,
chosen by the same code. ``webhook`` hands each one to a Make.com scenario that
posts it to the company page; ``share_links`` is the manual fallback, pushing
a prefilled composer link to a phone. See ``docs/linkedin.md``.

Like every other publisher in the pipeline it is a no-op without its secrets,
so a fork, a pull-request run or an unconfigured repo skips quietly.
"""
