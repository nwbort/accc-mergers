# ATProto identity and lexicons

The site's AT Protocol identity and the schemas it publishes under. See
[`docs/atproto.md`](../docs/atproto.md) for what any of it is for and how to
set it up.

- `identity.json` — the site's DID, handle and PDS. Public values only; the
  app password lives in a repository secret. An empty `did` means the ATmosphere
  publishing is not configured, and everything that reads this file skips.
- `lexicons/` — the `fyi.mergers.*` schemas, published to the site's repo as
  `com.atproto.lexicon.schema` records by
  `python -m scripts.atproto.publish_lexicons`.

`fyi.mergers` is `mergers.fyi` reversed, which is what makes these names ones
only this site can answer for. A schema here whose `id` disagrees with its
filename, or which strays outside that authority, fails the test suite — both
mistakes publish perfectly happily and then resolve to nothing.
