import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'

export default defineConfig({
  plugins: [
    vue(),
    tailwindcss()
  ],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
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
            if (id.includes('canvg') || id.includes('pdfjs-dist')) return 'vendor-viz';
            
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