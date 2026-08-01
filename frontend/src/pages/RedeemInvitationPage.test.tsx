/**
 * 招待コードでのアカウント作成。
 *
 * 入力欄の下限・上限はサーバーのスキーマと同じにする。欠けると、送るまで気付けず
 * 422 で跳ね返る（`InvitationRedeemRequest`）。
 */
import { screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { renderWithProviders } from '../test-support/renderWithProviders'
import { RedeemInvitationPage } from './RedeemInvitationPage'

vi.mock('../services/families', () => ({
  families: { redeemInvitation: vi.fn() },
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
})
