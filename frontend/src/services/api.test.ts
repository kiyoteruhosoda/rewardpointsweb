/** API client token storage and error code conversion. */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import en from '../i18n/en.json'
import ja from '../i18n/ja.json'
import {
  api,
  ApiError,
  clearOfflineViewCache,
  clearTokens,
  errorMessageKey,
  hasTokens,
  setTokens,
} from './api'
import { subscribeSessionEnded } from './sessionEnded'

const { renewInFrame } = vi.hoisted(() => ({ renewInFrame: vi.fn() }))
vi.mock('./silentRenewal', () => ({
  renewInFrame,
  oneAtATime: <T>(task: () => Promise<T>) => task(),
}))

describe('errorMessageKey', () => {
  it('converts ApiError codes to i18n keys', () => {
    expect(errorMessageKey(new ApiError(401, 'invalid_token'))).toBe('error.invalid_token')
  })

  it('rounds non-API exceptions to unknown_error', () => {
    expect(errorMessageKey(new Error('boom'))).toBe('error.unknown_error')
  })

  it('does not crash on non-exception values', () => {
    expect(errorMessageKey(undefined)).toBe('error.unknown_error')
    expect(errorMessageKey('invalid_token')).toBe('error.unknown_error')
  })

  it('points validation failures at the message for the failed field', () => {
    expect(errorMessageKey(new ApiError(422, 'validation_error', ['password']))).toBe(
      'error.invalid_password',
    )
  })

  it('falls back to a generic message for fields without one (never shows the key)', () => {
    expect(errorMessageKey(new ApiError(422, 'validation_error', ['idempotency_key']))).toBe(
      'error.validation_error',
    )
  })

  it('uses the generic message for validation failures without a field name', () => {
    expect(errorMessageKey(new ApiError(422, 'validation_error'))).toBe('error.validation_error')
  })
})

describe('validation messages', () => {
  /**
   * Every key `errorMessageKey` can return must exist in the dictionaries. Otherwise `t` returns
   * the key as is and the screen shows the string `error.invalid_email`.
   *
   * Multiple schemas share field names, so a message must not assert the cause
   * (`code` is used both for invitation codes and authenticator app codes). Only fields whose
   * rules match across all schemas may be asserted. See the note in `api.ts`.
   */
  const KEYS = [
    'amount',
    'code',
    'display_name',
    'email',
    'name',
    'password',
    'reason',
    'username',
  ].map((field) => `error.invalid_${field}`)

  // Keys contain `.`, so pass them as an array (a string would be read as a nested path).
  it.each([...KEYS, 'error.validation_error'])('%s exists in both en and ja', (key) => {
    expect(en).toHaveProperty([key])
    expect(ja).toHaveProperty([key])
  })
})

describe('token storage', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('holds nothing before saving', () => {
    expect(hasTokens()).toBe(false)
  })

  it('is held after saving', () => {
    setTokens('access', 'refresh')
    expect(hasTokens()).toBe(true)
  })

  it('returns to not held after clearing', () => {
    setTokens('access', 'refresh')
    clearTokens()
    expect(hasTokens()).toBe(false)
  })

  it('clears the offline view cache along with the tokens (ADR-0015)', () => {
    const deleteCache = vi.fn<(name: string) => Promise<boolean>>().mockResolvedValue(true)
    vi.stubGlobal('caches', { delete: deleteCache })
    try {
      clearTokens()
      expect(deleteCache).toHaveBeenCalledWith('offline-views')
    } finally {
      vi.unstubAllGlobals()
    }
  })

  it('can clear the cache alone so login success can use it (ADR-0015)', async () => {
    // The cache is keyed only by URL and cannot tell whose response it is, so it is wiped
    // even when re-entering as another account without logging out (login in AuthContext).
    const deleteCache = vi.fn<(name: string) => Promise<boolean>>().mockResolvedValue(true)
    vi.stubGlobal('caches', { delete: deleteCache })
    try {
      await clearOfflineViewCache()
      expect(deleteCache).toHaveBeenCalledWith('offline-views')
    } finally {
      vi.unstubAllGlobals()
    }
  })
})

describe('GET with fetch time (for offline viewing, ADR-0015)', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  function stubFetch(headers: Record<string, string>): void {
    vi.stubGlobal(
      'fetch',
      vi.fn(() =>
        Promise.resolve(new Response(JSON.stringify({ balance: 100 }), { status: 200, headers })),
      ),
    )
  }

  it('returns the Date header as the fetch time', async () => {
    stubFetch({ Date: 'Sat, 01 Aug 2026 10:00:00 GMT' })

    const result = await api.getFetched<{ balance: number }>('/api/families/1/ledgers/2')

    expect(result.data).toEqual({ balance: 100 })
    expect(result.fetchedAt).toEqual(new Date('2026-08-01T10:00:00Z'))
  })

  it('fetch time is null without a Date header', async () => {
    stubFetch({})

    const result = await api.getFetched<{ balance: number }>('/api/families/1/ledgers/2')

    expect(result.data).toEqual({ balance: 100 })
    expect(result.fetchedAt).toBeNull()
  })
})

/**
 * Continue the session once after a 401 (ADR-0058). Password and passkey logins use refresh;
 * SSO logins (no refresh) query the IdP in a hidden frame and exchange the ticket for tokens.
 */
describe('continuing the session', () => {
  const expired = { detail: { error: 'invalid_token', reason: 'token_expired' } }

  function json(status: number, body: unknown = {}): Response {
    return new Response(JSON.stringify(body), {
      status,
      headers: { 'Content-Type': 'application/json' },
    })
  }

  beforeEach(() => {
    renewInFrame.mockReset()
    localStorage.clear()
    sessionStorage.clear()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    localStorage.clear()
  })

  it('SSO tokens have no refresh', () => {
    setTokens('a', 'r')
    setTokens('a2', null)
    expect(localStorage.getItem('refresh_token')).toBeNull()
    expect(localStorage.getItem('access_token')).toBe('a2')
  })

  it('does not open a frame when refresh exists (password login)', async () => {
    setTokens('old', 'r')
    vi.stubGlobal(
      'fetch',
      vi.fn((path: string) => {
        if (path === '/api/auth/refresh')
          return Promise.resolve(json(200, { access_token: 'new', refresh_token: 'r2' }))
        return Promise.resolve(
          localStorage.getItem('access_token') === 'new'
            ? json(200, { ok: 1 })
            : json(401, expired),
        )
      }),
    )

    await expect(api.get('/api/families')).resolves.toEqual({ ok: 1 })
    expect(renewInFrame).not.toHaveBeenCalled()
  })

  it('without refresh, asks the IdP in a hidden frame and swaps the ticket using the token', async () => {
    setTokens('old', null)
    renewInFrame.mockResolvedValue({ result: 'renewed', ticket: 't1' })
    const fetchMock = vi.fn((path: string, init?: RequestInit) => {
      if (path === '/api/auth/sso/token') {
        expect(JSON.parse(init?.body as string)).toEqual({ ticket: 't1', continuing: true })
        expect((init?.headers as Record<string, string>).Authorization).toBe('Bearer old')
        return Promise.resolve(json(200, { access_token: 'new', refresh_token: null }))
      }
      return Promise.resolve(
        localStorage.getItem('access_token') === 'new' ? json(200, { ok: 1 }) : json(401, expired),
      )
    })
    vi.stubGlobal('fetch', fetchMock)

    await expect(api.get('/api/families')).resolves.toEqual({ ok: 1 })
    expect(renewInFrame).toHaveBeenCalledTimes(1)
    expect(localStorage.getItem('refresh_token')).toBeNull()
  })

  it('when the IdP refuses, announces the session ended and throws', async () => {
    setTokens('old', null)
    renewInFrame.mockResolvedValue({ result: 'declined' })
    vi.stubGlobal(
      'fetch',
      vi.fn(() => Promise.resolve(json(401, expired))),
    )
    const ended = vi.fn()
    const stop = subscribeSessionEnded(ended)

    await expect(api.get('/api/families')).rejects.toMatchObject({ status: 401 })
    expect(ended).toHaveBeenCalledTimes(1)
    // This tab no longer tries on the login screen
    expect(sessionStorage.getItem('ssoSilentTried')).toBe('1')
    stop()
  })

  it('does not continue when someone else came back (ticket exchange gives 401)', async () => {
    setTokens('old', null)
    renewInFrame.mockResolvedValue({ result: 'renewed', ticket: 't1' })
    vi.stubGlobal(
      'fetch',
      vi.fn((path: string) =>
        Promise.resolve(
          path === '/api/auth/sso/token'
            ? json(401, { detail: { error: 'sso_renewal_switched_user' } })
            : json(401, expired),
        ),
      ),
    )

    await expect(api.get('/api/families')).rejects.toMatchObject({ status: 401 })
    expect(localStorage.getItem('access_token')).toBe('old')
  })

  it('does not query the IdP after signing out', async () => {
    setTokens('old', null)
    localStorage.setItem('ssoSignedOut', '1')
    vi.stubGlobal(
      'fetch',
      vi.fn(() => Promise.resolve(json(401, expired))),
    )

    await expect(api.get('/api/families')).rejects.toMatchObject({ status: 401 })
    expect(renewInFrame).not.toHaveBeenCalled()
  })

  it('does not continue on the entry 401 (wrong password)', async () => {
    const fetchMock = vi.fn(() =>
      Promise.resolve(json(401, { detail: { error: 'invalid_credentials' } })),
    )
    vi.stubGlobal('fetch', fetchMock)

    await expect(api.post('/api/auth/login', {})).rejects.toMatchObject({
      code: 'invalid_credentials',
    })
    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(renewInFrame).not.toHaveBeenCalled()
  })
})
