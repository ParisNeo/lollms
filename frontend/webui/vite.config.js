import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'
import { fileURLToPath } from 'url'

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [vue(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:9642',
        changeOrigin: true,
      },
      '/ws': {
        target: 'ws://127.0.0.1:9642',
        ws: true,
      },
      '/user_assets': {
        target: 'http://127.0.0.1:9642',
        changeOrigin: true,
      },
    },
  },
  build: {
    chunkSizeWarningLimit: 1200,
    rollupOptions: {
      onwarn(warning, warn) {
        // Suppress known eval() warning from exceljs (third-party, webpack-compat code)
        if (warning.code === 'EVAL' && warning.id && warning.id.includes('exceljs')) return;
        warn(warning);
      },
      output: {
        // Advanced manual chunking to isolate heavy libraries
        manualChunks(id) {
          if (id.includes('node_modules')) {
            if (id.includes('highlight.js')) return 'vendor-highlight';
            if (id.includes('pyodide')) return 'vendor-python';
            if (id.includes('canvg') || id.includes('pdfjs-dist')) return 'vendor-viz';

            // Standard vendor chunk for smaller libs
            return 'vendor';
          }
          // DO NOT separately chunk src/stores/ — it causes circular chunk references
          // with vendor chunks. Let Rollup inline stores naturally.
        }
      }
    }
  }
})