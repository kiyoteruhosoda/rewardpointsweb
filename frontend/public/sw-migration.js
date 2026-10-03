/*
 * 「黙って入れ替える」作りから「知らせて押したら入れ替える」作りへ移る、一度きりの処理（ADR-0044）。
 *
 * 前の Service Worker（autoUpdate）に制御されている画面は、待機した新しい Service Worker を
 * 入れ替える手段を持たない（入れ替えの合図を送るのは新しい作りの画面だけ）。何もしないと、
 * 新しい版は端末のアプリを完全に閉じるまで待機したままになり、画面は古いまま止まる。
 *
 * そこで「知らせる作りの Service Worker が一度でも有効になったか」を印（Cache Storage の
 * 名前）で覚え、印が無いとき——前の作りから移るとき——だけ待たずに有効になる。前の作りの
 * 画面は有効化を受けて自分で再読み込みする。印が付いた後の更新は待機し、画面が知らせを出す。
 *
 * workbox の `importScripts` で sw.js の先頭に読み込む。
 */
const PROMPT_MODE_MARKER = 'rewardpoints-update-prompt-v1'

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.has(PROMPT_MODE_MARKER).then((promptModeWasActive) => {
      if (!promptModeWasActive) return self.skipWaiting()
      return undefined
    }),
  )
})

self.addEventListener('activate', (event) => {
  event.waitUntil(caches.open(PROMPT_MODE_MARKER))
})
