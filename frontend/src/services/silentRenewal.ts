/**
 * Continue an expired login without showing a screen (ADR-0058).
 *
 * Logins made via SSO have no refresh token. When the access token (5 minutes) expires,
 * open `/api/auth/sso/renew` in a hidden frame (iframe) and ask the IdP with `prompt=none`.
 * If the IdP login is still alive, the return (`/api/auth/sso/callback`) attaches a one-time ticket and
 * sends it to the result page (`/api/auth/sso/renewed?result=renewed&ticket=…`). The screen reads the frame's location (same origin)
 * and exchanges the ticket for tokens (`api.ts`; this app keeps tokens in localStorage).
 *
 * - No script runs inside the frame (no `postMessage`). The result is passed only via the URL
 * - The frame stopping on the IdP's screen (loading finished on an unreadable origin) or timing out is `failed`
 * - **One at a time across tabs** (Web Locks). There is a single passphrase cookie, so running them concurrently
 *   lets the later round trip overwrite the earlier one's cookie, and the earlier one always fails
 */

/** Result page (pairs with the server's `bounded_contexts/identity_federation/presentation/renewal.py`). */
export const RENEWAL_RESULT_PATH = '/api/auth/sso/renewed'
const START_PATH = '/api/auth/sso/renew'
const LOCK_NAME = 'sso-renewal'
/** How long to wait for the IdP round trip. After this, give up and send the user to the login screen. */
export const RENEWAL_TIMEOUT_MS = 15_000

export type RenewalResult = 'renewed' | 'declined' | 'failed'

/** Result from the frame. A ticket is attached only when the login could be continued. */
export type RenewalOutcome =
  { result: 'renewed'; ticket: string } | { result: 'declined' | 'failed'; ticket?: undefined }

const FAILED: RenewalOutcome = { result: 'failed' }

/** Read the result from the frame's current location. null while still in progress (`about:blank`). */
function resultOf(frame: HTMLIFrameElement): RenewalOutcome | null {
  let location: Location | undefined
  try {
    location = frame.contentWindow?.location
    if (!location || location.href === 'about:blank') return null
    if (location.pathname !== RENEWAL_RESULT_PATH) return FAILED
  } catch {
    // Stopped on an unreadable origin (the IdP's screen). With prompt=none no screen should appear
    return FAILED
  }
  const query = new URLSearchParams(location.search)
  const value = query.get('result')
  const ticket = query.get('ticket')
  if (value === 'renewed' && ticket) return { result: 'renewed', ticket }
  return value === 'declined' ? { result: 'declined' } : FAILED
}

/** Ask once in a hidden frame. */
export function renewInFrame(timeoutMs = RENEWAL_TIMEOUT_MS): Promise<RenewalOutcome> {
  return new Promise((resolve) => {
    const frame = document.createElement('iframe')
    frame.hidden = true
    frame.tabIndex = -1
    frame.setAttribute('aria-hidden', 'true')
    let settled = false
    const finish = (result: RenewalOutcome) => {
      if (settled) return
      settled = true
      window.clearTimeout(timer)
      frame.remove()
      resolve(result)
    }
    const timer = window.setTimeout(() => {
      finish(FAILED)
    }, timeoutMs)
    frame.addEventListener('load', () => {
      const result = resultOf(frame)
      if (result) finish(result)
    })
    frame.src = START_PATH
    document.body.appendChild(frame)
  })
}

/** Run one at a time across tabs. Browsers without Web Locks (old ones, http in development) just run it. */
export async function oneAtATime<T>(task: () => Promise<T>): Promise<T> {
  const locks = (navigator as Partial<Pick<Navigator, 'locks'>>).locks
  if (!locks) return task()
  return locks.request(LOCK_NAME, task)
}
