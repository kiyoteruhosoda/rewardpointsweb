/**
 * Relay screen receiving the return from the IdP.
 *
 * The ticket works only once, so also check it is not sent twice (sending it a second time on a StrictMode
 * re-render would get a valid return rejected as "expired").
 */
import { screen } from '@testing-library/react'
import { Route, useLocation, useSearchParams } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '../services/api'
import { renderWithProviders } from '../test-support/renderWithProviders'
import { SsoCallbackPage } from './SsoCallbackPage'

function renderCallback(route: string, loginWithSsoTicket: (ticket: string) => Promise<string>) {
  return renderWithProviders(<SsoCallbackPage />, {
    route,
    path: '/login/sso',
    loginWithSsoTicket,
    extraRoutes: (
      <>
        <Route path="/families" element={<FamiliesProbe />} />
        <Route path="/login" element={<LoginProbe />} />
      </>
    ),
  })
}

/** Marker for reading whether the invitation code was reattached. */
function FamiliesProbe() {
  const { hash } = useLocation()
  return <p>families page: {hash === '' ? '(no code)' : hash}</p>
}

/** Marker for reading the returned failure code. */
function LoginProbe() {
  const [params] = useSearchParams()
  return <p>login page: {params.get('sso_error') ?? '(none)'}</p>
}

describe('SsoCallbackPage', () => {
  beforeEach(() => {
    sessionStorage.clear()
  })

  it('exchanges the ticket for tokens and sends the user to the screen where SSO started', async () => {
    const exchange = vi.fn<(ticket: string) => Promise<string>>().mockResolvedValue('/families')

    renderCallback('/login/sso?ticket=abc', exchange)

    expect(await screen.findByText('families page: (no code)')).toBeInTheDocument()
    expect(exchange).toHaveBeenCalledExactlyOnceWith('abc')
  })

  it('returns to the login screen without a ticket (treated as expired)', async () => {
    const exchange = vi.fn<(ticket: string) => Promise<string>>()

    renderCallback('/login/sso', exchange)

    expect(await screen.findByText('login page: sso_ticket_invalid')).toBeInTheDocument()
    expect(exchange).not.toHaveBeenCalled()
  })

  it('carries the reason the exchange failed to the login screen', async () => {
    const exchange = vi
      .fn<(ticket: string) => Promise<string>>()
      .mockRejectedValue(new ApiError(401, 'sso_account_not_linked'))

    renderCallback('/login/sso?ticket=abc', exchange)

    expect(await screen.findByText('login page: sso_account_not_linked')).toBeInTheDocument()
  })

  it('reattaches the invitation code lost on the IdP round trip to the destination (ADR-0025)', async () => {
    // Stashed by the login screen. It cannot travel in the query, so it was lost with the fragment
    sessionStorage.setItem('pendingInvitationCode', 'CODE1234')
    const exchange = vi.fn<(ticket: string) => Promise<string>>().mockResolvedValue('/families')

    renderCallback('/login/sso?ticket=abc', exchange)

    expect(await screen.findByText('families page: #code=CODE1234')).toBeInTheDocument()
    // The stash is one-time (not carried over to the next login)
    expect(sessionStorage.getItem('pendingInvitationCode')).toBeNull()
  })
})
