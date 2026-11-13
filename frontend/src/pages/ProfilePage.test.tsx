/** Profile settings: your own info, display settings (language, theme) and security. */
import { fireEvent, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it } from 'vitest'

import { renderWithProviders } from '../test-support/renderWithProviders'
import { ProfilePage } from './ProfilePage'

describe('ProfilePage', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('shows the display name and login ID', () => {
    renderWithProviders(<ProfilePage />, { scopes: ['family:view'] })
    expect(screen.getByText('Signs in as manager')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Account' })).toBeInTheDocument()
  })

  it('lets you change the display name and email (login ID is not editable)', () => {
    renderWithProviders(<ProfilePage />, { scopes: ['family:view'] })

    expect(screen.getByLabelText('Display name')).toHaveValue('manager')
    expect(screen.getByLabelText('Email (optional)')).toHaveValue('manager@example.com')
    expect(screen.queryByLabelText('Username')).not.toBeInTheDocument()
  })

  it('holds language and theme as display settings (on this screen, not in the header)', () => {
    renderWithProviders(<ProfilePage />)
    expect(screen.getByLabelText('Language')).toBeInTheDocument()
    expect(screen.getByLabelText('Theme')).toBeInTheDocument()
  })

  it('saves and applies a theme immediately when chosen', () => {
    renderWithProviders(<ProfilePage />)

    fireEvent.change(screen.getByLabelText('Theme'), { target: { value: 'dark' } })
    expect(localStorage.getItem('theme')).toBe('dark')
    expect(document.documentElement.dataset.theme).toBe('dark')
  })

  it('has no entry to system administration (it is a separate Sidebar section)', () => {
    renderWithProviders(<ProfilePage />, { scopes: ['user:manage', 'log:view'] })
    expect(screen.queryByText('System administration')).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Users' })).not.toBeInTheDocument()
  })
})
