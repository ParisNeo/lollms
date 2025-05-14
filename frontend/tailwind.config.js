// tailwind.config.js
/** @type {import('tailwindcss').Config} */
import formsPlugin from '@tailwindcss/forms'; // This will only work if @tailwindcss/forms exports an ESM default
import typographyPlugin from '@tailwindcss/typography'; // Same condition

export default {
  content: [
    "./index.html",
    "./src/**/*.{vue,js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {},
  },
  plugins: [
    formsPlugin,
    typographyPlugin,
  ],
};