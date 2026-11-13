/**
 * Render helper for screen tests.
 *
 * Screens only work on top of i18n, theme, toasts, router, auth (scopes) and the user's
 * family. Prepare them here so the same nesting need not be written each time. Scopes and
 * family can be replaced via arguments, so "with/without permission" and "with/without
 * a family" rendering can be verified directly.
 */
import { render, type RenderResult } from '@testing-library/react'
import type { ReactElement, ReactNode } from 'react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

import { ToastProvider } from '../components/ToastNotification'
import { I18nProvider } from '../i18n'
import type { FamilyDetail } from '../services/families'
import type { UiSettings } from '../services/uiSettings'
import { AuthContext, type AuthValue, type Me } from '../store/AuthContext'
import { FamilyContext, type FamilyValue } from '../store/FamilyContext'
import { ThemeProvider } from '../theme'

const SETTINGS: UiSettings = {
  languages: ['en'],
  default_locale: 'en',
  default_theme: 'system',
}

const USER: Me = {
  user_id: 1,
  username: 'manager',
  display_name: 'manager',
  email: 'manager@example.com',
  scopes: [],
  must_change_password: false,
  has_password: true,
  display_device: false,
}

interface Options {
  /** Scopes held by the signed-in user. */
  scopes?: string[]
  /** URL to display (needed for screens using `useParams`). */
  route?: string
  /** Path of the route definition. Matches anything by default. */
  path?: string
  /** Observes logout (used by screens that verify the re-login prompt). */
  logout?: () => void
  /** SSO exchange (replaced for screens that receive the return from the IdP). */
  loginWithSsoTicket?: (ticket: string) => Promise<string>
  /** The user's family. Defaults to not belonging to any family. */
  family?: FamilyDetail | null
  /** State where the family failed to load (membership unknown). */
  familyFailed?: boolean
  /** Observes family reloads (used by screens that verify reloading after changes). */
  reloadFamily?: () => Promise<void>
  /**
   * Extra `<Route>`s. Placed as destination markers when verifying that a screen
   * navigates to another URL (use with a narrowed `path`).
   */
  extraRoutes?: ReactNode
}

function authValueOf(
  scopes: string[],
  logout: () => void,
  loginWithSsoTicket: (ticket: string) => Promise<string>,
): AuthValue {
  return {
    user: { ...USER, scopes },
    loading: false,
    unreachable: false,
    login: () => Promise.resolve(),
    loginWithPasskey: () => Promise.resolve(),
    loginWithSsoTicket,
    logout,
    refreshMe: () => Promise.resolve(),
    hasScope: (...codes: string[]) => codes.every((code) => scopes.includes(code)),
  }
}

function familyValueOf(
  family: FamilyDetail | null,
  failed: boolean,
  reload: () => Promise<void>,
): FamilyValue {
  return { family, failed, loading: false, reload }
}

export function renderWithProviders(ui: ReactElement, options: Options = {}): RenderResult {
  const {
    scopes = [],
    route = '/',
    path = '*',
    logout = () => undefined,
    loginWithSsoTicket = () => Promise.resolve('/'),
    family = null,
    familyFailed = false,
    reloadFamily = () => Promise.resolve(),
    extraRoutes = null,
  } = options
  // Fix the language to en. A leftover user choice (localStorage) would change expected text.
  localStorage.setItem('locale', 'en')

  return render(
    <I18nProvider settings={SETTINGS}>
      <ThemeProvider settings={SETTINGS}>
        <AuthContext.Provider value={authValueOf(scopes, logout, loginWithSsoTicket)}>
          <FamilyContext.Provider value={familyValueOf(family, familyFailed, reloadFamily)}>
            <ToastProvider>
              <MemoryRouter initialEntries={[route]}>
                <Routes>
                  <Route path={path} element={ui} />
                  {extraRoutes}
                </Routes>
              </MemoryRouter>
            </ToastProvider>
          </FamilyContext.Provider>
        </AuthContext.Provider>
      </ThemeProvider>
    </I18nProvider>,
  )
}
