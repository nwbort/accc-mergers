// Single source of truth for pages surfaced in the Navbar and the
// CommandPalette. Each entry carries both `navOrder` and `paletteOrder` so
// each surface can render its own filtered, ordered list from one place
// instead of hardcoding a diverging copy.
export const NAV_PAGES = [
  { label: 'Dashboard', path: '/', shortcut: 'd', inNavbar: true, navOrder: 1, inPalette: true, paletteOrder: 1 },
  { label: 'Mergers', path: '/mergers', shortcut: 'm', inNavbar: true, navOrder: 2, inPalette: true, paletteOrder: 2 },
  { label: 'Phase 2', path: '/phase-2', inNavbar: true, navOrder: 3, inPalette: true, paletteOrder: 3 },
  { label: 'Industries', path: '/industries', shortcut: 'i', inNavbar: true, navOrder: 4, inPalette: true, paletteOrder: 4 },
  { label: 'Parties', path: '/parties', inNavbar: false, inPalette: true, paletteOrder: 5 },
  { label: 'Analysis', path: '/analysis', shortcut: 'a', inNavbar: true, navOrder: 6, inPalette: true, paletteOrder: 6 },
  { label: 'Commentary', path: '/commentary', shortcut: 'c', inNavbar: false, inPalette: true, paletteOrder: 7 },
  {
    label: 'Digest',
    navbarLabel: 'Catch me up',
    path: '/digest',
    inNavbar: true,
    navOrder: 7,
    inPalette: true,
    paletteOrder: 8,
  },
  { label: 'Current status', path: '/current-status', inNavbar: false, inPalette: true, paletteOrder: 9 },
  { label: 'Refiled waivers', path: '/refiled-notifications', inNavbar: false, inPalette: true, paletteOrder: 10 },
];
