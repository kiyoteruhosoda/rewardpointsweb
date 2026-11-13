/**
 * Building and reading URLs that carry an invitation code.
 *
 * Handing over only the code means the recipient must separately be told "which screen to open
 * and where to type it", and typos happen. Handing over a URL to the join entry point with the code on it
 * starts them with the code already filled in.
 *
 * **The code travels in the fragment (`#code=...`), never in the query (`?code=`)** (ADR-0025).
 * Browsers do not send the fragment to the server, so it stays out of the reverse proxy's access log
 * and the request log. The code is a capability usable as-is while valid, and
 * keeping only its hash in the DB is pointless if plaintext is left somewhere along the way.
 *
 * The three receiving screens (`/join`, `/login`, `/families`) all read and write the code
 * through here. If one of them falls back to the query, plaintext lands in logs from there on.
 *
 * The destination of the URL depends on the invitation's role. Child invitations go to the account creation screen (`/join`),
 * parent invitations to the login screen (`/login`). ⚠ **Parents do not create a new account; they log in
 * and then join** (ADR-0048) -- creating a separate account here would give the same person two
 * accounts once they sign in via SSO. First-timers also get an account by logging in via SSO.
 *
 * The URL's host is the same entry point (`origin`) the issuing parent is currently viewing.
 * The `APP_BASE_URL` setting is the source for email bodies and is empty by default. Using it while empty would
 * hand out a URL that cannot be opened, so it is not referenced here.
 *
 * SSO goes through the IdP's screen, so the fragment is lost. **Do not make up for it with the query** --
 * once in `redirect_to`, the code reaches the server and is left in plaintext in the access log
 * and in `sso_login_sessions`. During the round trip it is kept in the same tab's
 * `sessionStorage` (`rememberInvitationCode` / `takeRememberedInvitationCode`).
 */

import type { FamilyRole } from './families'

/** Screen for creating an account and joining a family (can be opened unauthenticated). */
const JOIN_PATH = '/join'
/** Screen people who already have an account go through first. */
const SIGN_IN_PATH = '/login'
/** Screen for using the code after login (joining a family). */
const ACCEPT_PATH = '/families'

const CODE_KEY = 'code'

/** Where the code is kept during the round trip to the IdP (same tab only). */
const PENDING_KEY = 'pendingInvitationCode'

/** Put the code in the fragment. Omit it when empty (nothing at the destination would pick it up). */
function withCode(path: string, code: string): string {
  const trimmed = code.trim()
  if (!trimmed) return path
  return `${path}#${CODE_KEY}=${encodeURIComponent(trimmed)}`
}

/** First screen the invitee opens (creating an account). */
export function invitationJoinPath(code: string): string {
  return withCode(JOIN_PATH, code)
}

/** Destination for someone who already has an account and goes to login carrying the code. */
export function invitationSignInPath(code: string): string {
  return withCode(SIGN_IN_PATH, code)
}

/** Screen where a logged-in user uses the code. */
export function invitationAcceptPath(code: string): string {
  return withCode(ACCEPT_PATH, code)
}

/**
 * URL that can be handed to the recipient as-is.
 *
 * @param role Role of the invitation. Parents (owner, parent) get the login screen, children the account creation screen.
 * @param origin Origin of the issuing screen (`window.location.origin`). A trailing `/` is dropped.
 */
export function invitationUrl(code: string, role: FamilyRole, origin: string): string {
  const path =
    role === 'owner' || role === 'parent' ? invitationSignInPath(code) : invitationJoinPath(code)
  return `${origin.replace(/\/+$/, '')}${path}`
}

/**
 * Extract the code from the URL fragment.
 *
 * @param hash `useLocation().hash` (`#code=...` or empty).
 */
export function readInvitationCode(hash: string): string {
  return new URLSearchParams(hash.replace(/^#/, '')).get(CODE_KEY)?.trim() ?? ''
}

/**
 * Keep the code during the round trip to the IdP (within the same tab only).
 *
 * Browsers do not send the fragment to the IdP, so it is gone on return. `sessionStorage` is used
 * rather than `localStorage` because it should vanish when the tab closes (the code
 * is the capability itself). Browsers configured not to allow writes silently give up -- losing the code
 * only means retyping it on the join screen; the login itself proceeds.
 */
export function rememberInvitationCode(code: string): void {
  const trimmed = code.trim()
  try {
    if (trimmed) sessionStorage.setItem(PENDING_KEY, trimmed)
    else sessionStorage.removeItem(PENDING_KEY)
  } catch {
    // Browser configured not to allow storage (private mode etc.). Give up
  }
}

/** Take out the stored code (only once; it is removed when taken). */
export function takeRememberedInvitationCode(): string {
  try {
    const stored = sessionStorage.getItem(PENDING_KEY)
    sessionStorage.removeItem(PENDING_KEY)
    return stored?.trim() ?? ''
  } catch {
    return ''
  }
}
