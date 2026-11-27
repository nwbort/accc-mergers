/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
    // The build-time prerenderer emits Tailwind classes of its own for the
    // static HTML crawlers and first paint see. Without this entry those
    // classes are purged from the stylesheet and the prerendered pages render
    // as unstyled text until React mounts.
    "./prerender.js",
  ],
  theme: {
    extend: {
      colors: {
        // Material 3 colour roles, for /merged (the Australia Merged deck) and
        // nothing else yet. The deck wears the Android app's Material 3
        // Expressive language, which needs the tonal surface ladder and the
        // container roles that the site's own palette doesn't have.
        //
        // Namespaced `m3-*` on purpose: the full redesign (PR #1138) replaces
        // the site's colours, greys and shape scale with these roles
        // unprefixed, and would restyle every page. Until that lands these sit
        // beside the existing tokens and change nothing. When it does, these
        // entries fold into it and `m3-` drops off.
        //
        // Values are that branch's generated scheme (src/theme/m3-theme.json:
        // material-color-utilities, TonalSpot, 2025 spec, seeded on the brand
        // green), with `primary` kept as the brand green itself, as the app's
        // own scheme does (ui/theme/Theme.kt).
        m3: {
          'primary': '#335145',
          'on-primary': '#ffffff',
          'primary-container': '#aff0d5',
          'on-primary-container': '#195c47',
          'secondary': '#4d645a',
          'secondary-container': '#cee9db',
          'on-secondary-container': '#3f574d',
          'tertiary': '#2e6770',
          'tertiary-container': '#b9f2fd',
          'on-tertiary-container': '#225d66',
          'on-surface': '#2b3530',
          'on-surface-variant': '#57615c',
          'outline': '#737d77',
          'outline-variant': '#aab4ae',
          'surface': '#f6faf6',
          'surface-dim': '#d2ddd6',
          'surface-container-lowest': '#ffffff',
          'surface-container-low': '#eff5f0',
          'surface-container': '#e8f0ea',
          'surface-container-high': '#e2eae4',
          'surface-container-highest': '#dae5de',
        },
        primary: '#335145',
        'primary-light': '#4a6d5e',
        'primary-dark': '#223a30',
        accent: '#10b981',
        'accent-light': '#34d399',
        'accent-dark': '#059669',
        surface: {
          50: '#f8fafc',
          100: '#f1f5f9',
          200: '#e2e8f0',
          300: '#cbd5e1',
        },
        // Custom theme colors for digest sections
        'new-merger': {
          DEFAULT: '#5B3758',
          light: '#8B6787',
          dark: '#3D2539',
          pale: '#F3EBF2',
        },
        // `dark` is the shade used for text on white/pale surfaces, so it
        // has to clear 4.5:1 there (WCAG 1.4.3) — the DEFAULT green is a fill
        // colour and only reaches 2.5:1 as small text.
        'cleared': {
          DEFAULT: '#10b981',
          light: '#34d399',
          dark: '#047857',
          pale: '#D1FAE5',
        },
        'declined': {
          DEFAULT: '#f49097',
          light: '#F9B5BA',
          dark: '#C42A38',
          pale: '#FEE7E9',
        },
        'ceased': {
          DEFAULT: '#9333ea',
          light: '#c084fc',
          dark: '#7e22ce',
          pale: '#faf5ff',
        },
        'tribunal-appeal': {
          DEFAULT: '#2563eb',
          light: '#60a5fa',
          dark: '#1d4ed8',
          pale: '#DBEAFE',
        },
        'phase-1': {
          DEFAULT: '#B8935C',
          light: '#D4B384',
          // Deep enough to clear 4.5:1 as small text on both white and the
          // pale fill it's paired with in the phase pills.
          dark: '#6F562F',
          pale: '#FCECC9',
        },
        'phase-2': {
          DEFAULT: '#52489c',
          light: '#7B72B8',
          dark: '#3A3372',
          pale: '#E8E5F3',
        },
        'phase-2-referral': {
          DEFAULT: '#d97706',
          light: '#f59e0b',
          dark: '#b45309',
          pale: '#fef3c7',
        },
        // Waiver merger type. Currently the same amber family as
        // phase-2-referral (see issue #668) — kept as a distinct token so the
        // two unrelated concepts can diverge without a find-and-replace.
        'waiver': {
          DEFAULT: '#fbbf24',
          light: '#fcd34d',
          dark: '#b45309',
          pale: '#fffbeb',
        },
      },
      boxShadow: {
        'glass': '0 8px 32px 0 rgba(31, 38, 135, 0.07)',
        'card': '0 1px 3px 0 rgba(0, 0, 0, 0.04), 0 1px 2px -1px rgba(0, 0, 0, 0.04)',
        'card-hover': '0 10px 25px -3px rgba(0, 0, 0, 0.08), 0 4px 6px -4px rgba(0, 0, 0, 0.04)',
        'elevated': '0 20px 40px -12px rgba(0, 0, 0, 0.1)',
      },
      borderRadius: {
        'xl': '0.75rem',
        '2xl': '1rem',
        '3xl': '1.5rem',
        // Material 3 Expressive's shape scale (the Android app's AppShapes),
        // for /merged. Namespaced for the same reason as the m3 colours: the
        // redesign rounds the site's own scale and this must not do that yet.
        'm3-xs': '0.5rem',
        'm3-sm': '0.75rem',
        'm3-md': '1.25rem',
        'm3-lg': '1.5rem',
        'm3-xl': '2rem',
      },
      backdropBlur: {
        'xs': '2px',
      },
      // M3 motion: the emphasized curve for things that move or fade, and the
      // expressive spring (a little overshoot) for things that grow, press or
      // change shape. Added, not defaulted — the site's existing transitions
      // keep whatever easing they already have.
      transitionTimingFunction: {
        'm3-emphasized': 'cubic-bezier(0.2, 0, 0, 1)',
        'm3-spring': 'cubic-bezier(0.34, 1.45, 0.64, 1)',
      },
      animation: {
        'gradient': 'gradient 8s ease infinite',
        'fade-in': 'fadeIn 0.15s ease-out',
        'slide-up': 'slideUp 0.15s ease-out',
        'pulse-soft': 'pulseSoft 2s ease-in-out infinite',
        // /merged: a card's contents springing in as it lands.
        'm3-rise': 'm3Rise 0.42s cubic-bezier(0.34, 1.45, 0.64, 1) both',
        'm3-pop': 'm3Pop 0.38s cubic-bezier(0.34, 1.45, 0.64, 1) both',
      },
      keyframes: {
        gradient: {
          '0%, 100%': { backgroundPosition: '0% 50%' },
          '50%': { backgroundPosition: '100% 50%' },
        },
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideUp: {
          '0%': { opacity: '0', transform: 'translateY(10px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        pulseSoft: {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.5' },
        },
        m3Rise: {
          '0%': { opacity: '0', transform: 'translateY(10px)' },
          '100%': { opacity: '1', transform: 'none' },
        },
        m3Pop: {
          '0%': { opacity: '0', transform: 'scale(0.5)' },
          '100%': { opacity: '1', transform: 'none' },
        },
      },
    },
  },
  plugins: [],
}
