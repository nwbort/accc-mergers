// Variants for the small pill buttons (Track, Share) that sit in a page
// header, on the two surfaces they appear on. `dark` is used by the merger
// detail header, whose title block is filled with the colour of whatever the
// matter is carrying: the resting state darkens that fill rather than washing
// it with white (a white/15 wash only reaches ~4.1:1 for the label), and the
// focus ring goes white, since the site-wide primary green would fall under
// the 3:1 a focus indicator needs there (WCAG 1.4.11).
export const HEADER_BUTTON_VARIANTS = {
  light: {
    active: 'bg-primary text-white border-primary hover:bg-primary-dark',
    inactive: 'bg-surface-container-high text-gray-700 border-transparent hover:bg-surface-container-highest',
  },
  dark: {
    active: 'bg-white text-gray-900 border-white hover:bg-white/90',
    inactive: 'bg-black/20 text-white border-white/30 hover:bg-black/30',
    focus: 'focus-visible:ring-white focus-visible:ring-offset-0',
  },
};

// M3 Expressive's small buttons: pills that square off a little when pressed.
export const HEADER_BUTTON_BASE =
  'press-morph inline-flex items-center justify-center gap-1.5 h-9 px-4 text-sm font-semibold rounded-full border flex-shrink-0';
