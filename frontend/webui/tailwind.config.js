/** @type {import('tailwindcss').Config} */
export default {
  // This is crucial. It tells Tailwind to scan all your Vue components,
  // JS files, and the main index.html for class names.
  content: [
    "./index.html",
    "./src/**/*.{vue,js,ts,jsx,tsx}",
  ],
  // This enables dark mode based on a class being present on a parent element.
  // We control this with the '.dark' class on the <html> tag.
  darkMode: 'class',
  theme: {
    extend: {      colors: {
        gray: {
          750: '#374151', // Custom gray-750
        }
      }},
  },
  // FIX: Add the typography plugin here.
  plugins: [
    require('@tailwindcss/typography'),
  ],
}