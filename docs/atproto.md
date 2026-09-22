# mergers.fyi in the ATmosphere

The ATmosphere is the network of applications built on the [AT
Protocol](https://atproto.com) — Bluesky is the largest, but the protocol is
general: an account is a *repo* of typed JSON records, each record belongs to a
*collection* named by a lexicon, and anything on the network can read anybody's
records without asking permission.

That makes it a good fit for this site in a way a social account alone is not.
The register is structured public data that nobody else republishes in a form a
machine can use; putting it in the ATmosphere means an Australian competition
researcher, a law firm's internal tool or somebody's weekend feed generator can
build on ACCC merger reviews without scraping mergers.fyi or the ACCC.

Three separate things live under this heading. They are independent — any one
of them works without the others — and **all three are inert until configured**,
on the same principle as the ntfy notifications: a fork or a pull-request run
has no secrets, and the pipeline must not go red because it could not reach a
social network.

| Piece | What it does | Needs |
| --- | --- | --- |
| Handle | Makes `mergers.fyi` usable as an ATProto handle | A DID in `atproto/identity.json` |
| Lexicons + matter records | Publishes the register as `fyi.mergers.matter` records | An account, an app password, one DNS record |
| Bluesky posts | Posts milestones to a feed | The above, plus an explicit switch |

All three hang off one account, so start there.

---

## The account

All three pieces write into, or point at, one **account** — which in AT
Protocol terms is a *repo*: a signed collection of typed JSON records. Concretely,
you create one by signing up for a Bluesky account. There is no separate
"ATProto account" to make: the signup provisions the repo, hands you a
`did:plc:…` identifier, and that DID is what goes in `atproto/identity.json`.

A repo is not partitioned by application. One account holds ordinary Bluesky
posts and this site's `fyi.mergers.matter` records side by side, which is why
the Bluesky posting and the data publishing here need one account between them
rather than one each. `standard.site`'s repo is a good look at what that ends
up like in practice:

```console
$ curl -sS "https://bsky.social/xrpc/com.atproto.repo.describeRepo?repo=standard.site"
...
  app.bsky.feed.post              # ordinary Bluesky posts
  com.atproto.lexicon.schema      # the lexicons it publishes
  site.standard.document          # its own records
  sh.tangled.repo                 # a third-party app's records
```

Four things that are not obvious from the signup flow:

- **Use a new, dedicated account, not a personal one.** The app password sitting
  in CI can write anything into whatever repo it opens. Scoping that to an
  account whose only job is the site is what keeps a bug from writing 673
  records into your own repo.
- **You will sign up with a `.bsky.social` handle first**, and switch to
  `mergers.fyi` afterwards. It cannot happen the other way round: verifying the
  domain requires the site to already serve the DID of an account that exists.
  So the order is sign up → take the DID → commit it → deploy → then change the
  handle. Nothing else waits on that last step: the publishers log in by DID,
  so records and posts work before the handle switch as well as after.
- **The DID is permanent; the handle is not.** Changing the handle later breaks
  no `at://` URI, because every record is addressed by DID. That is why
  `identity.json` carries the DID and the handle is only a convenience.
- **The app password is not the login password.** Bluesky: Settings → Privacy
  and security → App passwords. One can write records and post, but cannot
  change the handle or delete the account, which is the right blast radius for
  something living in CI.

Finding the DID of an account you have just made:

```console
$ curl -sS "https://bsky.social/xrpc/com.atproto.repo.describeRepo?repo=<your>.bsky.social"
{"handle": "...", "did": "did:plc:xxxxxxxxxxxxxxxxxxxxxxxx", ...}
```

### Not using bsky.social

Nothing here assumes it. `service` in `atproto/identity.json` points at
whichever PDS holds the repo, and `login()` follows the account's DID document
to the real PDS regardless — so a self-hosted PDS (where `did:web` and full
independence live) works the same, and migrating to one later is a supported
path rather than a rewrite.

---

## 1. The handle

An ATProto handle is a domain you prove you control. Two methods exist; the
site uses the HTTPS one, because it needs no DNS access and the site already
serves static files:

```
GET https://mergers.fyi/.well-known/atproto-did
→ 200, text/plain, body: did:plc:xxxxxxxxxxxxxxxxxxxxxxxx
```

`scripts/build.sh` writes that file into the deployment, taking the DID from
`$ATPROTO_DID` if the Pages project sets one and otherwise from the tracked
`atproto/identity.json`. It is **generated, not committed**: until a DID is
configured the path simply isn't there, because a 200 carrying a DID that
resolves to nothing is worse for a resolver than a 404.

`frontend/public/_headers` pins the response to `text/plain`, which the handle
spec requires and which Pages would otherwise guess at for an extensionless
file.

### Setting it up

1. Create the account and take its DID — see [The account](#the-account)
   above, which is also where the reasons for doing it in this order are.
2. Put the DID in `atproto/identity.json` and merge. The next Pages deploy
   serves `/.well-known/atproto-did`.
3. In the Bluesky app: Settings → Handle → *I have my own domain* → enter
   `mergers.fyi` → verify. The old `.bsky.social` handle stays reserved to the
   account rather than being freed for anyone else (Bluesky changed that in
   December 2024), and existing mentions of it keep resolving.

**If verification fails on the content type**, the DNS method is the
documented alternative and does not involve this repo at all: a TXT record at
`_atproto.mergers.fyi` with the value `did=did:plc:…`. Either method is
sufficient on its own.

---

## 2. Lexicons and matter records

### The namespace

Record types are named by NSID, and an NSID's authority is a domain reversed.
`mergers.fyi` reversed is `fyi.mergers`, so **`fyi.mergers.matter` is a name
only this site can answer for** — that is the whole reason for using the site's
own domain rather than a name under somebody else's.

Two schemas live in `atproto/lexicons/`:

- **`fyi.mergers.defs`** — shared shapes: `party`, `industry`, `determination`,
  `event`, `appeal`.
- **`fyi.mergers.matter`** — one record per matter on the ACCC register.

The record key is the ACCC's own matter identifier, so a matter is addressable
without a lookup:

```
at://did:plc:xxxx/fyi.mergers.matter/MN-01016
```

which is the same bet the site makes with its URLs, and the thing that lets
anything else on the network reference one specific Australian merger review.

Records are built from the generated detail files the site itself serves
(`frontend/public/data/mergers/`), deliberately: the ATmosphere copy should say
what mergers.fyi says, so the two can never drift into two different accounts
of the register.

Two conventions worth knowing before reading a record:

- **Dates are dates.** The register publishes dates; the pipeline stores them
  as midday UTC so they survive a timezone round trip. Republishing that midday
  as a real instant would be inventing a fact, so every date-shaped field is a
  plain `YYYY-MM-DD` string. `indexedAt` is the only datetime, because it is
  the only instant we actually know.
- **`indexedAt` is a last-*changed* signal, not a heartbeat.** It only moves
  when something in the matter moved. See the digest state below.

### Publishing the schemas

`publish-lexicons.yml` does this automatically on any push to `main` that
touches `atproto/lexicons/**`, which is the point: a schema edit cannot be
merged and then forgotten. The same workflow can be dispatched by hand, with a
`dry_run` input, for the first publish or a re-run. Locally:

```bash
python -m scripts.atproto.publish_lexicons --dry-run   # validate, print the DNS record
python -m scripts.atproto.publish_lexicons             # write them to the repo
```

Schemas are published like any other record — `com.atproto.lexicon.schema`,
keyed by the NSID. Resolution then runs domain → DID → schema, and the first
hop is DNS, so this is needed once:

```
_lexicon.mergers.fyi   TXT   "did=did:plc:xxxxxxxxxxxxxxxxxxxxxxxx"
```

One record covers both NSIDs: they differ only in their final segment, so they
share an authority. `publish_lexicons` prints the exact line to add.

Note this is a *different* record from the `_atproto.mergers.fyi` one mentioned
above. `_atproto` says who owns the handle; `_lexicon` says who defines the
schemas.

### Publishing the matters

```bash
python -m scripts.atproto.publish_matters --dry-run
python -m scripts.atproto.publish_matters [--limit N] [--pause 0.2]
```

Runs are incremental. `data/processed/atproto_records.json` holds each record's
content digest as last written, so a pipeline run several times a day rewrites
only the matters that moved; matters that leave the dataset are deleted, which
keeps the collection in step with the self-pruning generated data directories.

The state file is an optimisation and nothing more — `putRecord` is an upsert,
so losing it costs one full republish and no correctness. The first run is a
full publish of every matter on the register (~670 records at the time of
writing), which is what `--limit` and `--pause` are for.

---

## 3. Bluesky posts

The records above are data: complete, addressable, and invisible unless
somebody goes looking. `post_bluesky` is the other half — the same milestones
as ordinary `app.bsky.feed.post` records.

What gets posted is deliberately narrow: a matter **arriving**, being
**referred to phase 2**, being **decided**, having its assessment **ceased**,
or going to the **Tribunal** or the **Federal Court**. Questionnaires, timeline
extensions and remedy offers are all on the site and in the records; posting
them would turn a useful account into a firehose.

A **waiver** application is the exception to "arriving": the ACCC only
publishes a waiver once it has been determined, so its notification date is
never news — it would land seconds before the determination post, announcing
something already over. Waivers are posted on their determination only.

Each post is a headline, the matter name, then the matter id, its stage and the
date, the link, and `#accc`:

```
Notification waiver granted: OceanaGold - Ausgold

WA-95041 · Waiver application · 17 Sep 2026
https://mergers.fyi/mergers/WA-95041

#accc
```

The tags come from `POST_HASHTAGS` and are published as
`app.bsky.richtext.facet#tag` facets alongside the link facet, not just as
text — Bluesky indexes tags from the facet, so an unfaceted `#accc` would be
invisible to the search it was added for. Adding a tag to that tuple is all
there is to it, but each one costs characters the matter name would otherwise
have.

```bash
python -m scripts.atproto.post_bluesky --dry-run       # see what is due
python -m scripts.atproto.post_bluesky [--max-posts N]
```

Two safeguards, because this is the only part of the pipeline that speaks to
people rather than to files:

- Posting needs `ATPROTO_POST_ENABLED` **on top of** the credentials, so adding
  the step to a workflow is not the thing that starts posting.
- The first *enabled* run **seeds**: it records every milestone currently on
  the register as already seen and posts nothing. Switching posting on
  therefore cannot dump the back catalogue into a feed — whatever happens next
  is what gets posted.

`--max-posts` (default 10) caps a single run, so a re-scrape that rediscovers a
batch of matters cannot flood a feed; the overflow goes out next run, oldest
first.

---

## Configuration

### Tracked, public

`atproto/identity.json` — the DID, the handle and the PDS. All three are public
by design (the DID is served at `/.well-known/atproto-did` so the handle
resolves at all), so there is nothing to hide and a lot to gain from one
committed copy that the publishers, the build and this document all read.

### Secrets and variables

| Name | Where | Purpose |
| --- | --- | --- |
| `ATPROTO_APP_PASSWORD` | Repo secret | App password for the account. **Not** the account password — create one under Settings → Privacy and security → App passwords. |
| `ATPROTO_IDENTIFIER` | Repo variable (optional) | Login identifier. Defaults to the DID in `identity.json`, which is always correct; only needed to point a run at a different account. |
| `ATPROTO_POST_ENABLED` | Repo variable | `true` switches Bluesky posting on. |
| `ATPROTO_DID` / `ATPROTO_SERVICE` | Env (optional) | Override the identity file — how the publishers get exercised against a throwaway account before the real one exists. |

An app password can write anything into the repo it opens, posts included, so
it is a repository secret like any other and never goes in a file.

Before publishing, `open_client` checks that the DID it logged in as matches
the one in `identity.json`. They differ when a password for the wrong account
gets set, and the failure that would cause — the whole register republished
into a stranger's repo — is not one worth discovering afterwards.

## Where it runs

The matters and the posts run in `pipeline.yml`, right after the static data is
generated and before the commit, so the two state files land in the same commit
as the data they describe. Both steps skip in a fork or a PR run, where no
secret exists.

The lexicons have their own workflow, `publish-lexicons.yml`, triggered by a
push to `main` touching `atproto/lexicons/**` (or the workflow file) and by
`workflow_dispatch`, which takes a `dry_run` input. They are on a different
clock from the data: a schema moves only when a person edits one, so a
path-filtered push fires exactly then, where the pipeline would re-read both
records several times a day to learn that nothing had changed. It installs only
`requests`, since `publish_lexicons` reaches nothing else.

A missing `ATPROTO_APP_PASSWORD` behaves differently in the two cases, on
purpose. On a push it is a skip, like everywhere else in this repo — a fork has
no secrets and absent credentials never turn a run red. On a manual run it is an
error: somebody asked for the records to be written, and a green tick for
nothing happening is the wrong report.

## Trying it out without touching production

Every entry point has `--dry-run`, and none of them need credentials for it:

```bash
python -m scripts.atproto.publish_lexicons --dry-run
python -m scripts.atproto.publish_matters --dry-run
python -m scripts.atproto.post_bluesky --dry-run
```

To publish against a throwaway account, set `ATPROTO_DID` and
`ATPROTO_IDENTIFIER` to that account's, and point the state files elsewhere by
running in a scratch checkout.

## What is deliberately not here

- **A feed generator.** `app.bsky.feed.generator` needs a always-on service
  indexing the firehose, which is a Worker and a database, not a static site.
- **`site.standard.*` publication records.** The [Standard.site](https://standard.site)
  lexicons model long-form articles. They would suit the weekly digest and the
  commentary, and not the register — a matter is a database row, not an essay.
  Worth revisiting if the commentary grows.
- **Backfilling posts.** See the seeding rule above.
