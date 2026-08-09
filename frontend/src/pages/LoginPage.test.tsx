/**
 * ログイン画面のうち、招待コードを持ったまま来た場合の動線。
 *
 * アカウント作成の画面から回されてきた人は、ログインが終わったところで
 * 「コードで参加する」欄まで運ばれる必要がある。既定の行き先（ダッシュボード）
 * へ落とすと、コードを持っているのに入口が見つからない状態に戻ってしまう。
 */
import { fireEvent, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { Route } from 'react-router-dom'

import { renderWithProviders } from '../test-support/renderWithProviders'
import { LoginPage } from './LoginPage'

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
})
