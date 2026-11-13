import { createHash } from 'node:crypto'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'
import type { Plugin } from 'vite'
import { VitePWA } from 'vite-plugin-pwa'

// Icons live in `public/` under fixed names (written by scripts/generate_app_icons.py).
// If the artwork changes but the URL stays the same, browsers keep using their local icon,
// and installed PWAs treat the manifest as unchanged and keep showing the old artwork.
// Add a version derived from the content to the query so the URL changes with the artwork.
const PUBLIC_DIR = fileURLToPath(new URL('./public', import.meta.url))
const ICON_LINKS_IN_HTML = ['favicon.svg', 'apple-touch-icon.png'] as const

const iconUrl = (name: string): string => {
  const digest = createHash('sha256')
    .update(readFileSync(`${PUBLIC_DIR}/${name}`))
    .digest('hex')
  return `/${name}?v=${digest.slice(0, 8)}`
}

/** Also version the icon references in index.html (the manifest side does it via icons). */
const versionIconUrls = (): Plugin => ({
  name: 'version-icon-urls',
  transformIndexHtml: (html: string): string =>
    ICON_LINKS_IN_HTML.reduce(
      (acc, name) => acc.replaceAll(`"/${name}"`, `"${iconUrl(name)}"`),
      html,
    ),
})

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [
    react(),
    versionIconUrls(),
    VitePWA({
      // We register it ourselves (services/appUpdate.ts, ADR-0045). The plugin's registration code
      // silently reloads the moment it activates and wipes in-progress input, so it is not used
      registerType: 'autoUpdate',
      injectRegister: false,
      manifest: {
        name: 'RewardPoints',
        short_name: 'RewardPoints',
        description: 'ポイントの加算・消費・履歴を人ごとに管理する',
        lang: 'ja',
        start_url: '/',
        scope: '/',
        display: 'standalone',
        theme_color: '#1c80fa',
        background_color: '#ffffff',
        icons: [
          { src: iconUrl('pwa-192x192.png'), sizes: '192x192', type: 'image/png' },
          { src: iconUrl('pwa-512x512.png'), sizes: '512x512', type: 'image/png' },
          // For maskable, pass a separate image painted to the edges with the design inside the inner 80% (safe zone).
          // Using the rounded icon as-is for maskable lets the launcher's crop
          // shave the corners and chip the border.
          {
            src: iconUrl('pwa-maskable-512x512.png'),
            sizes: '512x512',
            type: 'image/png',
            purpose: 'maskable',
          },
        ],
      },
      workbox: {
        // Activate a new version as soon as it is delivered (ADR-0045). Since it does not wait, a reload
        // brings in the new version. ⚠ With injectRegister: false the plugin does not add these two
        // automatically (only when we do not register ourselves), so set them explicitly here
        skipWaiting: true,
        clientsClaim: true,
        // Precache only the SPA shell (build output). API, auto-generated docs and
        // operational endpoints are excluded from the navigation fallback so the SW
        // does not return index.html and break JSON responses.
        globPatterns: ['**/*.{js,css,html,svg,png,ico,json}'],
        // Icons are not precached. Every reference is a versioned URL (with `?v=`), which
        // never matches the precache entry name, so they would sit unused and only cost
        // 110KB on every SW update. Offline misses do not matter on screen, since browsers
        // and launchers use the icon from install time.
        globIgnores: ['favicon.svg', 'apple-touch-icon.png', 'pwa-*.png'],
        navigateFallback: '/index.html',
        navigateFallbackDenylist: [
          /^\/api\//,
          /^\/docs/,
          /^\/redoc/,
          /^\/openapi\.json/,
          /^\/metrics/,
          /^\/healthz/,
          /^\/readyz/,
          /^\/info/,
        ],
        // Cache only read-only GETs for offline viewing (ADR-0015).
        // Network-first, so online views are always fresh and the cache is only served
        // when offline. The screen shows the fetch time from the response's Date header.
        // Writes, invitations and admin endpoints are not cached (offline they fail as before).
        // The cache name pairs with OFFLINE_VIEW_CACHE in frontend/src/services/api.ts
        // (deleted from there on logout).
        runtimeCaching: [
          {
            urlPattern: /\/api\/(?:auth\/me|families(?:\/\d+(?:\/ledgers\/\d+)?)?)$/,
            method: 'GET',
            handler: 'NetworkFirst',
            options: {
              cacheName: 'offline-views',
              expiration: { maxEntries: 64, maxAgeSeconds: 60 * 60 * 24 * 30 },
              cacheableResponse: { statuses: [200] },
            },
          },
        ],
      },
    }),
  ],
  server: {
    port: 5173,
    proxy: {
      // In development, proxy to the backend (uv run python main.py)
      '/api': { target: 'http://localhost:8000', changeOrigin: true },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: true,
  },
  test: {
    // jsdom: for tests that render React components
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./vitest.setup.ts'],
    include: ['src/**/*.{test,spec}.{ts,tsx}'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'lcov'],
      include: ['src/**/*.{ts,tsx}'],
      exclude: [
        'src/**/*.{test,spec}.{ts,tsx}',
        'src/test-support/**',
        'src/vite-env.d.ts',
        'src/main.tsx',
      ],
    },
  },
})
