/**
 * ログイン画面。招待コードを持ったまま来た場合の動線と、SSO の出し分け。
 *
 * アカウント作成の画面から回されてきた人は、ログインが終わったところで
 * 「コードで参加する」欄まで運ばれる必要がある。既定の行き先（ダッシュボード）
 * へ落とすと、コードを持っているのに入口が見つからない状態に戻ってしまう。
 *
 * SSO のボタンは、サーバーが「使える」と答えたときにだけ出す。失敗の理由は
 * 画面遷移で戻ってくるため URL に載る（ADR-0029）。
 */
import { fireEvent, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { Route } from 'react-router-dom'

import { renderWithProviders } from '../test-support/renderWithProviders'
import type { SsoProvider } from '../services/sso'
import { LoginPage } from './LoginPage'

const fetchSsoProvider = vi.fn<() => Promise<SsoProvider>>()
const startSsoLogin = vi.fn<(redirectTo: string) => void>()

vi.mock('../services/sso', () => ({
  fetchSsoProvider: () => fetchSsoProvider(),
  startSsoLogin: (redirectTo: string) => {
    startSsoLogin(redirectTo)
  },
}))

function renderLogin(route: string) {
  return renderWithProviders(<LoginPage />, {
    route,
    path: '/login',
    extraRoutes: (
      <>
        <Route path="/families" element={<p>families page</p>} />
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
    // 既定は「SSO は使えない」。使える場合は各テストで差し替える
    fetchSsoProvider.mockResolvedValue({ enabled: false, display_name: '' })
  })

  it('招待コードを持って来た人には、先にログインする理由を出す', () => {
    renderLogin('/login#code=CODE1234')

    expect(
      screen.getByText(
        'Sign in first. Right after that you can join your family with the invitation code you entered.',
      ),
    ).toBeInTheDocument()
  })

  it('ログイン後はコードを持ったまま家族の画面へ送る', async () => {
    renderLogin('/login#code=CODE1234')
    signIn()

    expect(await screen.findByText('families page')).toBeInTheDocument()
  })

  it('コードが無ければ従来どおり最初の画面へ送る', async () => {
    renderLogin('/login')
    signIn()

    expect(await screen.findByText('dashboard')).toBeInTheDocument()
    expect(screen.queryByText(/Sign in first/)).not.toBeInTheDocument()
  })

  describe('SSO', () => {
    it('使える構成のときだけボタンを出す', async () => {
      fetchSsoProvider.mockResolvedValue({ enabled: true, display_name: 'Nolumia' })
      renderLogin('/login')

      expect(
        await screen.findByRole('button', { name: 'Sign in with Nolumia' }),
      ).toBeInTheDocument()
    })

    it('使えないときは出さない', async () => {
      renderLogin('/login')

      await screen.findByRole('button', { name: 'Sign in' })
      expect(screen.queryByRole('button', { name: /Sign in with/ })).not.toBeInTheDocument()
    })

    it('問い合わせに失敗しても、パスワードでのログインは邪魔しない', async () => {
      fetchSsoProvider.mockRejectedValue(new Error('offline'))
      renderLogin('/login')

      expect(await screen.findByRole('button', { name: 'Sign in' })).toBeInTheDocument()
      expect(screen.queryByRole('button', { name: /Sign in with/ })).not.toBeInTheDocument()
    })

    it('押したら、ログイン後の行き先を添えて IdP へ送り出す', async () => {
      fetchSsoProvider.mockResolvedValue({ enabled: true, display_name: 'Nolumia' })
      renderLogin('/login#code=CODE1234')

      fireEvent.click(await screen.findByRole('button', { name: 'Sign in with Nolumia' }))

      // 戻り先はサーバーへ届く。招待コードは載せず、同じタブへ預ける（ADR-0025）
      expect(startSsoLogin).toHaveBeenCalledExactlyOnceWith('/families')
      expect(sessionStorage.getItem('pendingInvitationCode')).toBe('CODE1234')
    })

    it('IdP から戻された失敗を出す', () => {
      renderLogin('/login?sso_error=sso_account_not_linked')

      expect(
        screen.getByText(
          'No account here matches that sign-in. An administrator has to add the email address to your account first.',
        ),
      ).toBeInTheDocument()
    })

    it('知らないコードは一般的な文言へ倒す（キーをそのまま出さない）', () => {
      renderLogin('/login?sso_error=something_new')

      expect(screen.getByText('Single sign-on failed. Please try again.')).toBeInTheDocument()
    })
  })
})
