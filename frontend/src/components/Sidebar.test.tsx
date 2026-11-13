/** Navigation: showing items by scope, and how the drawer closes on narrow screens. */
import { fireEvent, screen } from '@testing-library/react'
import { useState } from 'react'
import { describe, expect, it, vi } from 'vitest'

import { familyOf, member } from '../test-support/familyFixtures'
import { renderWithProviders } from '../test-support/renderWithProviders'
import { Sidebar } from './Sidebar'

const CLOSE_LABEL = 'Close the menu'

describe('Sidebar', () => {
  it("lists the family's children under the dashboard (entries to their ledgers)", () => {
    renderWithProviders(<Sidebar open={false} onClose={vi.fn()} />, {
      scopes: ['dashboard:view', 'family:view'],
      family: familyOf('owner', [
        member({ id: 1, display_name: 'おとうさん', role: 'owner', ledger_id: null }),
        member(),
        member({ id: 3, display_name: 'タロウ', ledger_id: 30 }),
      ]),
    })

    expect(screen.getByRole('link', { name: 'ハナ' })).toHaveAttribute(
      'href',
      '/families/1/ledgers/20',
    )
    // Participants without a ledger (parents) are not listed
    expect(screen.queryByRole('link', { name: 'おとうさん' })).not.toBeInTheDocument()
    // The order stays as returned by the server (the order the family chose)
    const links = screen.getAllByRole('link').map((link) => link.textContent)
    expect(links).toEqual(['Dashboard', 'ハナ', 'タロウ', 'Family settings', 'Profile & settings'])
  })

  it('shows no child entries without a family', () => {
    renderWithProviders(<Sidebar open={false} onClose={vi.fn()} />, {
      scopes: ['dashboard:view', 'family:view'],
    })

    expect(screen.getAllByRole('link').map((link) => link.textContent)).toEqual([
      'Dashboard',
      'Family settings',
      'Profile & settings',
    ])
  })

  it('shows only items the user has the scope for', () => {
    renderWithProviders(<Sidebar open={false} onClose={vi.fn()} />, {
      scopes: ['family:view'],
    })
    expect(screen.getByRole('link', { name: 'Family settings' })).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Dashboard' })).not.toBeInTheDocument()
  })

  it('shows system administration as a separate section only to people with the scope', () => {
    renderWithProviders(<Sidebar open={false} onClose={vi.fn()} />, {
      scopes: ['family:view', 'user:manage', 'admin:system-settings', 'log:view'],
    })
    expect(screen.getByText('System administration')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Users' })).toHaveAttribute('href', '/admin/users')
    expect(screen.getByRole('link', { name: 'System settings' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'System logs' })).toBeInTheDocument()
    // Items without the scope (roles, permissions) are not shown
    expect(screen.queryByRole('link', { name: 'Roles' })).not.toBeInTheDocument()
  })

  it('does not show the section at all without the system administration scope', () => {
    renderWithProviders(<Sidebar open={false} onClose={vi.fn()} />, {
      scopes: ['family:view'],
    })
    expect(screen.queryByText('System administration')).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Users' })).not.toBeInTheDocument()
  })

  it('does not show the backdrop while closed', () => {
    renderWithProviders(<Sidebar open={false} onClose={vi.fn()} />, {
      scopes: ['family:view'],
    })
    expect(screen.queryByRole('button', { name: CLOSE_LABEL })).not.toBeInTheDocument()
    expect(screen.getByRole('navigation')).not.toHaveClass('sidebar-open')
  })

  it('adds sidebar-open while open', () => {
    renderWithProviders(<Sidebar open onClose={vi.fn()} />, { scopes: ['family:view'] })
    expect(screen.getByRole('navigation')).toHaveClass('sidebar-open')
  })

  it('closes when the backdrop is touched', () => {
    const onClose = vi.fn()
    renderWithProviders(<Sidebar open onClose={onClose} />, { scopes: ['family:view'] })

    fireEvent.click(screen.getByRole('button', { name: CLOSE_LABEL }))
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('closes when an item is chosen (the drawer does not stay over the content)', () => {
    const onClose = vi.fn()
    renderWithProviders(<Sidebar open onClose={onClose} />, { scopes: ['family:view'] })

    fireEvent.click(screen.getByRole('link', { name: 'Family settings' }))
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('closes with Escape', () => {
    const onClose = vi.fn()
    renderWithProviders(<Sidebar open onClose={onClose} />, { scopes: ['family:view'] })

    fireEvent.keyDown(window, { key: 'Escape' })
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('ignores Escape while closed', () => {
    const onClose = vi.fn()
    renderWithProviders(<Sidebar open={false} onClose={onClose} />, {
      scopes: ['family:view'],
    })

    fireEvent.keyDown(window, { key: 'Escape' })
    expect(onClose).not.toHaveBeenCalled()
  })

  it('moves focus to the first item when opened', () => {
    renderWithProviders(<Sidebar open onClose={vi.fn()} />, {
      scopes: ['dashboard:view', 'family:view'],
    })
    expect(document.activeElement).toBe(screen.getByRole('link', { name: 'Dashboard' }))
  })

  it('Tab from the last element goes back to the first (does not escape to controls behind)', () => {
    renderWithProviders(<Sidebar open onClose={vi.fn()} />, {
      scopes: ['dashboard:view', 'family:view'],
    })
    // The last in the cycle is the backdrop's "close" button
    screen.getByRole('button', { name: CLOSE_LABEL }).focus()

    fireEvent.keyDown(window, { key: 'Tab' })
    expect(document.activeElement).toBe(screen.getByRole('link', { name: 'Dashboard' }))
  })

  it('Shift+Tab from the first goes around to the last', () => {
    renderWithProviders(<Sidebar open onClose={vi.fn()} />, {
      scopes: ['dashboard:view', 'family:view'],
    })

    fireEvent.keyDown(window, { key: 'Tab', shiftKey: true })
    expect(document.activeElement).toBe(screen.getByRole('button', { name: CLOSE_LABEL }))
  })

  it('returns focus to the control that opened it (the header toggle) when closed', () => {
    // Stand-in for the toggle button. Assumes it holds focus when the drawer is opened.
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
    expect(document.activeElement).toBe(screen.getByRole('link', { name: 'Family settings' }))

    fireEvent.click(screen.getByRole('button', { name: CLOSE_LABEL }))
    expect(document.activeElement).toBe(opener)
    opener.remove()
  })
})
