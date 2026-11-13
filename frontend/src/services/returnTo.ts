/**
 * Keep the destination across the sign-in round trip (ADR-0051).
 *
 * Opening a deep link (`/families/<id>/ledgers/<id>`, `/admin/logs?…` etc.) while signed out
 * sends the user to the login screen. Sending them without the destination lands them on `/` after sign-in,
 * and **they can never get back to the screen they were opening**. The query is carried along as part of the destination, not just the path.
 *
 * ⚠ **Never return to an external URL.** The authoritative check is server-side (`RedirectTarget.parse`);
 * this only narrows to the same shape before passing it on.
 */

/** Query name used by the login screen and the SSO entry point (same spelling on both sides). */
export const REDIRECT_TO_PARAM = 'redirect_to'

/** Fallback when there is no destination (or it points outside). */
const LANDING = '/'

/**
 * Maximum length the server accepts (`redirect_to` of `/api/auth/sso/login` and the round-trip record column).
 * A longer value would make the entry point stop with 422, so fall back to the landing page.
 */
const MAX_LENGTH = 255

/** Allow only absolute paths within this site. ⚠ Same rule as the server. Never loosen only one side. */
export function sanitizeRedirectTo(candidate: string | null | undefined): string {
  if (!candidate) return LANDING
  if (!candidate.startsWith('/')) return LANDING
  // `//evil.example` is a protocol-relative URL. Browsers resolve it as external.
  if (candidate.startsWith('//')) return LANDING
  // Some browsers resolve `/\evil.example` as external.
  if (candidate.startsWith('/\\')) return LANDING
  if (candidate.includes('\r') || candidate.includes('\n')) return LANDING
  if (candidate.length > MAX_LENGTH) return LANDING
  return candidate
}

/**
 * Login screen URL to send a signed-out user to.
 *
 * Coming from the landing page (`/`), no destination is attached (going to the landing page after sign-in is the default).
 */
export function signInPathFor(location: { pathname: string; search?: string }): string {
  const here = sanitizeRedirectTo(`${location.pathname}${location.search ?? ''}`)
  if (here === LANDING) return '/login'
  return `/login?${REDIRECT_TO_PARAM}=${encodeURIComponent(here)}`
}
