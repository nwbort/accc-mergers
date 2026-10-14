// Variants for the small pill buttons (Track, Share) that sit in a page
// header, on the two surfaces they appear on. `dark` is used by the merger
// detail header, whose title block is filled with the colour of whatever the
// matter is carrying: the resting state darkens that fill rather than washing
// it with white (a white/15 wash only reaches ~4.1:1 for the label), and the
// focus ring goes white, since the site-wide primary green would fall under
// the 3:1 a focus indicator needs there (WCAG 1.4.11).
export const HEADER_BUTTON_VARIANTS = {
  light: {
    active: 'bg-primary text-white border-primary hover:bg-primary-dark shadow-sm',
    inactive: 'bg-gray-100 text-gray-600 border-gray-200/60 hover:bg-gray-200',
  },
  dark: {
    active: 'bg-white text-gray-900 border-white hover:bg-white/90 shadow-sm',
    inactive: 'bg-black/20 text-white border-white/30 hover:bg-black/30',
    focus: 'focus-visible:ring-white focus-visible:ring-offset-0',
  },
};

export const HEADER_BUTTON_BASE =
  'inline-flex items-center justify-center gap-1.5 px-2.5 py-1 text-xs font-semibold rounded-lg border transition-all duration-200 flex-shrink-0';
