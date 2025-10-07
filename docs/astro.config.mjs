import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';

export default defineConfig({
  site: 'https://fullzer4.github.io/pybenchx',
  base: '/pybenchx',
  contentLayer: true,
  integrations: [
    starlight({
      title: 'PyBenchx',
      tagline: 'Tiny, precise microbenchmarks for Python.',
      description: 'A tiny, precise microbenchmarking framework for Python.',
      social: [
        { icon: 'github', label: 'GitHub', href: 'https://github.com/fullzer4/pybenchx' }
      ],
      editLink: {
        baseUrl: 'https://github.com/fullzer4/pybenchx/edit/main/docs/src/content/docs/'
      },
      lastUpdated: true,
      sidebar: [
        { label: 'Overview', link: '/' },
        { label: 'Getting Started', link: '/getting-started' },
        { label: 'CLI', link: '/cli' },
        { label: 'Behavior & Accuracy', link: '/behavior' },
        {
          label: 'API Reference',
          items: [
            { label: 'Overview', link: '/api' },
            { label: 'Decorators & Suites', link: '/api/decorators' },
            { label: 'BenchContext & Runner', link: '/api/context' },
            { label: 'Runs, Storage & Compare', link: '/api/storage' },
            { label: 'Reporters & Exports', link: '/api/reporters' }
          ]
        },
        { label: 'Examples & Cookbook', link: '/examples' },
        { label: 'Internals', link: '/internals' },
        { label: 'Contributing', link: '/contributing' }
      ]
    })
  ]
});
