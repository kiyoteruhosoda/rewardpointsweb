import { createHash } from 'node:crypto'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'
import type { Plugin } from 'vite'
import { VitePWA } from 'vite-plugin-pwa'

// アイコンは `public/` に固定の名前で置く（scripts/generate_app_icons.py が書き出す）。
// 絵柄を差し替えても URL が同じままだと、ブラウザは手元のアイコンを使い続け、
// インストール済みの PWA は manifest が変わっていないと見なして古い絵を出し続ける。
// 中身から作った版を問い合わせに付け、絵柄が変われば URL も変わるようにする。
const PUBLIC_DIR = fileURLToPath(new URL('./public', import.meta.url))
const ICON_LINKS_IN_HTML = ['favicon.svg', 'apple-touch-icon.png'] as const

const iconUrl = (name: string): string => {
  const digest = createHash('sha256')
    .update(readFileSync(`${PUBLIC_DIR}/${name}`))
    .digest('hex')
  return `/${name}?v=${digest.slice(0, 8)}`
}

/** index.html のアイコン参照にも版を付ける（manifest 側は icons で付ける）。 */
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
      registerType: 'autoUpdate',
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
          // maskable は端まで塗り、図柄を内側 80%（セーフゾーン）に収めた別画像を渡す。
          // 角丸のアイコンをそのまま maskable にすると、ランチャー側の切り抜きで
          // 角が削れて縁が欠ける。
          {
            src: iconUrl('pwa-maskable-512x512.png'),
            sizes: '512x512',
            type: 'image/png',
            purpose: 'maskable',
          },
        ],
      },
      workbox: {
        // SPA のシェル（ビルド成果物）だけを precache する。API・自動生成ドキュメント・
        // 運用エンドポイントはナビゲーションフォールバックの対象外にし、SW が
        // index.html を返して JSON 応答を壊さないようにする。
        globPatterns: ['**/*.{js,css,html,svg,png,ico,json}'],
        // アイコンは precache しない。参照はすべて版付き URL（`?v=` 付き）になり
        // precache の登録名とは一致しないため、置いても使われないまま SW の更新の
        // たびに 110KB を落とすだけになる。圏外で取れなくても、ブラウザとランチャーは
        // インストール時のアイコンを使うので画面には影響しない。
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
        // 閲覧系の GET だけオフライン閲覧用にキャッシュする（ADR-0015）。
        // network-first なのでオンラインの表示は常に最新で、キャッシュが出るのは
        // オフラインのときだけ。画面は応答の Date ヘッダーで取得時刻を示す。
        // 書き込み・招待・管理系はキャッシュしない（オフラインでは従来通り失敗）。
        // キャッシュ名は frontend/src/services/api.ts の OFFLINE_VIEW_CACHE と対
        // （ログアウト時にそちらから削除する）。
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
      // 開発時はバックエンド（uv run python main.py）へプロキシする
      '/api': { target: 'http://localhost:8000', changeOrigin: true },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: true,
  },
  test: {
    // jsdom: React コンポーネントの描画を伴うテスト用
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
