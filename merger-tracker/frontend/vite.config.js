/// <reference types="vitest" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { copyFileSync, existsSync, mkdirSync, statSync } from 'node:fs'
import { resolve, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = dirname(fileURLToPath(import.meta.url))

// Copy the canonical embedding artefacts (committed to data/ at the repo root)
// into public/data/ so Vite serves them at /data/embeddings.{json,bin}. Keeping
// the originals at data/ avoids duplicating ~1 MB of binary in git; the copies
// in public/data/ are gitignored. Runs on dev/build start, plus on data/
// changes during dev so refreshed embeddings show up without a restart.
function copyEmbeddings() {
  const repoRoot = resolve(__dirname, '../..')
  const srcDir = resolve(repoRoot, 'data')
  const destDir = resolve(__dirname, 'public/data')
  const files = ['embeddings.json', 'embeddings.bin']

  const sync = () => {
    if (!existsSync(destDir)) mkdirSync(destDir, { recursive: true })
    for (const name of files) {
      const src = resolve(srcDir, name)
      if (!existsSync(src)) continue
      const dest = resolve(destDir, name)
      const srcStat = statSync(src)
      if (existsSync(dest)) {
        const destStat = statSync(dest)
        if (destStat.mtimeMs >= srcStat.mtimeMs && destStat.size === srcStat.size) continue
      }
      copyFileSync(src, dest)
    }
  }

  return {
    name: 'copy-embeddings',
    buildStart() {
      sync()
    },
    configureServer(server) {
      sync()
      server.watcher.add(resolve(srcDir, 'embeddings.json'))
      server.watcher.add(resolve(srcDir, 'embeddings.bin'))
      server.watcher.on('change', (path) => {
        if (path.startsWith(srcDir)) sync()
      })
    },
  }
}

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), copyEmbeddings()],
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
  // transformers.js is loaded lazily inside a Web Worker on the semantic
  // search page only, so skip pre-bundling it for the main entry.
  optimizeDeps: {
    exclude: ['@huggingface/transformers'],
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.js'],
    css: false,
  },
})
