/**
 * API client (fetch wrapper).
 *
 * - Keeps the JWT in localStorage and sends it in the Authorization header.
 * - On a 401, continue the login once and retry. Logins via password or passkey use the
 *   refresh token, display devices use the device credential (ADR-0047), and SSO logins (which have no
 *   refresh token) ask the IdP in a hidden frame and exchange the returned ticket for tokens
 *   (ADR-0058, `silentRenewal.ts`). If it cannot continue, emit "the login has ended".
 * - The backend returns error codes ({"error": "..."}). Converting them to display text is
 *   done by i18n (on the frontend).
 */
import { reportSessionEnded } from './sessionEnded'
import { oneAtATime, renewInFrame } from './silentRenewal'
import { clearSilentSsoMarks, markSilentSsoTried, signedOutHere } from './silentSso'

const ACCESS_KEY = 'access_token'
const REFRESH_KEY = 'refresh_token'
/**
 * Credential of a display device (signage) (ADR-0047). Received only once at pairing.
 *
 * ⚠ **Not removed on logout or session expiry** (outside `clearTokens`). It is removed only
 * when the server answers "removed / revoked". Removing it just because a request failed to arrive would
 * force the device to re-pair on every release (same idea as ADR-0046).
 */
const DISPLAY_CREDENTIAL_KEY = 'display_credential'

/**
 * Cache name where the Service Worker stores read-only GETs for offline viewing
 * (ADR-0015). Pairs with `runtimeCaching.cacheName` in `frontend/vite.config.ts`.
 * Responses contain personal point records, so it is deleted together with the tokens.
 */
const OFFLINE_VIEW_CACHE = 'offline-views'

export class ApiError extends Error {
  status: number
  code: string
  /** Names of fields that failed input validation (set only for `validation_error`). */
  fields: string[]

  constructor(status: number, code: string, fields: string[] = []) {
    super(code)
    this.status = status
    this.code = code
    this.fields = fields
  }
}

/** Code attached to input validation failures (pairs with `presentation/fastapi/error_handling.py`). */
const VALIDATION_ERROR_CODE = 'validation_error'

/**
 * Field names that have their own message.
 *
 * An input validation failure cannot be fixed unless it says "what is wrong", so look up
 * `error.invalid_<field>` from the field name. Only the names listed here are used so that keys missing
 * from the dictionary are never shown on screen as-is (unknown fields fall back to the generic
 * `validation_error` message). Names are spelled the same as the API field names.
 *
 * **Messages only say "which field" and never assert the cause.** Several schemas use the same field name,
 * each with different rules. `code` is used both for invitation codes (`InvitationRedeemRequest`)
 * and authenticator app codes (`TotpCodeRequest`, 6-10 characters), so
 * writing "Please enter the invitation code" would be wrong on the two-factor screen. `amount` also
 * fails two ways, at 0 and at the maximum. A cause can be stated only for fields whose rules agree across all schemas
 * (`email` format, `password` 8 characters).
 */
const NAMED_VALIDATION_FIELDS = new Set([
  'amount',
  'code',
  'display_name',
  'email',
  'name',
  'password',
  'reason',
  'username',
])

/**
 * Convert an exception into an i18n translation key.
 *
 * The backend returns only error codes, so the screen's handling always comes down to
 * "look up `error.<code>`". A single entry point so each page does not repeat the same branching.
 * Only for input validation failures, the failed field's message (`error.invalid_password` etc.) takes precedence.
 */
export function errorMessageKey(error: unknown): string {
  if (!(error instanceof ApiError)) return 'error.unknown_error'
  if (error.code === VALIDATION_ERROR_CODE) {
    const field = error.fields.find((name) => NAMED_VALIDATION_FIELDS.has(name))
    if (field !== undefined) return `error.invalid_${field}`
  }
  return `error.${error.code}`
}

/** Store the tokens. SSO logins have no refresh token (`null`, ADR-0058). */
export function setTokens(access: string, refresh: string | null): void {
  localStorage.setItem(ACCESS_KEY, access)
  if (refresh) localStorage.setItem(REFRESH_KEY, refresh)
  else localStorage.removeItem(REFRESH_KEY)
}

export function displayCredential(): string | null {
  return localStorage.getItem(DISPLAY_CREDENTIAL_KEY)
}

export function rememberDisplayCredential(credential: string): void {
  localStorage.setItem(DISPLAY_CREDENTIAL_KEY, credential)
}

export function forgetDisplayCredential(): void {
  localStorage.removeItem(DISPLAY_CREDENTIAL_KEY)
}

/** Result of opening a display device session. */
export type DisplaySessionOutcome = 'opened' | 'removed' | 'unreachable'

/**
 * Exchange the device credential for a 5-minute access token (ADR-0047).
 *
 * A 401 means "removed / revoked", so the credential is removed (re-pair from scratch).
 * Any other failure is treated as not arriving, and the credential is kept.
 */
export async function openDisplaySession(): Promise<DisplaySessionOutcome> {
  const credential = displayCredential()
  if (!credential) return 'removed'
  let response: Response
  try {
    response = await fetch('/api/display/session', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ device_credential: credential }),
    })
  } catch {
    return 'unreachable'
  }
  if (response.status === 401) {
    forgetDisplayCredential()
    clearTokens()
    return 'removed'
  }
  if (!response.ok) return 'unreachable'
  const session = (await response.json()) as { access_token: string }
  // There is no refresh token. When it expires, re-obtain with the credential
  localStorage.setItem(ACCESS_KEY, session.access_token)
  localStorage.removeItem(REFRESH_KEY)
  return 'opened'
}

/**
 * Clear the offline viewing cache (ADR-0015).
 *
 * The cache is keyed only by URL and ignores the Authorization header. It cannot tell
 * whose response it is, so it is cleared entirely at points where the user may change (logout, session expiry,
 * successful login).
 */
export async function clearOfflineViewCache(): Promise<void> {
  if (typeof caches !== 'undefined') await caches.delete(OFFLINE_VIEW_CACHE)
}

export function clearTokens(): void {
  localStorage.removeItem(ACCESS_KEY)
  localStorage.removeItem(REFRESH_KEY)
  // After logout or session expiry, keep another user of the same browser from seeing the previous user's
  // balance and history (ADR-0015).
  void clearOfflineViewCache()
}

export function hasTokens(): boolean {
  return localStorage.getItem(ACCESS_KEY) !== null
}

function detailOf(body: unknown): unknown {
  return body && typeof body === 'object' ? (body as Record<string, unknown>).detail : undefined
}

function extractErrorCode(body: unknown): string {
  const detail = detailOf(body)
  if (detail && typeof detail === 'object') {
    const code = (detail as Record<string, unknown>).error
    if (typeof code === 'string') return code
  }
  if (typeof detail === 'string') return detail
  return 'unknown_error'
}

/**
 * A rate-limit rejection (429) with no code in the body is treated as `too_many_attempts`.
 * The 429 the front nginx returns for its per-IP limit is HTML, and falling back to `unknown_error`
 * would not convey that "waiting a while will do" (task #733).
 */
function errorCodeOf(status: number, body: unknown): string {
  const code = extractErrorCode(body)
  return status === 429 && code === 'unknown_error' ? 'too_many_attempts' : code
}

/** Names of fields that failed input validation. The backend returns names only (no values). */
function extractErrorFields(body: unknown): string[] {
  const detail = detailOf(body)
  if (!detail || typeof detail !== 'object') return []
  const fields = (detail as Record<string, unknown>).fields
  return Array.isArray(fields)
    ? fields.filter((name): name is string => typeof name === 'string')
    : []
}

/** Response of ``/api/auth/refresh`` and ``/api/auth/sso/token``. */
interface TokenPair {
  access_token: string
  refresh_token: string | null
}

/** The continuation currently running. Requests that hit 401 at the same time wait on this one. */
let continuing: Promise<boolean> | null = null

function tryRefresh(): Promise<boolean> {
  continuing ??= continueSession().finally(() => {
    continuing = null
  })
  return continuing
}

async function continueSession(): Promise<boolean> {
  // Display devices have no refresh token. Re-obtain with the credential (ADR-0047)
  if (displayCredential()) return (await openDisplaySession()) === 'opened'
  const refresh = localStorage.getItem(REFRESH_KEY)
  if (refresh) return sendRefresh(refresh)
  // SSO login (ADR-0058). After sign-out, do not ask the IdP
  if (!hasTokens() || signedOutHere()) return false
  return oneAtATime(async () => {
    // Another tab may have continued it while we waited (localStorage is shared)
    if (await stillSignedIn()) return true
    const outcome = await renewInFrame()
    if (outcome.result === 'declined') markSilentSsoTried()
    if (outcome.result !== 'renewed') return false
    const exchanged = await exchangeRenewal(outcome.ticket)
    if (exchanged) clearSilentSsoMarks()
    return exchanged
  })
}

async function sendRefresh(refresh: string): Promise<boolean> {
  const response = await fetch('/api/auth/refresh', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh_token: refresh }),
  })
  if (!response.ok) {
    clearTokens()
    return false
  }
  const pair = (await response.json()) as TokenPair
  setTokens(pair.access_token, pair.refresh_token)
  return true
}

function authorization(): Record<string, string> {
  const access = localStorage.getItem(ACCESS_KEY)
  return access ? { Authorization: `Bearer ${access}` } : {}
}

async function stillSignedIn(): Promise<boolean> {
  const response = await fetch('/api/auth/me', { headers: authorization() })
  return response.ok
}

/**
 * Exchange the continuation round trip's ticket for tokens. The local (expired) token is attached, so
 * the server exchanges only for the same person (401 for someone else).
 */
async function exchangeRenewal(ticket: string): Promise<boolean> {
  const response = await fetch('/api/auth/sso/token', {
    method: 'POST',
    headers: { ...authorization(), 'Content-Type': 'application/json' },
    body: JSON.stringify({ ticket, continuing: true }),
  })
  if (!response.ok) return false
  const pair = (await response.json()) as TokenPair
  setTokens(pair.access_token, pair.refresh_token)
  return true
}

/**
 * Whether this is a 401 for an expired or missing login. Do not continue on entry-point 401s (wrong password, missing second factor etc.)
 * -- continuing would query the IdP just because a password was mistyped.
 */
const SESSION_ERRORS = new Set(['authentication_required', 'invalid_token'])

async function meansSessionExpired(response: Response): Promise<boolean> {
  try {
    return SESSION_ERRORS.has(extractErrorCode(await response.clone().json()))
  } catch {
    return false
  }
}

/** Whether the login could be continued after a 401. If not, emit "the login has ended". */
async function continuedAfter(response: Response): Promise<boolean> {
  if (!(await meansSessionExpired(response))) return false
  if (await tryRefresh()) return true
  reportSessionEnded()
  return false
}

async function requestResponse(
  method: string,
  path: string,
  body?: unknown,
  retry = true,
): Promise<Response> {
  const headers: Record<string, string> = {}
  const access = localStorage.getItem(ACCESS_KEY)
  if (access) headers['Authorization'] = `Bearer ${access}`
  if (body !== undefined) headers['Content-Type'] = 'application/json'

  const init: RequestInit = { method, headers }
  if (body !== undefined) init.body = JSON.stringify(body)

  const response = await fetch(path, init)

  if (response.status === 401 && retry && (await continuedAfter(response))) {
    return requestResponse(method, path, body, false)
  }
  if (!response.ok) {
    let payload: unknown = null
    try {
      payload = await response.json()
    } catch {
      /* non-JSON response */
    }
    throw new ApiError(
      response.status,
      errorCodeOf(response.status, payload),
      extractErrorFields(payload),
    )
  }
  return response
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const response = await requestResponse(method, path, body)
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

/** Response body and the time the response was created. */
export interface Fetched<T> {
  data: T
  /**
   * The response's ``Date`` header. Offline, the Service Worker returns the response along with
   * the headers saved at the time, so only this time can tell "how old the information is" (ADR-0015).
   * null for responses without a readable header.
   */
  fetchedAt: Date | null
}

function fetchedAtOf(response: Response): Date | null {
  const value = response.headers.get('date')
  if (!value) return null
  const parsed = new Date(value)
  return Number.isNaN(parsed.getTime()) ? null : parsed
}

async function requestFetched<T>(path: string): Promise<Fetched<T>> {
  const response = await requestResponse('GET', path)
  return { data: (await response.json()) as T, fetchedAt: fetchedAtOf(response) }
}

export const api = {
  get: <T>(path: string) => request<T>('GET', path),
  /** For screens that support offline viewing. Returns the data with the fetch time (Date header). */
  getFetched: <T>(path: string) => requestFetched<T>(path),
  post: <T>(path: string, body?: unknown) => request<T>('POST', path, body),
  put: <T>(path: string, body?: unknown) => request<T>('PUT', path, body),
  patch: <T>(path: string, body?: unknown) => request<T>('PATCH', path, body),
  delete: <T>(path: string) => request<T>('DELETE', path),
}
