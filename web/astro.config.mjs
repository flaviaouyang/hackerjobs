import preact from '@astrojs/preact';
import { defineConfig } from 'astro/config';
import { loadEnv } from 'vite';

const { PUBLIC_GOATCOUNTER_CODE: goatcounter } = loadEnv(process.env.NODE_ENV ?? 'production', process.cwd(), '');
const counter = goatcounter ? [`https://${goatcounter}.goatcounter.com`] : [];

export default defineConfig({
  site: 'https://flaviaouyang.github.io',
  base: '/hackerjobs',
  trailingSlash: 'always',
  integrations: [preact()],
  redirects: { '/': '/hiring/' },
  // No Markdown code blocks here; Shiki's inline styles would conflict with the CSP.
  markdown: { syntaxHighlight: false },
  // GitHub Pages can't send headers, so the policy goes in a <meta> tag with hashes of the site's
  // own scripts and styles. Only GoatCounter is allowed beyond the site itself.
  security: {
    csp: {
      scriptDirective: { resources: ["'self'", ...(goatcounter ? ['https://gc.zgo.at'] : [])] },
      directives: [
        "default-src 'self'",
        `img-src 'self' data: ${counter.join(' ')}`.trim(),
        `connect-src 'self' ${counter.join(' ')}`.trim(),
        "object-src 'none'",
        "base-uri 'self'",
        "form-action 'none'",
      ],
    },
  },
});
