/** プロフィール設定: 自分の情報・表示設定（言語・テーマ）・システム管理の入口。 */
import { fireEvent, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it } from 'vitest'

import { renderWithProviders } from '../test-support/renderWithProviders'
import { ProfilePage } from './ProfilePage'

describe('ProfilePage', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('自分のアカウント情報を出す', () => {
    renderWithProviders(<ProfilePage />, { scopes: ['member:view'] })
    expect(screen.getByText('manager@example.com')).toBeInTheDocument()
    expect(screen.getByText('manager')).toBeInTheDocument()
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

  it('scope を持つ人にだけシステム管理の入口を出す', () => {
    renderWithProviders(<ProfilePage />, { scopes: ['user:manage', 'log:view'] })
    expect(screen.getByText('System administration')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Users' })).toHaveAttribute('href', '/admin/users')
    expect(screen.getByRole('link', { name: 'System logs' })).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Roles' })).not.toBeInTheDocument()
  })

  it('scope が無ければシステム管理そのものを出さない', () => {
    renderWithProviders(<ProfilePage />, { scopes: ['member:view'] })
    expect(screen.queryByText('System administration')).not.toBeInTheDocument()
  })
})
