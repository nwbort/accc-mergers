# LinkedIn posts

The register's milestones are posted to the mergers.fyi LinkedIn company page
through a [Make.com](https://www.make.com) scenario. The scenario holds the
LinkedIn connection; `scripts/linkedin/webhook.py` POSTs it one JSON object
per milestone, and the scenario posts it to the page. This project doesn't
call LinkedIn's own API, so there is no LinkedIn app, token or approval to
manage.

The milestones are the same ones [`post_bluesky`](atproto.md#3-bluesky-posts)
posts to Bluesky, chosen by the same `milestones()` function, so the two
accounts always announce the same things: a matter **arriving** (or held
**materially incomplete**, then its assessment **recommencing**), being
**referred to phase 2**, being **decided**, a **public benefit** application
and its determination, a **ceased** assessment, and a **Tribunal** or
**Federal Court** review.

Like every other publisher here, it does nothing until it is configured.
Without its secrets the step prints a reason and exits 0.

Make's free plan covers it. A webhook spends credits only when it's called,
about 3 per post (the trigger, the image download and the LinkedIn module).
The register produces about 135 milestones a month (late 2026), so that's
about 400 of the free 1,000 credits. An RSS trigger would cost more and be slower, because Make and Zapier
spend a credit on every poll whether or not anything is new. Zapier's free plan
allows 100 tasks a month, which is too few to post every milestone.

## What a post looks like

LinkedIn allows 3,000 characters, not 300, so a post also includes the
opening of the matter's description: its first sentence, which on the register
almost always states the deal (plus the second when the first is under ~100
characters, as "The Principal Party is …" lines are), cut with "…" only if it
runs past 500 characters. The link card's description is the same opening,
capped at 300. Both come from `first_sentence()` in
`scripts/atproto/post_bluesky.py`, shared with the Bluesky cards:

```
Cleared by the ACCC: Asahi – Warehouse site on Tilburn Rd, Deer Park (Vic)

Asahi will enter into an agreement for lease with GPT …

MN-01016 · Phase 1 - initial assessment · 5 Sep 2026

#accc
```

The link to the matter page is the post's **article card**, with the generic
card image for the matter's latest milestone (see the share links below).

Make's LinkedIn module passes the post's text to LinkedIn unchanged, and
LinkedIn reads it in its
["little" text format](https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/little-text-format),
where `( ) [ ] { } < > # * _ ~ @ | \` are all markup. An unescaped `(` in a
matter name can truncate a post, so `scripts/linkedin/text.py` escapes every
piece of register text and writes the hashtags as `{hashtag|\#|accc}`
templates, using the same `POST_HASHTAGS` tuple that Bluesky uses.

## The Make.com webhook

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

- `commentary_little` is the post without the link, in LinkedIn's
  ["little" format](#what-a-post-looks-like), with brackets escaped and `#accc`
  as a hashtag template. Map **this** to the Make LinkedIn module's Content.
  The module passes Content to LinkedIn unchanged, so plain text with a
  `(` in it can be cut off.
- `url`, `title`, `description` and `image_url` make the post's link card.
  The image is the generic card for the matter's latest milestone (see the
  share links below).
- `text` (the whole post as plain text, link included) and `commentary`
  (`commentary_little` without the escapes) are for a destination that wants
  plain text.

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
3. Add **HTTP → Download a file** with URL `{{1.image_url}}`. LinkedIn
   doesn't fetch link previews for posts Make creates, so the card image has
   to be uploaded with the post.
4. Add **LinkedIn → Create a Company Text Post**. Connect it as an admin of
   the page, pick the page, and set:
   - Content: `{{1.commentary_little}}`
   - Media Type: **Article**
   - Link: URL `{{1.url}}`, Title `{{1.title}}`, Description `{{1.description}}`
   - Thumbnail: map the file from the Download step (File name `{{3.fileName}}`,
     Data `{{3.data}}`), with Thumbnail Alt Text `{{1.headline}}`

   Without the Article media type, the link shows as bare text with no card.
   Run the scenario once (**Run once**, then `--sample` again) and check the
   post. Delete it from the page afterwards.
5. In the scenario's settings, turn on **Allow storing of incomplete
   executions** and **Sequential processing**. A post LinkedIn refuses then
   waits in Make to be retried instead of being lost, and posts go out in the
   order they were sent. Schedule the scenario to run **immediately as data
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
- The share links stand down while `LINKEDIN_WEBHOOK_URL` is set, so only one
  of the two handles any milestone.

```bash
python -m scripts.linkedin.webhook --dry-run    # print the payloads that are due
```

## Fallback: share links

`scripts/linkedin/share_links.py` gets the posts out by hand when the Make.com
webhook isn't configured. For each new milestone it sends an [ntfy](notifications.md) notification carrying a
`linkedin.com/feed/?shareActive=true&text=…` link. That link opens LinkedIn's
own post box with the post already written. Nothing goes out until you press
**Post**.

- The link only works **in a browser**. A phone hands linkedin.com links to the
  LinkedIn app, which opens with an empty post box. So the notification's
  **Copy LinkedIn link** button puts the link on the clipboard, to paste into a
  browser where you're signed in. Tapping the notification itself opens the
  matter page. The copy button works in the ntfy Android app and the ntfy web
  app. The ntfy docs don't say whether the iOS app supports it.
- The text is the webhook's post as plain text. The matter's link sits just above
  the hashtags, so LinkedIn turns it into the matter page's preview card. The
  notification body is the full link alone.
- The preview's image is a **generic card for the matter's latest milestone**
  ("Cleared by the ACCC" in green, "Referred to Phase 2" in amber, and so on),
  not a per-matter picture; the preview prints the matter's name under it
  anyway. There are 16 of them, one per headline the posters
  use (grey "Notification materially incomplete" only while a matter is
  waiting on an effective notification date), committed in `frontend/public/og/` and chosen per matter by
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
shares `linkedin_posts.json` with the webhook. Its first run seeds that file
and sends nothing, and a milestone is recorded only once its notification is
delivered. When you set `LINKEDIN_WEBHOOK_URL`, the share links stop by
themselves and the webhook carries on from the same point, so nothing is
announced twice. At most 10
links go out per run, like the posts.

```bash
python -m scripts.linkedin.share_links --dry-run    # see the links that are due
```
