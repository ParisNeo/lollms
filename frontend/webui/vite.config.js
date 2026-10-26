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
  // Pre-bundle dynamically imported preview libraries at dev-server start.
  // They are only referenced via runtime import() in ArtefactSplitView.vue,
  // so without this Vite discovers them mid-session, mints a new dep hash,
  // and already-loaded pages 504 on the stale hashed URL.
  optimizeDeps: {
    include: [
      '@silurus/ooxml/xlsx',
      'exceljs',
      'mammoth',
      'pptx-preview',
    ],
  },
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
      output: {
        // Advanced manual chunking to isolate heavy libraries
        manualChunks(id) {
          if (id.includes('node_modules')) {
            if (id.includes('mermaid')) return 'vendor-mermaid';
            if (id.includes('codemirror') || id.includes('@codemirror')) return 'vendor-editor';
            if (id.includes('highlight.js')) return 'vendor-highlight';
            if (id.includes('pyodide')) return 'vendor-python';
            // Keep canvg + pdfjs-dist AND their shared runtime deps in ONE chunk.
            // pdfjs-dist internally extends classes from modules that canvg also
            // imports (raf, xmlserializer, ...). If Rollup splits that shared
            // subgraph across chunk boundaries, the base class evaluates to
            // undefined at chunk-eval time -> "Class extends value undefined".
            if (
              id.includes('canvg') ||
              id.includes('pdfjs-dist') ||
              id.includes('node_modules/raf') ||
              id.includes('node_modules/xmlserializer')
            ) return 'vendor-viz';

            // Standard vendor chunk for smaller libs
            return 'vendor';
          }
          // Split stores into their own chunk to help with circularity
          if (id.includes('src/stores/')) {
            return 'app-stores';
          }
        }
      }
    }
  }
})