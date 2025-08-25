// docs/starlight.config.ts
import { defineConfig } from '@astrojs/starlight/config';

export default defineConfig({
  title: 'PyBenchx',
  tagline: 'Tiny, precise microbenchmarks for Python.',
  description: 'A tiny, precise microbenchmarking framework for Python.',
  favicon: '/favicon.svg',
  social: {
    github: 'fullzer4/pybenchx'
  },
  editLink: {
    baseUrl: 'https://github.com/fullzer4/pybenchx/edit/main/docs/src/content/docs/'
  },
  lastUpdated: true,
  sidebar: [
    { label: 'Overview', link: '/' },
    { label: 'Getting Started', link: '/getting-started' },
    { label: 'CLI', link: '/cli' },
    {
      label: 'API Reference',
      items: [
        { label: 'bench / Bench / BenchContext', link: '/api' }
      ]
    },
    { label: 'Examples', link: '/examples' },
    { label: 'Contributing', link: '/contributing' }
  ]
});
