/** ナビゲーション: scope による出し分けと、狭い画面での引き出しの閉じ方。 */
import { fireEvent, screen } from '@testing-library/react'
import { useState } from 'react'
import { describe, expect, it, vi } from 'vitest'

import { renderWithProviders } from '../test-support/renderWithProviders'
import { Sidebar } from './Sidebar'

const CLOSE_LABEL = 'Close the menu'

describe('Sidebar', () => {
  it('scope を持つ項目だけを出す', () => {
    renderWithProviders(<Sidebar open={false} onClose={vi.fn()} />, {
      scopes: ['family:view'],
    })
    expect(screen.getByRole('link', { name: 'Family' })).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Dashboard' })).not.toBeInTheDocument()
  })

  it('システム管理は scope を持つ人にだけ独立した節として出す', () => {
    renderWithProviders(<Sidebar open={false} onClose={vi.fn()} />, {
      scopes: ['family:view', 'user:manage', 'admin:system-settings', 'log:view'],
    })
    expect(screen.getByText('System administration')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Users' })).toHaveAttribute('href', '/admin/users')
    expect(screen.getByRole('link', { name: 'System settings' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'System logs' })).toBeInTheDocument()
    // scope の無い項目（ロール・権限）は出さない
    expect(screen.queryByRole('link', { name: 'Roles' })).not.toBeInTheDocument()
  })

  it('システム管理の scope が無ければ節そのものを出さない', () => {
    renderWithProviders(<Sidebar open={false} onClose={vi.fn()} />, {
      scopes: ['family:view'],
    })
    expect(screen.queryByText('System administration')).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Users' })).not.toBeInTheDocument()
  })

  it('閉じているあいだは背景を出さない', () => {
    renderWithProviders(<Sidebar open={false} onClose={vi.fn()} />, {
      scopes: ['family:view'],
    })
    expect(screen.queryByRole('button', { name: CLOSE_LABEL })).not.toBeInTheDocument()
    expect(screen.getByRole('navigation')).not.toHaveClass('sidebar-open')
  })

  it('開いているあいだは sidebar-open を付ける', () => {
    renderWithProviders(<Sidebar open onClose={vi.fn()} />, { scopes: ['family:view'] })
    expect(screen.getByRole('navigation')).toHaveClass('sidebar-open')
  })

  it('背景に触れると閉じる', () => {
    const onClose = vi.fn()
    renderWithProviders(<Sidebar open onClose={onClose} />, { scopes: ['family:view'] })

    fireEvent.click(screen.getByRole('button', { name: CLOSE_LABEL }))
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('項目を選ぶと閉じる（引き出しが本文に被さったままにならない）', () => {
    const onClose = vi.fn()
    renderWithProviders(<Sidebar open onClose={onClose} />, { scopes: ['family:view'] })

    fireEvent.click(screen.getByRole('link', { name: 'Family' }))
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('Escape で閉じる', () => {
    const onClose = vi.fn()
    renderWithProviders(<Sidebar open onClose={onClose} />, { scopes: ['family:view'] })

    fireEvent.keyDown(window, { key: 'Escape' })
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('閉じているときは Escape を拾わない', () => {
    const onClose = vi.fn()
    renderWithProviders(<Sidebar open={false} onClose={onClose} />, {
      scopes: ['family:view'],
    })

    fireEvent.keyDown(window, { key: 'Escape' })
    expect(onClose).not.toHaveBeenCalled()
  })

  it('開くと先頭の項目へ焦点を移す', () => {
    renderWithProviders(<Sidebar open onClose={vi.fn()} />, {
      scopes: ['dashboard:view', 'family:view'],
    })
    expect(document.activeElement).toBe(screen.getByRole('link', { name: 'Dashboard' }))
  })

  it('最後の要素から Tab すると先頭へ戻す（背後の操作子へ抜けない）', () => {
    renderWithProviders(<Sidebar open onClose={vi.fn()} />, {
      scopes: ['dashboard:view', 'family:view'],
    })
    // 巡回の最後は背景の「閉じる」ボタン
    screen.getByRole('button', { name: CLOSE_LABEL }).focus()

    fireEvent.keyDown(window, { key: 'Tab' })
    expect(document.activeElement).toBe(screen.getByRole('link', { name: 'Dashboard' }))
  })

  it('先頭から Shift+Tab すると末尾へ回す', () => {
    renderWithProviders(<Sidebar open onClose={vi.fn()} />, {
      scopes: ['dashboard:view', 'family:view'],
    })

    fireEvent.keyDown(window, { key: 'Tab', shiftKey: true })
    expect(document.activeElement).toBe(screen.getByRole('button', { name: CLOSE_LABEL }))
  })

  it('閉じると開いた操作子（ヘッダーの開閉ボタン）へ焦点を戻す', () => {
    // 開閉ボタンの代役。引き出しを開いた時点で焦点を持っている前提。
    const opener = document.createElement('button')
    document.body.append(opener)
    opener.focus()

    function Drawer() {
      const [open, setOpen] = useState(true)
      return (
        <Sidebar
          open={open}
          onClose={() => {
            setOpen(false)
          }}
        />
      )
    }

    renderWithProviders(<Drawer />, { scopes: ['family:view'] })
    expect(document.activeElement).toBe(screen.getByRole('link', { name: 'Family' }))

    fireEvent.click(screen.getByRole('button', { name: CLOSE_LABEL }))
    expect(document.activeElement).toBe(opener)
    opener.remove()
  })
})
