import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';

export default defineConfig({
  site: 'https://fullzer4.github.io/pybenchx',
  base: '/pybenchx',
  integrations: [starlight()]
});
