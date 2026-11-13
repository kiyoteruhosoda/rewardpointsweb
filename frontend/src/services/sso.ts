/**
 * Login via an external IdP (OIDC).
 *
 * It starts with a browser navigation (fetch cannot show the IdP's login screen).
 * When returning from the IdP the token is not in the URL; instead a one-time
 * ticket is attached. `exchangeSsoTicket` exchanges it for tokens (ADR-0029).
 */
import { api } from './api'

export interface SsoProvider {
  enabled: boolean
  /** Name shown on the login button (the IdP's display name). */
  display_name: string
}

export interface SsoSession {
  access_token: string
  /** Not present for logins made via SSO (ADR-0058). */
  refresh_token: string | null
  /** Screen where SSO was started (an in-app path). */
  redirect_to: string
}

/** Ask whether SSO is configured (callable without authentication). */
export function fetchSsoProvider(): Promise<SsoProvider> {
  return api.get<SsoProvider>('/api/auth/sso/provider')
}

/**
 * Send the user to the IdP. The return destination is `redirectTo` (only in-app paths are valid).
 * With `silent`, add `prompt=none` (the attempt made when the login screen opens, ADR-0052).
 *
 * Use `replace`, not `assign`. Leaving the login screen in history would make "back"
 * after login return to the login screen.
 */
export function startSsoLogin(redirectTo: string, options: { silent?: boolean } = {}): void {
  const query = new URLSearchParams({ redirect_to: redirectTo })
  // Try without letting the IdP show a screen (ADR-0052, services/silentSso.ts)
  if (options.silent) query.set('prompt', 'none')
  window.location.replace(`/api/auth/sso/login?${query.toString()}`)
}

/** Exchange the ticket for tokens. */
export function exchangeSsoTicket(ticket: string): Promise<SsoSession> {
  return api.post<SsoSession>('/api/auth/sso/token', { ticket })
}
