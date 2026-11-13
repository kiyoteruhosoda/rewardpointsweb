/**
 * Entry to families: if already a member, go to the details; otherwise show only create and join.
 */
import { fireEvent, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { FamilyDetail, RedeemedInvitation } from '../services/families'
import { familyOf, member } from '../test-support/familyFixtures'
import { renderWithProviders } from '../test-support/renderWithProviders'
import { FamiliesPage } from './FamiliesPage'

const create = vi.fn<(name: string) => Promise<FamilyDetail>>()
const acceptInvitation = vi.fn<(code: string) => Promise<RedeemedInvitation>>()

vi.mock('../services/families', () => ({
  families: {
    create: (name: string) => create(name),
    acceptInvitation: (code: string) => acceptInvitation(code),
  },
}))

const PARENT_SCOPES = ['family:view', 'family:manage', 'point:view', 'point:manage']

describe('FamiliesPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('shows "Create" to a parent (family:manage)', () => {
    renderWithProviders(<FamiliesPage />, { scopes: PARENT_SCOPES })

    expect(screen.getByRole('button', { name: 'Create a family' })).toBeInTheDocument()
  })

  it('shows only the invitation code entry, not "Create", to a child (family:view only)', () => {
    renderWithProviders(<FamiliesPage />, { scopes: ['family:view', 'point:view'] })

    expect(screen.getByRole('button', { name: 'Join with a code' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Create a family' })).not.toBeInTheDocument()
  })

  it('goes to the details without showing create or join when already in a family', () => {
    renderWithProviders(<FamiliesPage />, {
      scopes: PARENT_SCOPES,
      family: familyOf('parent', [member()]),
      path: '/families',
      route: '/families',
    })

    expect(screen.queryByRole('button', { name: 'Create a family' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Join with a code' })).not.toBeInTheDocument()
  })

  it('does not show create or join when membership could not be confirmed (pressing would always fail)', () => {
    renderWithProviders(<FamiliesPage />, { scopes: PARENT_SCOPES, familyFailed: true })

    expect(screen.getByText('This family could not be loaded.')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Create a family' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Join with a code' })).not.toBeInTheDocument()
  })

  it('moves to the new family details after creating it', async () => {
    create.mockResolvedValue(familyOf('owner', []))
    const reloadFamily = vi.fn<() => Promise<void>>().mockResolvedValue()
    renderWithProviders(<FamiliesPage />, { scopes: PARENT_SCOPES, reloadFamily })

    fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'ほその家' } })
    fireEvent.click(screen.getByRole('button', { name: 'Create a family' }))

    await waitFor(() => {
      expect(create).toHaveBeenCalledWith('ほその家')
    })
    // Reload before going to the details (the left navigation switches to the new family at the same time)
    await waitFor(() => {
      expect(reloadFamily).toHaveBeenCalled()
    })
  })

  it('can join with an invitation code', async () => {
    acceptInvitation.mockResolvedValue({
      family_id: 1,
      family_name: 'ほその家',
      membership_id: 2,
      role: 'parent',
      username: 'mom',
    })
    renderWithProviders(<FamiliesPage />, { scopes: PARENT_SCOPES })

    fireEvent.change(screen.getByLabelText('Invitation code'), { target: { value: 'CODE1234' } })
    fireEvent.click(screen.getByRole('button', { name: 'Join with a code' }))

    expect(await screen.findByText('You joined the family.')).toBeInTheDocument()
  })

  it('prefills the code entered before signing in', async () => {
    renderWithProviders(<FamiliesPage />, {
      scopes: PARENT_SCOPES,
      route: '/families#code=CODE1234',
    })

    expect(await screen.findByLabelText('Invitation code')).toHaveValue('CODE1234')
    expect(
      screen.getByText(
        'The invitation code you entered before signing in was carried over. Choose “Join with a code” to join the family.',
      ),
    ).toBeInTheDocument()
  })
})
