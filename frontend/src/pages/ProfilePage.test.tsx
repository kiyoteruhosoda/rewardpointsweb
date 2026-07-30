/** プロフィール: 自分の情報と、表示設定（言語・テーマ）の切り替え。 */
import { fireEvent, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it } from 'vitest'

import { renderWithProviders } from '../test-support/renderWithProviders'
import { ProfilePage } from './ProfilePage'

describe('ProfilePage', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('自分の情報と付与されている scope を出す', () => {
    renderWithProviders(<ProfilePage />, { scopes: ['member:view'] })
    expect(screen.getByText('manager@example.com')).toBeInTheDocument()
    expect(screen.getByText('member:view')).toBeInTheDocument()
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
})
