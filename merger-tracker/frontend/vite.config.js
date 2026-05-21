/// <reference types="vitest" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Inlines the build CSS into index.html so first paint isn't blocked on a
// separate stylesheet round-trip. The SPA only ships one CSS chunk and it's
// small (~10 KiB gzipped), so the size cost in HTML is acceptable.
function inlineCss() {
  return {
    name: 'inline-css',
    enforce: 'post',
    apply: 'build',
    transformIndexHtml(html, ctx) {
      const linkRe = /<link rel="stylesheet"[^>]*href="\/([^"]+\.css)"[^>]*>/
      const match = html.match(linkRe)
      if (!match) return html
      const asset = ctx.bundle?.[match[1]]
      if (!asset || asset.type !== 'asset') return html
      return html.replace(match[0], `<style>${asset.source.toString()}</style>`)
    },
  }
}

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), inlineCss()],
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          'react-vendor': ['react', 'react-dom', 'react-router-dom'],
          'chart': ['chart.js', 'react-chartjs-2'],
          'date': ['date-fns'],
        }
      }
    }
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.js'],
    css: false,
  },
})
