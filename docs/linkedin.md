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
opening of the matter's description: its first sentence, which on the register
almost always states the deal (plus the second when the first is under ~100
characters, as "The Principal Party is …" lines are), cut with "…" only if it
runs past 500 characters. The article card's description is the same opening,
capped at 300. Both come from `first_sentence()` in
`scripts/atproto/post_bluesky.py`, shared with the Bluesky cards:

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

## Before the API is approved: share links

`scripts/linkedin/share_links.py` gets the posts out by hand while the API
route is still waiting on LinkedIn. For each milestone the API poster would
post, it sends an [ntfy](notifications.md) notification carrying a
`linkedin.com/feed/?shareActive=true&text=…` link. That link opens LinkedIn's
own post box with the post already written. Nothing goes out until you press
**Post**.

- The link only works **in a browser**. A phone hands linkedin.com links to the
  LinkedIn app, which opens with an empty post box. So the notification's
  **Copy LinkedIn link** button puts the link on the clipboard, to paste into a
  browser where you're signed in. Tapping the notification itself opens the
  matter page. The copy button works in the ntfy Android app and the ntfy web
  app. The ntfy docs don't say whether the iOS app supports it.
- The text is the API post as plain text. The matter's link sits just above
  the hashtags, so LinkedIn turns it into the matter page's preview card. The
  notification body is the full link alone.
- The preview's image is a **generic card for the matter's latest milestone**
  ("Cleared by the ACCC" in green, "Referred to Phase 2" in amber, and so on),
  not the per-matter picture the API attaches; the preview prints the matter's
  name under it anyway. There are 14 of them, one per headline the posters
  use, committed in `frontend/public/og/` and chosen per matter by
  `scripts/generate/og_cards.py`, which writes the choice into each
  `mergers/{id}.json` as `og_card`. The Pages Function that answers link
  preview bots (`functions/mergers/[matter]/[[path]].js`) reads that field, as
  do the prerendered page and the SPA. Redraw them with
  `python -m scripts.generate.og_cards` after changing a headline or the
  design; a test fails if one is missing.
- LinkedIn caches a link's preview for about a week, so the link carries the
  milestone's kind (`?m=determined`). Sharing a matter again at its next
  milestone uses a URL LinkedIn hasn't seen, and it scrapes the new card rather
  than reusing last week's. If a preview still looks stale, LinkedIn's
  [Post Inspector](https://www.linkedin.com/post-inspector/) forces a rescrape.
- The post box posts as whoever is signed in. To post as the page, switch the
  author to the page in the post box, or paste the text into the page's own
  "Create a post" box.

It needs the repo variable **`LINKEDIN_SHARE_LINKS=true`** and the existing
`NTFY_TOPIC` secret (`NTFY_TOKEN` and `NTFY_SERVER` are used if set). It
shares `linkedin_posts.json` with the API poster. Its first run seeds that file
and sends nothing, and a milestone is recorded only once its notification is
delivered. When you later set `LINKEDIN_POST_ENABLED`, the share links stop by
themselves and the API carries on from the same point, so nothing is
announced twice. At most 10 links go out per run, like the posts.

```bash
python -m scripts.linkedin.share_links --dry-run    # see the links that are due
```

## API version

Every call carries a `LinkedIn-Version: YYYYMM` header (`DEFAULT_API_VERSION`
in `scripts/linkedin/config.py`). LinkedIn retires each version about a year
after release. When the pinned version is retired, the step starts failing on
it. To fix that, bump the constant, or set the `LINKEDIN_API_VERSION` variable
in the meantime.
