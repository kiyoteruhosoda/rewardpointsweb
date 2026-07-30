/** ナビゲーション: scope による出し分けと、狭い画面での引き出しの閉じ方。 */
import { fireEvent, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { renderWithProviders } from '../test-support/renderWithProviders'
import { Sidebar } from './Sidebar'

const CLOSE_LABEL = 'Close the menu'

describe('Sidebar', () => {
  it('scope を持つ項目だけを出す', () => {
    renderWithProviders(<Sidebar open={false} onClose={vi.fn()} />, {
      scopes: ['member:view'],
    })
    expect(screen.getByRole('link', { name: 'Points' })).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Users' })).not.toBeInTheDocument()
  })

  it('閉じているあいだは背景を出さない', () => {
    renderWithProviders(<Sidebar open={false} onClose={vi.fn()} />, {
      scopes: ['member:view'],
    })
    expect(screen.queryByRole('button', { name: CLOSE_LABEL })).not.toBeInTheDocument()
    expect(screen.getByRole('navigation')).not.toHaveClass('sidebar-open')
  })

  it('開いているあいだは sidebar-open を付ける', () => {
    renderWithProviders(<Sidebar open onClose={vi.fn()} />, { scopes: ['member:view'] })
    expect(screen.getByRole('navigation')).toHaveClass('sidebar-open')
  })

  it('背景に触れると閉じる', () => {
    const onClose = vi.fn()
    renderWithProviders(<Sidebar open onClose={onClose} />, { scopes: ['member:view'] })

    fireEvent.click(screen.getByRole('button', { name: CLOSE_LABEL }))
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('項目を選ぶと閉じる（引き出しが本文に被さったままにならない）', () => {
    const onClose = vi.fn()
    renderWithProviders(<Sidebar open onClose={onClose} />, { scopes: ['member:view'] })

    fireEvent.click(screen.getByRole('link', { name: 'Points' }))
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('Escape で閉じる', () => {
    const onClose = vi.fn()
    renderWithProviders(<Sidebar open onClose={onClose} />, { scopes: ['member:view'] })

    fireEvent.keyDown(window, { key: 'Escape' })
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('閉じているときは Escape を拾わない', () => {
    const onClose = vi.fn()
    renderWithProviders(<Sidebar open={false} onClose={onClose} />, {
      scopes: ['member:view'],
    })

    fireEvent.keyDown(window, { key: 'Escape' })
    expect(onClose).not.toHaveBeenCalled()
  })
})
