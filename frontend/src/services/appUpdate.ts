/**
 * 新しい版が配られたことの検出（Service Worker の更新。ADR-0045）。
 *
 * 新しい Service Worker は配られたらすぐ有効になる（`skipWaiting` / `clientsClaim`）。
 * 待機させないので、**リロードすれば必ず新しい版になる**。
 *
 * ただし、開いている画面の JavaScript は差し替わらない（SPA は画面を描き替えるだけで
 * 読み込み直さない）。そこで制御が新しい Service Worker へ移った（`controllerchange`）
 * ことを画面へ伝え、再読み込みは利用者が押したときに行う。黙って再読み込みすると、
 * 打っている途中の内容が消える。
 *
 * ⚠ 待つだけでは気付けない。ブラウザが Service Worker の更新を確認するのは
 * **ページ遷移のとき**で、SPA の画面切り替えはページ遷移ではない。ここで
 * 定期的に・タブが手前へ戻ったときに確認を起こす。
 */

/** 更新を確認する間隔。 */
export const UPDATE_CHECK_INTERVAL_MS = 30 * 60 * 1000

/** 確認どうしの最短間隔（タブの出入りを繰り返しても頻繁には叩かない）。 */
const MIN_CHECK_GAP_MS = 60 * 1000

/** vite-plugin-pwa が書き出す Service Worker。 */
const SERVICE_WORKER_URL = '/sw.js'

/** 新しい版へ入れ替える（現在の画面を再読み込みする）。 */
export type ApplyUpdate = () => void

/** 新しい版が有効になったときに呼ばれる。 */
export type UpdateReadyListener = (apply: ApplyUpdate) => void

/** 新しい版を見張る。 */
export type WatchForUpdate = (onUpdateReady: UpdateReadyListener) => void

function scheduleChecks(registration: ServiceWorkerRegistration): void {
  let checkedAt = 0

  const check = (): void => {
    const now = Date.now()
    // 取得中・オフライン・直前に確認済みのときは起こさない。
    if (registration.installing || !navigator.onLine || now - checkedAt < MIN_CHECK_GAP_MS) return
    checkedAt = now
    void registration.update().catch(() => {
      // 確認できなくても画面には出さない（次の機会に取り直す）。
    })
  }

  setInterval(check, UPDATE_CHECK_INTERVAL_MS)
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') check()
  })
}

export const watchForUpdate: WatchForUpdate = (onUpdateReady) => {
  // 開発サーバーでは Service Worker を作らない（vite-plugin-pwa の既定と同じ）
  if (!import.meta.env.PROD || !('serviceWorker' in navigator)) return
  const workers = navigator.serviceWorker

  // 初めて開いた画面は、登録した Service Worker に制御されるときにも合図が来る。
  // それは新しい版ではないので、すでに制御されていた画面の合図だけを知らせる
  let controlled = workers.controller !== null
  workers.addEventListener('controllerchange', () => {
    if (controlled) {
      onUpdateReady(() => {
        window.location.reload()
      })
    }
    controlled = true
  })

  workers
    .register(SERVICE_WORKER_URL, { scope: '/' })
    .then(scheduleChecks)
    .catch(() => {
      // 登録できなくても画面は動く（オフライン閲覧と版の知らせが無いだけ）。
    })
}
