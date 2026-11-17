# ADR-0063: npm の弱点の検査で止めるのは、利用者のブラウザに届く部品だけにする

- 日付: 2026-11-17
- 状態: 承認

## 文脈

2026-11-17、picomatch（ファイル名のパターン判定）に high の弱点が公表され（GHSA-fc5q-39xc-vjpf）、最新版まで全部が対象で
直した版が無かった。picomatch は vite・vitest など（ビルドと試験の道具）の中だけで使われ、画面のファイルには入らない。
それでも `npm audit --audit-level=high`（deploy-repo ADR-0002）が main を赤くし、配布が止まる。
持ち主の判断で eikaiwa が先に分け（eikaiwa ADR-0120）、全リポジトリで揃える（task #1097）。

## 決定

deploy-repo の ADR-0002 の npm の行を置き換える ADR（task #1097）に従う。

1. `security-audit.yml` の npm は 2 段にする。**止める段**は `npm audit --audit-level=high --omit=dev`（ブラウザに届く部品）。
   **知らせる段**は全部の部品を調べ、high 以上があれば注意（warning）を出すが、検査は緑のまま。
2. ブラウザに届くのに `devDependencies` の道具（vite-plugin-pwa）の奥から入る部品は、`dependencies` に書いて止める段に入れる。いまは workbox の次の部品:
   - `workbox-core`: Service Worker
   - `workbox-precaching`: Service Worker（画面のファイルの先読み）
   - `workbox-routing`: Service Worker（`navigateFallback`）
   - `workbox-strategies`: Service Worker（API の `NetworkFirst`）
   - `workbox-expiration`: Service Worker（一時保存の期限）
   - `workbox-cacheable-response`: Service Worker（保存する応答の選別）

## 影響

- 画面の中で新しい部品を使うとき、`devDependencies` の道具経由で届くものなら `dependencies` にも書く。
- 届く部品の弱点は今までどおり high 以上で main が赤になり、直すまで配らない。
