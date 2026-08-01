/** プロフィール設定: 自分の情報・表示設定（言語・テーマ）・セキュリティ。 */
import { fireEvent, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it } from 'vitest'

import { renderWithProviders } from '../test-support/renderWithProviders'
import { ProfilePage } from './ProfilePage'

describe('ProfilePage', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('表示名とログイン ID を出す', () => {
    renderWithProviders(<ProfilePage />, { scopes: ['family:view'] })
    expect(screen.getByText('Signs in as manager')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Account' })).toBeInTheDocument()
  })

  it('表示名とメールアドレスを変えられる（ログイン ID は編集させない）', () => {
    renderWithProviders(<ProfilePage />, { scopes: ['family:view'] })

    expect(screen.getByLabelText('Display name')).toHaveValue('manager')
    expect(screen.getByLabelText('Email (optional)')).toHaveValue('manager@example.com')
    expect(screen.queryByLabelText('Username')).not.toBeInTheDocument()
  })

  it('表示設定として言語とテーマを持つ（ヘッダーではなくこの画面に置く）', () => {
    renderWithProviders(<ProfilePage />)
    expect(screen.getByLabelText('Language')).toBeInTheDocument()
    expect(screen.getByLabelText('Theme')).toBeInTheDocument()
  })

  it('テーマを選ぶと保存して即座に反映する', () => {
    renderWithProviders(<ProfilePage />)

    fireEvent.change(screen.getByLabelText('Theme'), { target: { value: 'dark' } })
    expect(localStorage.getItem('theme')).toBe('dark')
    expect(document.documentElement.dataset.theme).toBe('dark')
  })

  it('システム管理の入口は置かない（Sidebar の独立した節にある）', () => {
    renderWithProviders(<ProfilePage />, { scopes: ['user:manage', 'log:view'] })
    expect(screen.queryByText('System administration')).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Users' })).not.toBeInTheDocument()
  })
})
