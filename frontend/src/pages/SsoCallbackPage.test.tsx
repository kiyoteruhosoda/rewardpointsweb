/**
 * IdP からの戻りを受ける中継画面。
 *
 * 券は 1 回しか使えないので、二重に投げないことまで見る（StrictMode の再描画で
 * 2 回目を投げると、正しい戻りが「期限切れ」で弾かれる）。
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

/** 招待コードが付け直されたかを読み取るための目印。 */
function FamiliesProbe() {
  const { hash } = useLocation()
  return <p>families page: {hash === '' ? '(no code)' : hash}</p>
}

/** 戻された失敗のコードを読み取るための目印。 */
function LoginProbe() {
  const [params] = useSearchParams()
  return <p>login page: {params.get('sso_error') ?? '(none)'}</p>
}

describe('SsoCallbackPage', () => {
  beforeEach(() => {
    sessionStorage.clear()
  })

  it('券をトークンへ換え、SSO を始めた画面へ送る', async () => {
    const exchange = vi.fn<(ticket: string) => Promise<string>>().mockResolvedValue('/families')

    renderCallback('/login/sso?ticket=abc', exchange)

    expect(await screen.findByText('families page: (no code)')).toBeInTheDocument()
    expect(exchange).toHaveBeenCalledExactlyOnceWith('abc')
  })

  it('券が無ければログイン画面へ戻す（期限切れとして扱う）', async () => {
    const exchange = vi.fn<(ticket: string) => Promise<string>>()

    renderCallback('/login/sso', exchange)

    expect(await screen.findByText('login page: sso_ticket_invalid')).toBeInTheDocument()
    expect(exchange).not.toHaveBeenCalled()
  })

  it('換えられなかった理由はログイン画面へ持って行く', async () => {
    const exchange = vi
      .fn<(ticket: string) => Promise<string>>()
      .mockRejectedValue(new ApiError(401, 'sso_account_not_linked'))

    renderCallback('/login/sso?ticket=abc', exchange)

    expect(await screen.findByText('login page: sso_account_not_linked')).toBeInTheDocument()
  })

  it('IdP への往復で消えた招待コードを、戻り先へ付け直す（ADR-0025）', async () => {
    // ログイン画面が預けたもの。クエリでは運べないため断片ごと消えている
    sessionStorage.setItem('pendingInvitationCode', 'CODE1234')
    const exchange = vi.fn<(ticket: string) => Promise<string>>().mockResolvedValue('/families')

    renderCallback('/login/sso?ticket=abc', exchange)

    expect(await screen.findByText('families page: #code=CODE1234')).toBeInTheDocument()
    // 預かりは 1 回限り（次のログインへ持ち越さない）
    expect(sessionStorage.getItem('pendingInvitationCode')).toBeNull()
  })
})
