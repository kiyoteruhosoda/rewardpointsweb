/**
 * 招待コードでのアカウント作成。
 *
 * 入力欄の下限・上限はサーバーのスキーマと同じにする。欠けると、送るまで気付けず
 * 422 で跳ね返る（`InvitationRedeemRequest`）。
 */
import { fireEvent, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import type { RedeemedInvitation } from '../services/families'
import { renderWithProviders } from '../test-support/renderWithProviders'
import { RedeemInvitationPage } from './RedeemInvitationPage'

const redeemInvitation =
  vi.fn<
    (
      code: string,
      username: string,
      password: string,
      displayName: string,
    ) => Promise<RedeemedInvitation>
  >()

vi.mock('../services/families', () => ({
  families: {
    redeemInvitation: (code: string, username: string, password: string, displayName: string) =>
      redeemInvitation(code, username, password, displayName),
  },
}))

describe('RedeemInvitationPage', () => {
  it('パスワードは 8 文字以上（サーバーの min_length と同じ）', () => {
    renderWithProviders(<RedeemInvitationPage />)
    expect(screen.getByLabelText('Password')).toHaveAttribute('minlength', '8')
  })

  it('ユーザー名は 3〜255 文字（Username の値オブジェクトと同じ）', () => {
    renderWithProviders(<RedeemInvitationPage />)
    const username = screen.getByLabelText('Username')
    expect(username).toHaveAttribute('minlength', '3')
    expect(username).toHaveAttribute('maxlength', '255')
  })

  it('招待コードは 64 文字まで（CodeStr と同じ）', () => {
    renderWithProviders(<RedeemInvitationPage />)
    expect(screen.getByLabelText('Invitation code')).toHaveAttribute('maxlength', '64')
  })

  it('名前は 100 文字まで（DisplayName の MAX_LENGTH と同じ）', () => {
    renderWithProviders(<RedeemInvitationPage />)
    expect(screen.getByLabelText('Name')).toHaveAttribute('maxlength', '100')
  })

  it('入力した名前をそのまま送る', async () => {
    redeemInvitation.mockReset()
    redeemInvitation.mockResolvedValue({
      family_id: 1,
      family_name: 'ほその家',
      membership_id: 2,
      role: 'child',
      username: 'taro',
    })
    renderWithProviders(<RedeemInvitationPage />)

    fireEvent.change(screen.getByLabelText('Invitation code'), { target: { value: 'CODE1234' } })
    fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'たろう' } })
    fireEvent.change(screen.getByLabelText('Username'), { target: { value: 'taro' } })
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'password123' } })
    fireEvent.click(screen.getByRole('button', { name: 'Create my account' }))

    await waitFor(() => {
      expect(redeemInvitation).toHaveBeenCalledWith('CODE1234', 'taro', 'password123', 'たろう')
    })
  })

  it('すでにアカウントがある人には、入力済みのコードを持たせてログインへ送る', () => {
    renderWithProviders(<RedeemInvitationPage />)

    fireEvent.change(screen.getByLabelText('Invitation code'), { target: { value: 'CODE 1234' } })

    expect(screen.getByRole('link', { name: 'Sign in and join' })).toHaveAttribute(
      'href',
      '/login?code=CODE%201234',
    )
  })

  it('コードが空ならログインへの導線にコードを付けない', () => {
    renderWithProviders(<RedeemInvitationPage />)

    expect(screen.getByRole('link', { name: 'Sign in and join' })).toHaveAttribute('href', '/login')
  })

  it('URL で渡されたコードを入れておく（ログインから戻ってきた場合）', () => {
    renderWithProviders(<RedeemInvitationPage />, { route: '/join?code=CODE1234' })
    expect(screen.getByLabelText('Invitation code')).toHaveValue('CODE1234')
  })
})
