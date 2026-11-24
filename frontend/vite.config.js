/// <reference types="vitest" />
import { build, defineConfig } from 'vite'
import { fileURLToPath } from 'node:url'
import react from '@vitejs/plugin-react'
import prerenderMergers from './prerender.js'

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

// Builds the browser-notification service worker (src/push/sw.js) to
// dist/sw.js once the site is built. On its own and as one classic script,
// not as an entry of the main build: a service worker needs a fixed URL, and
// Firefox can't load one that imports chunks.
function serviceWorker() {
  let outDir
  return {
    name: 'service-worker',
    apply: 'build',
    configResolved(config) {
      outDir = config.build.outDir
    },
    async closeBundle() {
      await build({
        configFile: false,
        logLevel: 'warn',
        publicDir: false,
        build: {
          outDir,
          emptyOutDir: false,
          lib: {
            entry: fileURLToPath(new URL('./src/push/sw.js', import.meta.url)),
            formats: ['iife'],
            name: 'mergersFyiServiceWorker',
            fileName: () => 'sw.js',
          },
        },
      })
    },
  }
}

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), inlineCss(), prerenderMergers(), serviceWorker()],
  build: {
    rollupOptions: {
      output: {
        // Function form, matching on node_modules paths. The object form
        // names only each package's entry, so shared dependencies (the JSX
        // runtime, react-dom/client, scheduler) landed wherever Rollup first
        // met them: the JSX runtime in the chart chunk, which every page then
        // preloaded, and react-dom/client in the per-deploy main chunk.
        manualChunks(id) {
          if (!id.includes('/node_modules/')) return undefined
          if (/\/node_modules\/(react|react-dom|scheduler|react-router)\//.test(id)) return 'react-vendor'
          if (/\/node_modules\/(chart\.js|react-chartjs-2|@kurkle)\//.test(id)) return 'chart'
          if (/\/node_modules\/date-fns\//.test(id)) return 'date'
          return undefined
        },
      }
    }
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.js'],
    css: false,
    // Node 25+ ships its own global localStorage, which without
    // --localstorage-file is undefined and shadows jsdom's. Turn it off so
    // the tests see jsdom's storage, as the browser would.
    execArgv: ['--no-experimental-webstorage'],
  },
})
