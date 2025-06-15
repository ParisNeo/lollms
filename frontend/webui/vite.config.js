import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [vue()],
  server: {
    // Proxy API requests to the backend server to avoid CORS issues during development
    proxy: {
      '/api': {
        target: 'http://localhost:9601',
        changeOrigin: true,
      },
      '/admin': {
        target: 'http://localhost:9601',
        changeOrigin: true,
      },
      '/locals': {
        target: 'http://localhost:9601',
        changeOrigin: true,
      },
       '/favicon.ico': {
        target: 'http://localhost:9601',
        changeOrigin: true,
      },
    },
  },
  build: {
    // This sets the output directory for the build command.
    // We use resolve to go one level up from the current directory (`webui`)
    // and create a 'dist' folder there.
    // The final output will be in `frontend/dist/`.
    outDir: resolve(__dirname, '../dist'),
    // This ensures that the output directory is cleared before each build.
    emptyOutDir: true,
  },
})