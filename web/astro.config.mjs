import preact from '@astrojs/preact';
import { defineConfig } from 'astro/config';

export default defineConfig({
  site: 'https://flaviaouyang.github.io',
  base: '/hackerjobs',
  trailingSlash: 'always',
  integrations: [preact()],
  redirects: { '/': '/hiring/' },
});
