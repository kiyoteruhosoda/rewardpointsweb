/** ヘッダ: アカウントへの入口（狭い画面では頭文字の丸）と引き出しの開閉。 */
import { fireEvent, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { renderWithProviders } from '../test-support/renderWithProviders'
import { Header } from './Header'

describe('Header', () => {
  it('アカウントへの入口は頭文字の丸と利用者名を持つ', () => {
    renderWithProviders(<Header navOpen={false} onToggleNav={vi.fn()} />)

    // 名前は狭い画面で隠れる（index.css）ので、読み上げ用の名前は aria-label に置く
    const account = screen.getByRole('link', { name: 'Account (manager)' })
    expect(account).toHaveAttribute('href', '/profile')
    expect(account).toHaveAttribute('title', 'manager')
    expect(account).toHaveTextContent('M')
    expect(account).toHaveTextContent('manager')
  })

  it('引き出しの開閉ボタンは開いているかどうかを伝える', () => {
    const onToggleNav = vi.fn()
    renderWithProviders(<Header navOpen onToggleNav={onToggleNav} />)

    const toggle = screen.getByRole('button', { name: 'Menu' })
    expect(toggle).toHaveAttribute('aria-expanded', 'true')
    fireEvent.click(toggle)
    expect(onToggleNav).toHaveBeenCalled()
  })
})
