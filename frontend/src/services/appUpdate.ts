/**
 * Detecting that a new version has been delivered (Service Worker update, ADR-0045).
 *
 * A new Service Worker activates as soon as it is delivered (`skipWaiting` / `clientsClaim`).
 * Since it does not wait, **a reload always brings the new version**.
 *
 * However, the JavaScript of an open page is not replaced (an SPA only redraws the screen and
 * does not reload). So tell the screen that control moved to the new Service Worker (`controllerchange`)
 * and reload only when the user presses the button. Reloading silently would lose
 * whatever is being typed.
 *
 * ⚠ Just waiting will not notice it. Browsers check for Service Worker updates
 * **on page navigation**, and SPA screen changes are not page navigations. So we
 * trigger the check periodically and when the tab comes back to the foreground.
 */

/** Interval between update checks. */
export const UPDATE_CHECK_INTERVAL_MS = 30 * 60 * 1000

/**
 * Check interval for the display screen (`/display`). There is no interaction or tab switching, so the interval is all we have.
 * Kept short so it switches over within minutes of delivery (task #498; a check only fetches `sw.js`).
 */
export const DISPLAY_UPDATE_CHECK_INTERVAL_MS = 2 * 60 * 1000

/** Minimum gap between checks (repeated tab switching does not hit it often). */
const MIN_CHECK_GAP_MS = 60 * 1000

/** Service Worker written out by vite-plugin-pwa. */
const SERVICE_WORKER_URL = '/sw.js'

/** Switch to the new version (reload the current page). */
export type ApplyUpdate = () => void

/** Called when a new version becomes active. */
export type UpdateReadyListener = (apply: ApplyUpdate) => void

/** How to watch. */
export interface WatchOptions {
  /** Interval between update checks (defaults to `UPDATE_CHECK_INTERVAL_MS`). */
  checkIntervalMs?: number
}

/** Watch for a new version. */
export type WatchForUpdate = (onUpdateReady: UpdateReadyListener, options?: WatchOptions) => void

function scheduleChecks(registration: ServiceWorkerRegistration, intervalMs: number): void {
  let checkedAt = 0

  const check = (): void => {
    const now = Date.now()
    // Do not trigger while fetching, offline, or right after a check.
    if (registration.installing || !navigator.onLine || now - checkedAt < MIN_CHECK_GAP_MS) return
    checkedAt = now
    void registration.update().catch(() => {
      // Even if the check fails, show nothing on screen (retry at the next opportunity).
    })
  }

  setInterval(check, intervalMs)
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') check()
  })
}

export const watchForUpdate: WatchForUpdate = (onUpdateReady, options = {}) => {
  // No Service Worker on the dev server (same as the vite-plugin-pwa default)
  if (!import.meta.env.PROD || !('serviceWorker' in navigator)) return
  const workers = navigator.serviceWorker

  // A page opened for the first time also gets the signal when the registered Service Worker takes control.
  // That is not a new version, so only report the signal for pages that were already controlled
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
    .then((registration) => {
      scheduleChecks(registration, options.checkIntervalMs ?? UPDATE_CHECK_INTERVAL_MS)
    })
    .catch(() => {
      // The page works even if registration fails (just without offline viewing and version notices).
    })
}
