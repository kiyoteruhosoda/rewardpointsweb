/** Dashboard: balances of the family's children. Looks the same regardless of role. */
import { screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { familyOf, member } from '../test-support/familyFixtures'
import { renderWithProviders } from '../test-support/renderWithProviders'
import { DashboardPage } from './DashboardPage'

describe('DashboardPage', () => {
  it('shows a greeting and a balance card per child', () => {
    renderWithProviders(<DashboardPage />, {
      scopes: ['family:view'],
      family: familyOf('owner', [
        member(),
        member({ id: 3, display_name: 'タロウ', ledger_id: 30, balance: 30 }),
      ]),
    })

    expect(screen.getByText('70 pt')).toBeInTheDocument()
    expect(screen.getByText('30 pt')).toBeInTheDocument()
    expect(screen.getByText('Hello, manager')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /ハナ/ })).toHaveAttribute(
      'href',
      '/families/1/ledgers/20',
    )
  })

  it('keeps the order the server returned (the order the family chose)', () => {
    renderWithProviders(<DashboardPage />, {
      scopes: ['family:view'],
      family: familyOf('owner', [
        member({ id: 3, display_name: 'タロウ', ledger_id: 30, balance: 30 }),
        member(),
      ]),
    })

    // Order of headings without the initial badge (a card is initial + name + balance)
    const names = screen
      .getAllByRole('link')
      .map((link) => link.querySelector('.member-card-name')?.textContent)
    expect(names).toEqual(['タロウ', 'ハナ'])
  })

  it('shows the same dashboard to non-owners (a parent who joined by invitation)', () => {
    renderWithProviders(<DashboardPage />, {
      scopes: ['family:view'],
      family: familyOf('parent', [
        member(),
        member({ id: 3, display_name: 'タロウ', ledger_id: 30, balance: 30 }),
      ]),
    })

    expect(screen.getByText('70 pt')).toBeInTheDocument()
    expect(screen.getByText('30 pt')).toBeInTheDocument()
  })

  it('does not list participants without a ledger (parents) as cards', () => {
    renderWithProviders(<DashboardPage />, {
      scopes: ['family:view'],
      family: familyOf('owner', [
        member({
          id: 1,
          display_name: 'おとうさん',
          role: 'owner',
          ledger_id: null,
          balance: null,
        }),
        member(),
      ]),
    })

    expect(screen.getByText('70 pt')).toBeInTheDocument()
    expect(screen.queryByText('おとうさん')).not.toBeInTheDocument()
  })

  it('marks the ledger that belongs to the viewer', () => {
    renderWithProviders(<DashboardPage />, {
      scopes: ['family:view'],
      family: familyOf('child', [member({ is_me: true })]),
    })

    expect(screen.getByText(/\(you\)/)).toBeInTheDocument()
  })

  it('does not show system operations info (API docs)', () => {
    renderWithProviders(<DashboardPage />, {
      scopes: ['family:view'],
      family: familyOf('owner', [member()]),
    })

    expect(screen.queryByRole('link', { name: '/docs' })).not.toBeInTheDocument()
    expect(screen.queryByText(/openapi/i)).not.toBeInTheDocument()
  })

  it('points to the family screen when there are no children', () => {
    renderWithProviders(<DashboardPage />, { scopes: ['family:view'] })

    expect(screen.getByRole('link', { name: 'Set up your family' })).toHaveAttribute(
      'href',
      '/families',
    )
  })

  it('does not say "no children" when loading failed', () => {
    renderWithProviders(<DashboardPage />, { scopes: ['family:view'], familyFailed: true })

    expect(screen.getByText('This family could not be loaded.')).toBeInTheDocument()
    expect(
      screen.queryByText('No children yet. Add them from Family settings.'),
    ).not.toBeInTheDocument()
  })

  it('shows no empty-state hint without family:view (nowhere to go)', () => {
    renderWithProviders(<DashboardPage />, { scopes: ['dashboard:view'] })

    expect(screen.getByText('Hello, manager')).toBeInTheDocument()
    expect(
      screen.queryByText('No children yet. Add them from Family settings.'),
    ).not.toBeInTheDocument()
  })
})
