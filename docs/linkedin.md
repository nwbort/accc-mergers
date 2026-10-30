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

## Before the API is approved: a Make.com webhook

`scripts/linkedin/webhook.py` posts to the company page without a LinkedIn app
of our own. A [Make.com](https://www.make.com) scenario holds the LinkedIn
connection. For each milestone the API poster would post, the script POSTs one
JSON object to the scenario's webhook, and the scenario posts it to the page.

Make's free plan covers it. A webhook spends credits only when it's called,
about 2 per post (the trigger plus the LinkedIn module). The register produces
about 135 milestones a month (late 2026), so that's about 270 of the free 1,000
credits. An RSS trigger would cost more and be slower, because Make and Zapier
spend a credit on every poll whether or not anything is new. Zapier's free plan
allows 100 tasks a month, which is too few to post every milestone.

### What the webhook receives

```json
{
  "key": "MN-01016:determined:2025-09-05",
  "matter_id": "MN-01016",
  "date": "2025-09-05",
  "headline": "Cleared by the ACCC",
  "title": "Asahi – Warehouse site on Tilburn Rd, Deer Park (Vic)",
  "text": "Cleared by the ACCC: Asahi – …\n\nAsahi will enter …\n\nMN-01016 · Phase 1 - initial assessment · 5 Sep 2025\n\nhttps://mergers.fyi/mergers/MN-01016?m=determined\n\n#accc",
  "commentary": "Cleared by the ACCC: Asahi – …\n\nAsahi will enter …\n\nMN-01016 · Phase 1 - initial assessment · 5 Sep 2025\n\n#accc",
  "commentary_little": "Cleared by the ACCC: Asahi – … Deer Park \\(Vic\\) … {hashtag|\\#|accc}",
  "url": "https://mergers.fyi/mergers/MN-01016?m=determined",
  "description": "Asahi will enter into an agreement for lease …",
  "image_url": "https://mergers.fyi/og/cleared-by-the-accc.png"
}
```

- `text` is the whole post as plain text, link included, for a **text post**
  that LinkedIn unfurls (the same text as the share links below).
- `commentary` is the post without the link, for a **link/article post**. Map
  the card from `url`, `title`, `description` and `image_url`. The image is the
  generic card for the matter's latest milestone (see the share links below).
- `commentary_little` is `commentary` in LinkedIn's
  ["little" format](#what-a-post-looks-like). Use it only if posts with
  brackets in them come out truncated, which would mean the module passes text
  straight to the Posts API without escaping it.

Scenarios map these keys by name, so add new keys rather than renaming existing ones.

### Setting it up

1. In Make, create a scenario whose trigger is **Webhooks → Custom webhook**.
   Add a webhook and copy its URL. Turn on its **API key authentication**
   too. Without it the URL is the only credential, and anyone who has it can
   post as the page. The script sends the key as the `x-make-apikey` header.
2. Teach the webhook the payload's shape. With the webhook waiting for data
   (it is after you create it, or press **Redetermine data structure**), run:

   ```bash
   LINKEDIN_WEBHOOK_URL=… LINKEDIN_WEBHOOK_API_KEY=… \
     python -m scripts.linkedin.webhook --sample
   ```

   This sends the register's latest milestone and records nothing.
3. Add the **LinkedIn** app's company post module (a link/article post if one
   is offered, otherwise the company text post). Connect it as an admin of the
   page and pick the page. Map the fields as described above.
4. Run the scenario once (**Run once**, then `--sample` again) and check the
   post. Delete it from the page afterwards.
5. In the scenario's settings, turn on **Allow storing of incomplete
   executions**. A post LinkedIn refuses then waits in Make to be retried,
   instead of being lost. Schedule the scenario to run **immediately as data
   arrives**, and switch it on.
6. Add the repo secrets **`LINKEDIN_WEBHOOK_URL`** and, if the webhook has
   one, **`LINKEDIN_WEBHOOK_API_KEY`**. The next
   `linkedin-share-links.yml` run (after the pipeline, or dispatched by hand)
   posts whatever is new.

### How it behaves

- It runs in `linkedin-share-links.yml` with `--wait-for-deploy 900`, like the
  share links. A milestone goes out only once mergers.fyi serves its matter's
  detail file. If LinkedIn scrapes the link, it gets this run's card.
- It shares `linkedin_posts.json`, so it continues from the milestones the
  share links already announced. If that file doesn't exist, the first run
  seeds it and posts nothing.
- A milestone is recorded once the webhook accepts it. Accepting the request is
  all the script can see. A scenario that fails afterwards (for example because
  the LinkedIn connection expired) shows up in Make's history and incomplete
  executions, not in the Actions run.
- There's no read-back. If the state commit is lost, the next run posts the
  same milestones again.
- `--max-posts` (default 10) caps each run, and posts go out 5 seconds apart.
- The share links stand down while `LINKEDIN_WEBHOOK_URL` is set, and the
  webhook stands down once `LINKEDIN_POST_ENABLED` is set. Only one of the
  three handles any milestone.

```bash
python -m scripts.linkedin.webhook --dry-run    # print the payloads that are due
```

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
- That cache is also why the links wait for the deploy. They're sent by their
  own workflow, `linkedin-share-links.yml`, which runs when `pipeline.yml`
  finishes on `main`. It sends a matter's link only once mergers.fyi serves the
  exact detail file on `main` (`--wait-for-deploy 900`). Sent any earlier,
  LinkedIn would scrape the old card, or the home page for a matter not yet
  deployed, and keep it for a week. A matter still not live after 15 minutes
  is left for the next run. When several links are due they go out 30 seconds
  apart (`LINK_SPACING_SECONDS`), so the phone isn't handed a burst at once.
  The state file is committed by that workflow with
  `[skip ci]`. Waiting inside the pipeline would hold its concurrency group, so
  an email-triggered run would queue behind it.
- The post box posts as whoever is signed in. To post as the page, switch the
  author to the page in the post box, or paste the text into the page's own
  "Create a post" box.

It needs the repo variable **`LINKEDIN_SHARE_LINKS=true`** and the existing
`NTFY_TOPIC` secret (`NTFY_TOKEN` and `NTFY_SERVER` are used if set). It
shares `linkedin_posts.json` with the API poster. Its first run seeds that file
and sends nothing, and a milestone is recorded only once its notification is
delivered. When you later set `LINKEDIN_WEBHOOK_URL` or
`LINKEDIN_POST_ENABLED`, the share links stop by themselves and the new route
carries on from the same point, so nothing is announced twice. At most 10
links go out per run, like the posts.

```bash
python -m scripts.linkedin.share_links --dry-run    # see the links that are due
```

## API version

Every call carries a `LinkedIn-Version: YYYYMM` header (`DEFAULT_API_VERSION`
in `scripts/linkedin/config.py`). LinkedIn retires each version about a year
after release. When the pinned version is retired, the step starts failing on
it. To fix that, bump the constant, or set the `LINKEDIN_API_VERSION` variable
in the meantime.
