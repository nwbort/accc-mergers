/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
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
        'cleared': {
          DEFAULT: '#10b981',
          light: '#34d399',
          dark: '#059669',
          pale: '#D1FAE5',
        },
        'declined': {
          DEFAULT: '#f49097',
          light: '#F9B5BA',
          dark: '#E8636C',
          pale: '#FEE7E9',
        },
        'phase-1': {
          DEFAULT: '#B8935C',
          light: '#D4B384',
          dark: '#8A6B3E',
          pale: '#FCECC9',
        },
        'phase-2': {
          DEFAULT: '#52489c',
          light: '#7B72B8',
          dark: '#3A3372',
          pale: '#E8E5F3',
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
      },
      backdropBlur: {
        'xs': '2px',
      },
      animation: {
        'gradient': 'gradient 8s ease infinite',
        'fade-in': 'fadeIn 0.15s ease-out',
        'slide-up': 'slideUp 0.15s ease-out',
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
        pulseSoft: {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.5' },
        },
      },
    },
  },
  plugins: [],
}
