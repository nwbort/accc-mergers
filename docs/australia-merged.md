# Australia Merged — the 2026 year in review

A Spotify-Wrapped-style walkthrough of the first year of Australia's mandatory
merger control regime, at `/wrapped` (with `/australia-merged` redirecting to
it). Full-bleed cards the reader taps through, five of them interactive, and a
share card at the end.

This document is the **content**: every card, the exact copy, the number behind
it, where that number comes from, and the quiz answers. Nothing here is
invented — every figure was computed from the committed data files and is
reproduced in `scripts/generate/static_data/outputs/wrapped.py` (to be written)
so the page can't drift from the register.

**All figures below are as at 27 November 2026.** See
[*The year isn't over*](#the-year-isnt-over) for how that's handled.

## Why this works for this register, and not for most data sites

Wrapped works because it tells you something about *yourself* that you half
knew and couldn't have counted. This register has three of those, and they're
what the whole page hangs on:

1. **2026 is year one.** The mandatory regime commenced 1 January 2026. Nobody
   has a baseline, so "the first ever X" is a true statement roughly fifteen
   times over, and every number is a record by construction. This is the only
   year this page can be written without a comparison column — lean on it.
2. **The reader already has a personal dataset.** `TrackingContext` holds the
   matters and industries they followed, in localStorage, dated. That's the
   "your top artist" slot, and it needs no login, no account and no server.
3. **The outcomes are genuinely surprising.** 99.3% clearance, a median review
   twelve business days inside the statutory clock, and then three refusals, two
   Tribunal reviews and a Federal Court challenge. The gentle year with the
   violent tail is a story with a shape.

## The run of show

Nineteen cards. Roman numerals are the reveal/interactive ones. Target: four
minutes end to end, under two if you tap fast.

### 1. Open — "Australia Merged"

> **Australia Merged**
> The first year of merger control in Australia. 896 deals. One year. Let's go.

No numbers yet beyond the headline count. Tap to start.

### 2. The scale

> **896 matters** came to the ACCC in 2026.
> 328 notifications. 568 waiver applications.
> That's **3.8 a business day**, every business day, all year.

Only **12** business days out of 237 passed without a single filing.

*Source: `mergers/list.json`, filtered on `effective_notification_datetime`
starting `2026`.*

### 3. The shape of the year

A bar per month, counting up as the card lands.

| | Jan | Feb | Mar | Apr | May | Jun | Jul | Aug | Sep | Oct | Nov |
|---|---|---|---|---|---|---|---|---|---|---|---|
| matters | 37 | 52 | 69 | 71 | 100 | 97 | **116** | 107 | 86 | **116** | 45* |

> January was a trickle. By July the ACCC was taking **116 matters a month** —
> three times the opening pace. It never went back.

\* November is incomplete (to the 27th).

*Source: `analysis.json → monthly_volume`, notifications + waivers.*

### 4. Busiest day — I. REVEAL

Hold the number back behind a tap.

> **One day in 2026, 13 matters landed at once.**
> _[tap]_ **Friday 14 August.**

And then the gag that actually tells you something:

> Fridays took **217** filings. Mondays took **139**.
> Nineteen deals were filed on a **weekend** — someone, somewhere, filed a
> merger notification on Sunday 11 January.

*Source: derived from `effective_notification_datetime`. Busiest week was
18–24 May, at 38 matters.*

### 5. Speed

> The law gives the ACCC **30 business days** for a phase 1 review.
> It used a median of **18**.
>
> Half of all phase 1 reviews were done with **twelve business days to spare.**

Second beat:

> Waivers: median **15 business days**.
> The fastest was **one**. Kiwa – CSA Group filed on Monday 23 November and had
> its answer on the Tuesday.

The fastest full phase 1 reviews came in at **15 business days** — and six
separate matters hit exactly that, which is the floor, not a coincidence: a
phase 1 review can't conclude before the public consultation period closes.

*Source: `analysis.json → phase1_duration.stats` (median 18 BD, 310 completed),
`waiver_duration.stats` (median 15 BD, min 1). Business-day counts throughout
use `scripts/generate/static_data/business_days.py`, which honours ACT public
holidays — don't recompute them with a plain weekday count, which drifts by a
day or two.*

### 6. The verdict

> **99.3%** of completed phase 1 reviews ended in clearance.
> **95.1%** of waiver applications were granted.
>
> If you filed a merger in Australia in 2026, you were almost certainly fine.

Then turn it:

> Almost.

*Source: `stats.json → clearance_rate` (302/304), waivers 540/568.*

### 7. The 0.7% — the refusals

> Three deals were refused in 2026. All three had been through phase 2.

- **Coles – Kalgoorlie supermarket site** — refused 1 July. A single
  supermarket in a Western Australian mining town became the most litigated
  merger of the year.
- **MicroStar Logistics – Konvoy** — refused 7 August, after **114 business
  days**. Beer kegs.
- **IAG – RAC Insurance** — refused 23 September. Western Australian car and
  home insurance.

> The ACCC said no three times in 2026, and twice it was about a car park or a
> keg. Nobody had this on their bingo card.

*Source: `phase2.json → completed`, `mergers/list.json`.*

### 8. Longest review — II. GUESS

The user's own idea, in its best form. Four options, one tap, reveal.

> **Which review concluded in 2026 took the longest?**
> - Ampol – EG Australia ✅ (147 BD)
> - Coles – Kalgoorlie (133 BD)
> - MicroStar Logistics – Konvoy (114 BD)
> - Google – Wiz (28 BD)

> **Ampol – EG Australia: 147 business days**, notification to determination.
> Nearly five times the statutory phase 1 clock. It was approved — with
> conditions, the first conditional clearance of the regime.
>
> Second was **Coles – Kalgoorlie** at 133, third **MicroStar – Konvoy** at 114.
>
> And **Google – Wiz**? Twenty-eight business days. The ACCC cleared a global
> cloud-security acquisition in under six weeks and spent seven months on a
> supermarket in Kalgoorlie.

The last line is the fact worth having on the page, and it's why Google – Wiz
belongs in the options rather than a fourth long matter: the reader needs to see
how far off it is.

*Source: `calculate_business_days()` over `effective_notification_datetime` →
`determination_publication_date`. All four figures are real.*

### 9. Extensions — III. GUESS

> **28 matters had their clock extended** in 2026 — 8.2% of notifications.
> **507 business days** of extra time, across 46 separate extensions.
>
> **Which deal ate the most of it?**
> - Insurance Australia Group – RAC Insurance (35 BD)
> - Saipem – Subsea7 (48 BD)
> - Zoetis – Neogen Genomics ✅ (63 BD)
> - Coles – Angle Vale, SA (33 BD)

> **Zoetis – Neogen Genomics: 63 business days, over five extensions.** Three
> months of extra clock on a deal about genomic testing for cattle.
>
> The single biggest one-off extension was **33 business days**, for a Coles
> supermarket site in Angle Vale, South Australia — one request, more extra time
> than the entire statutory clock allows.

And the real finding, which is the best fact on the page:

> **Who asked for the extra time?** The merger parties, 33 times out of 46.
> The ACCC asked 6 times.
>
> **And it mattered.** 2.6% of notifications went to phase 2 — but **28.6% of
> extended ones did.** Eight of the nine phase 2 referrals in 2026 had been
> extended first.
>
> An extension is the tell.

Then the one that shows what an extension actually costs:

> **Black Rhino – Club Hotel Motel Roma** spent **56 business days** in phase 1.
> The statutory clock is 30. Three extensions, worth 30 business days, got it
> there — and it was then approved, with conditions.
>
> It is a single pub in Roma, Queensland, and it had the longest phase 1
> review of any deal the ACCC cleared in 2026.

*Source: `extensions.json` — `summary`, `reasons`, `matters`; the Black Rhino
duration from `effective_notification_datetime` → `phase_1_determination_date`.
All four quiz figures are real, which is what makes the guess hard.*

### 10. Phase 2

> **Nine matters** went to phase 2 in 2026, out of 328.
> Seven finished. Two are still going.

- 3 refused
- 3 assessments ceased (the parties walked away)
- 1 approved with conditions — **Ampol – EG Australia**, the first conditional
  clearance under the new regime
- 2 live at year end: **Saipem – Subsea7** and **Zoetis – Neogen**

> Three of the seven completed phase 2 reviews ended with the parties simply
> giving up. Getting to phase 2 is, on 2026's numbers, a coin flip you lose.

*Source: `phase2.json`, `stats.json → by_phase_2_determination`.*

### 11. The Coles card

One matter deserves its own card.

> **Coles – Kalgoorlie** was filed on 27 November 2025, the voluntary window,
> before the regime even started.
>
> - Referred to phase 2 — 29 January
> - Refused — 1 July
> - Tribunal review lodged — 15 July
> - Federal Court judicial review filed — 17 July
> - Nine-day Tribunal hearing — 9 to 19 November
>
> **74 events. 53 documents before the Tribunal.** Fighting on two fronts at
> once over one supermarket in Kalgoorlie, and still going.

*Source: `mergers/MN-01068.json` (74 events), `data/processed/tribunal_appeals.json`
(ACT 1 of 2026, 53 documents), `data/processed/judicial_reviews.json`
(NSD1310/2026).*

### 12. Appeals

> Three Tribunal reviews were lodged in 2026, by **Coles**, by **IAG**, and by
> **RACWA** — which went to the Tribunal to challenge a deal it was *selling*
> into.
>
> None has been decided. The IAG and RACWA hearings start **30 March 2027**.
>
> Year one ends with the hard questions all still open.

*Source: `data/processed/tribunal_appeals.json`.*

### 13. Questionnaires — IV. GUESS

> The ACCC published **339 market questionnaires** in 2026, asking **1,424
> questions** in total.
>
> The median questionnaire asked **three**. 239 of the 339 asked exactly three —
> the standard set, barely changed.
>
> **How many did the most-questioned deal get?**
> - 8
> - 12
> - 20 ✅
> - 35

> **Twenty**, for **Caterpillar – RPMGlobal Holdings**.
> The shortest, **Gilead – Arcellx**, got two.
>
> When the ACCC writes you a fourth question, pay attention.

*Source: `questionnaires/*.json → questions_count`.*

### 14. Before the clock starts

> The review is only the part you can see.
>
> Deals notified in 2026 had already spent an estimated median **21 days** in
> pre-notification talks with the ACCC before the clock started.
>
> The longest: **Steadfast – Axiom Insurance Brokers**, an estimated **183
> days** — six months of conversation with the ACCC before day one of the
> review, which was still running at the end of November.
>
> Second: **Kimberly-Clark – Kenvue**, an estimated 166 days. Third:
> **Amadeus – Idemia Public Security**, 132.

Caveat on the card, in small type: these are estimates with a confidence
rating, from `pre_notification_summary`.

*Source: `mergers/{id}.json → pre_notification`, 328 matters with an estimate.*

### 15. Who was busiest — V. GUESS

> **3,183 different companies** appeared on the register in 2026.
>
> **Who turned up most?**
> - Coles Group ✅ (22)
> - Endeavour Group (8)
> - Australian Venue Co (20)
> - Blackstone (10)

> **Coles Group: 22 matters.** Australian Venue Co was second with 20 — a
> different pub, nearly every fortnight.
>
> The ACCC flagged **68 serial-acquisition patterns** in 2026: the same buyer,
> the same industry, over and over. Vet clinics. Dental practices. Pubs. Petrol
> stations. Aged care.
>
> The regime was designed for the billion-dollar deal. It spent 2026 counting
> vet clinics.

*Source: `parties.json`, `serial-acquirers.json` (68 clusters).*

### 16. The industry card

> The single most-tagged industry of 2026 was **Financial Asset Investing** —
> 240 matters. Which is mostly private equity wearing a trench coat.
>
> After that: **software and IT** (140), **property** (62), and — at 51 matters
> — **pubs, taverns and bars**.

*Source: `mergers/list.json → anzsic_codes`, aggregated.*

### 17. The comeback

> Getting knocked back isn't the end.
>
> **18 deals** were refused a waiver and came back as a full notification.
> **16 of the 17** that have finished were cleared.
>
> **Salesforce – Qualified** was the first knock-back of the new regime, and it
> took three weeks to arrive: waiver filed 8 January, declined 21 January, eight
> business days later. Salesforce re-filed as a full notification on 19 February
> and was cleared on 17 March, in 17 business days.
>
> **Peter Warren – Wakeling Automotive** went further: into phase 2, abandoned
> in June, re-filed in July, cleared with conditions in September.

*Source: `refiled-notifications.json`.*

### 18. Your year — the personal card

Read from localStorage (`merger_tracker_tracked`, `merger_tracker_tracked_industries`).
No server, no account.

> **You followed 7 matters this year.**
> The first was **Google – Wiz**, on 14 January.
> Five of them have been decided. Four were cleared.
> You followed **2 industries**: Veterinary Services and Pubs, Taverns and Bars.
>
> You were watching **Coles – Kalgoorlie** before the Tribunal was.

Needs a graceful empty state — most visitors will have followed nothing:

> **You followed nothing this year.** Which is one way to do it.
> [Follow something →]

The "before the Tribunal was" line only renders when the follow genuinely
predates the event; otherwise drop it. Everything on this card is computed in
the browser, which is what lets it be this specific.

### 19. Close + share

> **That was year one.**
> 896 matters. 99.3% cleared. Three refused. Three in court.
> See you in 2027.

Share button produces a static card (see [*Sharing*](#sharing)) and a link to
`/wrapped`. Also: "Your score: 4/5" if they took the quiz.

## The quiz

Five questions, interleaved rather than batched — a quiz block is a chore, a
question every third card is a rhythm. All in cards 8, 9, 13, 15 and the longest
review.

| # | Card | Question | Answer | Why the distractors work |
|---|---|---|---|---|
| 1 | 8 | Longest review concluded in 2026 | Ampol – EG Australia, 147 BD | Coles (133) and MicroStar (114) are genuine near misses, so elimination doesn't work; Google – Wiz at 28 is the sanity check that makes the answer land |
| 2 | 9 | Biggest total extension | Zoetis – Neogen, 63 BD | All four options are real extended matters with real figures (35, 48, 63, 33), so there's no process-of-elimination tell |
| 3 | 13 | Most questions in one questionnaire | 20 | The median is 3, so every option feels absurd; 35 is the plausible over-guess |
| 4 | 15 | Busiest party | Coles Group, 22 | Australian Venue Co at 20 is genuinely close, and Blackstone/Endeavour are the names people expect |
| 5 | 7 | Which of these was *refused*? | Coles – Kalgoorlie | Put it against three large approved deals (Google – Wiz, Alcoa – South32, Anglo American – Teck). Nobody guesses the supermarket |

Scoring is per-answer feedback plus a running total; keep the total out of the
way until the close card. No timer — this is a register, not a game show.

Each question needs the answer *and the near-miss figure* on the reveal, because
the near miss is where the fact lives: "Australian Venue Co was second with 20"
is more interesting than "Coles: 22".

## The year isn't over

Today is 27 November 2026. December will add roughly 90 matters, several
determinations, and possibly a fourth refusal. Three options, in order of
preference:

1. **Publish on about 15 December, data to 30 November, and say so.** The card
   footer reads "as at 30 November 2026" and the page states in one line that
   December's matters land in the 2027 edition. This is what every Wrapped does
   (Spotify cuts off in late October) and nobody minds. **Recommended.**
2. **Publish on 2 January with the full year.** Cleaner data, worse timing — the
   audience for a professional year-in-review is gone by then.
3. **Regenerate daily and let the numbers move.** Technically easy, since the
   generator runs anyway. But the quiz answers could change mid-season, the
   share cards would go stale, and a "year in review" that changes isn't one.

Either way `wrapped.json` carries an `as_at` and a `coverage` string that every
card can cite, and the generator asserts that the quiz answers haven't changed
since the file was last published — a changed answer should fail the build, not
surprise a reader.

## Data

Everything above exists in committed data today. The page needs one new
generated file, `wrapped.json`, written by
`scripts/generate/static_data/outputs/wrapped.py`:

| Card | Source, already generated |
|---|---|
| Scale, cadence, weekday split, busiest day/week | `mergers/list.json` |
| Monthly shape | `analysis.json → monthly_volume` |
| Durations, records, deadline use | `analysis.json → phase1_duration`, `waiver_duration`, `deadline_utilisation` |
| Clearance, outcomes | `stats.json` |
| Phase 2 | `phase2.json` |
| Extensions (all of card 9) | `extensions.json` |
| Questionnaires | `questionnaires/*.json` |
| Pre-notification | `mergers/{id}.json → pre_notification` |
| Parties, serial acquirers | `parties.json`, `serial-acquirers.json` |
| Refiles | `refiled-notifications.json` |
| Appeals, Coles timeline | `tribunal_appeals.json`, `judicial_reviews.json`, `mergers/MN-01068.json` |
| Your year | localStorage, in the browser |

`wrapped.json` should hold the finished card copy, not just the figures — the
same reason `quarterly.json` carries its own `findings`: the page and the share
cards then can't disagree, and the copy is reviewable in a diff.

### One source worth adding

The per-merger follow counters in the `mergers-feedback` D1 database
(`track_merger_{id}`, see `utils/trackEvent.js`) would give **Australia's
most-watched merger of 2026** — the one card that reports what readers did
rather than what the ACCC did, which is the most Wrapped-ish thing available.
It is an aggregate count per merger with no per-visitor record, so it's publishable
as-is. It needs a query against D1 and a figure baked into `wrapped.json`;
worth it if the counts are not too thin.

## Scope note on "2026 only"

"2026" means **anything that happened in 2026**, not deals filed in 2026. The
distinction matters once: **Coles – Kalgoorlie** was filed on 27 November 2025,
in the voluntary transition window, and is the central matter of 2026 — refused,
appealed, in the Federal Court. Scoping on filing date would cut the best story
on the page.

So: *counting* cards (how many matters, how fast, what share cleared) are
filed-in-2026, since that's what a volume statistic means. *Narrative* cards
(refusals, appeals, records) are anything dated 2026. Thirteen matters were
filed in the 2025 voluntary window; the page mentions that once, on card 11,
where it's the point.

## Sharing

A reader who finishes should get an image. Reuse `scripts/generate/og_cards.py`,
which already draws cards with `card_image.py`:

- One static OG card for `/wrapped` itself, in `og/` alongside the existing
  `PAGE_CARDS` entries, listed in `STATIC_PAGE_META`.
- A share card per quiz score (0–5, six PNGs), so "I got 4/5 on Australia
  Merged" has a picture. These are drawn at build time, not per reader — six
  files, no runtime image generation.
- The personal card can't be a server-drawn image, since the data never leaves
  the browser. Draw it to a canvas client-side and offer a download.

Share text: *"896 mergers. 3 refused. I got 4/5 on Australia Merged →
mergers.fyi/wrapped"*

## Tone

The register's own voice is dry and exact, and the joke should come from the
facts rather than from the writing. "The regime was designed for the
billion-dollar deal. It spent 2026 counting vet clinics" works because both
halves are true and the reader does the laughing. "Beer kegs." works because it
is the whole explanation of a 120-business-day review.

Three things to avoid: no emoji-per-card, no "you're in the top 1% of merger
nerds" (there's no denominator and the reader knows it), and no exclamation
marks on a page about statutory deadlines.

## Accessibility

The regime here is a card deck, which is the hard case, so this needs doing
properly from the start rather than retrofitted (see `docs/accessibility.md`):

- Keyboard is first-class: ← → to move, Enter to answer, Esc to leave. No
  swipe-only interaction.
- No auto-advance timer. Wrapped's timed progress bars are a WCAG 2.2 failure
  (2.2.1 Timing Adjustable) and also just annoying when you're reading numbers.
- Every card is a section with a heading, in one scrollable document, so the
  whole thing reads top to bottom with assistive tech and without JavaScript.
  The card deck is a presentation layer over that, not a replacement for it.
- The monthly bar chart gets the canvas + `sr-only` table treatment the other
  charts use.
- Respect `prefers-reduced-motion` on the count-up animations: show the final
  number.

## Open questions

1. **Route and nav.** `/wrapped` with a dashboard promo banner (`constants/promo.js`
   already does this) and a command palette entry seems right; probably not a
   navbar link, since it is a seasonal page. Keep it live all year or 404 it in
   March?
2. **Prerendering.** It should be in `renderStatic.jsx` — the copy is fully known
   at build time, and this is the one page likely to be shared cold to people
   with no JavaScript. The personal card is the only client-only part.
3. **Does the personal card earn its place** if most visitors have followed
   nothing? The empty state is a decent joke, but a five-card page for the
   median visitor and a six-card page for the regulars is a slightly awkward
   deck.
4. **Most-watched merger** — query D1 and see whether the follow counts are
   thick enough to publish.
