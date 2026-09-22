"""Publishing mergers.fyi into the ATmosphere (the AT Protocol network).

Three things live here, in increasing order of how much setup they need:

* ``publish_lexicons`` - writes the ``fyi.mergers.*`` schemas in
  ``atproto/lexicons/`` to the site's repo as ``com.atproto.lexicon.schema``
  records, so the lexicons this data is published under are resolvable.
* ``publish_matters`` - writes one ``fyi.mergers.matter`` record per matter on
  the ACCC register, keyed by the ACCC's own matter id.
* ``post_bluesky`` - posts newly notified, referred, determined and appealed
  matters to Bluesky as ordinary ``app.bsky.feed.post`` records.

Every entry point is a no-op without credentials, on the same principle as the
ntfy notifications: a fork, a pull-request run or an unconfigured repo should
skip quietly rather than fail the pipeline. See ``docs/atproto.md``.
"""
