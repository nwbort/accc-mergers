# LinkedIn posts

`scripts/linkedin/post_linkedin.py` posts the register's milestones to
LinkedIn, the same way [`post_bluesky`](atproto.md#3-bluesky-posts) does to
Bluesky. Both choose milestones with the same `milestones()` function, so the
two accounts always announce the same things: a matter **arriving**, being
**referred to phase 2**, being **decided**, a **public benefit** application
and its determination, a **ceased** assessment, and a **Tribunal** or
**Federal Court** review.

Like every other publisher here, it does nothing until it is configured, and
it can't fail the pipeline. Without its secrets the step prints a reason and
exits 0.

## What a post looks like

LinkedIn allows 3,000 characters, not 300, so a post also includes the
matter's description, cut to 500 characters:

```
Cleared by the ACCC: Asahi – Warehouse site on Tilburn Rd, Deer Park (Vic)

Asahi will enter into an agreement for lease with GPT …

MN-01016 · Phase 1 - initial assessment · 5 Sep 2026

#accc
```

The link to the matter page is the post's **article card**. The card's image is
the same per-milestone picture the Bluesky cards use
(`scripts/atproto/card_image.py`), uploaded through LinkedIn's Images API.
LinkedIn never scrapes a link that arrives through the API, so without the card
the post would have no preview. If the card image can't be drawn or uploaded,
the post uses the site's `og-image.png` instead. If that fails too, the post
goes out without an image.

The commentary uses LinkedIn's
["little" text format](https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/little-text-format),
where `( ) [ ] { } < > # * _ ~ @ | \` are all markup. An unescaped `(` in a
matter name can truncate a post, so every piece of register text is escaped.
The hashtags are written as `{hashtag|\#|accc}` templates, using the same
`POST_HASHTAGS` tuple that Bluesky uses.

```bash
python -m scripts.linkedin.post_linkedin --dry-run        # see what is due, as it will read
python -m scripts.linkedin.post_linkedin [--max-posts N]
```

## Safeguards

These are the same as Bluesky's, with one difference:

- Posting needs **`LINKEDIN_POST_ENABLED`** on top of the credentials.
- The first enabled run **seeds** `data/processed/linkedin_posts.json`: it
  records every milestone already on the register and posts nothing. This file
  is separate from Bluesky's, so switching LinkedIn on later can't replay
  everything Bluesky has posted since its own launch.
- Before posting, the run **reads back** the author's last 100 posts and skips
  any milestone already there. This needs permission to read the author's
  posts, which only a company page has (see below). For a personal profile
  the read fails with a 403. The run then reports that and posts without the
  check, so a run whose commit was lost could post a milestone twice. Any
  other read-back failure means nothing is posted that run.
- `--max-posts` (default 10) caps each run, and anything left over goes out
  next run.

## Setting it up

There are two routes, and they differ in what LinkedIn will give a self-serve
app.

### A company page (recommended)

1. Create a LinkedIn page for mergers.fyi, if there isn't one, and an app at
   <https://www.linkedin.com/developers/apps> that is associated with the page.
2. Request the **Community Management API** product for the app. LinkedIn
   reviews these requests and approval is not automatic. It grants
   `w_organization_social` and `r_organization_social` (post and read back),
   plus programmatic **refresh tokens** that last a year.
3. As a page admin, go through the OAuth authorization code flow with those
   scopes. Keep the `refresh_token` it returns.
4. Set these in the repo's Actions settings:
   - variable `LINKEDIN_AUTHOR_URN` = `urn:li:organization:{page id}`
   - variable `LINKEDIN_CLIENT_ID`
   - secret `LINKEDIN_CLIENT_SECRET`
   - secret `LINKEDIN_REFRESH_TOKEN`

   Each run then mints its own access token. You'll need to authorize again
   once a year, when the refresh token expires.

### A personal profile

1. Create an app and add the self-serve **Share on LinkedIn** product. It
   grants `w_member_social` straight away.
2. Go through the OAuth flow with `openid profile w_member_social`. Get your
   member id from `GET https://api.linkedin.com/v2/userinfo` (its `sub`).
3. Set the variable `LINKEDIN_AUTHOR_URN` = `urn:li:person:{sub}` and the
   secret `LINKEDIN_ACCESS_TOKEN`.

This route has two drawbacks:

- **The token expires after 60 days**, and self-serve apps get no refresh
  token. When it expires, the step fails with "LinkedIn token rejected" and you
  have to replace the secret by hand. Posting stops until you do, and then
  catches up, oldest first.
- **There's no read-back** (`r_member_social` is restricted), so the
  duplicate check described above doesn't run.

### Switching it on

1. Run `python -m scripts.linkedin.post_linkedin --dry-run` and check the output.
2. Set the repo variable **`LINKEDIN_POST_ENABLED=true`**. The next pipeline
   run seeds the state file, and the run after that is the first to post.

## API version

Every call carries a `LinkedIn-Version: YYYYMM` header (`DEFAULT_API_VERSION`
in `scripts/linkedin/config.py`). LinkedIn retires each version about a year
after release. When the pinned version is retired, the step starts failing on
it. To fix that, bump the constant, or set the `LINKEDIN_API_VERSION` variable
in the meantime.
