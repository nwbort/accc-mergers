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
      },
    },
  },
  plugins: [],
}
