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
    // 入口の出し分けを見る試験。ボタンを押さずに入る試し（ADR-0052）は済んだことにする
    sessionStorage.setItem('ssoSilentTried', '1')
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

  it('開こうとしていた画面（redirect_to）へ、クエリごと戻す（ADR-0051）', async () => {
    renderLogin('/login?redirect_to=%2Fadmin%2Flogs%3Flevel%3DERROR')
    signIn()

    expect(await screen.findByText('logs page')).toBeInTheDocument()
  })

  it('招待コードがあれば、redirect_to より家族の画面を先にする', async () => {
    renderLogin('/login?redirect_to=%2Fadmin%2Flogs#code=CODE1234')
    signIn()

    expect(await screen.findByText('families page')).toBeInTheDocument()
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

    it('問い合わせが届かなければ伝えて聞き直し、つながったらボタンを出す', async () => {
      // リリース中はサーバーに届かない。一度で諦めると、戻っても SSO のボタンが出ない（ADR-0046）
      vi.useFakeTimers({ shouldAdvanceTime: true })
      fetchSsoProvider
        .mockRejectedValueOnce(new Error('offline'))
        .mockResolvedValue({ enabled: true, display_name: 'Nolumia' })
      renderLogin('/login')

      expect(await screen.findByText(/Cannot reach the server/)).toBeInTheDocument()
      // パスワードでのログインは邪魔しない
      expect(screen.getByRole('button', { name: 'Sign in' })).toBeInTheDocument()
      expect(screen.queryByRole('button', { name: /Sign in with/ })).not.toBeInTheDocument()

      await vi.advanceTimersByTimeAsync(5000)
      expect(
        await screen.findByRole('button', { name: 'Sign in with Nolumia' }),
      ).toBeInTheDocument()
      expect(screen.queryByText(/Cannot reach the server/)).not.toBeInTheDocument()
      vi.useRealTimers()
    })

    it('押したら、ログイン後の行き先を添えて IdP へ送り出す', async () => {
      fetchSsoProvider.mockResolvedValue({ enabled: true, display_name: 'Nolumia' })
      renderLogin('/login#code=CODE1234')

      fireEvent.click(await screen.findByRole('button', { name: 'Sign in with Nolumia' }))

      // 戻り先はサーバーへ届く。招待コードは載せず、同じタブへ預ける（ADR-0025）
      expect(startSsoLogin).toHaveBeenCalledExactlyOnceWith('/families')
      expect(sessionStorage.getItem('pendingInvitationCode')).toBe('CODE1234')
    })

    it.each([
      ['/login?redirect_to=%2Fadmin%2Flogs%3Fq%3Da', '/admin/logs?q=a'],
      ['/login', '/'],
      ['/login?redirect_to=https%3A%2F%2Fevil.example%2F', '/'],
    ])('開こうとしていた画面を IdP の往復に渡す（%s → %s。ADR-0051）', async (entry, expected) => {
      fetchSsoProvider.mockResolvedValue({ enabled: true, display_name: 'Nolumia' })
      renderLogin(entry)

      fireEvent.click(await screen.findByRole('button', { name: 'Sign in with Nolumia' }))

      expect(startSsoLogin).toHaveBeenCalledExactlyOnceWith(expected)
    })

    it('IdP から戻された失敗を出す', () => {
      renderLogin('/login?sso_error=sso_account_not_linked')

      expect(
        screen.getByText(
          'An account with this email address already exists but is not linked yet. Sign in to it with your password, then link it from “Two-factor authentication & passkeys” in your profile.',
        ),
      ).toBeInTheDocument()
    })

    it('知らないコードは一般的な文言へ倒す（キーをそのまま出さない）', () => {
      renderLogin('/login?sso_error=something_new')

      expect(screen.getByText('Single sign-on failed. Please try again.')).toBeInTheDocument()
    })
  })

  describe('ボタンを押さずに入る試し（ADR-0052）', () => {
    beforeEach(() => {
      sessionStorage.clear()
      fetchSsoProvider.mockResolvedValue({ enabled: true, display_name: 'Nolumia' })
    })

    afterEach(() => {
      vi.restoreAllMocks()
    })

    it('開いたら入口を描かずに prompt=none で IdP へ送り出す（行き先は保つ）', async () => {
      renderLogin('/login?redirect_to=%2Fadmin%2Flogs')

      await waitFor(() => {
        expect(startSsoLogin).toHaveBeenCalledExactlyOnceWith('/admin/logs', { silent: true })
      })
      expect(screen.queryByRole('button', { name: 'Sign in with Nolumia' })).not.toBeInTheDocument()
      // 試す前にパスワード欄を描かない（一瞬見えてから IdP へ飛ばない）
      expect(screen.queryByLabelText('Password')).not.toBeInTheDocument()
    })

    it('試して戻ってきたら、エラーを出さずにふつうの入口を出す', async () => {
      renderLogin('/login?sso_silent=declined&redirect_to=%2Fadmin%2Flogs')

      expect(
        await screen.findByRole('button', { name: 'Sign in with Nolumia' }),
      ).toBeInTheDocument()
      expect(startSsoLogin).not.toHaveBeenCalled()
      expect(screen.queryByText('Single sign-on failed. Please try again.')).not.toBeInTheDocument()
    })

    it('招待コードを持って来たときは試さない', async () => {
      renderLogin('/login#code=CODE1234')

      expect(
        await screen.findByRole('button', { name: 'Sign in with Nolumia' }),
      ).toBeInTheDocument()
      expect(startSsoLogin).not.toHaveBeenCalled()
    })

    it('試して戻った画面を再読み込みしたら、もう 1 回試す（ADR-0054）', async () => {
      sessionStorage.setItem('ssoSilentTried', '1')
      vi.spyOn(window.performance, 'getEntriesByType').mockReturnValue([
        { type: 'reload' } as PerformanceNavigationTiming,
      ])
      renderLogin('/login?sso_silent=declined&redirect_to=%2Fadmin%2Flogs')

      await waitFor(() => {
        expect(startSsoLogin).toHaveBeenCalledExactlyOnceWith('/admin/logs', { silent: true })
      })
    })

    it('再読み込みでも、サインアウトした後は試さない', async () => {
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

    it('再読み込みでも、エラーの知らせが付いていたら試さない', async () => {
      vi.spyOn(window.performance, 'getEntriesByType').mockReturnValue([
        { type: 'reload' } as PerformanceNavigationTiming,
      ])
      renderLogin('/login?sso_silent=declined&sso_error=sso_failed')

      expect(
        await screen.findByRole('button', { name: 'Sign in with Nolumia' }),
      ).toBeInTheDocument()
      expect(startSsoLogin).not.toHaveBeenCalled()
    })

    it('再読み込みでも、招待コードを持って来たときは試さない', async () => {
      vi.spyOn(window.performance, 'getEntriesByType').mockReturnValue([
        { type: 'reload' } as PerformanceNavigationTiming,
      ])
      renderLogin('/login?sso_silent=declined#code=CODE1234')

      expect(
        await screen.findByRole('button', { name: 'Sign in with Nolumia' }),
      ).toBeInTheDocument()
      expect(startSsoLogin).not.toHaveBeenCalled()
    })

    it('このタブで一度試していたら試さない', async () => {
      sessionStorage.setItem('ssoSilentTried', '1')
      renderLogin('/login')

      expect(
        await screen.findByRole('button', { name: 'Sign in with Nolumia' }),
      ).toBeInTheDocument()
      expect(startSsoLogin).not.toHaveBeenCalled()
    })

    it('サインアウトした後は試さない', async () => {
      localStorage.setItem('ssoSignedOut', '1')
      renderLogin('/login')

      expect(
        await screen.findByRole('button', { name: 'Sign in with Nolumia' }),
      ).toBeInTheDocument()
      expect(startSsoLogin).not.toHaveBeenCalled()
    })
  })
})
