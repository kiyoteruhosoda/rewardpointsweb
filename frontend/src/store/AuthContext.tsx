/** Authentication state (signed-in user and scopes). Authorization is checked with hasScope. */
import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react'

import { clearSessionDrafts } from '../hooks/useSessionDraft'
import {
  ApiError,
  api,
  clearOfflineViewCache,
  clearTokens,
  hasTokens,
  setTokens,
} from '../services/api'
import { subscribeSessionEnded } from '../services/sessionEnded'
import { exchangeSsoTicket } from '../services/sso'
import { clearSilentSsoMarks, markSignedOut } from '../services/silentSso'
import { assertPasskey, type PasskeyChallenge } from '../services/webauthn'

export interface Me {
  user_id: number
  /** Login identifier. Email is optional (ADR-0011). */
  username: string
  display_name: string
  email: string | null
  scopes: string[]
  /** Signed in with a temporary password. No other action passes until it is changed. */
  must_change_password: boolean
  /**
   * Whether the user has a password as a way in (ADR-0034).
   * false = a user who can only enter via SSO. The screen offers no password change.
   */
  has_password: boolean
  /** Whether this is a display device (signage) session (ADR-0047). If true, only the display. */
  display_device: boolean
}

interface TokenPair {
  access_token: string
  /** Not present for logins via SSO (ADR-0058). */
  refresh_token: string | null
}

export interface AuthValue {
  user: Me | null
  loading: boolean
  /**
   * The server is unreachable (5xx, network failure), e.g. while a new version is rolling out.
   * ⚠ **Do not set user to null here, and do not clear tokens (or the offline view cache)** —
   * this is not a logout, and sending them to the login screen would strand them on a screen
   * without the IdP entry once the server is back. Retry automatically until connected.
   */
  unreachable: boolean
  /** totpCode is required for accounts with two-factor auth (totp_required if omitted). */
  login: (username: string, password: string, totpCode?: string) => Promise<void>
  loginWithPasskey: () => Promise<void>
  /** Sign in with the exchange ticket attached on return from the IdP. Returns the return path. */
  loginWithSsoTicket: (ticket: string) => Promise<string>
  logout: () => void
  refreshMe: () => Promise<void>
  hasScope: (...codes: string[]) => boolean
}

/** Exported so tests can render with replaced scopes (production builds it in AuthProvider). */
export const AuthContext = createContext<AuthValue | null>(null)

const SERVER_ERROR = 500
/** Retry interval while the server is unreachable */
export const RECONNECT_INTERVAL_MS = 5000

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<Me | null>(null)
  const [loading, setLoading] = useState(true)
  const [unreachable, setUnreachable] = useState(false)

  const refreshMe = useCallback(async () => {
    if (!hasTokens()) {
      setUser(null)
      return
    }
    try {
      setUser(await api.get<Me>('/api/auth/me'))
      setUnreachable(false)
    } catch (e) {
      // 4xx (401 etc.) means the server answered "not signed in". Anything else did not get through
      if (e instanceof ApiError && e.status < SERVER_ERROR) {
        clearTokens()
        setUser(null)
        setUnreachable(false)
      } else {
        setUnreachable(true)
      }
    }
  }, [])

  // Could not continue the session (ADR-0058). Moves to login (destination and drafts are kept)
  useEffect(
    () =>
      subscribeSessionEnded(() => {
        setUser(null)
      }),
    [],
  )

  useEffect(() => {
    if (!unreachable) return
    const timer = window.setInterval(() => {
      void refreshMe()
    }, RECONNECT_INTERVAL_MS)
    return () => {
      window.clearInterval(timer)
    }
  }, [unreachable, refreshMe])

  useEffect(() => {
    void refreshMe().finally(() => {
      setLoading(false)
    })
  }, [refreshMe])

  const login = async (username: string, password: string, totpCode?: string) => {
    const pair = await api.post<TokenPair>('/api/auth/login', {
      username,
      password,
      totp_code: totpCode || null,
    })
    // Even when re-entering with another account without logging out, do not carry over the
    // previous user's offline view cache (ADR-0015)
    await clearOfflineViewCache()
    setTokens(pair.access_token, pair.refresh_token)
    clearSilentSsoMarks()
    await refreshMe()
  }

  const loginWithPasskey = async () => {
    const challenge = await api.post<PasskeyChallenge>('/api/auth/passkey/challenge')
    const credential = await assertPasskey(challenge.public_key)
    const pair = await api.post<TokenPair>('/api/auth/passkey/login', {
      challenge_id: challenge.challenge_id,
      credential,
    })
    // As with login, clear it in case of re-entry with another account (ADR-0015)
    await clearOfflineViewCache()
    setTokens(pair.access_token, pair.refresh_token)
    clearSilentSsoMarks()
    await refreshMe()
  }

  const loginWithSsoTicket = async (ticket: string) => {
    const session = await exchangeSsoTicket(ticket)
    // As with login, clear it in case of re-entry with another account (ADR-0015)
    await clearOfflineViewCache()
    setTokens(session.access_token, session.refresh_token)
    clearSilentSsoMarks()
    await refreshMe()
    return session.redirect_to
  }

  const logout = () => {
    void api.post('/api/auth/logout').catch(() => undefined)
    clearTokens()
    setUser(null)
    // The IdP SSO session persists, so opening login must not re-enter without a tap (ADR-0052)
    markSignedOut()
    clearSessionDrafts()
  }

  const hasScope = (...codes: string[]) =>
    user !== null && codes.every((code) => user.scopes.includes(code))

  return (
    <AuthContext.Provider
      value={{
        user,
        loading,
        unreachable,
        login,
        loginWithPasskey,
        loginWithSsoTicket,
        logout,
        refreshMe,
        hasScope,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth(): AuthValue {
  const value = useContext(AuthContext)
  if (!value) throw new Error('useAuth must be used within AuthProvider')
  return value
}
