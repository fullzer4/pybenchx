import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';

export default defineConfig({
  site: 'https://fullzer4.github.io',
  base: '/pybenchx/',
  integrations: [
    starlight({
      title: 'PyBenchx',
      tagline: 'Tiny, precise microbenchmarks for Python.',
      description: 'A tiny, precise microbenchmarking framework for Python.',
      social: { github: 'https://github.com/fullzer4/pybenchx' },
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
          items: [{ label: 'bench / Bench / BenchContext', link: '/api' }]
        },
        { label: 'Examples', link: '/examples' },
        { label: 'Internals', link: '/internals' },
        { label: 'Contributing', link: '/contributing' }
      ]
    })
  ]
});
