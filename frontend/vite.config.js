import { fileURLToPath, URL } from 'node:url'

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import vueDevTools from 'vite-plugin-vue-devtools'
import path from 'path' // Import the 'path' module
// Get the directory name of the current module
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    vue(),
    vueDevTools(),
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    },
  },
  build: {
    // Output directory relative to the project root (lollms-chat-vue)
    // '../dist' means one level up from 'lollms-chat-vue', then into 'dist'
    outDir: path.resolve(__dirname, '../dist'), // More robust way
    // or simply: outDir: '../dist',
    emptyOutDir: true, // Recommended: Clears the directory before building
  }  
})
