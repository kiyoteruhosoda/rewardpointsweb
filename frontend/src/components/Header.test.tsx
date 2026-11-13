/** Header: the account entry (an initial in a circle on narrow screens) and opening/closing the drawer. */
import { fireEvent, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { renderWithProviders } from '../test-support/renderWithProviders'
import { Header } from './Header'

describe('Header', () => {
  it('the account entry has the initial circle and the user name', () => {
    renderWithProviders(<Header navOpen={false} onToggleNav={vi.fn()} />)

    // The name is hidden on narrow screens (index.css), so the screen-reader name goes in aria-label
    const account = screen.getByRole('link', { name: 'Account (manager)' })
    expect(account).toHaveAttribute('href', '/profile')
    expect(account).toHaveAttribute('title', 'manager')
    expect(account).toHaveTextContent('M')
    expect(account).toHaveTextContent('manager')
  })

  it('the drawer toggle button tells whether it is open', () => {
    const onToggleNav = vi.fn()
    renderWithProviders(<Header navOpen onToggleNav={onToggleNav} />)

    const toggle = screen.getByRole('button', { name: 'Menu' })
    expect(toggle).toHaveAttribute('aria-expanded', 'true')
    fireEvent.click(toggle)
    expect(onToggleNav).toHaveBeenCalled()
  })
})
