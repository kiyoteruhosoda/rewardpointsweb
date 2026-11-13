/**
 * Login screen: the flow for people arriving with an invitation code, and SSO gating.
 *
 * People sent here from the account creation screen must be carried to the
 * "join with a code" field once login finishes. Dropping them at the default destination
 * (dashboard) brings back the state where they hold a code but cannot find the entry.
 *
 * The SSO button is shown only when the server answers "available". Failure reasons
 * come back via navigation, so they are in the URL (ADR-0029).
 */
import { fireEvent, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { Route } from 'react-router-dom'

import { renderWithProviders } from '../test-support/renderWithProviders'
import type { SsoProvider } from '../services/sso'
import { LoginPage } from './LoginPage'

const fetchSsoProvider = vi.fn<() => Promise<SsoProvider>>()
const startSsoLogin = vi.fn<(redirectTo: string, options?: { silent?: boolean }) => void>()

vi.mock('../services/sso', () => ({
  fetchSsoProvider: () => fetchSsoProvider(),
  startSsoLogin: (redirectTo: string, options?: { silent?: boolean }) => {
    if (options) startSsoLogin(redirectTo, options)
    else startSsoLogin(redirectTo)
  },
}))

function renderLogin(route: string) {
  return renderWithProviders(<LoginPage />, {
    route,
    path: '/login',
    extraRoutes: (
      <>
        <Route path="/families" element={<p>families page</p>} />
        <Route path="/admin/logs" element={<p>logs page</p>} />
        <Route path="/" element={<p>dashboard</p>} />
      </>
    ),
  })
}

function signIn() {
  fireEvent.change(screen.getByLabelText('Username'), { target: { value: 'mom' } })
  fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'password123' } })
  fireEvent.click(screen.getByRole('button', { name: 'Sign in' }))
}

describe('LoginPage', () => {
  beforeEach(() => {
    fetchSsoProvider.mockReset()
    startSsoLogin.mockReset()
    sessionStorage.clear()
    localStorage.clear()
    // Tests of entry gating. Treat the no-tap sign-in attempt (ADR-0052) as already done
    sessionStorage.setItem('ssoSilentTried', '1')
    // Default is "SSO unavailable". Tests that need it replace this
    fetchSsoProvider.mockResolvedValue({ enabled: false, display_name: '' })
  })

  it('tells people with an invitation code why they must sign in first', () => {
    renderLogin('/login#code=CODE1234')

    expect(
      screen.getByText(
        'Sign in first. Right after that you can join your family with the invitation code you entered.',
      ),
    ).toBeInTheDocument()
  })

  it('sends them to the family screen with the code after login', async () => {
    renderLogin('/login#code=CODE1234')
    signIn()

    expect(await screen.findByText('families page')).toBeInTheDocument()
  })

  it('without a code, sends them to the first screen as before', async () => {
    renderLogin('/login')
    signIn()

    expect(await screen.findByText('dashboard')).toBeInTheDocument()
    expect(screen.queryByText(/Sign in first/)).not.toBeInTheDocument()
  })

  it('returns to the screen being opened (redirect_to), query included (ADR-0051)', async () => {
    renderLogin('/login?redirect_to=%2Fadmin%2Flogs%3Flevel%3DERROR')
    signIn()

    expect(await screen.findByText('logs page')).toBeInTheDocument()
  })

  it('with an invitation code, prefers the family screen over redirect_to', async () => {
    renderLogin('/login?redirect_to=%2Fadmin%2Flogs#code=CODE1234')
    signIn()

    expect(await screen.findByText('families page')).toBeInTheDocument()
  })

  describe('SSO', () => {
    it('shows the button only when configured as available', async () => {
      fetchSsoProvider.mockResolvedValue({ enabled: true, display_name: 'Nolumia' })
      renderLogin('/login')

      expect(
        await screen.findByRole('button', { name: 'Sign in with Nolumia' }),
      ).toBeInTheDocument()
    })

    it('hides it when unavailable', async () => {
      renderLogin('/login')

      await screen.findByRole('button', { name: 'Sign in' })
      expect(screen.queryByRole('button', { name: /Sign in with/ })).not.toBeInTheDocument()
    })

    it('reports and retries when unreachable, then shows the button once connected', async () => {
      // A release makes the server unreachable. Giving up once means no SSO button later (ADR-0046)
      vi.useFakeTimers({ shouldAdvanceTime: true })
      fetchSsoProvider
        .mockRejectedValueOnce(new Error('offline'))
        .mockResolvedValue({ enabled: true, display_name: 'Nolumia' })
      renderLogin('/login')

      expect(await screen.findByText(/Cannot reach the server/)).toBeInTheDocument()
      // Does not get in the way of password login
      expect(screen.getByRole('button', { name: 'Sign in' })).toBeInTheDocument()
      expect(screen.queryByRole('button', { name: /Sign in with/ })).not.toBeInTheDocument()

      await vi.advanceTimersByTimeAsync(5000)
      expect(
        await screen.findByRole('button', { name: 'Sign in with Nolumia' }),
      ).toBeInTheDocument()
      expect(screen.queryByText(/Cannot reach the server/)).not.toBeInTheDocument()
      vi.useRealTimers()
    })

    it('on tap, sends to the IdP with the post-login destination', async () => {
      fetchSsoProvider.mockResolvedValue({ enabled: true, display_name: 'Nolumia' })
      renderLogin('/login#code=CODE1234')

      fireEvent.click(await screen.findByRole('button', { name: 'Sign in with Nolumia' }))

      // The return path reaches the server; the invitation code is kept in this tab (ADR-0025)
      expect(startSsoLogin).toHaveBeenCalledExactlyOnceWith('/families')
      expect(sessionStorage.getItem('pendingInvitationCode')).toBe('CODE1234')
    })

    it.each([
      ['/login?redirect_to=%2Fadmin%2Flogs%3Fq%3Da', '/admin/logs?q=a'],
      ['/login', '/'],
      ['/login?redirect_to=https%3A%2F%2Fevil.example%2F', '/'],
    ])('passes the opened screen through the IdP (%s -> %s, ADR-0051)', async (entry, expected) => {
      fetchSsoProvider.mockResolvedValue({ enabled: true, display_name: 'Nolumia' })
      renderLogin(entry)

      fireEvent.click(await screen.findByRole('button', { name: 'Sign in with Nolumia' }))

      expect(startSsoLogin).toHaveBeenCalledExactlyOnceWith(expected)
    })

    it('shows a failure returned from the IdP', () => {
      renderLogin('/login?sso_error=sso_account_not_linked')

      expect(
        screen.getByText(
          'An account with this email address already exists but is not linked yet. Sign in to it with your password, then link it from “Two-factor authentication & passkeys” in your profile.',
        ),
      ).toBeInTheDocument()
    })

    it('falls back to a generic message for unknown codes (never shows the key)', () => {
      renderLogin('/login?sso_error=something_new')

      expect(screen.getByText('Single sign-on failed. Please try again.')).toBeInTheDocument()
    })
  })

  describe('no-tap sign-in attempt (ADR-0052)', () => {
    beforeEach(() => {
      sessionStorage.clear()
      fetchSsoProvider.mockResolvedValue({ enabled: true, display_name: 'Nolumia' })
    })

    afterEach(() => {
      vi.restoreAllMocks()
    })

    it('on open, goes to the IdP with prompt=none without rendering (keeps target)', async () => {
      renderLogin('/login?redirect_to=%2Fadmin%2Flogs')

      await waitFor(() => {
        expect(startSsoLogin).toHaveBeenCalledExactlyOnceWith('/admin/logs', { silent: true })
      })
      expect(screen.queryByRole('button', { name: 'Sign in with Nolumia' })).not.toBeInTheDocument()
      // Do not render the password field before trying (no flash before going to the IdP)
      expect(screen.queryByLabelText('Password')).not.toBeInTheDocument()
    })

    it('after trying and returning, shows the normal entry without an error', async () => {
      renderLogin('/login?sso_silent=declined&redirect_to=%2Fadmin%2Flogs')

      expect(
        await screen.findByRole('button', { name: 'Sign in with Nolumia' }),
      ).toBeInTheDocument()
      expect(startSsoLogin).not.toHaveBeenCalled()
      expect(screen.queryByText('Single sign-on failed. Please try again.')).not.toBeInTheDocument()
    })

    it('does not try when holding an invitation code', async () => {
      renderLogin('/login#code=CODE1234')

      expect(
        await screen.findByRole('button', { name: 'Sign in with Nolumia' }),
      ).toBeInTheDocument()
      expect(startSsoLogin).not.toHaveBeenCalled()
    })

    it('tries once more when the returned screen is reloaded (ADR-0054)', async () => {
      sessionStorage.setItem('ssoSilentTried', '1')
      vi.spyOn(window.performance, 'getEntriesByType').mockReturnValue([
        { type: 'reload' } as PerformanceNavigationTiming,
      ])
      renderLogin('/login?sso_silent=declined&redirect_to=%2Fadmin%2Flogs')

      await waitFor(() => {
        expect(startSsoLogin).toHaveBeenCalledExactlyOnceWith('/admin/logs', { silent: true })
      })
    })

    it('does not try on reload after signing out', async () => {
      localStorage.setItem('ssoSignedOut', '1')
      vi.spyOn(window.performance, 'getEntriesByType').mockReturnValue([
        { type: 'reload' } as PerformanceNavigationTiming,
      ])
      renderLogin('/login?sso_silent=declined')

      expect(
        await screen.findByRole('button', { name: 'Sign in with Nolumia' }),
      ).toBeInTheDocument()
      expect(startSsoLogin).not.toHaveBeenCalled()
    })

    it('does not try on reload when an error notice is attached', async () => {
      vi.spyOn(window.performance, 'getEntriesByType').mockReturnValue([
        { type: 'reload' } as PerformanceNavigationTiming,
      ])
      renderLogin('/login?sso_silent=declined&sso_error=sso_failed')

      expect(
        await screen.findByRole('button', { name: 'Sign in with Nolumia' }),
      ).toBeInTheDocument()
      expect(startSsoLogin).not.toHaveBeenCalled()
    })

    it('does not try on reload when holding an invitation code', async () => {
      vi.spyOn(window.performance, 'getEntriesByType').mockReturnValue([
        { type: 'reload' } as PerformanceNavigationTiming,
      ])
      renderLogin('/login?sso_silent=declined#code=CODE1234')

      expect(
        await screen.findByRole('button', { name: 'Sign in with Nolumia' }),
      ).toBeInTheDocument()
      expect(startSsoLogin).not.toHaveBeenCalled()
    })

    it('does not try if this tab already tried once', async () => {
      sessionStorage.setItem('ssoSilentTried', '1')
      renderLogin('/login')

      expect(
        await screen.findByRole('button', { name: 'Sign in with Nolumia' }),
      ).toBeInTheDocument()
      expect(startSsoLogin).not.toHaveBeenCalled()
    })

    it('does not try after signing out', async () => {
      localStorage.setItem('ssoSignedOut', '1')
      renderLogin('/login')

      expect(
        await screen.findByRole('button', { name: 'Sign in with Nolumia' }),
      ).toBeInTheDocument()
      expect(startSsoLogin).not.toHaveBeenCalled()
    })
  })
})
