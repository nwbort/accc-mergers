# Frontend DRY and alignment cleanup

An audit of `merger-tracker/frontend/src` found the issues below: duplicated
code that should be consolidated, and inconsistencies (colours, accessibility
attributes, navigation lists) that have drifted apart. Each item says what the
problem is, where it lives, and what "done" looks like. Items are independent —
they can be implemented one at a time, in any order, though the misalignment
fixes (1–6) are the highest value.

General rules for all items:

- Tailwind's scanner only keeps classes it can see as full literal strings, so
  never build class names by string interpolation. Shared class strings should
  be exported constants or live inside a shared component.
- New shared components go in `src/components/`, new shared constants in
  `src/constants/`, small helpers in `src/utils/`.
- Behaviour and appearance must not change unless the item explicitly says it
  fixes an inconsistency. Run the existing tests (`npm test` in
  `merger-tracker/frontend`) after each item.

---

## Misalignments

### 1. Inconsistent error states across pages

The snippet `<div className="text-red-600 p-8 text-center">Error: {error}</div>`
is repeated on ~12 pages, but only some include `role="alert"`:

- **Have `role="alert"`:** `pages/Extensions.jsx`, `pages/Industries.jsx`,
  `pages/Dashboard.jsx`, `pages/RefiledNotifications.jsx`, `pages/Parties.jsx`,
  `pages/Phase2.jsx`
- **Missing it:** `pages/Digest.jsx`, `pages/Timeline.jsx`,
  `pages/Commentary.jsx`, `pages/Analysis.jsx`, `pages/Mergers.jsx`

**Fix:** create a small `components/ErrorMessage.jsx` that renders the div
*with* `role="alert"`, taking the error string as a prop. Replace every inline
occurrence with it. (Note: `components/ErrorCard.jsx` already exists for the
richer detail-page error with a back link — leave those usages alone.)

### 2. Navbar and CommandPalette keep two diverging page lists

`components/Navbar.jsx` (top of file, `navLinks`) and
`components/CommandPalette.jsx` (top of file, `PAGES`) each hardcode a list of
pages. They disagree: the palette lacks Phase 2 (which is in the navbar), the
navbar lacks Parties and Refiled waivers (which are in the palette), and
neither lists the routed Timeline or Extensions pages.

**Fix:** create `constants/navPages.js` exporting one list of pages, each entry
having `label`, `path`, optional `shortcut`, and boolean flags `inNavbar` and
`inPalette` (preserve each surface's current ordering and labels — e.g. the
navbar calls Digest "Catch me up"; keep per-surface label overrides if needed).
Both components filter this list instead of defining their own. While doing
this, add Phase 2 to the palette list (`inPalette: true`) since its absence is
the clear drift bug; do not otherwise change which pages appear where without
checking with a maintainer.

### 3. Chart colours are hardcoded hexes duplicating the theme

Three problems:

- `pages/Analysis.jsx` defines a `COLORS` object (`#335145`, `#e07a5f`,
  `#6b8f7f`, `#8cafa0`) and `pages/Dashboard.jsx` hardcodes the same palette
  again as an array literal in `determinationData` and repeats two of the
  hexes in `waiverDeterminationData`.
- Dashboard's doughnut applies the array **positionally** to
  `Object.keys(stats.by_determination)`, so colours are tied to key order, not
  meaning — fragile.
- `pages/Extensions.jsx` inlines `#335145`, `#52489c`, `#d97706` in
  `EXTENSION_REASONS` — these are exactly the `primary`, `phase-2`, and
  `phase-2-referral` colours from `tailwind.config.js`, retyped by hand.

**Fix:** create `constants/chartColors.js` exporting (a) the named brand chart
palette used by Analysis/Dashboard (primary/accent/teal/sage plus their
`...Light` rgba variants), and (b) the theme hexes Extensions needs (primary,
phase-2, phase-2-referral) so each hex is written once. Import from it in all
three pages. For the Dashboard doughnut, build the background-colour array by
mapping over the actual determination labels with an explicit
label→colour lookup (falling back to the palette order for unknown labels), so
"Approved" is always the primary green regardless of key order.

### 4. Outcome→colour semantics defined in three places

The mapping "approved/not opposed = emerald-500, declined/not approved =
red-500, referred to phase 2 = amber-500, ceased = purple-500" is defined
independently in:

- `components/MergerTimeline.jsx` — `OUTCOME_DOT`
- `pages/MergerDetail.jsx` — the `EVENT_DOT_*` constants and `OUTCOME_EVENT_DOT`
- `pages/Timeline.jsx` — the `getEventColor` switch

**Fix:** add a shared map to `constants/` (next to the existing `CARD_STYLES`
in `cardStyles.js` and `STATUS_COLORS` in `mergerStatus.js`, which are the badge
and card variants of the same semantics). Key it by the `MERGER_STATUS`
constants. Each entry needs the plain dot class (`bg-emerald-500`) and the
tinted ring class (`bg-emerald-500/10`) since MergerDetail uses both. Rewrite
the three call sites on top of it. Full literal class strings, per the
Tailwind rule above. Colours must come out pixel-identical to today.

### 5. Waiver shares Phase 2 referral's amber

`components/WaiverBadge.jsx` and the Waiver group in
`components/IndustryMergerGroups.jsx` use the same amber family as the
"Referred to phase 2" treatments in `constants/mergerStatus.js` and
`constants/cardStyles.js`, so two unrelated concepts read as the same colour.
Also, in `IndustryMergerGroups.jsx` the Phase 1/Phase 2 groups use theme
palette classes (`bg-phase-1`, `bg-phase-2`) while Waiver uses raw amber
classes — half in the design system, half out.

**Fix (two steps, second needs sign-off):**

1. Mechanical: add a `waiver` colour to `tailwind.config.js` under
   `theme.extend.colors` (DEFAULT/light/dark/pale, same shape as `phase-1`),
   initially set to the *current* amber values so nothing visually changes, and
   switch WaiverBadge + the Waiver group styles to use it. This puts waiver in
   the design system.
2. Judgement call: actually changing waiver to a distinct hue is a design
   decision — propose a colour in the PR description but don't change the hue
   without maintainer approval.

### 6. Raw status strings bypass the `MERGER_STATUS` constants

`constants/mergerStatus.js` exists so status strings are written once (they
must match the data pipeline). These call sites use raw literals instead:

- `context/TrackingContext.jsx` — `'Assessment ceased'`
- `pages/Dashboard.jsx` — `'Approved'`, `'Not approved'`, and the link
  `href="/mergers?status=Under assessment"`
- `pages/IndustryDetail.jsx` — `'Under assessment'`, `'Assessment suspended'`,
  and a `'Phase 2'` phase check (use the `PHASES` constant for that one)

**Fix:** import and use `MERGER_STATUS` / `PHASES` at each site. For the
Dashboard href, build the query string from the constant (e.g. a template
string with `MERGER_STATUS.UNDER_ASSESSMENT`). Grep the whole `src/` tree for
each status string afterwards to catch stragglers (test files may legitimately
use literals; leave tests alone).

---

## DRY consolidations

### 7. `IndustryTreemap.jsx` and `PartyTreemap.jsx` are identical

The two components in `src/components/` are byte-for-byte the same logic —
including a duplicated `cellTone()` function and limit constants — differing
only in prop name (`industries` vs `parties`), key field (`code` vs `id`), and
path helper (`industryPath` vs `partyPath`).

**Fix:** create one generic `components/Treemap.jsx` taking `items`,
`getKey(item)`, and `getPath(item)` props (every item already has
`merger_count` and `name`). Either delete the two old files and update their
importers (`pages/Industries.jsx`, `pages/Parties.jsx`), or keep them as
two-line wrappers that pass the right props. Check
`components/__tests__/` for existing treemap tests and update them.

### 8. The three dashboard card grids duplicate their body markup

`components/RecentDeterminationsCards.jsx`,
`components/RecentMergersCards.jsx`, and
`components/Phase2CompletedCards.jsx` all render the same structure inside
`CardCollapseGrid`: uppercase label row (with optional "New" chip), a title
`Link` with the `after:absolute after:inset-0` stretched-link trick, and a
meta row of small text separated by `·`. The chip class string
(`inline-flex items-center rounded-md px-2 py-0.5 ...`) is retyped four times,
`DETERMINATION_LABELS = { [ASSESSMENT_CEASED]: 'Ceased' }` is defined twice,
and the empty-state card ("bg-white rounded-2xl ... No recent X.") appears
three times (third copy in `components/UpcomingEventsTimeline.jsx`).

**Fix:**

- Extract a `components/MergerCardBody.jsx` that takes the style object plus
  props for label, optional chip(s), the merger id/name (for the link), and
  meta children. The three grids' `renderBody` callbacks become thin calls to
  it.
- Move `DETERMINATION_LABELS` into `constants/mergerStatus.js` and import it
  in both places.
- Extract an `components/EmptyStateCard.jsx` (heading + message props) used by
  the three empty states.

Keep the rendered DOM effectively identical — these cards have snapshot-ish
tests in `components/__tests__/`.

### 9. Search input + magnifier SVG copy-pasted

The identical inline magnifying-glass SVG and long input class string
(`w-full pl-10 pr-3 py-2.5 bg-gray-50 border border-gray-200 rounded-xl
text-sm focus:ring-2 focus:ring-primary/20 ...`) appear in
`pages/Industries.jsx`, `pages/Parties.jsx`, and `pages/IndustryDetail.jsx`,
with near-variants in `pages/Mergers.jsx`.

**Fix:** create `components/SearchInput.jsx` wrapping the relative div, SVG,
and input; pass through `value`, `onChange`, `placeholder`, `aria-label`, and
allow extra className. Replace the three identical usages. The Mergers page
variants differ (extra right padding, conditional classes) — only migrate them
if it can be done without changing their appearance; otherwise leave Mergers
for a follow-up.

### 10. `IndustryDetail.jsx` and `PartyDetail.jsx` duplicate page sections

Both pages hand-roll the same pieces:

- A 2×4 stat-card grid (`bg-white p-5 rounded-2xl ...` with uppercase label +
  big number). Note this is *not* the existing `StatCard` component, which is a
  third, visually different treatment used on the Dashboard — don't merge with
  it.
- A breadcrumb `nav`/`ol` structure with `FaChevronRight` separators.
- A `decodeURIComponent(param)` wrapped in try/catch.
- The `ErrorCard` not-found vs generic-error branching.

**Fix:** extract `components/DetailStatGrid.jsx` (takes the `statCards` array),
`components/Breadcrumb.jsx` (takes a list of `{label, to}` items, last one
current), and a `utils/decodeParam.js` helper (or `useDecodedParam` hook) for
the try/catch. Use them in both pages. The error branching can stay inline —
it's short and the messages differ.

### 11. Follow/Track toggle button duplicated

`pages/IndustryDetail.jsx` (Follow/Following an industry) and
`pages/MergerDetail.jsx` (Track/Tracking a merger) render the same button:
same class strings including the active/inactive variants, same `BellIcon`,
same `aria-pressed` pattern. Only the labels and aria-labels differ.

**Fix:** extract `components/TrackButton.jsx` with props for `active`,
`onClick`, the active/inactive labels, and the aria-labels (and the optional
`title` tooltip IndustryDetail has). Use it in both pages.

### 12. Repeated utility-class idioms

Two class strings recur enough to drift:

- `bg-white rounded-2xl border border-gray-100 shadow-card` — ~57 occurrences
  across 25 files (some variants add hover classes).
- `text-xs font-medium text-gray-500 uppercase tracking-wider` — ~31
  occurrences across 10 files (section headings).

**Fix:** the lightest-touch approach, consistent with the existing
`PROSE_MARKDOWN` constant in `utils/classNames.js`: export two constants from
that file (e.g. `CARD` and `SECTION_HEADING`) and migrate occurrences with a
careful find-and-replace, keeping any per-site additions appended after the
constant. Do **not** attempt this as one mega-commit — it's safe to migrate
file by file, and it's fine to only migrate the exact-match occurrences and
leave variants alone. Full literal strings inside the constants, per the
Tailwind rule.
