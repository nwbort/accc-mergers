// Single source of truth for the site's top-level pages and the three surfaces
// that list them: the Navbar, the CommandPalette and the keyboard shortcuts
// (both the `g` chords themselves and the `?` help overlay).
//
// Each entry declares which surfaces it appears on, so a page can be on any
// combination of them — a shortcut with no navbar or palette entry is a
// deliberate option, not an oversight. The fields:
//
//   inNavbar / navOrder      — shown in the navbar, in navOrder order
//   inPalette / paletteOrder — listed in the command palette, in paletteOrder
//   shortcut                 — the key that follows `g` to reach the page. Also
//                              what the navbar draws as a hint badge while `g`
//                              is held. Must be unique across this table;
//                              navPages.test.js enforces that.
//
// Array order is itself meaningful: it is the order the keyboard-shortcut help
// overlay lists the chords in, so keep this list in a sensible reading order.
// The navbar and palette ignore it and sort by their own *Order fields.
export const NAV_PAGES = [
  { label: 'Dashboard', path: '/', shortcut: 'd', inNavbar: true, navOrder: 1, inPalette: true, paletteOrder: 1 },
  { label: 'Mergers', path: '/mergers', shortcut: 'm', inNavbar: true, navOrder: 2, inPalette: true, paletteOrder: 2 },
  // Reachable by its chord and by links from merger pages; deliberately on
  // neither the navbar nor the palette.
  { label: 'Timeline', path: '/timeline', shortcut: 't', inNavbar: false, inPalette: false },
  { label: 'Current status', path: '/current-status', shortcut: 's', inNavbar: true, navOrder: 3, inPalette: true, paletteOrder: 9 },
  { label: 'Phase 2', path: '/phase-2', inNavbar: true, navOrder: 4, inPalette: true, paletteOrder: 3 },
  // Industries keeps its `g i` shortcut and its palette entry; it is off the
  // navbar to make room for Current status without a seventh link.
  { label: 'Industries', path: '/industries', shortcut: 'i', inNavbar: false, inPalette: true, paletteOrder: 4 },
  { label: 'Parties', path: '/parties', shortcut: 'p', inNavbar: false, inPalette: true, paletteOrder: 5 },
  { label: 'Analysis', path: '/analysis', shortcut: 'a', inNavbar: true, navOrder: 5, inPalette: true, paletteOrder: 6 },
  { label: 'Commentary', path: '/commentary', shortcut: 'c', inNavbar: false, inPalette: true, paletteOrder: 7 },
  {
    label: 'Digest',
    navbarLabel: 'Catch me up',
    path: '/digest',
    inNavbar: true,
    navOrder: 6,
    inPalette: true,
    paletteOrder: 8,
  },
  { label: 'Refiled waivers', path: '/refiled-notifications', inNavbar: false, inPalette: true, paletteOrder: 10 },
];

/**
 * The pages reachable by a `g` chord, in the order the help overlay lists them.
 *
 * Both the hook that handles the chords and the overlay that documents them
 * read this, so a shortcut cannot exist without being listed or be listed
 * without working.
 */
export const SHORTCUT_PAGES = NAV_PAGES.filter((page) => page.shortcut);

/** `{ key: path }` for the chord handler — the same table, keyed for lookup. */
export const SHORTCUT_ROUTES = Object.fromEntries(
  SHORTCUT_PAGES.map(({ shortcut, path }) => [shortcut, path])
);
