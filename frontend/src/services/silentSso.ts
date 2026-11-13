/**
 * When the login screen opens, sign in without pressing the button if already signed in at the IdP (ADR-0052).
 *
 * Before rendering, send the user to the IdP with `prompt=none`. If signed in, a code comes back and the login follows
 * the same path as normal SSO; if not, the IdP returns without showing a screen (the server adds `?sso_silent=declined`
 * and returns to the login screen).
 *
 * When not to try (to prevent loops and unrequested re-logins):
 *
 * - **After signing out.** Sign-out does not end the IdP's SSO by default, so trying would immediately
 *   sign the user back in. The marker is in `localStorage` (no attempt in other tabs either)
 * - **After one attempt in this tab.** The marker is in `sessionStorage`
 * - When the login screen carries anything besides the destination (`redirect_to`)
 *   (an error, a sign-out notice, the attempted marker)
 *
 * However, **when the user reloads, try once more even with this tab's marker and the attempted marker (`sso_silent`)**
 * (for coming back after signing in to the IdP in another tab, ADR-0054). The navigation back after a decline is not a reload,
 * so it does not loop. The sign-out marker and error notices are honored even on reload.
 *
 * Both markers are **cleared on successful sign-in** through any entry point (so the next expiry tries again).
 *
 * ⚠ **Do not try in browsers that cannot write the markers.** Trying without them means that on return
 * there is no way to know an attempt was made, and the back-and-forth never stops.
 */
import { REDIRECT_TO_PARAM } from './returnTo'

const TRIED_KEY = 'ssoSilentTried'
const SIGNED_OUT_KEY = 'ssoSignedOut'
/** Marker for an attempt that was declined (added by the server). Only on reload may we try despite it. */
const SILENT_DECLINED_PARAM = 'sso_silent'

/** Whether this screen was opened by the user reloading. */
function openedByReload(): boolean {
  try {
    const [entry] = window.performance.getEntriesByType(
      'navigation',
    ) as PerformanceNavigationTiming[]
    return entry?.type === 'reload'
  } catch {
    return false
  }
}

/** Whether we may try, judging from this screen's URL query and the markers (does not set a marker). */
export function maySilentSso(params: URLSearchParams, reloaded = openedByReload()): boolean {
  for (const name of params.keys()) {
    if (name === REDIRECT_TO_PARAM || (reloaded && name === SILENT_DECLINED_PARAM)) continue
    return false
  }
  try {
    if (window.localStorage.getItem(SIGNED_OUT_KEY)) return false
    return reloaded || !window.sessionStorage.getItem(TRIED_KEY)
  } catch {
    return false
  }
}

/** Set the "tried in this tab" marker right before sending. false if it cannot be set (then do not try). */
export function markSilentSsoTried(): boolean {
  try {
    window.sessionStorage.setItem(TRIED_KEY, '1')
    return window.sessionStorage.getItem(TRIED_KEY) === '1'
  } catch {
    return false
  }
}

/** Whether the signed-out marker is set (no request to continue an expired login either, ADR-0058). true if unreadable. */
export function signedOutHere(): boolean {
  try {
    return window.localStorage.getItem(SIGNED_OUT_KEY) !== null
  } catch {
    return true
  }
}

/** Signed out. Do not try the next time the login screen opens. */
export function markSignedOut(): void {
  try {
    window.localStorage.setItem(SIGNED_OUT_KEY, '1')
  } catch {
    // Browsers that cannot write never try in the first place (markSilentSsoTried)
  }
}

/** Signed in. Clear the markers so the next expiry tries again. */
export function clearSilentSsoMarks(): void {
  try {
    window.localStorage.removeItem(SIGNED_OUT_KEY)
    window.sessionStorage.removeItem(TRIED_KEY)
  } catch {
    // Even if they cannot be cleared, the user is signed in
  }
}
