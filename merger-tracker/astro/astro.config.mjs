import { defineConfig } from 'astro/config';
import tailwind from '@astrojs/tailwind';
import sitemap from '@astrojs/sitemap';

export default defineConfig({
  site: 'https://mergers.fyi',
  integrations: [
    tailwind(),
    sitemap(),
  ],
  vite: {
    build: {
      rollupOptions: {
        output: {
          manualChunks: {
            'chart': ['chart.js'],
          },
        },
      },
    },
  },
});
