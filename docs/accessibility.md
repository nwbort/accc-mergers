# Accessibility

Target: **WCAG 2.2 Level AA**. The frontend is audited with
[axe-core](https://github.com/dequelabs/axe-core) plus a manual keyboard and
screen-reader-semantics pass.

## Running the audit

axe-core and Playwright aren't project dependencies — the audit is run
on demand against a production build rather than in CI, so nothing in
`package.json` carries the weight of a browser download.

```bash
cd merger-tracker/frontend
npm run build
npx --yes serve dist -l 4178          # or any static server rooted at dist/

# in a scratch directory
npm install --no-save playwright axe-core
```

Then drive a page with Playwright, inject `axe-core/axe.min.js`, and call
`axe.run(document, { runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa',
'wcag21a', 'wcag21aa', 'wcag22aa', 'best-practice'] } })`.

Cover, at minimum:

- every route in `src/App.jsx`, at 1280px **and** 390px wide (the navbar and
  the card grids render different markup at each);
- merger detail pages for each card treatment — approved, not approved,
  assessment ceased, under assessment, under appeal, current Phase 2 — since
  `CARD_STYLES` picks the colours per outcome;
- the overlay states: command palette (`Ctrl+K`), keyboard shortcuts (`?`),
  notification panel, and mobile menu.

Automated rules catch roughly half of what matters. Also check by hand: `Tab`
order and whether focus escapes an open dialog, `Escape` closing menus and
returning focus, and that the visible focus ring is actually painted.

## Conventions this codebase follows

**Colour.** Every colour family in `tailwind.config.js` carries a `dark` shade
that clears 4.5:1 on white and on the family's `pale` fill; that's the shade
used whenever the colour carries *text*. The `DEFAULT` shades are fills — bars,
dots, borders — and several of them (`cleared`, `phase-1`, `declined`,
`phase-2-referral`) do not pass as small text. `CARD_STYLES` in
`src/constants/cardStyles.js` documents the same rule for the solid-colour
cards: deep enough fill for white body text, full-opacity `sub` tints, and a
`bg-black/20` chip rather than a white wash.

**Badges** (`StatusBadge`, `WaiverBadge`, `AppealBadge`, `NewBadge`,
`RefiledBadge`) use `role="img"` with an `aria-label`, never `role="status"`:
they appear once per table row, and `role="status"` would make every one of
them a live region. `src/components/__tests__/accessibility.test.jsx` guards
this.

**Charts.** Chart.js puts `role="img"` on its own `<canvas>` with no name, so
every chart is rendered with `role="presentation"` and wrapped in a `<div
role="img">` that points at the section heading (`aria-labelledby`) and an
`sr-only` data table (`aria-describedby`). The table is the real text
alternative — a chart's meaning is its numbers.

**Headings.** Every route needs an `h1`. Pages that lead straight into content
(`/mergers`, `/timeline`, `/commentary`, `/analysis`) carry an `sr-only` one.
Levels increase by one at a time — cards in a top-level list are `h2`, not
`h3`.

**Motion.** `src/index.css` collapses animations under
`prefers-reduced-motion: reduce`. Anything looping (the gradient background,
the notification ping) must respect it.

**Overlays.** A dialog with `aria-modal="true"` traps `Tab`, closes on
`Escape`, and restores focus to whatever opened it. `CommandPalette` and
`KeyboardShortcutsHelp` both implement this; copy one of them rather than
inventing a third pattern.

## Known gaps

- The audit is manual, not wired into `frontend-test.yml`.
- Colour contrast is verified for the states the sample routes happen to
  render. A new `CARD_STYLES` entry or colour family needs its own check.
