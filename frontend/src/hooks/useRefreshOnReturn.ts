/**
 * Reloads when the screen comes back to the user.
 *
 * Points are recorded from several devices in the same family. A PWA opened from the home screen
 * keeps its tab alive for days, so if it keeps the balance from when it was opened, points
 * added by another parent never show up. Use the moment the user "comes back to look" as the
 * trigger to fetch.
 *
 * No reload while in the background (no traffic for an unseen screen).
 * Coming back from offline (`online`) is treated the same way: what was shown offline was the
 * cache (ADR-0015), so replace it with the latest once the connection is back.
 *
 * The caller decides what reloading means. Failure handling is also left to the caller, so
 * this fires and forgets without waiting (`refresh` must handle its own failures).
 */
import { useEffect } from 'react'

export function useRefreshOnReturn(refresh: () => Promise<void>): void {
  useEffect(() => {
    const refreshIfVisible = () => {
      if (document.visibilityState === 'visible') void refresh()
    }
    document.addEventListener('visibilitychange', refreshIfVisible)
    window.addEventListener('online', refreshIfVisible)
    return () => {
      document.removeEventListener('visibilitychange', refreshIfVisible)
      window.removeEventListener('online', refreshIfVisible)
    }
  }, [refresh])
}
