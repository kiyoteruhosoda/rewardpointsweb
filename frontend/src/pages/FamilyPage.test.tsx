/**
 * Family details: actions gated by server permissions; two ways to remove (independence, delete).
 */
import { fireEvent, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { FamilyDetail, FamilyRole, Invitation, Membership } from '../services/families'
import { familyOf, member } from '../test-support/familyFixtures'
import { renderWithProviders } from '../test-support/renderWithProviders'
import { FamilyPage } from './FamilyPage'

const listInvitations = vi.fn<() => Promise<never[]>>()
const proposeIndependence = vi.fn<(familyId: number, membershipId: number) => Promise<Membership>>()
const revokeIndependenceProposal =
  vi.fn<(familyId: number, membershipId: number) => Promise<void>>()
const removeMembership = vi.fn<(familyId: number, membershipId: number) => Promise<void>>()
const reorderMembers = vi.fn<(familyId: number, ids: number[]) => Promise<FamilyDetail>>()
const setRules = vi.fn<(familyId: number, rules: string) => Promise<FamilyDetail>>()
const leave = vi.fn<(familyId: number) => Promise<void>>()
const issueInvitation =
  vi.fn<(familyId: number, role: FamilyRole, targetId: number | null) => Promise<Invitation>>()

vi.mock('../services/families', () => ({
  // Same check as the real one. The server returns a trailing Z, so appending blindly gives `...ZZ`
  parseUtc: (value: string) =>
    new Date(/(?:Z|[+-]\d{2}:?\d{2})$/.test(value) ? value : `${value}Z`),
  families: {
    listInvitations: () => listInvitations(),
    proposeIndependence: (familyId: number, membershipId: number) =>
      proposeIndependence(familyId, membershipId),
    revokeIndependenceProposal: (familyId: number, membershipId: number) =>
      revokeIndependenceProposal(familyId, membershipId),
    removeMembership: (familyId: number, membershipId: number) =>
      removeMembership(familyId, membershipId),
    reorderMembers: (familyId: number, ids: number[]) => reorderMembers(familyId, ids),
    setRules: (familyId: number, rules: string) => setRules(familyId, rules),
    leave: (familyId: number) => leave(familyId),
    issueInvitation: (familyId: number, role: FamilyRole, targetId: number | null) =>
      issueInvitation(familyId, role, targetId),
  },
}))

function restoredParent(): Membership {
  return member({
    id: 5,
    display_name: 'おかあさん',
    role: 'parent',
    is_linked: false,
    username: null,
    ledger_id: null,
    balance: null,
    can_reset_password: false,
    can_propose_independence: false,
  })
}

function renderPage(
  family: FamilyDetail,
  reloadFamily = () => Promise.resolve(),
  scopes = ['family:view', 'family:manage', 'point:manage'],
) {
  return renderWithProviders(<FamilyPage />, {
    scopes,
    route: '/families/1',
    path: '/families/:familyId',
    family,
    reloadFamily,
  })
}

describe('FamilyPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    listInvitations.mockResolvedValue([])
    vi.spyOn(window, 'confirm').mockReturnValue(true)
  })

  it('orders participants -> family settings -> invitations -> adding children', () => {
    renderPage(familyOf('owner', [member()]))

    const sections = screen.getAllByRole('heading', { level: 2 }).map((h) => h.textContent)

    expect(sections).toEqual([
      'Members',
      'Family settings',
      'Daily bonus',
      'Invitations',
      'Add a child',
      'Backup',
    ])
  })

  it('shows participants and the balances the viewer can see', () => {
    renderPage(familyOf('owner', [member()]))

    expect(screen.getByText('70 pt')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'History' })).toHaveAttribute(
      'href',
      '/families/1/ledgers/20',
    )
  })

  it('shows neither balance nor entry for hidden ledgers (sibling balances)', () => {
    renderPage(
      familyOf('child', [
        member({ is_me: true, can_reset_password: false, can_propose_independence: false }),
        member({
          id: 3,
          display_name: 'タロウ',
          ledger_id: null,
          balance: null,
          can_reset_password: false,
          can_propose_independence: false,
        }),
      ]),
    )

    expect(screen.getByText('70 pt')).toBeInTheDocument()
    expect(screen.getAllByRole('link', { name: 'History' })).toHaveLength(1)
  })

  it('shows nothing for a family URL other than the current membership', () => {
    renderWithProviders(<FamilyPage />, {
      scopes: ['family:view'],
      route: '/families/9',
      path: '/families/:familyId',
      family: familyOf('owner', [member()]),
    })

    expect(screen.getByText('This family could not be loaded.')).toBeInTheDocument()
  })

  it('does not show adding children or invitations to a child', () => {
    renderPage(
      familyOf('child', [
        member({ is_me: true, can_reset_password: false, can_propose_independence: false }),
      ]),
    )

    expect(screen.queryByRole('button', { name: 'Add a child' })).not.toBeInTheDocument()
    expect(screen.queryByText('Invitations')).not.toBeInTheDocument()
  })

  it('shows adding children to a parent', () => {
    renderPage(familyOf('parent', [member()]))

    expect(screen.getByRole('button', { name: 'Add a child' })).toBeInTheDocument()
  })

  it('only owner can invite parents (parent sees only invitations for children)', () => {
    renderPage(familyOf('parent', [member({ is_linked: false })]))
    expect(screen.getByText('Invitations')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /ハナ/ })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Invite another parent' })).not.toBeInTheDocument()
  })

  it('also shows parent invitations to owner', () => {
    renderPage(familyOf('owner', [member()]))

    expect(screen.getByText('Invitations')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Invite another parent' })).toBeInTheDocument()
  })

  it('shows temporary password only when can_reset_password', () => {
    renderPage(familyOf('owner', [member({ is_linked: false, can_reset_password: false })]))

    expect(screen.getByText(/no sign-in yet/)).toBeInTheDocument()
    expect(
      screen.queryByRole('button', { name: 'Issue a temporary password' }),
    ).not.toBeInTheDocument()
  })

  it('shows the independence request only when can_propose_independence (not for others)', () => {
    renderPage(
      familyOf('parent', [
        member(),
        member({
          id: 3,
          display_name: 'タロウ',
          is_linked: false,
          can_propose_independence: false,
        }),
      ]),
    )

    expect(screen.getAllByRole('button', { name: 'Propose independence' })).toHaveLength(1)
  })

  it('sends an independence request to the server after confirmation', () => {
    renderPage(familyOf('parent', [member()]))

    fireEvent.click(screen.getByRole('button', { name: 'Propose independence' }))
    expect(proposeIndependence).toHaveBeenCalledWith(1, 2)
  })

  it('shows withdraw and a marker for a child with a pending request', () => {
    renderPage(familyOf('parent', [member({ independence_proposed: true })]))

    expect(screen.getByText('independence proposed')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Withdraw the proposal' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Propose independence' })).not.toBeInTheDocument()
  })

  it('shows delete only when can_remove (not for a child with records)', () => {
    renderPage(
      familyOf('owner', [
        member({ can_remove: false }),
        member({ id: 3, display_name: 'タロウ', balance: 0, can_remove: true }),
      ]),
    )

    const remove = screen.getAllByRole('button', { name: 'Delete' })
    expect(remove).toHaveLength(1)

    fireEvent.click(remove[0] as HTMLElement)
    expect(removeMembership).toHaveBeenCalledWith(1, 3)
  })

  it('shows independence approval to the child who received the request', () => {
    renderPage(
      familyOf('child', [
        member({
          is_me: true,
          independence_proposed: true,
          can_reset_password: false,
          can_propose_independence: false,
        }),
      ]),
    )

    expect(screen.getByRole('button', { name: 'Approve independence' })).toBeInTheDocument()
  })

  it('does not show approval to a child without a pending request', () => {
    renderPage(
      familyOf('child', [
        member({ is_me: true, can_reset_password: false, can_propose_independence: false }),
      ]),
    )

    expect(screen.queryByRole('button', { name: 'Approve independence' })).not.toBeInTheDocument()
  })

  it('shows rename, leave and dissolve to owner', () => {
    renderPage(familyOf('owner', [member()]))

    expect(screen.getByRole('button', { name: 'Rename' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Leave this family' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Dissolve this family' })).toBeInTheDocument()
  })

  it('shows only leave to parent (rename and dissolve are for owner)', () => {
    renderPage(familyOf('parent', [member()]))

    expect(screen.getByRole('button', { name: 'Leave this family' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Rename' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Dissolve this family' })).not.toBeInTheDocument()
  })

  it('does not show family settings to a child (a child cannot leave on their own)', () => {
    renderPage(
      familyOf('child', [
        member({ is_me: true, can_reset_password: false, can_propose_independence: false }),
      ]),
    )

    expect(screen.queryByText('Family settings')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Leave this family' })).not.toBeInTheDocument()
  })

  it('does not show reordering when there is only one child', () => {
    renderPage(familyOf('owner', [member()]))

    expect(screen.queryByRole('button', { name: 'Move ハナ down' })).not.toBeInTheDocument()
  })

  it('sends the swapped order when reordering', () => {
    reorderMembers.mockResolvedValue(familyOf('owner', []))
    renderPage(familyOf('owner', [member(), member({ id: 3, display_name: 'タロウ' })]))

    fireEvent.click(screen.getByRole('button', { name: 'Move タロウ up' }))
    expect(reorderMembers).toHaveBeenCalledWith(1, [3, 2])
  })

  it('reloads the family, then goes to the entry after leaving (not the gone family)', async () => {
    leave.mockResolvedValue()
    const reloadFamily = vi.fn<() => Promise<void>>().mockResolvedValue()
    renderPage(familyOf('parent', [member()]), reloadFamily)

    fireEvent.click(screen.getByRole('button', { name: 'Leave this family' }))

    await waitFor(() => {
      expect(reloadFamily).toHaveBeenCalled()
    })
  })

  it('cannot move the child at either end (no place to move to)', () => {
    renderPage(familyOf('owner', [member(), member({ id: 3, display_name: 'タロウ' })]))

    expect(screen.getByRole('button', { name: 'Move ハナ up' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Move タロウ down' })).toBeDisabled()
  })

  it('shows backup export to a parent (ADR-0026)', () => {
    renderPage(familyOf('parent', [member()]))

    expect(screen.getByRole('button', { name: 'Save a backup' })).toBeInTheDocument()
  })

  it('does not show it to a child (the backup contains every ledger in the family)', () => {
    renderPage(familyOf('child', [member({ is_me: true })]))

    expect(screen.queryByRole('button', { name: 'Save a backup' })).not.toBeInTheDocument()
  })

  it('can hand an invitation code targeting a parent restored from backup (ADR-0026)', async () => {
    listInvitations.mockResolvedValue([])
    renderPage(familyOf('owner', [restoredParent()]))

    fireEvent.click(screen.getByRole('button', { name: 'Invitation code for おかあさん' }))

    // The role is that participant's. Targeting keeps "recorded by" in the ledger unchanged
    await waitFor(() => {
      expect(issueInvitation).toHaveBeenCalledWith(1, 'parent', 5)
    })
  })

  describe('family rules (ADR-0027)', () => {
    it('parents can edit them (not only owner)', async () => {
      setRules.mockResolvedValue(familyOf('parent', [member()]))
      const reloadFamily = vi.fn<() => Promise<void>>().mockResolvedValue()
      renderPage(familyOf('parent', [member()]), reloadFamily)

      fireEvent.change(screen.getByLabelText('Family rules'), {
        target: { value: 'おかたづけ 10 pt' },
      })
      fireEvent.click(screen.getByRole('button', { name: 'Save' }))

      await waitFor(() => {
        expect(setRules).toHaveBeenCalledWith(1, 'おかたづけ 10 pt')
      })
      // The same text appears in children's ledgers, so reload the family after writing (ADR-0021)
      expect(reloadFamily).toHaveBeenCalled()
    })

    it('uses the existing rules as the initial input value', () => {
      renderPage({ ...familyOf('owner', [member()]), rules: 'ゲームは 1 日 1 時間' })

      expect(screen.getByLabelText('Family rules')).toHaveValue('ゲームは 1 日 1 時間')
    })

    it('does not show an edit entry to a child (they read it on their own ledger screen)', () => {
      renderPage(familyOf('child', [member({ is_me: true })]))

      expect(screen.queryByLabelText('Family rules')).not.toBeInTheDocument()
    })

    it('hides the input from a parent without family:manage (it would always 403)', () => {
      renderPage(familyOf('parent', [member()]), () => Promise.resolve(), ['family:view'])

      expect(screen.queryByLabelText('Family rules')).not.toBeInTheDocument()
    })
  })

  describe('daily bonus (ADR-0024, ADR-0027)', () => {
    it('shows a per-child setting to parents', () => {
      renderPage(familyOf('parent', [member(), member({ id: 3, display_name: 'タロウ' })]))

      expect(screen.getByLabelText('Points per day for ハナ')).toBeInTheDocument()
      expect(screen.getByLabelText('Points per day for タロウ')).toBeInTheDocument()
    })

    it('does not show it to a child (not even for their own ledger)', () => {
      renderPage(familyOf('child', [member({ is_me: true })]))

      expect(screen.queryByLabelText('Points per day for ハナ')).not.toBeInTheDocument()
    })

    it('hides it from a parent without point:manage (setting it rewrites ledgers)', () => {
      renderPage(familyOf('parent', [member()]), () => Promise.resolve(), [
        'family:view',
        'family:manage',
      ])

      expect(screen.queryByLabelText('Points per day for ハナ')).not.toBeInTheDocument()
    })
  })

  it('only owner can hand out codes for parents (ADR-0020)', () => {
    listInvitations.mockResolvedValue([])
    renderPage(familyOf('parent', [restoredParent()]))

    expect(
      screen.queryByRole('button', { name: 'Invitation code for おかあさん' }),
    ).not.toBeInTheDocument()
  })
})
