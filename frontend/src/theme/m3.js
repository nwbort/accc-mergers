/**
 * The site's Material 3 colour scheme, worked out by Google's
 * material-color-utilities from the brand green, the way an M3 app derives
 * its scheme from a seed colour.
 *
 * The result is written to m3-theme.json, which tailwind.config.js reads, so
 * neither the build nor the browser runs the library. Regenerate it with
 * `npm run theme` after changing anything here; __tests__/m3Theme.test.js
 * fails while the JSON and this module disagree, and holds the scheme's
 * contrast pairs to WCAG.
 *
 * Variant: TonalSpot, M3's default, on the 2025 colour spec (the one M3
 * Expressive ships with). One departure: `primary` stays the brand green
 * itself, as it does in the Android app's scheme (ui/theme/Theme.kt). Tonal
 * spot would move it to a lighter, more saturated tone of the same hue, which
 * is no longer the colour the site and the app are known by. Every other role
 * (the containers, the surfaces, outlines, error) is the library's.
 *
 * The greys: Tailwind's `gray` scale is replaced by tones of the scheme's
 * neutral palette, so the codebase's many `text-gray-*`/`bg-gray-*` classes
 * land in the same tonal family as the surfaces. Each step is the M3 tone
 * nearest the lightness of the Tailwind grey it replaces, nudged where text
 * contrast needs it (gray-500 is the muted text on every surface).
 */
import {
  Hct,
  argbFromHex,
  hexFromArgb,
  SchemeTonalSpot,
  MaterialDynamicColors,
} from '@material/material-color-utilities';

export const SEED = '#335145';

const ROLES = {
  'primary-container': 'primaryContainer',
  'on-primary-container': 'onPrimaryContainer',
  secondary: 'secondary',
  'secondary-container': 'secondaryContainer',
  'on-secondary-container': 'onSecondaryContainer',
  tertiary: 'tertiary',
  'tertiary-container': 'tertiaryContainer',
  'on-tertiary-container': 'onTertiaryContainer',
  error: 'error',
  'error-container': 'errorContainer',
  'on-error-container': 'onErrorContainer',
  'on-surface': 'onSurface',
  'on-surface-variant': 'onSurfaceVariant',
  outline: 'outline',
  'outline-variant': 'outlineVariant',
  surface: 'surface',
  'surface-dim': 'surfaceDim',
  'surface-container-lowest': 'surfaceContainerLowest',
  'surface-container-low': 'surfaceContainerLow',
  'surface-container': 'surfaceContainer',
  'surface-container-high': 'surfaceContainerHigh',
  'surface-container-highest': 'surfaceContainerHighest',
};

// Tailwind grey step -> neutral-palette tone (M3 tone = CIE L*).
const GRAY_TONES = {
  50: 98, 100: 95, 200: 91, 300: 84, 400: 66, 500: 44,
  600: 34, 700: 26, 800: 17, 900: 10, 950: 5,
};

export function buildTheme() {
  const scheme = new SchemeTonalSpot(Hct.fromInt(argbFromHex(SEED)), false, 0, '2025', 'phone');
  const colors = { primary: SEED, 'on-primary': '#ffffff' };
  for (const [name, role] of Object.entries(ROLES)) {
    colors[name] = hexFromArgb(MaterialDynamicColors[role].getArgb(scheme));
  }
  const gray = {};
  for (const [step, tone] of Object.entries(GRAY_TONES)) {
    gray[step] = hexFromArgb(scheme.neutralPalette.tone(tone));
  }
  return { seed: SEED, variant: 'tonalSpot', spec: '2025', colors, gray };
}
