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
        // Material 3 Expressive colour roles, the same scheme as the Android
        // app's `Light` (ui/theme/Theme.kt), seeded from the brand green.
        primary: '#335145',
        'primary-light': '#4a6d5e',
        'primary-dark': '#223a30',
        'on-primary': '#ffffff',
        'primary-container': '#d4e8dc',
        'on-primary-container': '#0e2a1e',
        'secondary-container': '#d1fae5',
        'on-secondary-container': '#064e3b',
        accent: '#10b981',
        'accent-light': '#34d399',
        'accent-dark': '#059669',
        // Surfaces step from the page (`surface`) up through the tonal
        // containers, as M3 elevates by tone rather than by shadow: cards are
        // `surface-container-lowest` (white) on the tinted page.
        surface: {
          DEFAULT: '#f3f6f4',
          dim: '#e3e9e6',
          'container-lowest': '#ffffff',
          'container-low': '#f2f5f3',
          container: '#ecf0ee',
          'container-high': '#e6ebe8',
          'container-highest': '#e0e6e3',
          50: '#f8faf9',
          100: '#eef2f0',
          200: '#e0e6e3',
          300: '#c9d1cd',
        },
        outline: {
          DEFAULT: '#6f7a75',
          variant: '#c3cbc7',
        },
        // Tailwind's grey, replaced by M3 neutral tones carrying a trace of
        // the brand's green hue, so every `text-gray-*` and `bg-gray-*` in the
        // codebase sits in the same tonal palette as the surfaces above. Each
        // step keeps the lightness of the Tailwind grey it replaces, so text
        // contrast is unchanged: gray-500 is 5.2:1 on white and 4.6:1 on
        // surface-container, as the old gray-500 was.
        gray: {
          50: '#f6f8f7',
          100: '#eef2f0',
          200: '#e0e6e3',
          300: '#c9d1cd',
          400: '#8f9a95',
          500: '#636f6a',
          600: '#47524d',
          700: '#333d39',
          800: '#1f2925',
          900: '#141b18',
          950: '#0b100e',
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
      // M3 elevation levels, tinted toward the neutral palette. Cards rest at
      // level 0 (tone does the work) and rise to level 2 on hover; menus and
      // dialogs sit at level 3.
      boxShadow: {
        'glass': '0 1px 3px 1px rgba(20, 27, 24, 0.08), 0 1px 2px rgba(20, 27, 24, 0.12)',
        'card': '0 0 0 0 rgba(0, 0, 0, 0)',
        'card-hover': '0 2px 6px 2px rgba(20, 27, 24, 0.08), 0 1px 2px rgba(20, 27, 24, 0.12)',
        'elevated': '0 4px 8px 3px rgba(20, 27, 24, 0.1), 0 1px 3px rgba(20, 27, 24, 0.14)',
      },
      // Material 3 Expressive's rounder shape scale (the app's AppShapes):
      // chips and badges 8, fields 12, small cards 16, cards 24, hero blocks
      // and dialogs 32.
      borderRadius: {
        'md': '0.5rem',
        'lg': '0.75rem',
        'xl': '1rem',
        '2xl': '1.5rem',
        '3xl': '2rem',
        '4xl': '2.5rem',
      },
      // M3 motion: the emphasized curve for things that move or fade, and an
      // expressive spring (a little overshoot) for things that grow, press or
      // change shape. The default curve is the emphasized one, so every
      // `transition-*` utility moves the M3 way.
      transitionTimingFunction: {
        DEFAULT: 'cubic-bezier(0.2, 0, 0, 1)',
        'emphasized': 'cubic-bezier(0.2, 0, 0, 1)',
        'spring': 'cubic-bezier(0.34, 1.45, 0.64, 1)',
      },
      backdropBlur: {
        'xs': '2px',
      },
      animation: {
        'gradient': 'gradient 8s ease infinite',
        'fade-in': 'fadeIn 0.3s cubic-bezier(0.2, 0, 0, 1)',
        'slide-up': 'slideUp 0.35s cubic-bezier(0.34, 1.45, 0.64, 1)',
        'pop-in': 'popIn 0.4s cubic-bezier(0.34, 1.45, 0.64, 1)',
        'pulse-soft': 'pulseSoft 2s ease-in-out infinite',
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
        popIn: {
          '0%': { opacity: '0', transform: 'scale(0.92)' },
          '100%': { opacity: '1', transform: 'scale(1)' },
        },
        pulseSoft: {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.5' },
        },
      },
    },
  },
  plugins: [],
}
