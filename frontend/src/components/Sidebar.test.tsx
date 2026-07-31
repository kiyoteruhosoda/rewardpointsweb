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
      scopes: ['member:view'],
    })
    expect(screen.getByRole('link', { name: 'Points' })).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Dashboard' })).not.toBeInTheDocument()
  })

  it('システム管理は scope があっても出さない（プロフィール設定から入る）', () => {
    renderWithProviders(<Sidebar open={false} onClose={vi.fn()} />, {
      scopes: ['member:view', 'user:manage', 'admin:system-settings', 'log:view'],
    })
    expect(screen.queryByRole('link', { name: 'Users' })).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'System settings' })).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'System logs' })).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Profile & settings' })).toBeInTheDocument()
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

  it('開くと先頭の項目へ焦点を移す', () => {
    renderWithProviders(<Sidebar open onClose={vi.fn()} />, {
      scopes: ['dashboard:view', 'member:view'],
    })
    expect(document.activeElement).toBe(screen.getByRole('link', { name: 'Dashboard' }))
  })

  it('最後の要素から Tab すると先頭へ戻す（背後の操作子へ抜けない）', () => {
    renderWithProviders(<Sidebar open onClose={vi.fn()} />, {
      scopes: ['dashboard:view', 'member:view'],
    })
    // 巡回の最後は背景の「閉じる」ボタン
    screen.getByRole('button', { name: CLOSE_LABEL }).focus()

    fireEvent.keyDown(window, { key: 'Tab' })
    expect(document.activeElement).toBe(screen.getByRole('link', { name: 'Dashboard' }))
  })

  it('先頭から Shift+Tab すると末尾へ回す', () => {
    renderWithProviders(<Sidebar open onClose={vi.fn()} />, {
      scopes: ['dashboard:view', 'member:view'],
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

    renderWithProviders(<Drawer />, { scopes: ['member:view'] })
    expect(document.activeElement).toBe(screen.getByRole('link', { name: 'Points' }))

    fireEvent.click(screen.getByRole('button', { name: CLOSE_LABEL }))
    expect(document.activeElement).toBe(opener)
    opener.remove()
  })
})
